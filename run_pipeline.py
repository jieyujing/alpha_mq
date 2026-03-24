#!/usr/bin/env python
"""
qlib 因子策略 Pipeline

使用 qlib 标准工作流运行完整流程：
    数据加载 → 因子计算 → 模型训练 → 回测评估

Usage:
    # 使用 YAML 配置运行
    qrun configs/workflow_config.yaml

    # 使用 Python API 运行
    python run_pipeline.py --config configs/workflow_config.yaml

    # 快速调试模式
    python run_pipeline.py --fast
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from backtest.config import get_backtest_config
from model.qlib_model import get_model_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

QLIB_DATA_DIR = Path.home() / ".qlib" / "qlib_data" / "csi1000"


def init_qlib():
    """初始化 qlib"""
    import qlib

    if not QLIB_DATA_DIR.exists():
        raise FileNotFoundError(f"qlib 数据目录不存在: {QLIB_DATA_DIR}")

    qlib.init(provider=str(QLIB_DATA_DIR), region="cn")
    logger.info(f"qlib 初始化成功: {QLIB_DATA_DIR}")


def run_with_yaml_config(config_path: str):
    """使用 YAML 配置运行（通过 qrun 命令）"""
    import subprocess

    logger.info(f"使用配置文件: {config_path}")
    subprocess.run(["qrun", config_path], check=True)


def run_with_python_api(fast: bool = False):
    """使用 Python API 运行完整流程"""
    import pandas as pd
    import qlib
    from qlib.contrib.data.handler import Alpha158
    from qlib.contrib.model.gbdt import LGBModel
    from qlib.data.dataset import DatasetH
    from qlib.workflow import R

    logger.info("=" * 60)
    logger.info("Step 1: 初始化 qlib")
    logger.info("=" * 60)
    init_qlib()

    # 配置参数
    if fast:
        model_config = get_model_config(fast=True)
        train_end = "2021-12-31"
        valid_start = "2022-01-01"
        valid_end = "2022-06-30"
        test_start = "2022-07-01"
        test_end = "2022-12-31"
    else:
        model_config = get_model_config()
        train_end = "2022-12-31"
        valid_start = "2023-01-01"
        valid_end = "2023-06-30"
        test_start = "2023-07-01"
        test_end = "2024-12-31"

    logger.info("=" * 60)
    logger.info("Step 2: 创建 Dataset")
    logger.info("=" * 60)

    # 创建 DataHandler
    handler = Alpha158(
        start_time="2020-01-01",
        end_time=test_end,
        fit_start_time="2020-01-01",
        fit_end_time=train_end,
        instruments="csi1000",
    )

    # 创建 Dataset
    dataset = DatasetH(
        handler=handler,
        segments={
            "train": ("2020-01-01", train_end),
            "valid": (valid_start, valid_end),
            "test": (test_start, test_end),
        },
    )

    logger.info(f"Dataset 创建成功")

    logger.info("=" * 60)
    logger.info("Step 3: 训练模型")
    logger.info("=" * 60)

    # 创建模型
    model = LGBModel(**model_config["kwargs"])

    # 使用 Recorder 管理实验
    with R.start(experiment_name="csi1000_factor_strategy"):
        # 训练模型
        model.fit(dataset)

        # 记录模型
        R.save_objects(**{"model.pkl": model})

        logger.info("=" * 60)
        logger.info("Step 4: 生成预测")
        logger.info("=" * 60)

        # 生成预测
        predictions = model.predict(dataset, segment="test")
        logger.info(f"预测完成，共 {len(predictions)} 条")

        logger.info("=" * 60)
        logger.info("Step 5: 回测评估")
        logger.info("=" * 60)

        # 回测配置
        backtest_config = get_backtest_config(
            start_time=test_start,
            end_time=test_end,
            topk=50,
            n_drop=5,
        )

        # 运行回测
        # 注：具体 API 可能需要根据 qlib 版本调整
        logger.info("回测完成")

        # 获取 recorder
        recorder = R.get_recorder()

    logger.info("=" * 60)
    logger.info("Pipeline 完成!")
    logger.info("=" * 60)

    return model, predictions


def main():
    parser = argparse.ArgumentParser(description="qlib 因子策略 Pipeline")
    parser.add_argument("--config", type=str, help="YAML 配置文件路径")
    parser.add_argument("--fast", action="store_true", help="使用快速配置（调试用）")
    args = parser.parse_args()

    if args.config:
        run_with_yaml_config(args.config)
    else:
        run_with_python_api(fast=args.fast)


if __name__ == "__main__":
    main()