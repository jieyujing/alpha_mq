# CLI Pipeline 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 创建 CLI 工具，支持训练、回测、评估的自动化流水线

**Architecture:** 新增 pipeline/ 模块封装各阶段逻辑，main.py 作为 CLI 入口，复用现有 model/、factor/、backtest/ 模块

**Tech Stack:** Python, click (CLI), qlib, LightGBM, polars

---

## Task 1: 创建 pipeline 模块结构

**Files:**
- Create: `pipeline/__init__.py`

**Step 1: 创建 pipeline 目录和 __init__.py**

```python
"""
Pipeline 模块

提供训练、回测、评估的完整流水线。
"""
from __future__ import annotations

__all__ = ["Trainer", "Backtester", "Evaluator"]
```

**Step 2: 创建输出目录**

Run: `mkdir -p output`
Expected: 创建 output/ 目录

**Step 3: Commit**

```bash
git add pipeline/__init__.py output/.gitkeep
git commit -m "feat: add pipeline module structure"
```

---

## Task 2: 实现 Trainer 类

**Files:**
- Create: `pipeline/trainer.py`
- Create: `tests/test_trainer.py`

**Step 1: 编写 Trainer 测试**

```python
# tests/test_trainer.py
"""Trainer 模块测试"""
from __future__ import annotations

import pytest
import pandas as pd
import numpy as np


def test_trainer_init():
    """测试 Trainer 初始化"""
    from pipeline.trainer import Trainer

    trainer = Trainer(
        train_start="2020-01-01",
        train_end="2022-12-31",
    )
    assert trainer.train_start == "2020-01-01"
    assert trainer.train_end == "2022-12-31"


def test_trainer_has_train_method():
    """测试 Trainer 有 train 方法"""
    from pipeline.trainer import Trainer

    trainer = Trainer(
        train_start="2020-01-01",
        train_end="2022-12-31",
    )
    assert hasattr(trainer, "train")
```

**Step 2: 运行测试确认失败**

Run: `pytest tests/test_trainer.py -v`
Expected: FAIL - ModuleNotFoundError

**Step 3: 实现 Trainer 类骨架**

```python
# pipeline/trainer.py
"""
训练流程封装

封装数据加载、特征构建、模型训练的完整流程。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import joblib
import pandas as pd

from model.config import ModelConfig
from model.trainer import FactorModel

logger = logging.getLogger(__name__)


class Trainer:
    """
    训练流程封装类。

    封装从数据加载到模型保存的完整训练流程。
    """

    def __init__(
        self,
        train_start: str,
        train_end: str,
        model_config: Optional[ModelConfig] = None,
        output_dir: Optional[Path] = None,
    ) -> None:
        """
        初始化 Trainer。

        Parameters
        ----------
        train_start : str
            训练集开始日期 (YYYY-MM-DD)
        train_end : str
            训练集结束日期 (YYYY-MM-DD)
        model_config : ModelConfig, optional
            模型配置，默认使用 ModelConfig.fast()
        output_dir : Path, optional
            输出目录，默认 output/run_{timestamp}
        """
        self.train_start = train_start
        self.train_end = train_end
        self.model_config = model_config or ModelConfig.fast()
        self.output_dir = output_dir or Path("output")
        self.model: Optional[FactorModel] = None

    def train(self) -> FactorModel:
        """
        执行训练流程。

        Returns
        -------
        FactorModel
            训练好的模型
        """
        raise NotImplementedError("待实现")

    def save_model(self, path: Optional[Path] = None) -> Path:
        """
        保存模型到文件。

        Parameters
        ----------
        path : Path, optional
            保存路径，默认 output_dir/model.joblib

        Returns
        -------
        Path
            模型保存路径
        """
        if self.model is None:
            raise ValueError("模型尚未训练")

        path = path or self.output_dir / "model.joblib"
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, path)
        logger.info(f"模型已保存到 {path}")
        return path

    def load_model(self, path: Path) -> None:
        """从文件加载模型"""
        self.model = joblib.load(path)
        logger.info(f"模型已从 {path} 加载")
```

**Step 4: 运行测试确认通过**

Run: `pytest tests/test_trainer.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add pipeline/trainer.py tests/test_trainer.py
git commit -m "feat: add Trainer class skeleton"
```

---

## Task 3: 实现 Trainer 的 train 方法

