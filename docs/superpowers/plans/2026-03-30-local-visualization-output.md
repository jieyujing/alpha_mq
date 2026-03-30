# 本地可视化图表输出实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 workflow_by_code.py 中的图表从 mlflow 上传改为直接保存到本地 HTML 文件

**Architecture:** 移除 mlflow 依赖，添加本地输出目录常量，用 plotly 的 write_html 方法保存图表

**Tech Stack:** Python, plotly (已依赖), os (标准库)

---

## 文件结构

| 文件 | 操作 | 说明 |
|------|------|------|
| `workflow_by_code.py` | 修改 | 移除 mlflow，添加本地输出逻辑 |

---

### Task 1: 移除 mlflow 依赖并添加输出目录配置

**Files:**
- Modify: `workflow_by_code.py:18-24`

- [ ] **Step 1: 删除 mlflow import 并添加输出目录配置**

将第 18 行的 `import mlflow` 替换为：

```python
import os
```

在 CSI1000_BENCH 常量定义前（约第 22 行）添加：

```python
# 输出目录配置
OUTPUT_DIR = "outputs/visualizations"
```

- [ ] **Step 2: 验证修改**

检查 import 部分应为：
```python
import logging
import os
import pandas as pd
from qlib.contrib.report import analysis_model, analysis_position
```

- [ ] **Step 3: Commit**

```bash
git add workflow_by_code.py
git commit -m "refactor: remove mlflow dependency, add local output config"
```

---

### Task 2: 修改可视化代码块

**Files:**
- Modify: `workflow_by_code.py:143-186`

- [ ] **Step 1: 修改可视化代码块开头**

将第 143-145 行：
```python
        # --- 可视化与 MLflow 深度集成 ---
        try:
            print("正在生成可视化图表并输出到 MLflow...")
```

替换为：
```python
        # --- 可视化图表输出到本地 ---
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        try:
            print(f"正在生成可视化图表并输出到 {OUTPUT_DIR}...")
```

- [ ] **Step 2: 替换累计收益率图表保存方式**

将第 161-165 行：
```python
                fig_port = analysis_position.report_graph(report_normal, show_notebook=False)
                # tuple 解包: report_graph 返回一个包含两张图的 tuple (return_graph, turnover_graph)
                mlflow.log_figure(fig_port[0], "visualizations/portfolio_cumulative_return.html")
            except Exception as e:
                logging.warning(f"生成回测图表失败: {e}")
```

替换为：
```python
                fig_port = analysis_position.report_graph(report_normal, show_notebook=False)
                # tuple 解包: report_graph 返回一个包含两张图的 tuple (return_graph, turnover_graph)
                fig_port[0].write_html(f"{OUTPUT_DIR}/portfolio_cumulative_return.html")
            except Exception as e:
                logging.warning(f"生成回测图表失败: {e}")
```

- [ ] **Step 3: 替换模型 IC 图表保存方式**

将第 168-174 行：
```python
                fig_model = analysis_model.model_performance_graph(pred_label, show_notebook=False)
                # model_performance_graph 返回一个 list 的 go.Figure
                for i, fig in enumerate(fig_model):
                    mlflow.log_figure(fig, f"visualizations/model_performance_ic_rankic_{i}.html")
            except Exception as e:
                logging.warning(f"生成模型表现图表失败: {e}")
```

替换为：
```python
                fig_model = analysis_model.model_performance_graph(pred_label, show_notebook=False)
                # model_performance_graph 返回一个 list 的 go.Figure
                for i, fig in enumerate(fig_model):
                    fig.write_html(f"{OUTPUT_DIR}/model_performance_ic_rankic_{i}.html")
            except Exception as e:
                logging.warning(f"生成模型表现图表失败: {e}")
```

- [ ] **Step 4: 替换 Score IC 图表保存方式**

将第 177-182 行：
```python
                fig_score = analysis_position.score_ic_graph(pred_label, show_notebook=False)
                # 返回一个 tuple/list
                mlflow.log_figure(fig_score[0], "visualizations/portfolio_score_ic.html")
            except Exception as e:
                logging.warning(f"生成分层收益率图表失败: {e}")
```

替换为：
```python
                fig_score = analysis_position.score_ic_graph(pred_label, show_notebook=False)
                # 返回一个 tuple/list
                fig_score[0].write_html(f"{OUTPUT_DIR}/portfolio_score_ic.html")
            except Exception as e:
                logging.warning(f"生成分层收益率图表失败: {e}")
```

- [ ] **Step 5: Commit**

```bash
git add workflow_by_code.py
git commit -m "feat: save visualization charts to local HTML files"
```

---

### Task 3: 验证输出

- [ ] **Step 1: 运行 workflow**

```bash
source .venv/bin/activate && python workflow_by_code.py
```

Expected: 脚本成功运行，输出目录 `outputs/visualizations/` 包含 4 个 HTML 文件

- [ ] **Step 2: 检查输出文件**

```bash
ls -la outputs/visualizations/
```

Expected output:
```
portfolio_cumulative_return.html
model_performance_ic_rankic_0.html
model_performance_ic_rankic_1.html
portfolio_score_ic.html
```

- [ ] **Step 3: 在浏览器中打开图表验证**

```bash
open outputs/visualizations/portfolio_cumulative_return.html
```

Expected: 浏览器打开交互式图表，可正常查看

---

## 自检清单

- [x] Spec 覆盖: 所有设计要求都有对应任务
- [x] 无占位符: 每个步骤包含完整代码
- [x] 类型一致性: 所有变量和函数名一致