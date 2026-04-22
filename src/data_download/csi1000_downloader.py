"""
CSI 1000 指数数据下载器

实现中证 1000 成分股数据的增量下载。
"""
import logging
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from tqdm import tqdm

from data_download.base import GMDownloader
from data_download.incremental import check_time_coverage, check_symbol_coverage
from data_download.gm_api import RateLimiter


class CSI1000Downloader(GMDownloader):
    """
    CSI 1000 指数数据下载器

    支持增量下载：
    - 时间范围补全：只下载缺失时间段
    - 标的补全：只下载新增成分股
    """

    # 数据类别配置
    CATEGORIES = {
        "history_1d": {
            "func_name": "history",
            "format": "parquet",
            "time_col": "bob",
            "fields": None,
            "frequency": "1d",
        },
        "valuation": {
            "func_name": "stk_get_daily_valuation",
            "format": "csv",
            "time_col": "bob",
            "fields": "pe_ttm,pb_mrq,ps_ttm,pcf_ttm_oper",
        },
        "mktvalue": {
            "func_name": "stk_get_daily_mktvalue",
            "format": "csv",
            "time_col": "bob",
            "fields": "tot_mv,a_mv",
        },
        "basic": {
            "func_name": "stk_get_daily_basic",
            "format": "csv",
            "time_col": "bob",
            "fields": "tclose,turnrate,ttl_shr,circ_shr,is_st,is_suspended",
        },
    }

    def __init__(self, config: Dict):
        super().__init__(config)
        self.index_code = config.get("index_code", "SHSE.000852")
        self.start_date = config.get("start_date", "2020-01-01")
        self.end_date = config.get("end_date", datetime.now().strftime("%Y-%m-%d"))
        self.token = config.get("token")

        # 初始化 GM SDK
        if self.token:
            from gm.api import set_token
            set_token(self.token)

        self.limiter = RateLimiter(max_req=950)
        self._constituents = None

    def get_target_pool(self) -> List[str]:
        """获取 CSI 1000 成分股"""
        if self._constituents is None:
            from gm.api import stk_get_index_constituents
            logging.info(f"Fetching {self.index_code} constituents...")
            self._constituents = stk_get_index_constituents(index=self.index_code)

        if self._constituents is None or self._constituents.empty:
            logging.error("Failed to get constituents")
            return []

        symbols = self._constituents['symbol'].tolist()
        # 加入指数自身
        return symbols + [self.index_code]

    def get_categories(self) -> Dict:
        """返回数据类别配置"""
        return self.CATEGORIES

    def _get_fetch_func(self, func_name: str):
        """获取 GM API 函数"""
        from gm import api as gm_api
        return getattr(gm_api, func_name, None)

    def download_category_incremental(self, category: str, cat_config: Dict):
        """执行单个类别的增量下载"""
        target_pool = self.get_target_pool()
        cat_dir = self.exports_base / category
        file_format = cat_config.get("format", "csv")
        time_col = cat_config.get("time_col", "bob")

        # 1. 检查标的覆盖
        symbol_gap = check_symbol_coverage(cat_dir, target_pool, file_format)

        logging.info(f"{category}: {len(symbol_gap.existing)} existing, {len(symbol_gap.missing)} missing")

        # 2. 确定需要下载的标的和时间范围
        end_dt = datetime.strptime(self.end_date, "%Y-%m-%d")

        download_tasks = []

        # 缺失标的：从配置起点开始下载
        for symbol in symbol_gap.missing:
            download_tasks.append((symbol, self.start_date, self.end_date))

        # 已有标的：检查时间缺口
        for symbol in symbol_gap.existing:
            file_path = cat_dir / f"{symbol}.{file_format}"
            coverage = check_time_coverage(file_path, end_dt, time_col)

            if not coverage.covered and coverage.gap_start:
                gap_start_str = coverage.gap_start.strftime("%Y-%m-%d")
                download_tasks.append((symbol, gap_start_str, self.end_date))

        if not download_tasks:
            logging.info(f"{category}: all data covered, skipping")
            return

        # 3. 执行下载
        fetch_func = self._get_fetch_func(cat_config["func_name"])
        if fetch_func is None:
            logging.error(f"GM API function not found: {cat_config['func_name']}")
            return

        logging.info(f"{category}: downloading {len(download_tasks)} tasks")

        for symbol, start, end in tqdm(download_tasks, desc=f"Downloading {category}"):
            self._download_single(symbol, start, end, cat_dir, cat_config, fetch_func)

    def _download_single(self, symbol: str, start_date: str, end_date: str,
                         cat_dir: Path, cat_config: Dict, fetch_func):
        """下载单个标的"""
        file_format = cat_config.get("format", "csv")
        file_path = cat_dir / f"{symbol}.{file_format}"

        try:
            self.limiter.wait()

            kwargs = {"symbol": symbol, "df": True}

            if cat_config["func_name"] == "history":
                kwargs.update({
                    "start_time": f"{start_date} 09:00:00",
                    "end_time": f"{end_date} 16:00:00",
                    "frequency": cat_config.get("frequency", "1d"),
                })
            else:
                kwargs.update({
                    "start_date": start_date,
                    "end_date": end_date,
                })

            if cat_config.get("fields"):
                kwargs["fields"] = cat_config["fields"]

            df = fetch_func(**kwargs)

            if df is None or df.empty:
                return

            # 处理时区
            df = self._clean_tz(df)

            # 合并已有数据
            if file_path.exists():
                if file_format == "parquet":
                    old_df = pd.read_parquet(file_path)
                else:
                    old_df = pd.read_csv(file_path)

                merge_col = cat_config.get("time_col", "bob")
                df = pd.concat([old_df, df]).drop_duplicates(subset=["symbol", merge_col])

            # 保存
            if file_format == "parquet":
                df.to_parquet(file_path, index=False)
            else:
                df.to_csv(file_path, index=False)

            logging.debug(f"Saved {symbol} to {file_path}")

        except Exception as e:
            logging.warning(f"Failed to download {symbol}: {e}")

    def _clean_tz(self, df: pd.DataFrame) -> pd.DataFrame:
        """移除时区信息"""
        if df is None:
            return pd.DataFrame()
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                if getattr(df[col].dt, 'tz', None) is not None:
                    df[col] = df[col].dt.tz_localize(None)
        return df

    def run(self):
        """执行完整下载流程"""
        self.setup()

        for category, cat_config in self.get_categories().items():
            logging.info(f"Processing category: {category}")
            self.download_category_incremental(category, cat_config)

        logging.info("Download completed")