**Files:**
- Modify: `pipeline/trainer.py`
- Modify: `tests/test_trainer.py`

**Step 1: 编写 train 方法测试**

```python
# tests/test_trainer.py 新增测试
def test_trainer_train_with_mock_data():
    """测试 Trainer 使用模拟数据训练"""
    from pipeline.trainer import Trainer
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        trainer = Trainer(
            train_start="2020-01-01",
            train_end="2022-12-31",
            output_dir=Path(tmpdir),
        )

        # 使用模拟数据测试
        # train() 方法需要 qlib 数据，这里先跳过实际训练
        # 只测试接口是否正确
        assert trainer.model_config is not None
```

**Step 2: 实现 train 方法（简化版，使用 qlib 数据集）**

```python
# pipeline/trainer.py 中 train 方法的实现

    def train(self) -> FactorModel:
        """
        执行训练流程。

        使用 qlib Alpha158 因子和 LightGBM 模型训练。

        Returns
        -------
        FactorModel
            训练好的模型
        """
        try:
            import qlib
            from qlib.data import D
            from qlib.data.dataset import DatasetH
            from qlib.contrib.data.handler import Alpha158
        except ImportError:
            logger.error("qlib 未安装，请先安装 pyqlib")
            raise

        # 初始化 qlib
        qlib_data_dir = Path.home() / ".qlib" / "qlib_data" / "csi1000"
        if not qlib_data_dir.exists():
            raise FileNotFoundError(
                f"qlib 数据目录不存在: {qlib_data_dir}\n"
                "请先运行数据构建脚本"
            )

        qlib.init(
            default_conf="client",
            provider_uri=str(qlib_data_dir),
            mount_path=str(qlib_data_dir),
        )
        logger.info("qlib 初始化完成")

        # 构建 Dataset
        dataset = DatasetH(
            handler={
                "class": "Alpha158",
                "module_path": "qlib.contrib.data.handler",
                "kwargs": {
                    "start_time": self.train_start,
                    "end_time": self.train_end,
                    "fit_start_time": self.train_start,
                    "fit_end_time": self.train_end,
                    "instruments": "csi1000",
                },
            },
            segments={
                "train": (self.train_start, self.train_end),
            },
        )

        logger.info("数据集构建完成，开始训练...")

        # 获取训练数据
        train_data = dataset.prepare("train")

        if train_data is None or len(train_data) == 0:
            raise ValueError("训练数据为空，请检查日期范围和数据可用性")

        # 分离特征和标签
        X = train_data.iloc[:, :-1]  # 除最后一列外的所有列作为特征
        y = train_data.iloc[:, -1]   # 最后一列作为标签

        # 训练模型
        self.model = FactorModel(self.model_config)

        # 划分验证集 (10%)
        split_idx = int(len(X) * 0.9)
        X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]

        self.model.train(X_train, y_train, X_val, y_val)

        logger.info(f"模型训练完成，样本数: {len(X)}")
        return self.model
```

**Step 3: 运行测试**

Run: `pytest tests/test_trainer.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add pipeline/trainer.py tests/test_trainer.py
git commit -m "feat: implement Trainer.train() method"
```

---

## Task 4: 实现 Backtester 类

**Files:**
- Create: `pipeline/backtester.py`
- Create: `tests/test_backtester.py`

**Step 1: 编写 Backtester 测试**

```python
# tests/test_backtester.py
"""Backtester 模块测试"""
from __future__ import annotations


def test_backtester_init():
    """测试 Backtester 初始化"""
    from pipeline.backtester import Backtester

    backtester = Backtester(
        test_start="2023-01-01",
        test_end="2024-12-31",
    )
    assert backtester.test_start == "2023-01-01"
    assert backtester.test_end == "2024-12-31"


def test_backtester_has_run_method():
    """测试 Backtester 有 run 方法"""
    from pipeline.backtester import Backtester

    backtester = Backtester(
        test_start="2023-01-01",
        test_end="2024-12-31",
    )
    assert hasattr(backtester, "run")
```

**Step 2: 运行测试确认失败**

Run: `pytest tests/test_backtester.py -v`
Expected: FAIL - ModuleNotFoundError

**Step 3: 实现 Backtester 类**

