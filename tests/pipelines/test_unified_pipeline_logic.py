import pytest
import polars as pl
from datetime import date
from src.pipelines.data_ingest.unified_pipeline import UnifiedDataPipeline

def test_asof_join_lookahead_prevention():
    # Mock daily spine
    spine = pl.DataFrame({
        "symbol": ["SHSE.600000"] * 5,
        "date": [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4), date(2023, 1, 5)],
        "close": [10.0, 10.1, 10.2, 10.3, 10.4]
    }).lazy()

    # Mock fundamentals: published on 2023-01-03
    fund = pl.DataFrame({
        "symbol": ["SHSE.600000"],
        "pub_date": [date(2023, 1, 3)],
        "net_profit": [1000.0]
    }).lazy()

    # Perform asof join (mimic align logic)
    result = spine.join_asof(
        fund,
        left_on="date",
        right_on="pub_date",
        by="symbol",
        strategy="backward"
    ).collect()

    # Check: net_profit should be null before 2023-01-03
    assert result.filter(pl.col("date") < date(2023, 1, 3))["net_profit"].null_count() == 2
    # Check: net_profit should be 1000.0 from 2023-01-03 onwards
    assert result.filter(pl.col("date") >= date(2023, 1, 3))["net_profit"].to_list() == [1000.0, 1000.0, 1000.0]
