"""
从 data/exports 合并数据生成 Qlib binary 格式

用法: uv run python scripts/merge_exports_to_qlib.py
"""
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

EXPORTS_DIR = Path("data/exports")
QLIB_BIN_DIR = Path("data/qlib_bin_full")
QLIB_CSV_DIR = Path("data/qlib_output/ohlcv_full")

OHLCV_FIELDS = ["open", "high", "low", "close", "volume", "amount", "factor"]
EXTRA_FIELDS = ["pe_ttm", "pb_mrq", "ps_ttm", "pcf_ttm_oper", "tot_mv", "a_mv", "turnrate"]


def normalize_symbol(s: str) -> str:
    """SHSE.600006 -> SH600006"""
    s = s.upper()
    if s.startswith("SHSE."):
        return "SH" + s[5:]
    elif s.startswith("SZSE."):
        return "SZ" + s[5:]
    return s


def load_symbol_data(sym_file: str) -> tuple[str, pd.DataFrame] | None:
    """加载单只股票的所有数据并合并"""
    try:
        sym = Path(sym_file).stem  # SHSE.600006
        qlib_sym = normalize_symbol(sym)

        # history_1d CSV (完整 OHLCV)
        history_path = EXPORTS_DIR / "history_1d" / f"{sym}.csv"
        if not history_path.exists():
            return None
        history = pd.read_csv(history_path)
        history["date"] = pd.to_datetime(history["bob"]).dt.strftime("%Y-%m-%d")

        # adj_factor CSV
        adj_path = EXPORTS_DIR / "adj_factor" / f"{sym}.csv"
        if adj_path.exists():
            adj = pd.read_csv(adj_path, encoding="gbk")
            adj["date"] = pd.to_datetime(adj["trade_date"]).dt.strftime("%Y-%m-%d")
            history = history.merge(adj[["date", "adj_factor_fwd"]], on="date", how="left")
            history["factor"] = history.get("adj_factor_fwd", 1.0).fillna(1.0)
        else:
            history["factor"] = 1.0

        # valuation (可能只有最近数据)
        val_path = EXPORTS_DIR / "valuation" / f"{sym}.csv"
        if val_path.exists():
            val = pd.read_csv(val_path, encoding="gbk")
            val["date"] = pd.to_datetime(val["trade_date"]).dt.strftime("%Y-%m-%d")
            history = history.merge(val[["date", "pe_ttm", "pb_mrq", "ps_ttm", "pcf_ttm_oper"]], on="date", how="left")

        # mktvalue
        mv_path = EXPORTS_DIR / "mktvalue" / f"{sym}.csv"
        if mv_path.exists():
            mv = pd.read_csv(mv_path, encoding="gbk")
            mv["date"] = pd.to_datetime(mv["trade_date"]).dt.strftime("%Y-%m-%d")
            history = history.merge(mv[["date", "tot_mv", "a_mv"]], on="date", how="left")

        # basic (turnrate)
        basic_path = EXPORTS_DIR / "basic" / f"{sym}.csv"
        if basic_path.exists():
            basic = pd.read_csv(basic_path, encoding="gbk")
            basic["date"] = pd.to_datetime(basic["trade_date"]).dt.strftime("%Y-%m-%d")
            history = history.merge(basic[["date", "turnrate"]], on="date", how="left")

        # 选择最终列
        final_cols = ["date"] + OHLCV_FIELDS + EXTRA_FIELDS
        available_cols = [c for c in final_cols if c in history.columns]
        result = history[available_cols].copy()
        result = result.drop_duplicates(subset=["date"]).sort_values("date")

        return qlib_sym, result
    except Exception as e:
        logging.warning(f"Error loading {sym_file}: {e}")
        return None


def main():
    # 获取所有股票文件
    history_dir = EXPORTS_DIR / "history_1d"
    csv_files = [f for f in history_dir.glob("*.csv") if not f.stem.endswith("000852")]  # 排除指数
    logging.info(f"Found {len(csv_files)} stock CSV files")

    # 并行加载
    all_data = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(load_symbol_data, str(f)) for f in csv_files]
        for i, future in enumerate(as_completed(futures)):
            if i % 200 == 0:
                logging.info(f"Loaded {i}/{len(futures)}...")
            result = future.result()
            if result:
                qlib_sym, df = result
                all_data[qlib_sym] = df

    logging.info(f"Successfully loaded {len(all_data)} symbols")

    # 构建全局日历
    all_dates = sorted(set(d for df in all_data.values() for d in df["date"]))
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
    inst_file = instruments_dir / "csi1000.txt"
    with open(inst_file, "w") as f:
        for qlib_sym, df in sorted(all_data.items()):
            f.write(f"{qlib_sym}\t{df['date'].min()}\t{df['date'].max()}\n")

    # 写每个股票的 binary 和 CSV
    logging.info("Writing Qlib binary files...")
    for i, (qlib_sym, df) in enumerate(sorted(all_data.items())):
        if i % 200 == 0:
            logging.info(f"  [{i}/{len(all_data)}] {qlib_sym}")

        sym_dir = features_dir / qlib_sym.lower()
        sym_dir.mkdir(parents=True, exist_ok=True)

        # CSV - 包含 OHLCV + 财务字段
        csv_cols = ["date"] + OHLCV_FIELDS + EXTRA_FIELDS
        csv_df = df[[c for c in csv_cols if c in df.columns]].copy()
        csv_df.to_csv(QLIB_CSV_DIR / f"{qlib_sym}.csv", index=False)

        # Binary - OHLCV + factor + 财务字段
        binary_fields = OHLCV_FIELDS + EXTRA_FIELDS
        for field in binary_fields:
            if field not in df.columns:
                continue
            values = df.set_index("date")[field].reindex(all_dates)
            first_valid = values.first_valid_index()
            if first_valid is None:
                continue
            start_pos = date_to_idx[first_valid]
            data = values.loc[first_valid:].values.astype(np.float32)

            bin_path = sym_dir / f"{field.lower()}.day.bin"
            binary = np.hstack([[start_pos], data]).astype("<f")
            binary.tofile(bin_path)

    logging.info(f"Done! Binary: {QLIB_BIN_DIR}, CSV: {QLIB_CSV_DIR}")


if __name__ == "__main__":
    main()