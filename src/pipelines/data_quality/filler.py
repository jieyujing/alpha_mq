"""
数据填充模块

处理低频数据（如财务数据）向后填充。
"""
import logging
from typing import List, Optional
import pandas as pd
import numpy as np


FINANCIAL_FIELDS = [
    "pe_ttm",
    "pb_mrq",
    "ps_ttm",
    "pcf_ttm_oper",
]


def fill_financial_data(
    df: pd.DataFrame,
    fill_fields: Optional[List[str]] = None,
    max_fill_days: int = 90,
    group_by: List[str] = ["instrument"],
) -> pd.DataFrame:
    """
    对财务等低频数据向后填充。

    财务数据通常按季度更新，在未发布新数据的日期需要向后填充旧值。

    Args:
        df: DataFrame，需有 datetime 和 instrument 索引级别
        fill_fields: 需填充的字段列表，默认为 FINANCIAL_FIELDS
        max_fill_days: 最大填充天数，防止过老数据被使用
        group_by: 分组字段，默认按 instrument

    Returns:
        填充后的 DataFrame
    """
    if fill_fields is None:
        fill_fields = [f for f in FINANCIAL_FIELDS if f in df.columns]

    if not fill_fields:
        logging.info("No financial fields found to fill")
        return df

    df_filled = df.copy()

    # 确保 datetime 在索引中
    if "datetime" not in df_filled.index.names:
        logging.warning("datetime not in index, cannot fill")
        return df

    # 按股票分组填充
    # 多级索引: 先 reset_index 再 groupby
    reset_df = df_filled.reset_index()

    for field in fill_fields:
        if field not in reset_df.columns:
            continue

        original_missing = reset_df[field].isna().sum()

        # 按 instrument 分组，对每个股票向后填充
        # 使用 ffill (forward fill)，即把过去的值填充到未来
        reset_df[field] = reset_df.groupby("instrument")[field].ffill(limit=max_fill_days)

        filled_count = original_missing - reset_df[field].isna().sum()
        logging.info(f"Field '{field}' filled {filled_count} values (max {max_fill_days} days)")

    # 恢复多级索引
    df_filled = reset_df.set_index(df_filled.index.names)

    return df_filled


def check_data_quality_summary(df: pd.DataFrame) -> dict:
    """
    生成数据质量摘要报告。

    Returns:
        dict: {
            total_rows: int,
            total_features: int,
            missing_pct: dict,
            inf_count: dict,
            financial_coverage: dict,
        }
    """
    total_rows = len(df)
    total_features = df.shape[1]

    # 缺失值统计
    missing_pct = {}
    for col in df.columns:
        missing = df[col].isna().sum()
        missing_pct[col] = round(missing / total_rows * 100, 2)

    # Inf 值统计
    inf_count = {}
    for col in df.select_dtypes(include=[np.number]).columns:
        inf = np.isinf(df[col]).sum()
        inf_count[col] = int(inf)

    # 财务数据覆盖情况（填充后）
    financial_coverage = {}
    for field in FINANCIAL_FIELDS:
        if field in df.columns:
            valid = df[field].notna().sum()
            financial_coverage[field] = round(valid / total_rows * 100, 2)

    return {
        "total_rows": total_rows,
        "total_features": total_features,
        "missing_pct": missing_pct,
        "inf_count": inf_count,
        "financial_coverage": financial_coverage,
    }