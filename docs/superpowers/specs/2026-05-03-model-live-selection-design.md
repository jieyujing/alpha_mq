# Model Live Selection 设计文档

**日期**: 2026-05-03
**状态**: Draft for review
**作者**: Codex + Developer

---

## 1. 目标

模型 pipeline 当前已经能训练、预测、方向修正、TopK 回测并生成报告；但最后的 Best Model 仍主要来自验证集 ICIR。这个选择方法适合研究阶段的比较，却不足以支撑实盘承诺。

本设计新增一个独立 Selector 模块，在 pipeline 最后对所有模型结果进行分析筛选，保留最佳的、适合实盘的模型和参数。筛选遵循两层结构：

1. **硬约束**: 先判断模型是否具备实盘候选资格。
2. **综合评分**: 只在通过硬约束的候选之间排序。

这相当于把研究员的 tacit knowing 显性化：我们仍然承认实盘判断包含个人承诺，但必须让这些判断能被复验、质疑和继承。

---

## 2. 非目标

- 不做自动参数搜索或贝叶斯优化。
- 不接入真实交易执行系统。
- 不保存完整模型二进制文件，除非后续部署阶段单独设计。
- 不改变现有训练、预测、回测接口。
- 不以单一收益指标替代风险、稳定性和成本约束。

---

## 3. 架构

新增文件：

```text
src/pipelines/model/selector.py
```

核心职责：

- 从 `TrainingResult` 中抽取验证、OOS、回测、滚动窗口、参数信息。
- 应用可配置硬约束。
- 计算可解释综合评分。
- 输出最佳候选、候选排序、剔除原因和参数快照。

`ModelPipeline` 的报告阶段调用 Selector：

```text
train -> predict -> orient -> backtest -> alphalens -> report
                                                |
                                                v
                                      LiveModelSelector
                                                |
                         model_report.md + model_selection.json
```

不新增 pipeline stage。原因是选择依赖完整评估结果，本质上属于报告前的分析层；这样可以保持现有 `configs/model_pipeline.yaml` 兼容。

---

## 4. 配置

在 `configs/model_pipeline.yaml` 的 `selection` 下扩展：

```yaml
selection:
  mode: "live"
  primary_metric: "live_score"
  constraints:
    min_oos_ic: 0.0
    min_oos_icir: 0.0
    min_ann_excess_return: 0.0
    min_excess_sharpe: 0.0
    max_drawdown: -0.25
    max_avg_turnover: 0.8
    min_positive_ratio: 0.52
    min_rolling_windows: 3
  weights:
    oos_icir: 0.30
    excess_sharpe: 0.30
    ann_excess_return: 0.20
    positive_ratio: 0.10
    drawdown: 0.05
    turnover: 0.05
```

默认值由 Selector 提供；配置中省略时仍可运行。

---

## 5. 数据结构

新增 dataclass：

```python
@dataclass
class SelectionCandidate:
    model_name: str
    label_name: str
    params: dict
    passed: bool
    score: float
    rank: int | None
    metrics: dict
    constraint_results: dict[str, bool]
    rejection_reasons: list[str]
    direction: int
    metadata: dict
```

新增结果容器：

```python
@dataclass
class SelectionResult:
    best: SelectionCandidate | None
    candidates: list[SelectionCandidate]
    rejected: list[SelectionCandidate]
    config: dict
    generated_at: str
```

---

## 6. 硬约束

默认硬约束：

| 约束 | 默认值 | 目的 |
|------|--------|------|
| OOS IC | `> 0` | 预测方向在样本外不能反向 |
| OOS ICIR | `> 0` | 预测稳定性不能为负 |
| 年化超额收益 | `> 0` | 扣成本后相对基准有正贡献 |
| 超额 Sharpe | `> 0` | 超额收益风险调整后为正 |
| 最大回撤 | `>= -25%` | 控制实盘可承受损失 |
| 平均换手 | `<= 0.8` | 控制交易成本与容量风险 |
| 正 IC 比例 | `>= 52%` | 避免少数极端日期支撑结果 |
| 滚动窗口数 | `>= 3` | 滚动模式下要求最小复验次数 |

