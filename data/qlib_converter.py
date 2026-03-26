"""Qlib 数据格式转换模块

将掘金(GM SDK)的Parquet格式数据转换为Qlib兼容的格式。
核心功能：
1. 合并价格数据与财务数据
2. 使用披露日期(pub_date)进行对齐，避免未来函数
3. 执行前向填充(FFill)
4. 导出为Qlib兼容的CSV格式
"""

from pathlib import Path
from typing import Optional

import polars as pl

from data.utils.date_utils import extract_date_from_datetime


class QlibBinConverter:
    """Qlib二进制格式转换器

    将掘金数据转换为Qlib格式，确保财务数据填充无"未来函数"。
    """

    # Qlib标准字段映射
    FIELD_MAPPING = {
        # 价格字段
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
        "amount": "amount",
        # 财务字段 -> Qlib标准名
        "ttl_ast": "total_assets",
        "ttl_eqy": "total_equity",
        "net_prof": "net_profit",
        # 估值字段
        "pe_ttm": "pe_ttm",
        "pb_lyr": "pb_lyr",
    }

    def __init__(self, raw_dir: str, output_dir: str):
        """初始化转换器

        Args:
            raw_dir: 原始数据目录 (data/raw)
            output_dir: 输出CSV目录 (data/csv_source)
        """
        self.raw_dir = Path(raw_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def load_price_data(self, year: Optional[int] = None) -> pl.DataFrame:
        """加载价格数据

        Args:
            year: 指定年份，None则加载所有年份

        Returns:
            合并后的价格DataFrame
        """
        price_dir = self.raw_dir / "price"
        files = sorted(price_dir.glob("price_*.parquet"))

        if year is not None:
            files = [f for f in files if str(year) in f.name]

        dfs = []
        for f in files:
            df = pl.read_parquet(f)
            dfs.append(df)

        return pl.concat(dfs) if dfs else pl.DataFrame()

    def load_fundamentals(self, table_name: str, year: Optional[int] = None) -> pl.DataFrame:
        """加载财务数据

        Args:
            table_name: 表名 (balance_sheet, trading_derivative_indicator等)
            year: 指定年份

        Returns:
            财务DataFrame
        """
        fund_dir = self.raw_dir / "fundamentals"
        files = sorted(fund_dir.glob(f"{table_name}_*.parquet"))

        if year is not None:
            files = [f for f in files if str(year) in f.name]

        dfs = []
        for f in files:
            df = pl.read_parquet(f)
            dfs.append(df)

        return pl.concat(dfs) if dfs else pl.DataFrame()

    def preprocess_price(self, df: pl.DataFrame) -> pl.DataFrame:
        """预处理价格数据

        - 提取日期（从bob字段）
        - 标准化symbol格式
        - 选择必要字段
        """
        # 从bob提取日期
        df = df.with_columns(
            pl.col("bob")
            .map_elements(extract_date_from_datetime, return_dtype=pl.String)
            .alias("date")
        )

        # 标准化symbol: SZSE.000001 -> SZ000001
        df = df.with_columns(
            pl.col("symbol")
            .str.replace("SZSE.", "SZ")
            .str.replace("SHSE.", "SH")
            .alias("symbol")
        )

        # 选择字段
        return df.select([
            "symbol", "date", "open", "high", "low", "close", "volume", "amount"
        ])

    def preprocess_fundamentals(
        self, df: pl.DataFrame, value_columns: list[str],
        date_column: str = "pub_date"
    ) -> pl.DataFrame:
        """预处理财务数据

        - 标准化symbol格式
        - 选择日期字段和数值字段

        Args:
            df: 原始财务数据
            value_columns: 需要保留的数值字段
            date_column: 日期字段名 (pub_date用于财报，trade_date用于每日数据)
        """
        df = df.with_columns(
            pl.col("symbol")
            .str.replace("SZSE.", "SZ")
            .str.replace("SHSE.", "SH")
            .alias("symbol")
        )

        # 确保日期字段是字符串格式
        if date_column in df.columns:
            df = df.with_columns(
                pl.col(date_column).cast(pl.String).alias(date_column)
            )

        cols = ["symbol", date_column] + [c for c in value_columns if c in df.columns]
        return df.select(cols)

    def merge_price_with_fundamentals(
        self,
        price_df: pl.DataFrame,
        fund_df: pl.DataFrame,
        fund_columns: list[str],
        date_column: str = "pub_date",
        use_ffill: bool = True,
    ) -> pl.DataFrame:
        """合并价格与财务数据

        核心逻辑：使用pub_date（披露日期）进行匹配，避免未来函数。

        Args:
            price_df: 预处理后的价格数据
            fund_df: 预处理后的财务数据
            fund_columns: 需要合并的财务字段
            date_column: 财务数据的日期字段 (pub_date或trade_date)
            use_ffill: 是否执行前向填充 (财报数据需要，每日数据不需要)

        Returns:
            合并后的DataFrame
        """
        # 确保日期类型 - 只有字符串才需要转换
        if price_df["date"].dtype == pl.String:
            price_df = price_df.with_columns(
                pl.col("date").str.to_date("%Y-%m-%d").alias("date")
            )
        if fund_df[date_column].dtype == pl.String:
            fund_df = fund_df.with_columns(
                pl.col(date_column).str.to_date("%Y-%m-%d").alias(date_column)
            )

        # 重命名日期字段为date用于join
        fund_for_join = fund_df.rename({date_column: "date"})

        # 左连接：在日期匹配
        merged = price_df.join(
            fund_for_join,
            on=["symbol", "date"],
            how="left",
        )

        # 按日期排序
        merged = merged.sort(["symbol", "date"])

        # 对财务字段执行ffill（按symbol分组）
        if use_ffill:
            for col in fund_columns:
                if col in merged.columns:
                    merged = merged.with_columns(
                        pl.col(col).forward_fill().over("symbol")
                    )

        return merged

    def export_to_csv(self, df: pl.DataFrame, symbol: str) -> Path:
        """导出单个股票的CSV文件

        Qlib期待的CSV格式：
        - 文件名: <symbol>.csv (如 SH600000.csv)
        - 必须包含: date, open, close, high, low, volume
        - 可选: 其他特征字段

        Args:
            df: 单只股票的数据
            symbol: 股票代码

        Returns:
            输出文件路径
        """
        output_path = self.output_dir / f"{symbol}.csv"
        df.write_csv(output_path)
        return output_path

    def convert_all_stocks(
        self,
        years: Optional[list[int]] = None,
        include_fundamentals: bool = True,
    ) -> dict[str, int]:
        """转换所有股票数据

        Args:
            years: 指定年份列表
            include_fundamentals: 是否包含财务数据

        Returns:
            转换统计信息
        """
        years = years or list(range(2015, 2027))
        stats = {"stocks": 0, "records": 0}

        # 加载所有价格数据
        print("Loading price data...")
        price_dfs = []
        for year in years:
            try:
                df = self.load_price_data(year)
                if len(df) > 0:
                    price_dfs.append(df)
            except Exception as e:
                print(f"Warning: Failed to load price data for {year}: {e}")

        if not price_dfs:
            print("No price data found!")
            return stats

        all_price = pl.concat(price_dfs)
        all_price = self.preprocess_price(all_price)

        # 加载财务数据（如果需要）
        fund_data = {}
        if include_fundamentals:
            print("Loading fundamentals data...")

            # 资产负债表
            balance_dfs = []
            for year in years:
                try:
                    df = self.load_fundamentals("balance_sheet", year)
                    if len(df) > 0:
                        balance_dfs.append(df)
                except Exception:
                    pass
            if balance_dfs:
                fund_data["balance"] = pl.concat(balance_dfs)

            # 估值指标
            tdi_dfs = []
            for year in years:
                try:
                    df = self.load_fundamentals("trading_derivative_indicator", year)
                    if len(df) > 0:
                        tdi_dfs.append(df)
                except Exception:
                    pass
            if tdi_dfs:
                fund_data["tdi"] = pl.concat(tdi_dfs)

        # 按股票分组处理
        print("Processing stocks...")
        symbols = all_price["symbol"].unique().to_list()

        for symbol in symbols:
            stock_price = all_price.filter(pl.col("symbol") == symbol)

            # 合并财务数据
            merged = stock_price

            # 资产负债表：使用pub_date，需要FFill
            if "balance" in fund_data:
                # 提取原始代码部分进行匹配 (SH600000 -> 600000)
                orig_code = symbol[2:]  # 去掉SH/SZ前缀
                balance = fund_data["balance"].filter(
                    pl.col("symbol").str.ends_with(orig_code) |
                    pl.col("symbol").str.contains(f"\\.{orig_code}")
                )
                if len(balance) > 0:
                    balance = self.preprocess_fundamentals(balance, ["ttl_ast", "ttl_eqy"], "pub_date")
                    merged = self.merge_price_with_fundamentals(
                        merged, balance, ["ttl_ast", "ttl_eqy"],
                        date_column="pub_date", use_ffill=True
                    )

            # 估值指标：使用trade_date，每日数据不需要FFill
            if "tdi" in fund_data:
                orig_code = symbol[2:]
                tdi = fund_data["tdi"].filter(
                    pl.col("symbol").str.ends_with(orig_code) |
                    pl.col("symbol").str.contains(f"\\.{orig_code}")
                )
                if len(tdi) > 0:
                    tdi = self.preprocess_fundamentals(tdi, ["pe_ttm", "pb_lyr"], "trade_date")
                    merged = self.merge_price_with_fundamentals(
                        merged, tdi, ["pe_ttm", "pb_lyr"],
                        date_column="trade_date", use_ffill=False
                    )

            # 导出CSV
            self.export_to_csv(merged, symbol)
            stats["stocks"] += 1
            stats["records"] += len(merged)

        print(f"Converted {stats['stocks']} stocks, {stats['records']} records")
        return stats