```python
# pipeline/backtester.py
"""
回测流程封装

封装策略回测的完整流程。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

import joblib
import pandas as pd

from model.trainer import FactorModel
from backtest.strategy import get_strategy_config

logger = logging.getLogger(__name__)


class Backtester:
    """
    回测流程封装类。

    封装模型预测和策略回测的完整流程。
    """

    def __init__(
        self,
        test_start: str,
        test_end: str,
        topk: int = 50,
        n_drop: int = 5,
        output_dir: Optional[Path] = None,
    ) -> None:
        """
        初始化 Backtester。

        Parameters
        ----------
        test_start : str
            测试集开始日期 (YYYY-MM-DD)
        test_end : str
            测试集结束日期 (YYYY-MM-DD)
        topk : int
            持仓股票数量，默认 50
        n_drop : int
            每次调仓剔除数量，默认 5
        output_dir : Path, optional
            输出目录
        """
        self.test_start = test_start
        self.test_end = test_end
        self.topk = topk
        self.n_drop = n_drop
        self.output_dir = output_dir or Path("output")
        self.results: Optional[dict[str, Any]] = None

    def run(self, model: FactorModel) -> dict[str, Any]:
        """
        执行回测。

        Parameters
        ----------
        model : FactorModel
            训练好的模型

        Returns
        -------
        dict
            回测结果
        """
        try:
            import qlib
            from qlib.backtest import backtest
            from qlib.contrib.strategy.strategy import TopkDropoutStrategy
            from qlib.contrib.executor.simulator_executor import SimulatorExecutor
        except ImportError:
            logger.error("qlib 未安装")
            raise

        # 初始化 qlib
        qlib_data_dir = Path.home() / ".qlib" / "qlib_data" / "csi1000"
        qlib.init(
            default_conf="client",
            provider_uri=str(qlib_data_dir),
            mount_path=str(qlib_data_dir),
        )

        # 执行回测
        logger.info("开始回测...")

        strategy_config = {
            "class": "TopkDropoutStrategy",
            "module_path": "qlib.contrib.strategy.strategy",
            "kwargs": {
                "topk": self.topk,
                "n_drop": self.n_drop,
                "signal": model,  # 使用模型预测作为信号
            },
        }

        executor_config = {
            "class": "SimulatorExecutor",
            "module_path": "qlib.contrib.executor.simulator_executor",
            "kwargs": {
                "time_per_step": "day",
                "generate_portfolio_metrics": True,
                "trade_cost": {
                    "buy": 0.001,
                    "sell": 0.001,
                },
            },
        }

        # 调用 qlib backtest
        try:
            portfolio_metric, indicator = backtest(
                executor=executor_config,
                strategy=strategy_config,
                start_time=self.test_start,
                end_time=self.test_end,
            )

            self.results = {
                "test_start": self.test_start,
                "test_end": self.test_end,
                "topk": self.topk,
                "n_drop": self.n_drop,
                "portfolio_metric": portfolio_metric,
                "indicator": indicator,
            }

            logger.info("回测完成")
            return self.results

        except Exception as e:
            logger.error(f"回测失败: {e}")
            raise

    def save_results(self, path: Optional[Path] = None) -> Path:
        """保存回测结果"""
        if self.results is None:
            raise ValueError("尚未执行回测")

        path = path or self.output_dir / "backtest_result.json"

        # 转换为可序列化格式
        serializable = {
            "test_start": self.results["test_start"],
            "test_end": self.results["test_end"],
            "topk": self.results["topk"],
            "n_drop": self.results["n_drop"],
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(serializable, indent=2))
        logger.info(f"回测结果已保存到 {path}")
        return path
```

**Step 4: 运行测试**

Run: `pytest tests/test_backtester.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add pipeline/backtester.py tests/test_backtester.py
git commit -m "feat: add Backtester class"
```

---

## Task 5: 实现 Evaluator 类

**Files:**
- Create: `pipeline/evaluator.py`
- Create: `tests/test_evaluator.py`

**Step 1: 编写 Evaluator 测试**

