#  Copyright (c) Microsoft Corporation.
#  Licensed under the MIT License.
"""
Qlib provides two kinds of interfaces.
(1) Users could define the Quant research workflow by a simple configuration.
(2) Qlib is designed in a modularized way and supports creating research workflow by code just like building blocks.

The interface of (1) is `qrun XXX.yaml`.  The interface of (2) is script like this, which nearly does the same thing as `qrun XXX.yaml`
"""

import os
# 设置环境变量以确保子进程也能屏蔽 Gym 告警
os.environ["PYTHONWARNINGS"] = "ignore::UserWarning:gym,ignore:.*Gym has been unmaintained since 2022.*"

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="gym")
warnings.filterwarnings("ignore", message=".*Gym has been unmaintained since 2022.*")

import qlib
from qlib.constant import REG_CN
from qlib.utils import init_instance_by_config, flatten_dict
from qlib.workflow import R
from qlib.workflow.record_temp import SignalRecord, PortAnaRecord, SigAnaRecord
from qlib.contrib.strategy import TopkDropoutStrategy
from qlib.backtest.decision import TradeDecisionWO

class PeriodicTopkDropoutStrategy(TopkDropoutStrategy):
    def __init__(self, period=1, **kwargs):
        super().__init__(**kwargs)
        self.period = period

    def generate_trade_decision(self, execute_result=None):
        # 仅在指定的周期（如每5天）生成交易决策
        if self.trade_calendar.get_trade_step() % self.period == 0:
            return super().generate_trade_decision(execute_result)
        else:
            # 非调仓日，不产生任何订单
            return TradeDecisionWO([], self)


import logging
import os
import pandas as pd
from qlib.contrib.report import analysis_model, analysis_position

# 输出目录配置
OUTPUT_DIR = "outputs/visualizations"

# 自定义中证 1000 配置
CSI1000_BENCH = "SH000852"  # 中证 1000 基准
CSI1000_MARKET = "all"  # 使用完整1000股票数据集

CSI1000_GBDT_TASK = {
    "model": {
        "class": "LGBModel",
        "module_path": "qlib.contrib.model.gbdt",
        "kwargs": {
            "loss": "mse",
            "colsample_bytree": 0.8879,
            "learning_rate": 0.0421,
            "subsample": 0.8789,
            "lambda_l1": 205.6999,
            "lambda_l2": 580.9768,
            "max_depth": 8,
            "num_leaves": 210,
            "num_threads": None,
            "verbosity": 1,
        },
    },
    "dataset": {
        "class": "DatasetH",
        "module_path": "qlib.data.dataset",
        "kwargs": {
            "handler": {
                # 使用固定 beta 版本 (beta=1)，省去 rolling beta 计算
                "class": "Alpha158FixedBetaHandler",
                "module_path": "data.handler_fixed_beta",
                "kwargs": {
                    "start_time": "2015-01-05",
                    "end_time": "2026-03-26",
                    "fit_start_time": "2015-01-05",
                    "fit_end_time": "2022-12-31",
                    "instruments": CSI1000_MARKET,
                    "benchmark": CSI1000_BENCH,
                    "beta_alpha": 0.5,
                    "filter_pipe": [
                        {
                            "filter_type": "ExpressionDFilter",
                            "rule_expression": "$volume > 0",
                            "filter_start_time": None,
                            "filter_end_time": None,
                            "keep": True,
                        }
                    ],
                },
            },
            "segments": {
                "train": ("2015-01-05", "2022-12-31"),
                "valid": ("2023-01-01", "2023-12-31"),
                "test": ("2024-01-01", "2026-03-25"),
            },
        },
    },
}

