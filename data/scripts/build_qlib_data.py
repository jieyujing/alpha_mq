#!/usr/bin/env python
"""Qlib数据构建脚本

将掘金(GM SDK)数据转换为Qlib二进制格式。

使用方法:
    # 转换所有数据
    python data/scripts/build_qlib_data.py

    # 仅转换指定年份
    python data/scripts/build_qlib_data.py --years 2023 2024

    # 仅转换价格数据（不含财务数据）
    python data/scripts/build_qlib_data.py --no-fundamentals
"""

import argparse
import subprocess
import sys
from pathlib import Path

import polars as pl

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from data.qlib_converter import QlibBinConverter


def build_csv_source(
    raw_dir: Path,
    csv_dir: Path,
    years: list[int] | None = None,
    include_fundamentals: bool = True,
) -> dict:
    """生成中间CSV文件

    Args:
        raw_dir: 原始数据目录
        csv_dir: CSV输出目录
        years: 指定年份
        include_fundamentals: 是否包含财务数据

    Returns:
        转换统计信息
    """
    print("=" * 60)
    print("Step 1: Building CSV source files")
    print("=" * 60)

    converter = QlibBinConverter(
        raw_dir=str(raw_dir),
        output_dir=str(csv_dir),
    )

    stats = converter.convert_all_stocks(
        years=years,
        include_fundamentals=include_fundamentals,
    )

    return stats


def build_calendar(csv_dir: Path, qlib_dir: Path) -> None:
    """构建交易日历

    从CSV文件中提取所有交易日期，生成Qlib需要的日历文件。
    """
    print("\n" + "=" * 60)
    print("Step 2: Building trading calendar")
    print("=" * 60)

    calendar_dir = qlib_dir / "calendars"
    calendar_dir.mkdir(parents=True, exist_ok=True)

    # 收集所有日期
    all_dates = set()
    for csv_file in csv_dir.glob("*.csv"):
        df = pl.read_csv(csv_file, columns=["date"])
        dates = df["date"].unique().to_list()
        all_dates.update(dates)

    # 排序并写入文件
    sorted_dates = sorted(all_dates)
    calendar_file = calendar_dir / "day.txt"

    with open(calendar_file, "w") as f:
        for date in sorted_dates:
            f.write(f"{date}\n")

    print(f"Calendar saved to {calendar_file}")
    print(f"Total trading days: {len(sorted_dates)}")


def build_instruments(csv_dir: Path, qlib_dir: Path) -> None:
    """构建股票池文件

    从CSV文件名中提取股票代码，生成instruments文件。
    """
    print("\n" + "=" * 60)
    print("Step 3: Building instruments file")
    print("=" * 60)

    instruments_dir = qlib_dir / "instruments"
    instruments_dir.mkdir(parents=True, exist_ok=True)

    # 收集所有股票代码
    symbols = []
    for csv_file in csv_dir.glob("*.csv"):
        symbol = csv_file.stem  # 文件名不含扩展名
        symbols.append(symbol)

    # 排序并写入文件
    symbols.sort()
    instruments_file = instruments_dir / "all.txt"

    with open(instruments_file, "w") as f:
        for symbol in symbols:
            f.write(f"{symbol}\n")

    print(f"Instruments saved to {instruments_file}")
    print(f"Total instruments: {len(symbols)}")


def run_dump_bin(csv_dir: Path, qlib_dir: Path) -> None:
    """调用qlib的dump_bin转换为二进制格式"""
    print("\n" + "=" * 60)
    print("Step 4: Converting to Qlib binary format")
    print("=" * 60)

    # 确保features目录存在
    features_dir = qlib_dir / "features"
    features_dir.mkdir(parents=True, exist_ok=True)

    # 构建dump_bin命令
    # 使用qlib的scripts/dump_bin.py
    try:
        import qlib
        qlib_path = Path(qlib.__file__).parent
        dump_bin_script = qlib_path / "scripts" / "dump_bin.py"

        if not dump_bin_script.exists():
            # 尝试其他路径
            dump_bin_script = qlib_path.parent / "scripts" / "dump_bin.py"

        if dump_bin_script.exists():
            cmd = [
                sys.executable,
                str(dump_bin_script),
                "dump_all",
                "--data_path", str(csv_dir),
                "--qlib_dir", str(qlib_dir),
                "--include_fields", "open,close,high,low,volume,amount,ttl_ast,ttl_eqy,pe_ttm,pb_lyr",
                "--file_suffix", ".csv",
                "--date_field_name", "date",
                "--symbol_field_name", "symbol",
            ]

            print(f"Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                print(f"Warning: dump_bin returned non-zero exit code")
                print(f"stdout: {result.stdout}")
                print(f"stderr: {result.stderr}")
            else:
                print("Binary conversion completed successfully")
        else:
            print("Warning: dump_bin.py not found, skipping binary conversion")
            print("You can manually run the conversion later using qlib.utils.dump_bin")

    except ImportError:
        print("Warning: qlib not installed, skipping binary conversion")


def main():
    parser = argparse.ArgumentParser(
        description="Build Qlib data from GM SDK Parquet files"
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw"),
        help="Raw data directory (default: data/raw)",
    )
    parser.add_argument(
        "--csv-dir",
        type=Path,
        default=Path("data/csv_source"),
        help="CSV output directory (default: data/csv_source)",
    )
    parser.add_argument(
        "--qlib-dir",
        type=Path,
        default=Path("data/qlib_data"),
        help="Qlib data output directory (default: data/qlib_data)",
    )
    parser.add_argument(
        "--years",
        type=int,
        nargs="+",
        default=None,
        help="Years to convert (default: all)",
    )
    parser.add_argument(
        "--no-fundamentals",
        action="store_true",
        help="Exclude fundamentals data",
    )
    parser.add_argument(
        "--skip-dump-bin",
        action="store_true",
        help="Skip binary conversion (only generate CSV)",
    )

    args = parser.parse_args()

    # 确保目录存在
    args.csv_dir.mkdir(parents=True, exist_ok=True)
    args.qlib_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: 生成CSV
    stats = build_csv_source(
        raw_dir=args.raw_dir,
        csv_dir=args.csv_dir,
        years=args.years,
        include_fundamentals=not args.no_fundamentals,
    )

    if stats["stocks"] == 0:
        print("No data converted, exiting...")
        return 1

    # Step 2: 构建日历
    build_calendar(csv_dir=args.csv_dir, qlib_dir=args.qlib_dir)

    # Step 3: 构建股票池
    build_instruments(csv_dir=args.csv_dir, qlib_dir=args.qlib_dir)

    # Step 4: 转换为二进制（可选）
    if not args.skip_dump_bin:
        run_dump_bin(csv_dir=args.csv_dir, qlib_dir=args.qlib_dir)

    print("\n" + "=" * 60)
    print("Data build completed!")
    print("=" * 60)
    print(f"  Stocks: {stats['stocks']}")
    print(f"  Records: {stats['records']}")
    print(f"  CSV dir: {args.csv_dir}")
    print(f"  Qlib dir: {args.qlib_dir}")

    return 0


if __name__ == "__main__":
    sys.exit(main())