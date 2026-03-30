# 合并可视化图表为单个 HTML 输出设计

**日期**: 2026-03-30

## 目标

将多个可视化图表合并为一个 HTML 文件输出，方便查看和分享。

## 改动范围

- 文件: `workflow_by_code.py`
- 改动量: 约 20 行代码

## 当前状态

生成 4 个独立 HTML 文件：
- `portfolio_cumulative_return.html`
- `model_performance_ic_rankic_0.html`
- `model_performance_ic_rankic_1.html`
- `portfolio_score_ic.html`

## 目标状态

生成单个文件：
- `report.html` — 包含所有图表，垂直堆叠

## 实现细节

### HTML 拼接方式

使用 plotly 的 HTML 生成功能，将多个图表拼接：

```python
# 收集所有图表
figures = []

# 1. 累计收益率图表
fig_port = analysis_position.report_graph(report_normal, show_notebook=False)
figures.append(fig_port[0])

# 2. 模型 IC 图表
fig_model = analysis_model.model_performance_graph(pred_label, show_notebook=False)
figures.extend(fig_model)

# 3. Score IC 图表
fig_score = analysis_position.score_ic_graph(pred_label, show_notebook=False)
figures.append(fig_score[0])

# 拼接为单个 HTML
with open(f"{OUTPUT_DIR}/report.html", "w") as f:
    f.write("<html><head><title>Qlib 回测报告</title></head><body>")
    for i, fig in enumerate(figures):
        f.write(fig.to_html(include_plotlyjs='cdn' if i == 0 else False, full_html=False))
    f.write("</body></html>")
```

### 关键点

- `include_plotlyjs='cdn'`：只在第一个图表加载 plotly.js（减少文件大小）
- `full_html=False`：生成片段 HTML，便于拼接
- 图表按顺序垂直堆叠，浏览器滚动查看

## 输出结构

```
outputs/visualizations/
└── report.html
```

## 使用方式

运行 workflow 后，用浏览器打开 `outputs/visualizations/report.html` 查看所有图表。