# Qlib Workflow Visualization Integration Design

## 1. Overview
The goal is to add visual outputs (interactive Plotly charts) into the existing `workflow_by_code.py` script. These charts will display portfolio returns, model IC/RankIC performance, and other relevant trading metrics. Instead of relying on local HTML file clutter, the visualizations will be uploaded straight to the active MLflow run artifacts using `mlflow.log_figure()`.

## 2. Architecture & Data Flow
The new visualization step will be inserted seamlessly after the `par.generate()` call in the script:
1. The backtest and signal analysis (`SigAnaRecord`, `PortAnaRecord`) compute metrics and save raw data (like `pred.pkl`, `label.pkl`, `portfolio_analysis/report_normal.pkl`) directly into MLflow via the Qlib `Recorder`.
2. A new `Visualization` block will re-fetch these raw metric objects from the recorder.
3. Qlib's standard visualization functions (`qlib.contrib.report.analysis_position`, `qlib.contrib.report.analysis_model`) will be fed these dataframes to generate `plotly.graph_objs.Figure` instances.
4. Finally, `mlflow.log_figure(fig, artifact_path)` will upload these interactive HTML charts into the MLflow UI under a newly created `visualizations/` folder artifact.

## 3. Components
To achieve this, the following module imports are necessary:
- `import mlflow`
- `from qlib.contrib.report import analysis_model, analysis_position`
- `import pandas as pd`

The charts that will be produced are:
1. **Portfolio Report Graph**: `analysis_position.report_graph(report_normal, show_notebook=False)` - Plots cumulative return and maximum drawdown.
2. **Model Performance Graph**: `analysis_model.model_performance_graph(pred_label_dict)` - Plots IC and Rank IC grouped across time periods.
3. **Score IC Graph** (Optional/Fallback): `analysis_position.score_ic_graph(report_normal)` or equivalent layer metrics.

## 4. Error Handling
The Qlib reporting tools might fail if certain data formats don't perfectly align (especially missing columns or empty test data).
To prevent the main backtest script from crashing right at the end:
- Each graph generation step will be enclosed in a `try...except Exception as e` guard.
- If a graph generation errors out, a soft Python `logging.warning()` or `print()` will output the error details, allowing the rest of the workflow/MLflow artifacts to naturally succeed.
