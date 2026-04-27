"""
GM → Qlib 数据接入管道

实现 CSI 1000 指数成分股数据从 GM 格式到 Qlib 格式的完整转换流程。
"""
import yaml
import logging
from pathlib import Path
from typing import List, Optional

from pipelines.base import DataPipeline
from pipelines.data_ingest.qlib_converter import (
    OhlcvConverter,
    FeatureConverter,
    PitConverter,
    QlibIngestor
)


class CSI1000QlibPipeline(DataPipeline):
    """
    CSI 1000 指数成分股 Qlib 数据管道

    Stages:
    - download: 从 GM API 下载数据 (可选，需 GM token)
    - validate: 验证数据完整性
    - clean: 转换数据格式 (OHLCV + Features + PIT)
    - ingest: 调用 Qlib dump_bin/dump_pit 入库
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.exports_base = Path(config.get("exports_base", "data/exports"))
        self.qlib_output = Path(config.get("qlib_output", "data/qlib_output"))
        self.qlib_bin = Path(config.get("qlib_bin", "data/qlib_bin"))

        # 子目录配置
        self.ohlcv_input = self.exports_base / "history_1d"
        self.ohlcv_output = self.qlib_output / "ohlcv"
        self.pit_output = self.qlib_output / "pit"
        self.adj_factor_dir = self.exports_base / "adj_factor"

        # 初始化转换器
        self._ohlcv_converter = None
        self._feature_converter = None
        self._pit_converter = None
        self._ingestor = None

    def setup(self):
        """创建必要的输出目录"""
        self.ohlcv_output.mkdir(parents=True, exist_ok=True)
        self.pit_output.mkdir(parents=True, exist_ok=True)
        self.qlib_bin.mkdir(parents=True, exist_ok=True)
        logging.info(f"Pipeline setup complete. Output: {self.qlib_output}")

    def download(self):
        """
        从 GM API 增量下载数据

        调用 CSI1000Downloader 执行增量下载：
        - 检查已有数据的时间覆盖
        - 只下载缺失时间段
        - 检查成分股变动，只下载新增标的
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
        download_config = {
            "token": token,
            "index_code": self.config.get("index_code", "SHSE.000852"),
            "exports_base": str(self.exports_base),
            "start_date": self.config.get("start_date", "2020-01-01"),
            "end_date": self.config.get("end_date"),
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
            parquet_count = len(list(self.ohlcv_input.glob("*.parquet")))
            if parquet_count == 0:
                errors.append("No OHLCV parquet files found")

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
        """执行数据转换 (OHLCV + Features + PIT)"""
        logging.info("Converting OHLCV data...")
        self._ohlcv_converter = OhlcvConverter(
            str(self.ohlcv_input),
            str(self.ohlcv_output),
            str(self.adj_factor_dir) if self.adj_factor_dir.exists() else None
        )
        converted_symbols = self._ohlcv_converter.convert_all()
        logging.info(f"Converted {len(converted_symbols)} OHLCV symbols")

        logging.info("Merging feature data...")
        self._feature_converter = FeatureConverter(
            str(self.exports_base),
            str(self.ohlcv_output)
        )
        for gm_symbol in converted_symbols:
            self._feature_converter.merge_features_for_symbol(gm_symbol)

        logging.info("Converting PIT data...")
        self._pit_converter = PitConverter(
            str(self.exports_base),
            str(self.pit_output)
        )
        pit_results = self._pit_converter.convert_all()
        logging.info(f"Converted PIT data for {len(pit_results)} symbols")

    def ingest_to_qlib(self):
        """调用 Qlib dump_bin/dump_pit 入库"""
        self._ingestor = QlibIngestor(str(self.qlib_bin))

        logging.info("Running Qlib dump_bin...")
        success = self._ingestor.dump_bin(str(self.ohlcv_output))
        if success:
            logging.info("dump_bin completed successfully")
        else:
            logging.error("dump_bin failed")

        logging.info("Running Qlib dump_pit...")
        success = self._ingestor.dump_pit(str(self.pit_output))
        if success:
            logging.info("dump_pit completed successfully")
        else:
            logging.error("dump_pit failed")

    def on_success(self):
        """Pipeline 成功完成后生成质量报告"""
        import sys
        from pathlib import Path

        # 确保 src 目录在 sys.path 中
        src_path = Path(__file__).parent.parent.parent
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from pipelines.data_quality import QualityReporter

        reporter = QualityReporter(self.config)
        report_path = reporter.save_report()
        logging.info(f"Pipeline completed successfully. Quality report: {report_path}")
