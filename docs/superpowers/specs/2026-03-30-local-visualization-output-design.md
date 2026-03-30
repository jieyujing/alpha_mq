# 本地可视化图表输出设计

**日期**: 2026-03-30

## 目标

将 workflow_by_code.py 中的图表从 mlflow 上传改为直接保存到本地 HTML 文件。

## 改动范围

- 文件: `workflow_by_code.py`
- 改动量: 约 15 行代码

## 实现细节

### 1. 移除 mlflow 依赖

- 删除 `import mlflow`（第 18 行）
- 删除所有 `mlflow.log_figure()` 调用

### 2. 添加输出目录

在文件顶部添加：
```python
OUTPUT_DIR = "outputs/visualizations"
```

在生成图表前创建目录：
```python
import os
os.makedirs(OUTPUT_DIR, exist_ok=True)
```

### 3. 保存图表到本地

替换 `mlflow.log_figure()` 为 `fig.write_html()`：

| 图表类型 | 输出路径 |
|---------|---------|
| 累计收益率 | `outputs/visualizations/portfolio_cumulative_return.html` |
| 模型 IC | `outputs/visualizations/model_performance_ic_rankic_{i}.html` |
| Score IC | `outputs/visualizations/portfolio_score_ic.html` |

## 输出结构

```
outputs/visualizations/
├── portfolio_cumulative_return.html
├── model_performance_ic_rankic_0.html
├── model_performance_ic_rankic_1.html
└── portfolio_score_ic.html
```

## 使用方式

运行 workflow 后，用浏览器打开 HTML 文件查看交互式图表。