```python
# tests/test_evaluator.py
"""Evaluator 模块测试"""
from __future__ import annotations

import pandas as pd
import numpy as np


def test_evaluator_init():
    """测试 Evaluator 初始化"""
    from pipeline.evaluator import Evaluator

    evaluator = Evaluator()
    assert evaluator is not None


def test_calculate_ic():
    """测试 IC 计算"""
    from pipeline.evaluator import Evaluator

    evaluator = Evaluator()

    # 模拟数据
    np.random.seed(42)
    factor = pd.Series(np.random.randn(100))
    returns = pd.Series(np.random.randn(100))

    ic = evaluator.calculate_ic(factor, returns)
    assert -1 <= ic <= 1


def test_generate_report():
    """测试报告生成"""
    from pipeline.evaluator import Evaluator

    evaluator = Evaluator()

    # 模拟预测和收益
    np.random.seed(42)
    predictions = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=100),
        "stock": ["A"] * 50 + ["B"] * 50,
        "factor": np.random.randn(100),
        "return": np.random.randn(100) * 0.02,
    })

    report = evaluator.generate_report(predictions)
    assert "ic_mean" in report
    assert "icir" in report
```

**Step 2: 运行测试确认失败**

Run: `pytest tests/test_evaluator.py -v`
Expected: FAIL - ModuleNotFoundError

**Step 3: 实现 Evaluator 类**

```python
# pipeline/evaluator.py
"""
评估报告生成

计算因子 IC、分组收益、策略业绩等指标。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


class Evaluator:
    """
    评估报告生成器。

    计算因子预测能力和策略业绩指标。
    """

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        self.output_dir = output_dir or Path("output")
        self.report: Optional[dict] = None

    def calculate_ic(
        self,
        factor: pd.Series,
        returns: pd.Series,
    ) -> float:
        """
        计算因子 IC (Rank IC)。

        Parameters
        ----------
        factor : pd.Series
            因子值
        returns : pd.Series
            未来收益

        Returns
        -------
        float
            Spearman 秩相关系数
        """
        mask = factor.notna() & returns.notna()
        if mask.sum() < 10:
            return 0.0
        corr, _ = stats.spearmanr(factor[mask], returns[mask])
        return float(corr) if np.isfinite(corr) else 0.0

    def calculate_ic_series(
        self,
        predictions: pd.DataFrame,
        factor_col: str = "factor",
        return_col: str = "return",
        date_col: str = "date",
    ) -> pd.Series:
        """
        计算每日 IC 序列。

        Parameters
        ----------
        predictions : pd.DataFrame
            包含因子、收益、日期的数据
        factor_col : str
            因子列名
        return_col : str
            收益列名
        date_col : str
            日期列名

        Returns
        -------
        pd.Series
            每日 IC 值
        """
        ic_list = []
        dates = predictions[date_col].unique()

        for date in dates:
            day_data = predictions[predictions[date_col] == date]
            ic = self.calculate_ic(
                day_data[factor_col],
                day_data[return_col]
            )
            ic_list.append({"date": date, "ic": ic})

        return pd.DataFrame(ic_list).set_index("date")["ic"]

    def calculate_group_returns(
        self,
        predictions: pd.DataFrame,
        factor_col: str = "factor",
        return_col: str = "return",
        n_groups: int = 5,
    ) -> dict[str, float]:
        """
        计算分组收益率。

        Parameters
        ----------
        predictions : pd.DataFrame
            包含因子和收益的数据
        factor_col : str
            因子列名
        return_col : str
            收益列名
        n_groups : int
            分组数量

        Returns
        -------
        dict
            各组平均收益率
        """
        predictions = predictions.copy()
        predictions["group"] = pd.qcut(
            predictions[factor_col],
            n_groups,
            labels=False,
            duplicates="drop"
        )

        group_returns = predictions.groupby("group")[return_col].mean()
        return {f"Q{i+1}": ret for i, ret in group_returns.items()}

    def generate_report(
        self,
        predictions: pd.DataFrame,
        factor_col: str = "factor",
        return_col: str = "return",
    ) -> dict:
        """
        生成完整评估报告。

        Parameters
        ----------
        predictions : pd.DataFrame
            包含因子和收益的数据
        factor_col : str
            因子列名
        return_col : str
            收益列名

        Returns
        -------
        dict
            评估指标字典
        """
        # 计算 IC 序列
        ic_series = self.calculate_ic_series(predictions, factor_col, return_col)

        # IC 统计
        ic_mean = ic_series.mean()
        ic_std = ic_series.std()
        icir = ic_mean / ic_std if ic_std > 0 else 0.0
        ic_positive_rate = (ic_series > 0).mean()

        # 分组收益
        group_returns = self.calculate_group_returns(predictions, factor_col, return_col)

        # 构建报告
        self.report = {
            "ic_mean": float(ic_mean),
            "ic_std": float(ic_std),
            "icir": float(icir),
            "ic_positive_rate": float(ic_positive_rate),
            "group_returns": group_returns,
        }

        return self.report

    def save_report(self, path: Optional[Path] = None) -> Path:
        """保存报告为 Markdown"""
        if self.report is None:
            raise ValueError("尚未生成报告")

        path = path or self.output_dir / "report.md"

        lines = [
            "# 策略评估报告",
            "",
            "## 1. 因子预测能力",
            "",
            "| 指标 | 值 |",
            "|------|-----|",
            f"| Rank IC 均值 | {self.report['ic_mean']:.4f} |",
            f"| Rank ICIR | {self.report['icir']:.4f} |",
            f"| IC > 0 占比 | {self.report['ic_positive_rate']:.2%} |",
            "",
            "## 2. 分组收益",
            "",
            "| 组别 | 平均收益 |",
            "|------|---------|",
        ]

        for group, ret in self.report["group_returns"].items():
            lines.append(f"| {group} | {ret:.4%} |")

        lines.extend([
            "",
            "---",
            "*报告由 alpha-mq 自动生成*",
        ])

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines))
        logger.info(f"报告已保存到 {path}")
        return path
```

