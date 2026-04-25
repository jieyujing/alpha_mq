"""
从 backend parquet 直接转换为 Qlib binary 格式

绕过 CSV 中间步骤，直接从 l1_basic.parquet 生成 Qlib binary。
用法: uv run python scripts/convert_backend_to_qlib.py
"""
import logging
import struct
import numpy as np
import pandas as pd
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- 路径配置 ---
BACKEND_DIR = Path("data/backend")
QLIB_BIN_DIR = Path("data/qlib_bin_full")
QLIB_CSV_DIR = Path("data/qlib_output/ohlcv_full")

OHLCV_FIELDS = ["open", "high", "low", "close", "volume", "amount", "factor"]
EXTRA_FIELDS = ["pe_ttm", "pb_mrq", "ps_ttm", "pcf_ttm_oper", "tot_mv", "a_mv", "turnrate"]


def load_backend():
    """加载 backend parquet 数据"""
    logging.info("Loading l1_basic.parquet...")
    df = pd.read_parquet(BACKEND_DIR / "l1_basic.parquet")
    logging.info(f"Loaded {len(df):,} rows, {df['symbol'].nunique()} symbols")
    return df


def normalize_symbol(s: str) -> str:
    """SHSE.600006 -> SH600006, SZSE.000001 -> SZ000001"""
    s = s.upper()
    if s.startswith("SHSE."):
        return "SH" + s[5:]
    elif s.startswith("SZSE."):
        return "SZ" + s[5:]
    return s


def convert_to_qlib_bin(df: pd.DataFrame):
    """将 backend 数据转为 Qlib binary + CSV"""
    # 标准化
    df = df.copy()
    df["qlib_symbol"] = df["symbol"].apply(normalize_symbol)
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

    # 构建全局日历
    all_dates = sorted(df["date"].unique())
    date_to_idx = {d: i for i, d in enumerate(all_dates)}
    logging.info(f"Calendar: {len(all_dates)} trading days ({all_dates[0]} ~ {all_dates[-1]})")

    # 创建目录
    calendars_dir = QLIB_BIN_DIR / "calendars"
    features_dir = QLIB_BIN_DIR / "features"
    instruments_dir = QLIB_BIN_DIR / "instruments"
    calendars_dir.mkdir(parents=True, exist_ok=True)
    features_dir.mkdir(parents=True, exist_ok=True)
    instruments_dir.mkdir(parents=True, exist_ok=True)
    QLIB_CSV_DIR.mkdir(parents=True, exist_ok=True)

    # 写日历
    cal_file = calendars_dir / "day.txt"
    cal_file.write_text("\n".join(all_dates) + "\n")

    # 写 instruments
    symbols = sorted(df["qlib_symbol"].unique())
    inst_file = instruments_dir / "csi1000.txt"
    with open(inst_file, "w") as f:
        for sym in symbols:
            sym_dates = df[df["qlib_symbol"] == sym]["date"]
            if len(sym_dates) > 0:
                f.write(f"{sym}\t{sym_dates.min()}\t{sym_dates.max()}\n")
    logging.info(f"Instruments: {len(symbols)} symbols")

    # 按 symbol 分组处理
    grouped = df.groupby("qlib_symbol")
    logging.info(f"Processing {len(grouped)} symbols...")

    for i, (qlib_sym, sdf) in enumerate(grouped):
        if i % 200 == 0:
            logging.info(f"  [{i}/{len(grouped)}] {qlib_sym}")

        sym_dir = features_dir / qlib_sym.lower()
        sym_dir.mkdir(parents=True, exist_ok=True)

        # 准备数据: 按 date 对齐到全局日历
        sdf = sdf.sort_values("date")
        sdf["factor"] = sdf.get("adj_factor", 1.0).fillna(1.0)

        # 写 CSV (供 Qlib 表达式引擎使用)
        csv_fields = ["date"] + [f for f in OHLCV_FIELDS if f != "factor"]
        csv_df = sdf[csv_fields].copy()
        csv_df.to_csv(QLIB_CSV_DIR / f"{qlib_sym}.csv", index=False)

        # 写 binary (供 Alpha158 handler 使用)
        all_fields = list(csv_fields[1:])  # exclude date

        for field in all_fields:
            if field not in sdf.columns:
                continue
            values = sdf.set_index("date")[field].reindex(all_dates)
            first_valid = values.first_valid_index()
            if first_valid is None:
                continue
            start_pos = date_to_idx[first_valid]
            data = values.loc[first_valid:].values.astype(np.float32)

            bin_path = sym_dir / f"{field.lower()}.day.bin"
            binary = np.hstack([[start_pos], data]).astype("<f")
            binary.tofile(bin_path)

    # 写 calendar 索引
    cal_bin = calendars_dir / "day.bin"
    # day.bin 不是必须的，qlib 只读 day.txt

    logging.info(f"Done! Binary: {QLIB_BIN_DIR}, CSV: {QLIB_CSV_DIR}")
    return QLIB_BIN_DIR


def main():
    df = load_backend()
    convert_to_qlib_bin(df)


if __name__ == "__main__":
    main()
