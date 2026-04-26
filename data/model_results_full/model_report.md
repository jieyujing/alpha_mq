# Model Training Report

**Generated**: 2026-04-26 12:54:48
**Static split - results may not reflect rolling live performance**

## 1. Model x Period Direction

| Model | Label | Val IC | Direction | Oriented IC | Oriented ICIR |
|-------|-------|--------|-----------|-------------|---------------|
| elastic_net | label_1d | 0.0403 | original | 0.0403 | 0.2959 |
| elastic_net | label_5d | 0.0316 | original | 0.0316 | 0.1909 |
| elastic_net | label_10d | 0.0488 | original | 0.0488 | 0.2443 |
| elastic_net | label_20d | 0.0876 | original | 0.0876 | 0.5329 |
| lgbm_regressor | label_1d | 0.0317 | original | 0.0317 | 0.2968 |
| lgbm_regressor | label_5d | 0.0184 | original | 0.0184 | 0.1699 |
| lgbm_regressor | label_10d | 0.0354 | original | 0.0354 | 0.2527 |
| lgbm_regressor | label_20d | 0.0600 | original | 0.0600 | 0.5191 |
| lgbm_ranker | label_1d | -0.0386 | flipped | 0.0386 | 0.2378 |
| lgbm_ranker | label_5d | -0.0007 | flipped | 0.0007 | 0.0084 |
| lgbm_ranker | label_10d | 0.0021 | original | 0.0021 | 0.0195 |
| lgbm_ranker | label_20d | 0.0449 | original | 0.0449 | 0.5750 |
| lgbm_classifier | label_1d | 0.0657 | original | 0.0657 | 0.5742 |
| lgbm_classifier | label_5d | 0.0711 | original | 0.0711 | 0.4644 |
| lgbm_classifier | label_10d | 0.0834 | original | 0.0834 | 0.4684 |
| lgbm_classifier | label_20d | 0.1132 | original | 0.1132 | 0.7941 |

## 2. Out-of-Sample TopK Performance

| Model | Label | Ann Ret | Excess Ann Ret | Sharpe | Max DD | Turnover | Cost Adj Sharpe |
|-------|-------|---------|----------------|--------|--------|----------|-----------------|
| elastic_net | label_1d | 160.71% | 66.34% | 3.85 | -14.74% | 0.767 | 5.48 |
| elastic_net | label_5d | 66.79% | 21.39% | 2.16 | -13.10% | 0.533 | 2.18 |
| elastic_net | label_10d | 41.47% | 4.43% | 1.54 | -13.65% | 0.443 | 0.43 |
| elastic_net | label_20d | 46.70% | 2.12% | 1.73 | -13.72% | 0.427 | 0.21 |
| lgbm_regressor | label_1d | 256.04% | 99.67% | 4.02 | -17.19% | 0.789 | 7.20 |
| lgbm_regressor | label_5d | 124.86% | 52.94% | 2.79 | -18.03% | 0.632 | 4.68 |
| lgbm_regressor | label_10d | 92.45% | 36.68% | 2.36 | -16.97% | 0.513 | 3.81 |
| lgbm_regressor | label_20d | 63.25% | 13.91% | 1.90 | -16.89% | 0.492 | 1.51 |
| lgbm_ranker | label_1d | -3.07% | -33.92% | -0.04 | -24.13% | 0.728 | -2.77 |
| lgbm_ranker | label_5d | 5.44% | -24.82% | 0.34 | -19.46% | 0.428 | -2.20 |
| lgbm_ranker | label_10d | 50.39% | 11.85% | 1.53 | -14.63% | 0.398 | 0.88 |
| lgbm_ranker | label_20d | 60.65% | 12.59% | 1.77 | -16.05% | 0.358 | 1.16 |
| lgbm_classifier | label_1d | 89.28% | 33.10% | 3.15 | -11.14% | 0.598 | 2.73 |
| lgbm_classifier | label_5d | 30.29% | -4.09% | 1.32 | -11.71% | 0.450 | -0.37 |
| lgbm_classifier | label_10d | 26.46% | -7.28% | 1.17 | -12.51% | 0.394 | -0.66 |
| lgbm_classifier | label_20d | 27.78% | -12.19% | 1.24 | -12.39% | 0.362 | -1.09 |

## 3. Best Model: lgbm_classifier + label_20d

- Validation IC: 0.1132
- Validation ICIR: 0.7941
- Signal direction: original
- OOS annual return: 27.78%
- OOS Sharpe: 1.24
- OOS max drawdown: -12.39%

## 4. Top 20 Feature Importance

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | STD60 | 254.0000 |
| 2 | turnrate | 254.0000 |
| 3 | CORD60 | 248.0000 |
| 4 | CORR60 | 237.0000 |
| 5 | WVMA30 | 188.0000 |
| 6 | CORD30 | 185.0000 |
| 7 | BETA60 | 171.0000 |
| 8 | STD30 | 168.0000 |
| 9 | ROC60 | 167.0000 |
| 10 | RSQR60 | 149.0000 |
| 11 | VSTD60 | 147.0000 |
| 12 | CORR30 | 141.0000 |
| 13 | ROC30 | 140.0000 |
| 14 | MIN60 | 124.0000 |
| 15 | RSQR30 | 122.0000 |
| 16 | MAX60 | 115.0000 |
| 17 | STD20 | 112.0000 |
| 18 | RSQR20 | 108.0000 |
| 19 | CORR20 | 106.0000 |
| 20 | RSV60 | 93.0000 |
