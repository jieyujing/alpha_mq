"""
GM 数据下载 CLI 入口

使用 src/data_download 模块执行增量下载。
"""
import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# 确保 src 目录在 sys.path 中
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from data_download import CSI1000Downloader


def main():
    parser = argparse.ArgumentParser(description="Download CSI 1000 Data from GM")
    parser.add_argument("--token", type=str, required=True, help="GM SDK Token")
    parser.add_argument("--index", type=str, default="SHSE.000852", help="Index code")
    parser.add_argument("--start", type=str, default="2020-01-01", help="Start date")
    parser.add_argument("--end", type=str, default=datetime.now().strftime("%Y-%m-%d"), help="End date")
    parser.add_argument("--exports", type=str, default="data/exports", help="Exports directory")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    config = {
        "token": args.token,
        "index_code": args.index,
        "exports_base": args.exports,
        "start_date": args.start,
        "end_date": args.end,
    }

    logging.info(f"Starting incremental download for {args.index}...")
    downloader = CSI1000Downloader(config)
    downloader.run()
    logging.info("Download completed")


if __name__ == "__main__":
    main()