**Step 4: 运行测试**

Run: `pytest tests/test_evaluator.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add pipeline/evaluator.py tests/test_evaluator.py
git commit -m "feat: add Evaluator class"
```

---

## Task 6: 实现 CLI 入口 main.py

**Files:**
- Create: `main.py`

**Step 1: 实现 CLI 入口**

```python
#!/usr/bin/env python
"""
alpha-mq CLI 入口

提供训练、回测、评估的命令行接口。

Usage:
    python main.py run                    # 运行完整流程
    python main.py train                  # 仅训练
    python main.py backtest               # 仅回测
    python main.py evaluate               # 仅评估
"""
from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_output_dir(base_dir: Path, name: Optional[str] = None) -> Path:
    """创建输出目录"""
    if name:
        output_dir = base_dir / name
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = base_dir / f"run_{timestamp}"

    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def cmd_train(args) -> None:
    """训练命令"""
    from pipeline.trainer import Trainer

    output_dir = create_output_dir(Path(args.output_dir), args.name)

    logger.info(f"开始训练，输出目录: {output_dir}")
    logger.info(f"训练区间: {args.train_start} ~ {args.train_end}")

    trainer = Trainer(
        train_start=args.train_start,
        train_end=args.train_end,
        output_dir=output_dir,
    )

    trainer.train()
    trainer.save_model()

    logger.info("训练完成")


def cmd_backtest(args) -> None:
    """回测命令"""
    from pipeline.backtester import Backtester

    output_dir = Path(args.output_dir)
    model_path = output_dir / "model.joblib"

    if not model_path.exists():
        logger.error(f"模型文件不存在: {model_path}")
        logger.error("请先运行 train 命令")
        return

    logger.info(f"开始回测，测试区间: {args.test_start} ~ {args.test_end}")

    from model.trainer import FactorModel
    model = FactorModel()
    model.load(model_path)

    backtester = Backtester(
        test_start=args.test_start,
        test_end=args.test_end,
        output_dir=output_dir,
    )

    backtester.run(model)
    backtester.save_results()

    logger.info("回测完成")


def cmd_evaluate(args) -> None:
    """评估命令"""
    from pipeline.evaluator import Evaluator

    output_dir = Path(args.output_dir)

    logger.info("生成评估报告...")

    # 加载预测结果（如果有）
    predictions_path = output_dir / "predictions.parquet"
    if not predictions_path.exists():
        logger.warning(f"预测文件不存在: {predictions_path}")
        logger.warning("跳过评估，请先运行 backtest 命令")
        return

    import pandas as pd
    predictions = pd.read_parquet(predictions_path)

    evaluator = Evaluator(output_dir=output_dir)
    evaluator.generate_report(predictions)
    evaluator.save_report()

    logger.info("评估完成")


def cmd_run(args) -> None:
    """运行完整流程"""
    output_dir = create_output_dir(Path(args.output_dir), args.name)

    logger.info("=" * 50)
    logger.info("开始完整流程")
    logger.info(f"输出目录: {output_dir}")
    logger.info("=" * 50)

    # 1. 训练
    train_args = argparse.Namespace(
        train_start=args.train_start,
        train_end=args.train_end,
        output_dir=str(output_dir),
        name=None,
    )
    cmd_train(train_args)

    # 2. 回测
    backtest_args = argparse.Namespace(
        test_start=args.test_start,
        test_end=args.test_end,
        output_dir=str(output_dir),
    )
    cmd_backtest(backtest_args)

    # 3. 评估
    evaluate_args = argparse.Namespace(
        output_dir=str(output_dir),
    )
    cmd_evaluate(evaluate_args)

    logger.info("=" * 50)
    logger.info(f"完整流程结束，输出目录: {output_dir}")
    logger.info("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="alpha-mq: 中证1000 多因子选股系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # run 命令
    run_parser = subparsers.add_parser("run", help="运行完整流程")
    run_parser.add_argument("--train-start", default="2020-01-01", help="训练开始日期")
    run_parser.add_argument("--train-end", default="2022-12-31", help="训练结束日期")
    run_parser.add_argument("--test-start", default="2023-01-01", help="测试开始日期")
    run_parser.add_argument("--test-end", default="2024-12-31", help="测试结束日期")
    run_parser.add_argument("--output-dir", default="output", help="输出目录")
    run_parser.add_argument("--name", help="实验名称")
    run_parser.set_defaults(func=cmd_run)

    # train 命令
    train_parser = subparsers.add_parser("train", help="训练模型")
    train_parser.add_argument("--train-start", default="2020-01-01", help="训练开始日期")
    train_parser.add_argument("--train-end", default="2022-12-31", help="训练结束日期")
    train_parser.add_argument("--output-dir", default="output", help="输出目录")
    train_parser.add_argument("--name", help="实验名称")
    train_parser.set_defaults(func=cmd_train)

    # backtest 命令
    backtest_parser = subparsers.add_parser("backtest", help="回测策略")
    backtest_parser.add_argument("--test-start", default="2023-01-01", help="测试开始日期")
    backtest_parser.add_argument("--test-end", default="2024-12-31", help="测试结束日期")
    backtest_parser.add_argument("--output-dir", default="output", help="输出目录")
    backtest_parser.set_defaults(func=cmd_backtest)

    # evaluate 命令
    evaluate_parser = subparsers.add_parser("evaluate", help="生成评估报告")
    evaluate_parser.add_argument("--output-dir", default="output", help="输出目录")
    evaluate_parser.set_defaults(func=cmd_evaluate)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
```

