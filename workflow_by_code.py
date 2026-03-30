#  Copyright (c) Microsoft Corporation.
#  Licensed under the MIT License.
"""
Qlib provides two kinds of interfaces.
(1) Users could define the Quant research workflow by a simple configuration.
(2) Qlib is designed in a modularized way and supports creating research workflow by code just like building blocks.

The interface of (1) is `qrun XXX.yaml`.  The interface of (2) is script like this, which nearly does the same thing as `qrun XXX.yaml`
"""

import qlib
from qlib.constant import REG_CN
from qlib.utils import init_instance_by_config, flatten_dict
from qlib.workflow import R
from qlib.workflow.record_temp import SignalRecord, PortAnaRecord, SigAnaRecord

import logging
import os
import pandas as pd
from qlib.contrib.report import analysis_model, analysis_position

# 输出目录配置
OUTPUT_DIR = "outputs/visualizations"

# 自定义中证 1000 配置
CSI1000_BENCH = "SH000852"  # 中证 1000 基准
CSI1000_MARKET = "all"      # 对应 instruments/all.txt

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
            "num_threads": 20,
        },
    },
    "dataset": {
        "class": "DatasetH",
        "module_path": "qlib.data.dataset",
        "kwargs": {
            "handler": {
                "class": "Alpha158",
                "module_path": "qlib.contrib.data.handler",
                "kwargs": {
                    "start_time": "2015-01-05",  # 数据起始日期
                    "end_time": "2026-03-26",    # 数据截止日期
                    "fit_start_time": "2015-01-05",
                    "fit_end_time": "2022-12-31",
                    "instruments": CSI1000_MARKET,
                    # 过滤停牌或无交易数据的样本
                    "filter_pipe": [
                        {
                            "filter_type": "ExpressionDFilter",
                            "rule_expression": "$volume > 0",  # 成交量大于 0 代表真正有交易（非停牌）
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
    # 使用本地 qlib 数据
    provider_uri = "data/qlib_data"
    qlib.init(provider_uri=provider_uri, region=REG_CN)

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
            "class": "TopkDropoutStrategy",
            "module_path": "qlib.contrib.strategy.signal_strategy",
            "kwargs": {
                "signal": (model, dataset),
                "topk": 3,      # 持仓 3 只股票
                "n_drop": 1,     # 跌出前 2 名即换仓
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

        # --- 可视化与 MLflow 深度集成 ---
        try:
            print("正在生成可视化图表并输出到 MLflow...")
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
            try:
                fig_port = analysis_position.report_graph(report_normal, show_notebook=False)
                # tuple 解包: report_graph 返回一个包含两张图的 tuple (return_graph, turnover_graph)
                mlflow.log_figure(fig_port[0], "visualizations/portfolio_cumulative_return.html")
            except Exception as e:
                logging.warning(f"生成回测图表失败: {e}")

            # 2. 模型表现 IC 图表
            try:
                fig_model = analysis_model.model_performance_graph(pred_label, show_notebook=False)
                # model_performance_graph 返回一个 list 的 go.Figure
                for i, fig in enumerate(fig_model):
                    mlflow.log_figure(fig, f"visualizations/model_performance_ic_rankic_{i}.html")
            except Exception as e:
                logging.warning(f"生成模型表现图表失败: {e}")

            # 3. 分层收益率图表 (TopK / BottomK)
            try:
                fig_score = analysis_position.score_ic_graph(pred_label, show_notebook=False)
                # 返回一个 tuple/list
                mlflow.log_figure(fig_score[0], "visualizations/portfolio_score_ic.html")
            except Exception as e:
                logging.warning(f"生成分层收益率图表失败: {e}")

        except Exception as e:
            logging.warning(f"数据提取失败，跳过可视化流程: {e}")
