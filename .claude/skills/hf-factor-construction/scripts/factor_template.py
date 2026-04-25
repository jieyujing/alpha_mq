"""Generate a fixed high-frequency factor design contract.

This is not a backtest tool. It creates the research document a senior
researcher can hand to implementation without losing causality and measurement
constraints.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from itertools import product
from typing import Dict, List, Sequence


VALID_TYPES = {"A", "C", "A_QTY", "A_RATE", "A_PRICE", "C_STATE", "C_EVENT"}
TYPE_ALIAS = {"A": "A_QTY", "C": "C_STATE"}


def normalize_type(value: str) -> str:
    v = value.strip().upper()
    v = TYPE_ALIAS.get(v, v)
    if v not in VALID_TYPES:
        raise ValueError(f"invalid type {value!r}; allowed={sorted(VALID_TYPES)}")
    return v


def _recommended_ops(types: Sequence[str]) -> List[str]:
    has_additive = any(t.startswith("A_") for t in types)
    has_categorical = any(t.startswith("C_") for t in types)
    if has_additive and has_categorical:
        return ["SUM(filtered)", "RATIO(filtered)", "INTENSITY(filtered)", "DIFF(filtered)"]
    if has_additive:
        return ["SUM", "DIFF", "RATIO", "INTENSITY", "ROBUST_ZSCORE"]
    return ["COUNT", "FREQ", "DURATION", "HAZARD_RATE"]


def generate_factor_template(
    dimension_names: Sequence[str],
    dimension_types: Sequence[str],
    factor_name: str,
    market_mechanism: str,
    use_case: str = "[maker gate / taker alpha / regime filter / cross-sectional]",
    forecast_horizon: str = "[e.g. next 1s / next 20 trades / next 5 bars]",
    market_scope: str = "[venue / asset universe / contract type]",
) -> Dict:
    if len(dimension_names) != len(dimension_types):
        raise ValueError("dimension_names and dimension_types must have the same length")
    if not (2 <= len(dimension_names) <= 4):
        raise ValueError("number of dimensions must be between 2 and 4")

    types = [normalize_type(t) for t in dimension_types]
    masks = []
    for bits in product("01", repeat=len(dimension_names)):
        mask = "".join(bits)
        masks.append(
            {
                "mask": mask,
                "dimension_values": dict(zip(dimension_names, bits)),
                "interpretation": f"[一句话解释 {' & '.join(f'{n}={b}' for n, b in zip(dimension_names, bits))} 的市场含义]",
                "is_primary": False,
                "expected_support": "[low / medium / high]",
                "possible": True,
            }
        )

    dimensions = []
    for name, t in zip(dimension_names, types):
        dimensions.append(
            {
                "id": name,
                "algebraic_type": t,
                "mask_definition": f"[历史可实时计算的 {name}=1 条件]",
                "continuous_carrier": "[e.g. signed notional / depletion rate / jump size / relative activity]",
                "input_columns": ["[fill me]"],
                "granularity": "[trade / snapshot / bar / bucket]",
                "time_axis": "[clock / event / volume / dollar]",
                "adaptive_threshold": "[rolling quantile / robust z / seasonal baseline / none]",
                "observability_risk": "[how this can be mismeasured]",
            }
        )

    return {
        "metadata": {
            "factor_name": factor_name,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "n_dimensions": len(dimension_names),
        },
        "mechanism": {
            "one_liner": market_mechanism or "[一句话说明微观机制]",
            "who_is_forced": "[谁在被迫交易 / 清库存 / 追价 / 撤单]",
            "why_edge_exists": "[为何该行为会对未来短期价格或成交质量产生影响]",
        },
        "research_context": {
            "use_case": use_case,
            "forecast_horizon": forecast_horizon,
            "market_scope": market_scope,
            "holding_logic": "[maker pre-fill / post-fill / taker / bucket close decision]",
        },
        "data_contract": {
            "required_columns": ["[fill me]"],
            "market_layer": "[trade / L1 / L2 / L3 / bar]",
            "sampling_axis": "[clock / event / volume / dollar]",
            "preprocessing": [
                "[session open/close handling]",
                "[auction / halt / maintenance handling]",
                "[trade-book alignment rule]",
            ],
        },
        "temporal_contract": {
            "t_obs": "[feature observation time]",
            "t_available": "[real data availability time]",
            "t_action": "[strategy action time]",
            "window_feature": "[historical lookback]",
            "window_target": "[future prediction window]",
            "time_axis": "[clock / event / volume / dollar]",
            "latency_assumption": {
                "feed": "[e.g. 80ms]",
                "decision": "[e.g. 5ms]",
                "order": "[e.g. 20ms]",
            },
        },
        "dimensions": dimensions,
        "mask_semantics": masks,
        "aggregation": {
            "operators": _recommended_ops(types),
            "formula": "[write the exact raw factor formula]",
            "lookback": "[e.g. trailing 2s / trailing 200 trades]",
            "denominator": "[baseline / total volume / local activity / none]",
            "units": "[bps / shares/sec / ratio / zscore]",
        },
        "normalization": {
            "within_symbol": "[robust z / percentile rank / none]",
            "cross_symbol": "[rank / ADV scaling / none]",
            "intraday_seasonality": "[how removed or why not needed]",
            "volatility_scaling": "[yes/no and estimator]",
            "activity_scaling": "[yes/no and baseline]",
        },
        "smoothing": {
            "method": "[none / EMA / Hawkes]",
            "when_applied": "post-aggregation",
            "parameters": {
                "half_life": "[state unit explicitly]",
                "eta": "[if Hawkes]",
                "span": "[if EMA]",
                "time_unit": "[seconds / events / volume-time]",
            },
            "rationale": "[why this smoothing matches the mechanism]",
        },
        "observability_risks": [
            "[measurement risk 1]",
            "[measurement risk 2]",
            "[measurement risk 3]",
        ],
        "must_fail_scenarios": [
            {"condition": "[scenario 1]", "reason": "[why the mechanism should disappear]"},
            {"condition": "[scenario 2]", "reason": "[why the mechanism should disappear]"},
        ],
        "minimal_sanity_gate": [
            "coverage / support is acceptable",
            "primary mask is neither too sparse nor too universal",
            "same-step edge is not purely stronger because of leakage",
            "adjacent thresholds keep sign / interpretation stable",
            "effect is not only a session artifact",
            "effect is not only an activity or spread proxy",
        ],
        "implementation_sketch": {
            "feature_grid": "[where factor values are emitted]",
            "pseudo_code": [
                "compute dimensions on historical-only window",
                "construct primary mask(s)",
                "aggregate continuous carrier under mask",
                "normalize",
                "smooth post-aggregation if needed",
            ],
        },
    }


def render_template_markdown(template: Dict) -> str:
    dims = template["dimensions"]
    masks = template["mask_semantics"]
    agg = template["aggregation"]
    norm = template["normalization"]
    smoothing = template["smoothing"]

    lines: List[str] = []
    lines.append(f"# {template['metadata']['factor_name']} — HF Factor Design Contract")
    lines.append("")
    lines.append(f"> created_at_utc: {template['metadata']['created_at_utc']}")
    lines.append(f"> n_dimensions: {template['metadata']['n_dimensions']}")
    lines.append("")

    lines.append("## 1. Mechanism")
    for k, v in template["mechanism"].items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")

    lines.append("## 2. Research context")
    for k, v in template["research_context"].items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")

    lines.append("## 3. Data contract")
    dc = template["data_contract"]
    lines.append(f"- **required_columns**: {', '.join(dc['required_columns'])}")
    lines.append(f"- **market_layer**: {dc['market_layer']}")
    lines.append(f"- **sampling_axis**: {dc['sampling_axis']}")
    lines.append("- **preprocessing**:")
    lines.extend([f"  - {x}" for x in dc["preprocessing"]])
    lines.append("")

    lines.append("## 4. Temporal contract")
    tc = template["temporal_contract"]
    for k, v in tc.items():
        if isinstance(v, dict):
            lines.append(f"- **{k}**:")
            for kk, vv in v.items():
                lines.append(f"  - {kk}: {vv}")
        else:
            lines.append(f"- **{k}**: {v}")
    lines.append("")

    lines.append("## 5. Dimensions")
    lines.append("| id | algebraic_type | mask_definition | continuous_carrier | granularity | time_axis | adaptive_threshold | observability_risk |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for d in dims:
        lines.append(
            f"| `{d['id']}` | `{d['algebraic_type']}` | {d['mask_definition']} | {d['continuous_carrier']} | {d['granularity']} | {d['time_axis']} | {d['adaptive_threshold']} | {d['observability_risk']} |"
        )
    lines.append("")

    lines.append("## 6. Mask semantics")
    lines.append("| mask | interpretation | expected_support | primary | possible |")
    lines.append("|---|---|---|---|---|")
    for m in masks:
        lines.append(
            f"| `{m['mask']}` | {m['interpretation']} | {m['expected_support']} | {'✓' if m['is_primary'] else ''} | {'yes' if m['possible'] else 'no'} |"
        )
    lines.append("")

    lines.append("## 7. Aggregation")
    lines.append(f"- **operators**: {', '.join(agg['operators'])}")
    lines.append(f"- **formula**: {agg['formula']}")
    lines.append(f"- **lookback**: {agg['lookback']}")
    lines.append(f"- **denominator**: {agg['denominator']}")
    lines.append(f"- **units**: {agg['units']}")
    lines.append("")

    lines.append("## 8. Normalization")
    for k, v in norm.items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")

    lines.append("## 9. Smoothing")
    lines.append(f"- **method**: {smoothing['method']}")
    lines.append(f"- **when_applied**: {smoothing['when_applied']}")
    lines.append("- **parameters**:")
    for k, v in smoothing["parameters"].items():
        lines.append(f"  - {k}: {v}")
    lines.append(f"- **rationale**: {smoothing['rationale']}")
    lines.append("")

    lines.append("## 10. Observability risks")
    lines.extend([f"- {x}" for x in template["observability_risks"]])
    lines.append("")

    lines.append("## 11. Must-fail scenarios")
    for item in template["must_fail_scenarios"]:
        lines.append(f"- **condition**: {item['condition']}")
        lines.append(f"  - reason: {item['reason']}")
    lines.append("")

    lines.append("## 12. Minimal sanity gate")
    lines.extend([f"- {x}" for x in template["minimal_sanity_gate"]])
    lines.append("")

    lines.append("## 13. Implementation sketch")
    lines.append(f"- **feature_grid**: {template['implementation_sketch']['feature_grid']}")
    lines.append("- **pseudo_code**:")
    lines.extend([f"  - {x}" for x in template["implementation_sketch"]["pseudo_code"]])
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a high-frequency factor design contract")
    parser.add_argument("-d", "--dimensions", required=True, help="Comma-separated dimension ids")
    parser.add_argument("-t", "--types", required=True, help="Comma-separated algebraic types")
    parser.add_argument("-n", "--name", required=True, help="Factor name")
    parser.add_argument("-m", "--mechanism", required=True, help="One-line market mechanism")
    parser.add_argument("--use-case", default="[maker gate / taker alpha / regime filter / cross-sectional]")
    parser.add_argument("--horizon", default="[e.g. next 1s / next 20 trades / next 5 bars]")
    parser.add_argument("--market-scope", default="[venue / asset universe / contract type]")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("-o", "--output", help="Optional output file")
    args = parser.parse_args()

    dims = [x.strip() for x in args.dimensions.split(",") if x.strip()]
    types = [x.strip() for x in args.types.split(",") if x.strip()]
    template = generate_factor_template(
        dimension_names=dims,
        dimension_types=types,
        factor_name=args.name,
        market_mechanism=args.mechanism,
        use_case=args.use_case,
        forecast_horizon=args.horizon,
        market_scope=args.market_scope,
    )
    output = render_template_markdown(template) if args.format == "markdown" else json.dumps(template, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
    else:
        print(output)
