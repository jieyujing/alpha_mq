"""QlibBinConverter 测试模块

测试数据转换的核心逻辑，特别是验证FFill避免未来函数的功能。
"""

import polars as pl
import pytest

from data.qlib_converter import QlibBinConverter


class TestFFillNoLookahead:
    """测试前向填充避免未来函数"""

    def test_ffill_uses_pub_date_not_rpt_date(self):
        """验证FFill使用披露日期(pub_date)而非报告期截止日(rpt_date)

        场景：
        - 1/25披露去年Q4财报（total_assets=100）
        - 4/20披露今年Q1财报（total_assets=150）
        - 验证4/19仍使用旧值100，4/20更新为新值150
        """
        # 构造价格数据：覆盖1/25到4/20
        price_df = pl.DataFrame({
            "symbol": ["SH600000"] * 5,
            "date": ["2024-01-24", "2024-01-25", "2024-04-19", "2024-04-20", "2024-04-21"],
            "close": [10.0, 10.1, 11.0, 11.5, 12.0],
        })

        # 构造财务数据：
        # - 1/25披露：total_assets=100
        # - 4/20披露：total_assets=150
        fund_df = pl.DataFrame({
            "symbol": ["SH600000", "SH600000"],
            "pub_date": ["2024-01-25", "2024-04-20"],  # 披露日期
            "total_assets": [100.0, 150.0],
        })

        # 创建转换器实例并执行合并
        converter = QlibBinConverter(raw_dir="data/raw", output_dir="data/csv_source")
        result = converter.merge_price_with_fundamentals(
            price_df, fund_df, ["total_assets"]
        )

        # 验证：1/24（披露前）应为null
        val_0124 = result.filter(pl.col("date") == pl.lit("2024-01-24").str.to_date())["total_assets"][0]
        assert val_0124 is None, f"1/24应在披露前，期望null，实际{val_0124}"

        # 验证：1/25（披露日）开始有值100
        val_0125 = result.filter(pl.col("date") == pl.lit("2024-01-25").str.to_date())["total_assets"][0]
        assert val_0125 == 100.0, f"1/25披露日应有值100，实际{val_0125}"

        # 验证：4/19仍使用旧值100（不是150！）
        val_0419 = result.filter(pl.col("date") == pl.lit("2024-04-19").str.to_date())["total_assets"][0]
        assert val_0419 == 100.0, f"4/19不应看到4/20披露的数据，期望100，实际{val_0419}"

        # 验证：4/20的数据更新为新值150
        val_0420 = result.filter(pl.col("date") == pl.lit("2024-04-20").str.to_date())["total_assets"][0]
        assert val_0420 == 150.0, f"4/20应看到新披露的数据，期望150，实际{val_0420}"

    def test_ffill_handles_multiple_stocks(self):
        """验证多股票情况下的FFill正确性

        场景：
        - SH600000: 4/20披露新数据
        - SZ000001: 4/21才披露，4/20仍为旧值
        """
        price_df = pl.DataFrame({
            "symbol": ["SH600000", "SH600000", "SZ000001", "SZ000001", "SZ000001"],
            "date": ["2024-01-25", "2024-04-20", "2024-01-25", "2024-04-20", "2024-04-21"],
            "close": [10.0, 10.5, 20.0, 20.5, 21.0],
        })

        fund_df = pl.DataFrame({
            "symbol": ["SH600000", "SH600000", "SZ000001", "SZ000001"],
            "pub_date": ["2024-01-25", "2024-04-20", "2024-01-25", "2024-04-21"],
            "total_assets": [100.0, 150.0, 200.0, 250.0],
        })

        converter = QlibBinConverter(raw_dir="data/raw", output_dir="data/csv_source")
        result = converter.merge_price_with_fundamentals(
            price_df, fund_df, ["total_assets"]
        )

        # SH600000: 4/20披露新数据
        sh_0420 = result.filter(
            (pl.col("symbol") == "SH600000") & (pl.col("date") == pl.lit("2024-04-20").str.to_date())
        )["total_assets"][0]
        assert sh_0420 == 150.0

        # SZ000001: 4/21才披露，4/20仍为旧值200
        sz_0420 = result.filter(
            (pl.col("symbol") == "SZ000001") & (pl.col("date") == pl.lit("2024-04-20").str.to_date())
        )["total_assets"][0]
        assert sz_0420 == 200.0, f"SZ000001在4/20应仍为旧值200，实际{sz_0420}"

        # SZ000001: 4/21更新为新值250
        sz_0421 = result.filter(
            (pl.col("symbol") == "SZ000001") & (pl.col("date") == pl.lit("2024-04-21").str.to_date())
        )["total_assets"][0]
        assert sz_0421 == 250.0


class TestQlibBinConverter:
    """测试QlibBinConverter类的功能"""

    def test_init(self):
        """测试初始化"""
        converter = QlibBinConverter(
            raw_dir="data/raw",
            output_dir="data/csv_source",
        )
        # Windows路径分隔符兼容
        assert converter.raw_dir.name == "raw"
        assert converter.output_dir.name == "csv_source"

    def test_preprocess_price(self):
        """测试价格数据预处理"""
        converter = QlibBinConverter(raw_dir="data/raw", output_dir="data/csv_source")

        # 构造测试数据
        raw_price = pl.DataFrame({
            "symbol": ["SHSE.600000", "SZSE.000001"],
            "open": [10.0, 20.0],
            "high": [11.0, 21.0],
            "low": [9.0, 19.0],
            "close": [10.5, 20.5],
            "volume": [1000, 2000],
            "amount": [10500, 41000],
            "bob": ["2024-04-20 00:00:00+08:00", "2024-04-20 00:00:00+08:00"],
        })

        result = converter.preprocess_price(raw_price)

        # 验证symbol标准化
        assert result["symbol"].to_list() == ["SH600000", "SZ000001"]

        # 验证日期提取
        assert result["date"].to_list() == ["2024-04-20", "2024-04-20"]

    def test_preprocess_fundamentals(self):
        """测试财务数据预处理"""
        converter = QlibBinConverter(raw_dir="data/raw", output_dir="data/csv_source")

        raw_fund = pl.DataFrame({
            "symbol": ["SHSE.600000"],
            "pub_date": ["2024-04-20"],
            "ttl_ast": [100.0],
            "ttl_eqy": [50.0],
        })

        result = converter.preprocess_fundamentals(raw_fund, ["ttl_ast", "ttl_eqy"])

        assert result["symbol"].to_list() == ["SH600000"]
        assert "ttl_ast" in result.columns
        assert "ttl_eqy" in result.columns