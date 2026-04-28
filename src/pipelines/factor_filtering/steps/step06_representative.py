"""Ring 6: 簇内代表因子选择。

每簇按综合评分选择 top_k 个代表因子。
score = 0.30*ICIR_norm + 0.20*monotonicity + 0.20*long_short
      + 0.30*stability
"""

from __future__ import annotations

import polars as pl


class RepresentativeSelector:
    """簇内代表因子选择。"""

    _META_COLS = {"datetime", "instrument"}

    def __init__(self, config: dict | None = None, n_per_cluster: int | None = None):
        self.config = config or {}
        self.n_per_cluster: int = (
            n_per_cluster if n_per_cluster is not None
            else self.config.get("n_per_cluster", 2)
        )

    def _factor_cols(self, df: pl.DataFrame) -> list[str]:
        return [
            c for c in df.columns
            if c not in self._META_COLS and not c.startswith("label")
        ]

    def _normalize(self, values: list[float]) -> list[float]:
        """Min-max 归一化到 [0, 1]。"""
        min_v = min(values)
        max_v = max(values)
        rng = max_v - min_v
        if rng == 0:
            return [0.5] * len(values)
        return [(v - min_v) / rng for v in values]

    def process(
        self, df: pl.DataFrame, clusters: dict[str, int],
        ic_metrics: dict, stability: dict
    ) -> tuple[pl.DataFrame, dict]:
        """选择每簇的代表因子。"""
        factor_cols = self._factor_cols(df)

        # 簇分组
        cluster_to_factors: dict[int, list[str]] = {}
        for f, cid in clusters.items():
            if f in factor_cols:
                cluster_to_factors.setdefault(cid, []).append(f)

        selected = []
        selection_detail = []

        for cid in sorted(cluster_to_factors):
            factors = cluster_to_factors[cid]
            scores = []
            for f in factors:
                m = ic_metrics.get(f, {})
                s = stability.get(f, {})

                icir = abs(m.get("icir", 0))
                mono = abs(m.get("monotonicity", 0))
                ls = abs(m.get("long_short", 0))
                stab = s.get("stability_score", 0.5)

                scores.append({
                    "factor": f,
                    "icir": icir,
                    "monotonicity": mono,
                    "long_short": ls,
                    "stability": stab,
                })

            if len(scores) == 0:
                continue

            # 归一化 + 加权
            icir_norm = self._normalize([s["icir"] for s in scores])
            mono_norm = self._normalize([s["monotonicity"] for s in scores])
            ls_norm = self._normalize([s["long_short"] for s in scores])
            stab_norm = self._normalize([s["stability"] for s in scores])

            for i, s in enumerate(scores):
                s["score"] = (
                    0.30 * icir_norm[i]
                    + 0.20 * mono_norm[i]
                    + 0.20 * ls_norm[i]
                    + 0.30 * stab_norm[i]
                )

            # 按 score 降序取 top_k
            scores.sort(key=lambda x: x["score"], reverse=True)
            top = scores[: self.n_per_cluster]
            for t in top:
                selected.append(t["factor"])
                selection_detail.append({
                    "factor": t["factor"],
                    "cluster": cid,
                    "score": t["score"],
                    "rank_in_cluster": top.index(t) + 1,
                })

        # 剔除未选中的因子
        cols_to_drop = [c for c in factor_cols if c not in selected]
        if cols_to_drop:
            df = df.drop(cols_to_drop)

        report = {
            "selected": selected,
            "selection_detail": selection_detail,
            "selected_count": len(selected),
        }
        return df, report
