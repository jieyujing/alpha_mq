# Factor Quality Report

**Generated**: 2026-04-26 14:19:20

---

## 1. Filter Funnel (过滤链漏斗)

| Step | Rows | Features |
|------|------|----------|
| DropMissingLabelStep | removed rows=5006 | reason=label is not null |
| DropMissingLabelStep | rows: 9976 -> 4970, features: 158 -> 158 |
| DropHighMissingFeatureStep | removed features=6 | reason=missing_ratio > 0.5 |
| DropHighMissingFeatureStep | rows: 4970 -> 4970, features: 158 -> 152 |
| DropHighInfFeatureStep | removed features=0 | reason=inf_ratio > 0.05 |
| DropHighInfFeatureStep | rows: 4970 -> 4970, features: 152 -> 152 |
| DropLowVarianceFeatureStep | removed features=12 | reason=nunique_ratio <= 0.005 or variance <= 1e-10 |
| DropLowVarianceFeatureStep | rows: 4970 -> 4970, features: 152 -> 140 |
| FactorQualityFilterStep relaxed | kept 122 factors: {4: 82, 3: 40} |
| FactorQualityFilterStep | removed features=18 | reason=mode=relaxed, |ic_mean| < 0.002 or |icir| < 0.05 or |monotonicity| < 0.02 or sign_flip_ratio > 0.55 |
| FactorQualityFilterStep | rows: 4970 -> 4970, features: 140 -> 122 |

---

## 2. Factor Quality Statistics (因子质量统计)

### IC/ICIR/Monotonicity Distribution

| Metric | Mean | Std | P25 | Median | P75 |
|--------|------|-----|-----|--------|-----|
| ic_mean | -0.0078 | 0.0405 | -0.0295 | -0.0076 | 0.0121 |
| icir | -0.0412 | 0.2376 | -0.1577 | -0.0375 | 0.0829 |
| monotonicity | -0.0213 | 0.1283 | -0.0810 | 0.0016 | 0.0719 |

### Factor Pool Summary

- **Total factors before filtering**: 158
- **Total factors after filtering**: 122
- **Retained rate**: 77.2%
- **Total samples**: 4970

---

## 3. Top Retained Factor Details (保留因子详情 Top 15)

| Rank | Factor | ic_mean | icir | monotonicity | sign_flip |
|------|--------|---------|------|--------------|-----------|
| 1 | CORR20 |  0.1143 |  0.8196 |  0.2828 | 0.4333 |
| 2 | CORR60 |  0.1056 |  0.7402 |  0.2966 | 0.3667 |
| 3 | CORR30 |  0.1056 |  0.7401 |  0.2828 | 0.3667 |
| 4 | KLOW |  0.0871 |  0.5209 |  0.1625 | 0.4839 |
| 5 | RSQR10 |  0.0833 |  0.4935 |  0.3172 | 0.3103 |
| 6 | WVMA20 |  0.0823 |  0.4012 |  0.3567 | 0.1724 |
| 7 | CORR10 |  0.0812 |  0.4547 |  0.0862 | 0.3000 |
| 8 | STD10 |  0.0801 |  0.3393 |  0.0613 | 0.2333 |
| 9 | KLEN |  0.0765 |  0.3479 |  0.0156 | 0.3226 |
| 10 | VMA10 |  0.0741 |  0.4706 |  0.1800 | 0.4667 |
| 11 | LOW0 |  0.0689 |  0.3460 |  0.0719 | 0.6129 |
| 12 | VMA60 |  0.0684 |  0.4650 |  0.1600 | 0.4667 |
| 13 | VMA30 |  0.0684 |  0.4647 |  0.1600 | 0.4667 |
| 14 | MIN20 |  0.0652 |  0.3262 |  0.0281 | 0.2903 |
| 15 | VMA20 |  0.0650 |  0.4491 |  0.1500 | 0.4667 |

---

## 4. Factor Group Breakdown (因子类型分组)

