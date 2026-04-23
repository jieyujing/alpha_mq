# tests/pipelines/factor/test_factor_report.py
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from pipelines.factor.factor_report import FactorQualityReporter


def make_sample_data(n=200, n_features=10):
    dates = pd.date_range("2020-01-01", periods=n // 2, freq="B")
    symbols = ["SH600000", "SZ000001"]
    index = pd.MultiIndex.from_product([dates, symbols],
                                        names=["datetime", "instrument"])
    X = pd.DataFrame({
        f"f{j}": np.random.randn(len(index)) for j in range(n_features)
    }, index=index)
    y = pd.Series(np.random.randn(len(index)), index=index)
    return X, y


@pytest.fixture
def report_data():
    X_before, y = make_sample_data(n_features=10)
    X_after = X_before.iloc[:len(X_before)//2]  # simulate filter kept 50%
    y = y.loc[X_after.index]
    artifacts = {
        "DropHighMissingFeatureStep.missing_ratio": pd.Series(
            np.random.uniform(0, 0.5, 10), index=[f"f{j}" for j in range(10)]
        ),
        "FactorQualityFilterStep.factor_stats": pd.DataFrame({
            "ic_mean": np.random.uniform(-0.1, 0.1, len(X_after.columns)),
            "icir": np.random.uniform(-2, 2, len(X_after.columns)),
            "monotonicity": np.random.uniform(-0.3, 0.3, len(X_after.columns)),
            "sign_flip_ratio": np.random.uniform(0.1, 0.8, len(X_after.columns)),
        }, index=X_after.columns),
    }
    logs = [
        "[DropMissingLabelStep] rows: 400 -> 400",
        "[DropHighMissingFeatureStep] features: 20 -> 10",
        "[FactorQualityFilterStep] features: 10 -> 10",
    ]
    all_labels = {
        "label_1d": y,
        "label_5d": y,
        "label_10d": y,
        "label_20d": y,
    }
    return X_before, X_after, y, artifacts, logs, all_labels


def test_generate_report_creates_file(tmp_path, report_data):
    """Report should generate a valid Markdown file."""
    X_before, X_after, y, artifacts, logs, all_labels = report_data
    output_path = str(tmp_path / "factor_report.md")

    reporter = FactorQualityReporter(output_path=output_path)
    path = reporter.generate(
        X_before=X_before, X_after=X_after, y=y,
        filter_artifacts=artifacts, filter_logs=logs,
        all_labels=all_labels,
    )

    assert Path(output_path).exists()
    content = Path(output_path).read_text()
    assert "# Factor Quality Report" in content
    assert "IC" in content