静态 split 没有 rolling windows 时，不应用 `min_rolling_windows`；报告中继续声明静态切分风险。

若无候选通过，Selector 不强行返回最佳模型；报告展示“无可实盘候选”，同时列出最接近候选及失败原因。

---

## 7. 综合评分

只对通过硬约束的候选计算 `live_score`。

默认权重：

| 指标 | 权重 |
|------|------|
| OOS ICIR | 30% |
| 成本后超额 Sharpe | 30% |
| 年化超额收益 | 20% |
| 正 IC 比例 | 10% |
| 回撤表现 | 5% |
| 换手表现 | 5% |

评分前对指标做温和归一化：

- 正向指标使用横截面 rank percentile，避免单个极端值支配结果。
- 回撤使用 `1 + max_drawdown`，回撤越小越好。
- 换手使用 `1 - min(avg_turnover / max_avg_turnover, 1)`，换手越低越好。

这种评分不是为了制造虚假的精确性，而是为了让多个辅助线索共同指向焦点判断；我们从 IC、收益、回撤、换手、稳定性这些 subsidiary clues，指向“是否值得实盘承诺”的 focal conclusion。

---

## 8. 参数快照

Selector 必须记录实际使用的模型参数：

- `model_name`
- `label_name`
- `model.params`
- `oriented_direction`
- `metadata`
- `selection_config`

滚动训练下，同一模型跨窗口参数相同，记录配置参数即可；若后续支持 per-window 参数搜索，再扩展为窗口级参数列表。

---

## 9. 输出

### 9.1 Markdown 报告

在 `model_report.md` 新增章节：

```text
## Live Trading Selection

### Best Live Candidate
...

### Passed Candidates
...

### Rejected Candidates
...

### Selection Constraints
...
```

报告必须展示：

- 最佳候选模型、标签周期、方向、综合分。
- 核心实盘指标。
- 参数快照。
- 所有通过候选排序。
- 所有剔除候选及剔除原因。

### 9.2 JSON 审计文件

新增输出：

```text
data/model_results/model_selection.json
```

内容包括：

- `best`
- `candidates`
- `rejected`
- `selection_config`
- `generated_at`

JSON 用于后续部署、对比历史运行结果和人工复核。

---

## 10. 错误处理

- 缺失 OOS 或回测指标时，该候选不通过，并记录具体缺失字段。
- 指标为 NaN 或 inf 时视为缺失。
- 权重总和不为 1 时自动归一化；若全部权重为 0，回退到默认权重。
- `self.results` 为空时输出空选择结果，不抛出未处理异常。

---

## 11. 测试

新增测试：

```text
tests/pipelines/model/test_selector.py
```

覆盖：

- 候选通过全部硬约束后按综合分排序。
- OOS IC、超额收益、回撤、换手等不满足时产生剔除原因。
- 无候选通过时 `best is None`。
- NaN 指标被识别为缺失并剔除。
- 权重配置缺失或异常时使用稳健默认行为。

更新 pipeline 集成测试：

- report 阶段生成 `model_selection.json`。
- Markdown 报告包含 `Live Trading Selection`。

---

## 12. 实施顺序

1. 新增 `selector.py` 与单元测试。
2. 扩展 `configs/model_pipeline.yaml` 的 selection 配置。
3. 在 `ModelPipeline.generate_report()` 前计算 `self.selection_result`。
4. 在静态和滚动报告中插入 Live Trading Selection 章节。
5. 写出 `model_selection.json`。
6. 运行 selector 单测和 model pipeline 相关测试。

---

## 13. 验收标准

- pipeline 结束后能看到最佳实盘候选或明确的“无候选通过”结论。
- 任何模型被剔除都有具体原因。
- 最佳候选包含模型参数快照。
- JSON 与 Markdown 中的选择结果一致。
- 现有训练、预测、回测行为不变。
- 新增和相关测试通过。