| Category | Count | Factors |
|----------|-------|---------|
| Momentum/Trend | 24 | MA10, MA20, MA30, MA5, MA60, MAX20, MAX30, MAX5, MAX60, SUMD10, SUMD20, SUMD30, SUMD5, SUMD60, SUMN10, SUMN20, SUMN30, SUMN5, SUMN60, SUMP10, SUMP20, SUMP30, SUMP5, SUMP60 |
| Volatility | 15 | RESI10, RESI20, RESI30, RESI5, RESI60, RSQR10, RSQR20, RSQR30, RSQR5, RSQR60, STD10, STD20, STD30, STD5, STD60 |
| Volume-Price | 18 | CNTD10, CNTN10, CNTP10, CNTP20, CORR10, CORR20, CORR30, CORR5, CORR60, KLOW, KLOW2, KUP, KUP2, VMA10, VMA20, VMA30, VMA5, VMA60 |
| Quantile/Extremes | 15 | MIN10, MIN20, MIN30, MIN5, MIN60, QTLD10, QTLD20, QTLD30, QTLD5, QTLD60, QTLU10, QTLU20, QTLU30, QTLU5, QTLU60 |
| Other | 50 | BETA10, BETA20, BETA30, BETA5, BETA60, CORD10, CORD20, CORD30, CORD5, CORD60, HIGH0, IMAX30, IMAX60, IMXD20, IMXD30, IMXD60, KLEN, KSFT, KSFT2, LOW0, RANK10, RANK20, RANK30, RANK60, RSV10, RSV20, RSV30, RSV5, RSV60, VSTD20, VSTD30, VSTD5, VSTD60, VSUMD10, VSUMD30, VSUMD5, VSUMD60, VSUMN10, VSUMN30, VSUMN5, VSUMN60, VSUMP10, VSUMP30, VSUMP5, VSUMP60, WVMA10, WVMA20, WVMA30, WVMA5, WVMA60 |

---

## 5. Highly Correlated Factor Pairs (高相关因子对)

*No redundancy analysis available.*

---

## 6. Label Statistics (标签统计)

| Label | Count | Mean | Std | Min | P25 | Median | P75 | Max |
|-------|-------|------|-----|-----|-----|--------|-----|-----|
| label_10d | 1836 | -0.013175 | 0.087433 | -0.282268 | -0.070737 | -0.013700 | 0.031923 | 0.439189 |
| label_1d | 8972 | 0.003999 | 0.026868 | -0.128438 | -0.009959 | 0.001897 | 0.014370 | 0.201149 |
| label_20d | 1156 | -0.027056 | 0.103794 | -0.313147 | -0.091755 | -0.041202 | 0.020647 | 0.472119 |
| label_5d | 4970 | 0.014192 | 0.064981 | -0.310413 | -0.018110 | 0.009095 | 0.039893 | 0.598904 |

---

## 7. Top Factor-Label Correlations (因子-label 相关性 Top 20)

| Rank | Factor | Correlation |
|------|--------|-------------|
| 1 | WVMA20 | -0.1744 |
| 2 | WVMA30 | -0.1519 |
| 3 | WVMA60 | -0.1505 |
| 4 | CNTP10 | -0.1469 |
| 5 | WVMA10 | -0.1412 |
| 6 | VSTD20 | -0.1366 |
| 7 | CNTP20 | -0.1333 |
| 8 | VSTD30 | -0.1252 |
| 9 | VSTD60 | -0.1234 |
| 10 | HIGH0 | 0.1199 |
| 11 | CNTN10 | -0.1187 |
| 12 | KLOW2 | -0.1059 |
| 13 | KSFT | -0.1038 |
| 14 | RESI60 | -0.1022 |
| 15 | RESI30 | -0.1020 |
| 16 | QTLD30 | 0.0924 |
| 17 | QTLD60 | 0.0923 |
| 18 | QTLD20 | 0.0912 |
| 19 | KSFT2 | -0.0900 |
| 20 | RESI20 | -0.0877 |
