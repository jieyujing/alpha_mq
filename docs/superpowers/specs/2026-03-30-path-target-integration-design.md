---
name: path-target-integration
description: 将 path_target.py 集成到 workflow_by_code.py 的设计文档
type: project
---

# Path Target 集成设计

**日期**: 2026-03-30
**状态**: 待用户审核
**目标**: 将路径质量 label (path_target) 替换 qlib 默认的收益率 label

---

## 1. 背景

当前 `workflow_by_code.py` 使用 qlib 标准工作流：
- **Features**: Alpha158 (158 个因子)
- **Label**: `Ref($close, -1)/$close - 1` (次日收益率)
- **Model**: LGBModel

`path_target.py` 实现了基于 AFML Triple Barrier Method 的路径质量评分：
- 波动率自适应止盈/止损屏障
- MAE (最大不利偏移) 路径惩罚
- Soft beta-neutral 扣减
- 输出 percentile rank (0, 1)

**目标**: 用 path_target 替换默认 label，让模型学习"路径质量"而非单纯收益率。

---

## 2. 技术方案

### 方案选择

采用 **自定义 Handler** 方案（qlib 官方推荐方式）：
- 继承 `Alpha158`，重写 `fetch_label` 方法
- Features 继续使用 Alpha158
- Label 由 `PathTargetBuilder` 生成

### 架构

```
workflow_by_code.py
    │
    ├── qlib.init(provider_uri="data/qlib_data")
    │
    ├── Alpha158PathTargetHandler (新建)
    │       ├── 继承 Alpha158
    │       ├── fetch_label() → PathTargetBuilder.build()
    │       └── fetch_feature() → 保持原样
    │
    └── DatasetH(handler=Alpha158PathTargetHandler)
    │
    └── LGBModel.fit(dataset)
```

---

## 3. 组件设计

### 3.1 Alpha158PathTargetHandler

**文件位置**: `data/handler.py` (新建) 或直接在 `workflow_by_code.py` 中定义

```python
class Alpha158PathTargetHandler(Alpha158):
    """
    继承 Alpha158，替换 label 为 path_target。
    """

    def __init__(
        self,
        benchmark: str = "SH000852",
        path_target_config: PathTargetConfig = None,
        beta_window: int = 60,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.benchmark = benchmark
        self.pt_config = path_target_config or PathTargetConfig()
        self.pt_builder = PathTargetBuilder(self.pt_config)
        self.beta_window = beta_window

    def fetch_label(self):
        """
        生成 path_target label。

        步骤:
        1. 从 qlib 获取 close panel (date × instrument)
        2. 从 qlib 获取 benchmark close
        3. 计算个股 beta (滚动回归)
        4. 转换为 Polars DataFrame
        5. 调用 PathTargetBuilder.build()
        6. 返回 Series (MultiIndex)
        """
        # 实现见下文
```

### 3.2 Beta 计算

```python
def compute_rolling_beta(
    close_panel: pl.DataFrame,
    benchmark_close: pl.DataFrame,
    window: int = 60,
    min_periods: int = 20
) -> pl.DataFrame:
    """
    计算个股对基准的滚动 beta。

    β_i = Cov(r_i, r_m) / Var(r_m)
    """
    # 1. 计算收益率
    # 2. 滚动协方差 / 方差
    # 3. 缺失值处理：默认 beta = 1.0
```

**参数**:
- `window`: 60 日 (约 3 个月)
- `min_periods`: 20 日
- `beta_alpha`: 0.5 (继承 PathTargetConfig)

### 3.3 fetch_label 实现

```python
def fetch_label(self):
    from qlib.data import D

    # 1. 获取 close panel
    instruments = self._instrument
    start_time = self.start_time
    end_time = self.end_time

    close_df = D.features(
        instruments=instruments,
        fields=["$close"],
        start_time=start_time,
        end_time=end_time,
        freq="day"
    )
    # close_df: MultiIndex(date, instrument) → pivot to wide

    # 2. 获取 benchmark close
    mkt_close = D.features(
        instruments=[self.benchmark],
        fields=["$close"],
        start_time=start_time,
        end_time=end_time,
        freq="day"
    )

    # 3. 计算 beta
    beta_df = compute_rolling_beta(close_panel, mkt_close, self.beta_window)

    # 4. 转换为 Polars
    close_pl = pl.from_pandas(close_wide)
    mkt_pl = pl.from_pandas(mkt_wide)
    beta_pl = pl.from_pandas(beta_wide)

    # 5. 构建 target
    target_series = self.pt_builder.build(
        ohlc={"close": close_pl},
        market_close=mkt_pl,
        beta_df=beta_pl
    )

    # 6. 返回 MultiIndex Series (qlib 格式)
    return target_series
```

---

## 4. workflow_by_code.py 改动

**改动位置**: `CSI1000_GBDT_TASK["dataset"]["kwargs"]["handler"]`

```python
# 原代码
"handler": {
    "class": "Alpha158",
    "module_path": "qlib.contrib.data.handler",
    "kwargs": {
        "start_time": "2015-01-05",
        "end_time": "2026-03-26",
        "fit_start_time": "2015-01-05",
        "fit_end_time": "2022-12-31",
        "instruments": CSI1000_MARKET,
        "filter_pipe": [...],
    },
}

# 改动后
"handler": {
    "class": "Alpha158PathTargetHandler",
    "module_path": "data.handler",  # 本地模块
    "kwargs": {
        "start_time": "2015-01-05",
        "end_time": "2026-03-26",
        "fit_start_time": "2015-01-05",
        "fit_end_time": "2022-12-31",
        "instruments": CSI1000_MARKET,
        "benchmark": CSI1000_BENCH,
        "filter_pipe": [...],
    },
}
```

**改动范围**: 仅修改 handler 配置，其余 (model, backtest, 可视化) 保持不变。

---

## 5. 文件结构

```
alpha_mq/
├── workflow_by_code.py      # 修改 handler 配置
├── path_target.py           # 保持不变
├── data/
│   ├── handler.py           # 新建: Alpha158PathTargetHandler
│   └── qlib_data/           # qlib 数据目录
│   └── csv_source/          # 原始 CSV (备用)
└── configs/
    └── workflow_config.yaml  # 可选: 后续配置化
```

---

## 6. 验证计划

1. **单元测试**: 测试 `fetch_label` 返回正确的 MultiIndex Series
2. **集成测试**: 运行完整 workflow，检查 model.fit() 正常
3. **对比验证**: 检查生成的 label 分布是否合理 (0, 1 区间)

---

## 7. 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| qlib 数据格式与 Polars 不兼容 | 使用 `pl.from_pandas()` 转换 |
| path_target 计算耗时 | 可后续预计算缓存 |
| beta 计算在新股上失效 | 默认 beta = 1.0 |

---

## 8. 后续优化

- 将 PathTargetConfig 参数写入 YAML 配置
- 添加预计算 target 缓存机制
- 支持多 benchmark 选择