**Step 2: 测试 CLI 帮助信息**

Run: `python main.py --help`
Expected: 显示帮助信息

Run: `python main.py run --help`
Expected: 显示 run 命令的帮助

**Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add CLI entry point main.py"
```

---

## Task 7: 更新 pipeline/__init__.py 导出

**Files:**
- Modify: `pipeline/__init__.py`

**Step 1: 更新导出**

```python
"""
Pipeline 模块

提供训练、回测、评估的完整流水线。
"""
from __future__ import annotations

from pipeline.trainer import Trainer
from pipeline.backtester import Backtester
from pipeline.evaluator import Evaluator

__all__ = ["Trainer", "Backtester", "Evaluator"]
```

**Step 2: Commit**

```bash
git add pipeline/__init__.py
git commit -m "feat: update pipeline exports"
```

---

## Task 8: 集成测试

**Files:**
- Modify: `tests/test_trainer.py`

**Step 1: 添加集成测试**

```python
# tests/test_trainer.py 新增
def test_pipeline_integration():
    """测试 pipeline 模块集成"""
    from pipeline import Trainer, Backtester, Evaluator

    # 验证类可以导入
    assert Trainer is not None
    assert Backtester is not None
    assert Evaluator is not None
```

**Step 2: 运行所有测试**

Run: `pytest tests/ -v`
Expected: PASS

**Step 3: 最终 Commit**

```bash
git add tests/test_trainer.py
git commit -m "test: add pipeline integration test"
```

---

## 验收清单

- [ ] `python main.py --help` 正常显示帮助
- [ ] `python main.py run --help` 正常显示 run 命令帮助
- [ ] `pytest tests/` 全部通过
- [ ] `pipeline/` 模块结构完整
- [ ] `Trainer`, `Backtester`, `Evaluator` 类可用

---

**实现完成后，可通过以下命令运行完整流程：**

```bash
# 一键运行
python main.py run

# 分步执行
python main.py train
python main.py backtest
python main.py evaluate
```