# Factor Quality Report

**Generated**: 2026-04-25 15:47:48

---

## 1. Filter Funnel (过滤链漏斗)

| Step | Rows | Features |
|------|------|----------|
| DropMissingLabelStep | removed rows=5001 | reason=label is not null |
| DropMissingLabelStep | rows: 9388 -> 4387, features: 166 -> 166 |
| DropLeakageStep | removed features=1 | reason=prefix match ['LABEL' |
| DropLeakageStep | rows: 4387 -> 4387, features: 166 -> 165 |
| DropHighMissingFeatureStep | removed features=22 | reason=missing_ratio > 0.3 |
| DropHighMissingFeatureStep | rows: 4387 -> 4387, features: 165 -> 143 |
| DropHighInfFeatureStep | removed features=0 | reason=inf_ratio > 0.01 |
| DropHighInfFeatureStep | rows: 4387 -> 4387, features: 143 -> 143 |
| DropLowVarianceFeatureStep | removed features=19 | reason=nunique_ratio <= 0.01 or variance <= 1e-08 |
| DropLowVarianceFeatureStep | rows: 4387 -> 4387, features: 143 -> 124 |
| FactorQualityFilterStep relaxed | kept 97 factors: {3: 64, 4: 33} |
| FactorQualityFilterStep | removed features=27 | reason=mode=relaxed, |ic_mean| < 0.005 or |icir| < 0.1 or |monotonicity| < 0.05 or sign_flip_ratio > 0.45 |
| FactorQualityFilterStep | rows: 4387 -> 4387, features: 124 -> 97 |
| DeduplicateStep | removed features=77 | reason=corr > 0.8 |
| DeduplicateStep | rows: 4387 -> 4387, features: 97 -> 20 |

---

## 2. Factor Quality Statistics (因子质量统计)

### IC/ICIR/Monotonicity Distribution

| Metric | Mean | Std | P25 | Median | P75 |
|--------|------|-----|-----|--------|-----|
| ic_mean | -0.0114 | 0.0391 | -0.0329 | -0.0103 | 0.0133 |
| icir | -0.0675 | 0.2257 | -0.1686 | -0.0498 | 0.0706 |
| monotonicity | -0.0246 | 0.1379 | -0.1076 | -0.0333 | 0.0966 |

### Factor Pool Summary

- **Total factors before filtering**: 166
- **Total factors after filtering**: 20
- **Retained rate**: 12.0%
- **Total samples**: 4387

---

## 3. Top Retained Factor Details (保留因子详情 Top 15)

| Rank | Factor | ic_mean | icir | monotonicity | sign_flip |
|------|--------|---------|------|--------------|-----------|
| 1 | CORR20 |  0.1193 |  0.8595 |  0.3000 | 0.3667 |
| 2 | STD10 |  0.1008 |  0.4613 |  0.0839 | 0.1667 |
| 3 | KLOW |  0.0970 |  0.5335 |  0.2375 | 0.4839 |
| 4 | RSQR10 |  0.0841 |  0.5026 |  0.3448 | 0.3103 |
| 5 | KLEN |  0.0783 |  0.4238 |  0.0125 | 0.3226 |
| 6 | MIN60 |  0.0712 |  0.3791 |  0.0594 | 0.4839 |
| 7 | MAX10 |  0.0522 |  0.2564 |  0.0406 | 0.3226 |
| 8 | RESI30 |  0.0511 |  0.2633 |  0.1414 | 0.3448 |
| 9 | VMA20 |  0.0452 |  0.2684 |  0.0833 | 0.5333 |
| 10 | HIGH0 |  0.0429 |  0.2169 |  0.0375 | 0.3226 |
| 11 | CNTN60 |  0.0346 |  0.1495 |  0.2556 | 0.3000 |
| 12 | QTLU10 |  0.0330 |  0.1793 |  0.1067 | 0.4333 |
| 13 | CNTD60 |  0.0311 |  0.1337 |  0.0704 | 0.3000 |
| 14 | CNTP30 |  0.0295 |  0.1323 |  0.1731 | 0.3667 |
| 15 | VSTD10 |  0.0294 |  0.1595 |  0.0000 | 0.2333 |

---

## 4. Factor Group Breakdown (因子类型分组)

| Category | Count | Factors |
|----------|-------|---------|
| Momentum/Trend | 1 | MAX10 |
| Volatility | 4 | RESI10, RESI30, RSQR10, STD10 |
| Volume-Price | 7 | CNTD60, CNTN60, CNTP30, CORR20, KLOW, KUP2, VMA20 |
| Quantile/Extremes | 2 | MIN60, QTLU10 |
| Extra Features | 1 | turnrate |
| Other | 5 | HIGH0, KLEN, RSV20, VSTD10, VSUMP5 |

---

## 5. Highly Correlated Factor Pairs (高相关因子对)

| Rank | Factor A | Factor B | |Correlation| |
|------|----------|----------|---------------|
| 1 | VSUMP5 | VSUMN5 | 1.0000 |
| 2 | VSUMP5 | VSUMD5 | 1.0000 |
| 3 | VSUMP10 | VSUMD10 | 1.0000 |
| 4 | VSUMP20 | VSUMN20 | 1.0000 |
| 5 | VSUMP20 | VSUMD20 | 1.0000 |
| 6 | VSUMP30 | VSUMN30 | 1.0000 |
| 7 | VSUMP30 | VSUMD30 | 1.0000 |
| 8 | VSUMP60 | VSUMN60 | 1.0000 |
| 9 | VSUMP60 | VSUMD60 | 1.0000 |
| 10 | VSUMN5 | VSUMD5 | 1.0000 |

---

## 6. Label Statistics (标签统计)

| Label | Count | Mean | Std | Min | P25 | Median | P75 | Max |
|-------|-------|------|-----|-----|-----|--------|-----|-----|
| label_10d | 1836 | -0.013175 | 0.087433 | -0.282268 | -0.070737 | -0.013700 | 0.031923 | 0.439189 |
| label_1d | 8965 | 0.003996 | 0.026878 | -0.128438 | -0.009967 | 0.001896 | 0.014361 | 0.201149 |
| label_20d | 1156 | -0.027056 | 0.103794 | -0.313147 | -0.091755 | -0.041202 | 0.020647 | 0.472119 |
| label_5d | 4967 | 0.014178 | 0.064998 | -0.310413 | -0.018127 | 0.009077 | 0.039886 | 0.598904 |

---

## 7. Top Factor-Label Correlations (因子-label 相关性 Top 20)

| Rank | Factor | Correlation |
|------|--------|-------------|
| 1 | turnrate | 0.1323 |
| 2 | HIGH0 | 0.1286 |
| 3 | CNTP30 | -0.1276 |
| 4 | VSTD10 | -0.1223 |
| 5 | RESI30 | -0.1121 |
| 6 | CNTN60 | -0.1073 |
| 7 | KLEN | 0.0749 |
| 8 | RESI10 | -0.0743 |
| 9 | KLOW | -0.0717 |
| 10 | MIN60 | 0.0684 |
| 11 | KUP2 | 0.0682 |
| 12 | STD10 | -0.0463 |
| 13 | RSV20 | -0.0352 |
| 14 | VMA20 | -0.0301 |
| 15 | VSUMP5 | 0.0219 |
| 16 | RSQR10 | 0.0189 |
| 17 | QTLU10 | 0.0116 |
| 18 | MAX10 | -0.0092 |
| 19 | CORR20 | -0.0091 |
| 20 | CNTD60 | -0.0064 |
