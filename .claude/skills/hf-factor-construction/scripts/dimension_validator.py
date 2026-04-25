"""Validation helpers for high-frequency factor construction.

This module is intentionally narrower than a full backtest framework. It checks
research hygiene:
- schema and binary validity
- temporal availability contract
- sparsity / support
- mask frequency collapse
- impossible mask occurrences
- threshold sensitivity summaries (when alternate columns are provided)

The validator works with either pandas or polars dataframes. Internally it uses
pandas for broad compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

try:
    import polars as pl  # type: ignore
except Exception:  # pragma: no cover
    pl = None


VALID_TYPES = {"A", "C", "A_QTY", "A_RATE", "A_PRICE", "C_STATE", "C_EVENT"}


def _normalize_type(value: str) -> str:
    v = value.strip().upper()
    alias = {"A": "A_QTY", "C": "C_STATE"}
    return alias.get(v, v)


def _to_pandas(df) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame):
        return df.copy()
    if pl is not None and isinstance(df, pl.DataFrame):
        return df.to_pandas()
    raise TypeError("df must be a pandas or polars DataFrame")


@dataclass
class DimensionSpec:
    name: str
    algebraic_type: str
    quantity: Optional[str] = None
    time_axis: Optional[str] = None
    granularity: Optional[str] = None
    timestamp_col: Optional[str] = None
    available_at_col: Optional[str] = None
    adaptive_threshold: Optional[str] = None
    partition_group: Optional[str] = None
    observability_risk: Optional[str] = None
    min_support: float = 0.01
    max_support: float = 0.99

    def normalized_type(self) -> str:
        t = _normalize_type(self.algebraic_type)
        if t not in VALID_TYPES:
            raise ValueError(f"invalid algebraic type {self.algebraic_type!r} for {self.name}")
        return t


@dataclass
class ValidationResult:
    passed: bool
    errors: Dict[str, List[str]]
    warnings: List[str]
    summary: Dict[str, object] = field(default_factory=dict)


@dataclass
class ThresholdSensitivityResult:
    dimension: str
    base_support: float
    variants: Dict[str, float]
    max_abs_delta: float


def build_mask_summary(
    df,
    dimension_names: Sequence[str],
    min_mask_support: float = 0.001,
) -> Dict[str, object]:
    pdf = _to_pandas(df)
    if not dimension_names:
        return {"frequencies": {}, "counts": {}, "collapse_warnings": []}

    mask_series = pdf[list(dimension_names)].astype("Int64").astype(str).agg("".join, axis=1)
    counts = mask_series.value_counts(dropna=False).sort_index().to_dict()
    total = int(sum(counts.values()))
    frequencies = {mask: (count / total if total > 0 else 0.0) for mask, count in counts.items()}

    all_masks = {"".join(bits) for bits in product("01", repeat=len(dimension_names))}
    warnings: List[str] = []
    missing = sorted(all_masks - set(counts))
    if missing:
        warnings.append(f"missing masks: {', '.join(missing)}")
    rare = sorted([m for m, f in frequencies.items() if f < min_mask_support])
    if rare:
        warnings.append(f"rare masks (< {min_mask_support:.4f}): {', '.join(rare)}")
    return {"frequencies": frequencies, "counts": counts, "collapse_warnings": warnings}


def validate_dimensions(
    df,
    dimension_specs: Sequence[DimensionSpec],
    impossible_masks: Optional[Iterable[str]] = None,
    threshold_variants: Optional[Dict[str, Sequence[str]]] = None,
) -> ValidationResult:
    pdf = _to_pandas(df)
    errors: Dict[str, List[str]] = {
        "schema": [],
        "binary": [],
        "nulls": [],
        "temporal": [],
        "algebraic": [],
        "mask": [],
    }
    warnings: List[str] = []
    summary: Dict[str, object] = {"dimension_support": {}, "threshold_sensitivity": []}

    if pdf.empty:
        errors["schema"].append("input dataframe is empty")
        return ValidationResult(False, errors, warnings, summary)

    granularities = set()
    time_axes = set()
    partition_groups: Dict[str, List[str]] = {}

    for spec in dimension_specs:
        t = spec.normalized_type()
        if spec.name not in pdf.columns:
            errors["schema"].append(f"missing dimension column: {spec.name}")
            continue

        if spec.granularity:
            granularities.add(spec.granularity)
        if spec.time_axis:
            time_axes.add(spec.time_axis)
        if spec.partition_group:
            partition_groups.setdefault(spec.partition_group, []).append(spec.name)

        col = pdf[spec.name]
        bad = [v for v in pd.unique(col) if pd.notna(v) and v not in [0, 1, True, False]]
        if bad:
            errors["binary"].append(f"{spec.name}: non-binary values found {bad[:10]}")

        nulls = int(col.isna().sum())
        if nulls > 0:
            errors["nulls"].append(f"{spec.name}: {nulls} null values")

        support = float(pd.to_numeric(col, errors="coerce").mean())
        summary["dimension_support"][spec.name] = round(support, 6)
        if support < spec.min_support:
            warnings.append(f"{spec.name}: support {support:.4f} < min_support {spec.min_support:.4f}")
        if support > spec.max_support:
            warnings.append(f"{spec.name}: support {support:.4f} > max_support {spec.max_support:.4f}")

        if t.startswith("A") and not spec.quantity:
            errors["algebraic"].append(f"{spec.name}: additive type requires quantity / carrier field")
        if spec.quantity and spec.quantity not in pdf.columns:
            warnings.append(f"{spec.name}: quantity column {spec.quantity!r} not found in dataframe")
        if not spec.adaptive_threshold and t.startswith("C"):
            warnings.append(f"{spec.name}: no adaptive threshold documented for categorical/event split")
        if not spec.observability_risk:
            warnings.append(f"{spec.name}: observability risk not documented")

        if spec.timestamp_col:
            if spec.timestamp_col not in pdf.columns:
                errors["temporal"].append(f"{spec.name}: timestamp_col {spec.timestamp_col!r} missing")
            else:
                ts = pdf[spec.timestamp_col]
                if ts.isna().sum() > 0:
                    errors["temporal"].append(f"{spec.name}: timestamp_col has null values")
                if pd.Series(ts).diff().dropna().lt(0).any():
                    warnings.append(f"{spec.name}: timestamps are not globally monotonic; verify grouping/sorting")

        if spec.available_at_col:
            if spec.available_at_col not in pdf.columns:
                errors["temporal"].append(f"{spec.name}: available_at_col {spec.available_at_col!r} missing")
            elif spec.timestamp_col and spec.timestamp_col in pdf.columns:
                negative_latency = int((pdf[spec.available_at_col] < pdf[spec.timestamp_col]).sum())
                if negative_latency > 0:
                    errors["temporal"].append(
                        f"{spec.name}: {negative_latency} rows have available_at < timestamp (causality violation)"
                    )

    if len(granularities) > 1:
        warnings.append(f"mixed granularities detected: {sorted(granularities)}")
    if len(time_axes) > 1:
        warnings.append(f"mixed time axes detected: {sorted(time_axes)}")

    for group_name, names in partition_groups.items():
        if len(names) != 2:
            warnings.append(f"partition_group {group_name!r} has {len(names)} dimensions; expected 2 for simple complements")
            continue
        both_one = int(((pdf[names[0]] == 1) & (pdf[names[1]] == 1)).sum())
        both_zero = int(((pdf[names[0]] == 0) & (pdf[names[1]] == 0)).sum())
        if both_one > 0:
            errors["binary"].append(f"partition_group {group_name}: {both_one} rows where both complement dimensions are 1")
        if both_zero > 0:
            errors["binary"].append(f"partition_group {group_name}: {both_zero} rows where both complement dimensions are 0")

    dim_names = [spec.name for spec in dimension_specs if spec.name in pdf.columns]
    mask_summary = build_mask_summary(pdf, dim_names)
    summary["mask_frequencies"] = {k: round(v, 6) for k, v in mask_summary["frequencies"].items()}
    if mask_summary["collapse_warnings"]:
        warnings.extend(mask_summary["collapse_warnings"])

    impossible_set = set(impossible_masks or [])
    if impossible_set and dim_names:
        mask_counts = mask_summary["counts"]
        for mask in sorted(impossible_set):
            if mask_counts.get(mask, 0) > 0:
                errors["mask"].append(f"impossible mask {mask} observed {mask_counts[mask]} times")

    if threshold_variants:
        for dim_name, variant_cols in threshold_variants.items():
            if dim_name not in pdf.columns:
                continue
            base_support = float(pd.to_numeric(pdf[dim_name], errors="coerce").mean())
            variants: Dict[str, float] = {}
            for variant in variant_cols:
                if variant in pdf.columns:
                    variants[variant] = float(pd.to_numeric(pdf[variant], errors="coerce").mean())
                else:
                    warnings.append(f"threshold variant column {variant!r} missing for {dim_name}")
            if variants:
                max_abs_delta = max(abs(v - base_support) for v in variants.values())
                summary["threshold_sensitivity"].append(
                    ThresholdSensitivityResult(
                        dimension=dim_name,
                        base_support=base_support,
                        variants=variants,
                        max_abs_delta=max_abs_delta,
                    ).__dict__
                )
                if max_abs_delta > 0.20:
                    warnings.append(
                        f"{dim_name}: threshold sensitivity high (max support delta={max_abs_delta:.4f})"
                    )

    passed = not any(errors.values())
    return ValidationResult(passed=passed, errors=errors, warnings=warnings, summary=summary)


def generate_validation_report(result: ValidationResult, dimension_specs: Sequence[DimensionSpec]) -> str:
    lines: List[str] = ["# HF Dimension Validation Report", ""]
    lines.append(f"- overall_passed: {'yes' if result.passed else 'no'}")
    lines.append(f"- dimensions: {', '.join(spec.name for spec in dimension_specs)}")
    lines.append("")

    for category, errs in result.errors.items():
        lines.append(f"## {category}")
        if errs:
            lines.extend([f"- ❌ {e}" for e in errs])
        else:
            lines.append("- ✓ none")
        lines.append("")

    lines.append("## warnings")
    if result.warnings:
        lines.extend([f"- ⚠️ {w}" for w in result.warnings])
    else:
        lines.append("- ✓ none")
    lines.append("")

    lines.append("## support summary")
    for name, support in result.summary.get("dimension_support", {}).items():
        lines.append(f"- {name}: {support}")
    lines.append("")

    lines.append("## mask frequencies")
    mask_freqs = result.summary.get("mask_frequencies", {})
    if mask_freqs:
        for mask, freq in sorted(mask_freqs.items()):
            lines.append(f"- {mask}: {freq}")
    else:
        lines.append("- none")
    lines.append("")

    if result.summary.get("threshold_sensitivity"):
        lines.append("## threshold sensitivity")
        for item in result.summary["threshold_sensitivity"]:
            lines.append(
                f"- {item['dimension']}: base={item['base_support']:.4f}, "
                f"max_abs_delta={item['max_abs_delta']:.4f}, variants={item['variants']}"
            )
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    df = pd.DataFrame(
        {
            "ts": [1, 2, 3, 4, 5],
            "available": [1, 2, 3, 4, 5],
            "volume": [10, 30, 5, 50, 12],
            "V_side": [1, 0, 1, 1, 0],
            "V_size_rel": [0, 1, 0, 1, 0],
            "P_jump_rel": [0, 0, 1, 1, 0],
        }
    )
    specs = [
        DimensionSpec("V_side", "A_qty", quantity="volume", time_axis="event", granularity="trade", timestamp_col="ts", available_at_col="available", observability_risk="side inference quality"),
        DimensionSpec("V_size_rel", "C_event", time_axis="event", granularity="trade", timestamp_col="ts", available_at_col="available", adaptive_threshold="rolling q80", observability_risk="size seasonality"),
        DimensionSpec("P_jump_rel", "C_event", time_axis="clock", granularity="trade", timestamp_col="ts", available_at_col="available", adaptive_threshold="rolling vol", observability_risk="session edges"),
    ]
    result = validate_dimensions(df, specs)
    print(generate_validation_report(result, specs))