if __name__ == "__main__":
    # 使用本地 qlib 数据,启用缓存优化内存使用
    provider_uri = "data/qlib_data"
    qlib.init(
        provider_uri=provider_uri,
        region=REG_CN,
        expression_cache="DiskExpressionCache",
        dataset_cache="DiskDatasetCache",
        mem_cache_size_limit=5000,  # 限制内存缓存500MB
    )

    # 从自定义配置初始化模型和数据集
    model = init_instance_by_config(CSI1000_GBDT_TASK["model"])
    dataset = init_instance_by_config(CSI1000_GBDT_TASK["dataset"])

    port_analysis_config = {
        "executor": {
            "class": "SimulatorExecutor",
            "module_path": "qlib.backtest.executor",
            "kwargs": {
                "time_per_step": "day",
                "generate_portfolio_metrics": True,
            },
        },
        "strategy": {
            "class": "PeriodicTopkDropoutStrategy",
            "module_path": "__main__",
            "kwargs": {
                "signal": (model, dataset),
                "topk": 3,      # 持仓 3 只股票
                "n_drop": 1,     # 跌出前 2 名即换仓
                "period": 5,    # 每 5 天调仓一次
            },
        },
        "backtest": {
            "start_time": "2024-01-01",  # 回测从测试集开始
            "end_time": "2026-03-25",
            "account": 100000000,
            "benchmark": CSI1000_BENCH,  # 使用中证 1000 作为基准
            "exchange_kwargs": {
                "freq": "day",
                "limit_threshold": 0.095,
                "deal_price": "close",
                "open_cost": 0.0003,
                "close_cost": 0.0013,
                "min_cost": 5,
            },
        },
    }

    # 可选：展示数据集头部信息
    # example_df = dataset.prepare("train")
    # print(example_df.head())

    # 开始实验
    with R.start(experiment_name="workflow_csi1000"):
        R.log_params(**flatten_dict(CSI1000_GBDT_TASK))
        model.fit(dataset)
        R.save_objects(**{"params.pkl": model})

        # 预测预测
        recorder = R.get_recorder()
        sr = SignalRecord(model, dataset, recorder)
        sr.generate()

        # 信号分析
        sar = SigAnaRecord(recorder)
        sar.generate()

        # 投资组合分析 (回测)
        par = PortAnaRecord(recorder, port_analysis_config, "day")
        par.generate()

        # --- 可视化图表输出到本地 ---
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        try:
            print(f"正在生成可视化图表并输出到 {OUTPUT_DIR}...")
            # 从 recorder 加载所需数据
            report_normal = recorder.load_object("portfolio_analysis/report_normal_1day.pkl")
            pred_df = recorder.load_object("pred.pkl")
            label_df = recorder.load_object("label.pkl")
            
            # 标准化 label 列名 (有些数据生成为 LABEL0)
            if "label" not in label_df.columns and len(label_df.columns) == 1:
                label_df.columns = ["label"]
            elif "LABEL0" in label_df.columns:
                label_df.rename(columns={"LABEL0": "label"}, inplace=True)
                
            # 组合 pred_label
            pred_label = pd.concat([pred_df, label_df], axis=1, sort=True).reindex(pred_df.index)

            # 1. 回测图表 (收益率与最大回撤)
            figures = []
            try:
                fig_port = analysis_position.report_graph(report_normal, show_notebook=False)
                # tuple 解包: report_graph 返回一个包含两张图的 tuple (return_graph, turnover_graph)
                figures.append(fig_port[0])
            except Exception as e:
                logging.warning(f"生成回测图表失败: {e}")

            # 2. 模型表现 IC 图表
            try:
                fig_model = analysis_model.model_performance_graph(pred_label, show_notebook=False)
                # model_performance_graph 返回一个 list 的 go.Figure
                figures.extend(fig_model)
            except Exception as e:
                logging.warning(f"生成模型表现图表失败: {e}")

            # 3. 分层收益率图表 (TopK / BottomK)
            try:
                fig_score = analysis_position.score_ic_graph(pred_label, show_notebook=False)
                # 返回一个 tuple/list
                figures.append(fig_score[0])
            except Exception as e:
                logging.warning(f"生成分层收益率图表失败: {e}")

            # 合并所有图表为单个 HTML 文件
            if figures:
                with open(f"{OUTPUT_DIR}/report.html", "w", encoding="utf-8") as f:
                    f.write("<html><head><meta charset='utf-8'><title>Qlib 回测报告</title></head><body>")
                    for i, fig in enumerate(figures):
                        # 只在第一个图表加载 plotly.js
                        f.write(fig.to_html(include_plotlyjs='cdn' if i == 0 else False, full_html=False))
                    f.write("</body></html>")
                print(f"报告已生成: {OUTPUT_DIR}/report.html")

        except Exception as e:
            logging.warning(f"数据提取失败，跳过可视化流程: {e}")
