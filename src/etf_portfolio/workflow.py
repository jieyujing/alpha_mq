"""
下载流程模板方法 - 稳定的骨架，可覆盖的步骤。
"""
from typing import Protocol, List, Callable, Optional, Any
import logging
import os
import pandas as pd


class DataSource(Protocol):
    """数据源协议 (引用 data_source.py 中的定义)"""
    fetch_history: Callable[..., pd.DataFrame]
    fetch_valuation: Callable[..., pd.DataFrame]
    fetch_basic: Callable[..., pd.DataFrame]


class DownloadWorkflow:
    """
    下载流程模板方法基类。

    稳定的骨架流程:
    1. setup() - 初始化
    2. get_target_pool() - 获取标的池
    3. for category in get_categories(): download_category()
    4. cleanup() - 清理

    可覆盖的步骤:
    - get_categories(): 返回要下载的数据类型列表
    - get_category_fetcher(category): 返回该类型的获取函数
    - get_category_fields(category): 返回该类型的字段定义
    """

    def __init__(
        self,
        source: DataSource,
        output_dir: str = "data/exports",
        limiter: Optional[Any] = None
    ):
        self.source = source
        self.output_dir = output_dir
        self.limiter = limiter
        self._setup_complete = False

    def setup(self) -> None:
        """初始化 - 创建输出目录等"""
        os.makedirs(self.output_dir, exist_ok=True)
        self._setup_complete = True
        logging.info(f"Workflow setup complete. Output dir: {self.output_dir}")

    def cleanup(self) -> None:
        """清理 - 可用于关闭连接等"""
        logging.info("Workflow cleanup complete.")

    def get_categories(self) -> List[str]:
        """返回要下载的数据类型列表。子类可覆盖。"""
        return []

    def get_category_fetcher(self, category: str) -> Optional[Callable]:
        """返回指定类型的获取函数。子类可覆盖。"""
        return None

    def get_category_fields(self, category: str) -> Optional[str]:
        """返回指定类型的字段定义。子类可覆盖。"""
        return None

    def get_target_pool(self, symbols: Optional[List[str]] = None) -> List[str]:
        """获取标的池 - 子类可覆盖"""
        return symbols or []

    def run(
        self,
        symbols: Optional[List[str]] = None,
        start_date: str = "2020-01-01",
        end_date: str = "2024-12-31"
    ) -> None:
        """执行下载流程 - 模板方法骨架 (不应被覆盖)"""
        self.setup()
        pool = self.get_target_pool(symbols)

        for category in self.get_categories():
            logging.info(f"Downloading {category}...")
            fetcher = self.get_category_fetcher(category)
            if fetcher is None:
                logging.warning(f"No fetcher for {category}, skipping.")
                continue

            self._download_category(pool, category, fetcher, start_date, end_date)

        self.cleanup()

    def _download_category(
        self,
        pool: List[str],
        category: str,
        fetcher: Callable,
        start_date: str,
        end_date: str
    ) -> None:
        """具体下载逻辑 - 可覆盖实现细节"""
        category_dir = os.path.join(self.output_dir, category)
        os.makedirs(category_dir, exist_ok=True)
        fields = self.get_category_fields(category)

        for symbol in pool:
            try:
                df = fetcher(
                    symbol=symbol,
                    start_time=start_date,
                    end_time=end_date,
                    fields=fields
                )
                if df is not None and not df.empty:
                    save_path = os.path.join(category_dir, f"{symbol}.parquet")
                    df.to_parquet(save_path, index=False)
            except Exception as e:
                logging.error(f"Failed to download {category} for {symbol}: {e}")


class HistoryWorkflow(DownloadWorkflow):
    """历史行情下载流程"""

    def get_categories(self) -> List[str]:
        return ["history_1d"]

    def get_category_fetcher(self, category: str) -> Optional[Callable]:
        if category == "history_1d":
            return self.source.fetch_history
        return None

    def get_category_fields(self, category: str) -> Optional[str]:
        if category == "history_1d":
            return "symbol,bob,open,high,low,close,volume,amount"
        return None


class ValuationWorkflow(DownloadWorkflow):
    """估值数据下载流程"""

    def get_categories(self) -> List[str]:
        return ["valuation"]

    def get_category_fetcher(self, category: str) -> Optional[Callable]:
        if category == "valuation":
            return self.source.fetch_valuation
        return None

    def get_category_fields(self, category: str) -> Optional[str]:
        if category == "valuation":
            return "pe_ttm,pb_mrq,ps_ttm,pcf_ttm_oper"
        return None