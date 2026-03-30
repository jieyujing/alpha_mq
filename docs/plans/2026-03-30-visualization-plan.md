# Visualization Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate interactive Qlib-native Plotly charts for backtest and model performance directly into MLflow artifacts without breaking existing script execution.

**Architecture:** Append an isolated block at the end of `workflow_by_code.py` that extracts MLflow recorded DataFrames, generates Plotly figures, and logs them back into MLflow as HTML artifacts using `mlflow.log_figure()`.

**Tech Stack:** Python, Qlib (`analysis_model`, `analysis_position`), MLflow, Plotly, Pandas.

---

### Task 1: Add Imports and Data Extraction

**Files:**
- Modify: `/Users/link/Documents/alpha_mq/workflow_by_code.py`

**Step 1: Write the minimal implementation**
Inject the required imports near the top, and extract data at the end:

```python
# At the top of workflow_by_code.py (around Line 11):
import logging
import mlflow
import pandas as pd
from qlib.contrib.report import analysis_model, analysis_position

# At the end of workflow_by_code.py (around Line 136):
        # --- 可视化与 MLflow 深度集成 ---
        try:
            print("正在生成可视化图表并输出到 MLflow...")
            # 从 recorder 加载所需数据
            report_normal = recorder.load_object("portfolio_analysis/report_normal.pkl")
            pred_df = recorder.load_object("pred.pkl")
            label_df = recorder.load_object("label.pkl")
            # 组合 pred_label
            pred_label = pd.concat([pred_df, label_df], axis=1, sort=True).reindex(pred_df.index)
        except Exception as e:
            logging.warning(f"数据提取失败，跳过可视化流程: {e}")
```

**Step 2: Run test to verify it passes**
Run: `python workflow_by_code.py`
Expected: Workflow finishes without errors and prints "正在生成可视化图表并输出到 MLflow...".

**Step 3: Commit**
```bash
git add workflow_by_code.py
git commit -m "feat: add imports and data extraction logic for MLflow visualization"
```

---

### Task 2: Generate and Log Portfolio Report Graph

**Files:**
- Modify: `/Users/link/Documents/alpha_mq/workflow_by_code.py`

**Step 1: Write the minimal implementation**
Append the graph generation to the `try` block:

```python
            # 1. 回测图表 (收益率与最大回撤)
            try:
                fig_port = analysis_position.report_graph(report_normal, show_notebook=False)
                # tuple 解包: report_graph 返回一个包含两张图的 tuple (return_graph, turnover_graph)
                mlflow.log_figure(fig_port[0], "visualizations/portfolio_cumulative_return.html")
            except Exception as e:
                logging.warning(f"生成回测图表失败: {e}")
```

**Step 2: Run test to verify it passes**
Run: `python workflow_by_code.py`
Expected: Executes without exception.

**Step 3: Commit**
```bash
git add workflow_by_code.py
git commit -m "feat: log portfolio cumulative return graph to mlflow"
```

---

### Task 3: Generate and Log Model Performance Graph & Score IC Graph

**Files:**
- Modify: `/Users/link/Documents/alpha_mq/workflow_by_code.py`

**Step 1: Write the minimal implementation**
Append the model evaluation graphs to the `try` block:

```python
            # 2. 模型表现 IC 图表
            try:
                fig_model = analysis_model.model_performance_graph({"gbdt": pred_label}, show_notebook=False)
                # model_performance_graph 返回一个 list 的 go.Figure
                for i, fig in enumerate(fig_model):
                    mlflow.log_figure(fig, f"visualizations/model_performance_ic_rankic_{i}.html")
            except Exception as e:
                logging.warning(f"生成模型表现图表失败: {e}")

            # 3. 分层收益率图表 (TopK / BottomK)
            try:
                fig_score = analysis_position.score_ic_graph(report_normal, show_notebook=False)
                # 返回一个 tuple/list
                mlflow.log_figure(fig_score[0], "visualizations/portfolio_score_ic.html")
            except Exception as e:
                logging.warning(f"生成分层收益率图表失败: {e}")
```

**Step 2: Run test to verify it passes**
Run: `python workflow_by_code.py`
Expected: Workflow completes silently or prints the loading statement without warnings, and artifacts appear in MLflow `mlruns`.

**Step 3: Commit**
```bash
git add workflow_by_code.py
git commit -m "feat: log model performance and score ic graphs to mlflow"
```
