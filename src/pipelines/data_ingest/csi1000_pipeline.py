"""
GM → Parquet 数据接入管道

实现 CSI 1000 指数成分股数据从 GM 格式到 Parquet 宽表的完整转换流程。
"""
import yaml
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from pipelines.base import DataPipeline
from pipelines.data_ingest.parquet_ingestor import ParquetIngestor


class CSI1000DataPipeline(DataPipeline):
    """
    CSI 1000 指数成分股 Parquet 数据管道

    Stages:
    - download: 从 GM API 增量下载数据 (可选，需 GM token)
    - validate: 验证数据完整性
    - clean: 转换数据格式 (OHLCV + Features + PIT)
    - ingest: 合并所有数据为 Parquet 宽表
    """

    STAGE_METHOD_MAP = {
        "download": "download",
        "validate": "validate",
        "clean": "clean",
        "ingest": "ingest_parquet",
    }

    def __init__(self, config: dict):
        super().__init__(config)
        self.exports_base = Path(config.get("exports_base", "data/exports"))
        self.parquet_output = Path(config.get("parquet_output", "data/parquet"))

        # 子目录配置
        self.ohlcv_input = self.exports_base / "history_1d"
        self.adj_factor_dir = self.exports_base / "adj_factor"

    def setup(self):
        """创建必要的输出目录"""
        self.parquet_output.mkdir(parents=True, exist_ok=True)
        logging.info(f"Pipeline setup complete. Output: {self.parquet_output}")

    def download(self):
        """
        从 GM API 增量下载数据
        """
        import sys
        from pathlib import Path

        # 确保 src 目录在 sys.path 中
        src_path = Path(__file__).parent.parent.parent
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from data_download import CSI1000Downloader

        # 获取 GM token (优先从环境变量)
        token = self.config.get("token")
        if not token:
            import os
            token = os.environ.get("GM_TOKEN")

        if not token:
            logging.warning("download stage requires GM token. Set token in config or GM_TOKEN env var.")
            return

        # 构建下载配置
        end_date = self.config.get("end_date") or datetime.now().strftime("%Y-%m-%d")
        download_config = {
            "token": token,
            "index_code": self.config.get("index_code", "SHSE.000852"),
            "exports_base": str(self.exports_base),
            "start_date": self.config.get("start_date", "2020-01-01"),
            "end_date": end_date,
        }

        logging.info(f"Starting incremental download for {download_config['index_code']}...")
        downloader = CSI1000Downloader(download_config)
        downloader.run()
        logging.info("Download stage completed")

    def validate(self) -> List[str]:
        """验证数据完整性"""
        errors = []

        if not self.ohlcv_input.exists():
            errors.append(f"Missing OHLCV input: {self.ohlcv_input}")
        else:
            all_files = list(self.ohlcv_input.glob("*.csv")) + list(self.ohlcv_input.glob("*.parquet"))
            if len(all_files) == 0:
                errors.append("No OHLCV CSV or Parquet files found")

        fund_dirs = ["fundamentals_balance", "fundamentals_income", "fundamentals_cashflow"]
        for fd in fund_dirs:
            fund_path = self.exports_base / fd
            if not fund_path.exists():
                errors.append(f"Missing fundamentals: {fund_path}")

        if errors:
            logging.warning(f"Validation found {len(errors)} issues")
        else:
            logging.info("Validation passed")

        return errors

    def clean(self):
        """数据清理占位 (exports 数据已经是 CSV 格式，无需额外转换)"""
        logging.info("Clean stage: data already in CSV format, nothing to transform")

    def ingest_parquet(self):
        """将 exports 数据合并为 Parquet 宽表"""
        ingestor = ParquetIngestor(
            str(self.exports_base),
            str(self.parquet_output),
        )
        ingestor.setup()

        # 获取所有需要处理的标的
        csv_files = list(self.ohlcv_input.glob("*.csv")) + list(self.ohlcv_input.glob("*.parquet"))
        symbols = set(f.stem for f in csv_files if not f.stem.endswith("000852"))  # 排除指数
        symbols = sorted(symbols)
        logging.info(f"Found {len(symbols)} stock symbols to process")

        stats = ingestor.process_all(symbols)
        logging.info(f"Ingest complete: {stats}")

    def on_success(self):
        """Pipeline 成功完成后生成质量报告"""
        import sys
        from pathlib import Path

        src_path = Path(__file__).parent.parent.parent
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        try:
            from pipelines.data_quality import QualityReporter
            reporter = QualityReporter(self.config)
            report_path = reporter.save_report()
            logging.info(f"Pipeline completed. Quality report: {report_path}")
        except Exception as e:
            logging.warning(f"Quality report failed: {e}")
        logging.info("Pipeline completed successfully.")
