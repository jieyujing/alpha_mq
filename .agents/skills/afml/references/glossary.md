# AFML Glossary & Concepts

## Data Structures

*   **Time Bars**: Standard OHLCV bars sampled by fixed time intervals (e.g., 1 minute, 1 day). *Discouraged in AFML due to poor statistical properties.*
*   **Dollar Bars**: Bars sampled every time a pre-defined value (e.g., $1M) is exchanged. *Preferred: better statistical properties, handles varying volatility.*
*   **Volume Bars**: Bars sampled every time a pre-defined volume (e.g., 1000 shares) is traded.
*   **Tick Bars**: Bars sampled every N transactions.

## Stationarity & Features

*   **Fractional Differentiation (FracDiff)**: A method to make a time series stationary while retaining as much memory (history) as possible. Unlike integer differencing (d=1), which wipes memory, FracDiff uses a fractional d (e.g., 0.4).
*   **Augmented Dickey-Fuller (ADF)**: Statistical test to check for stationarity. Null hypothesis is that a unit root is present (non-stationary).

## Labeling

*   **Triple-Barrier Method**: A labeling technique that sets three barriers:
    1.  **Upper**: Take profit level.
    2.  **Lower**: Stop loss level.
    3.  **Vertical**: Time expiration.
    *   The label is determined by which barrier is touched first.
*   **Meta-Labeling**: A secondary ML model that learns to predict whether the primary model's signal will result in a profit. It filters trades, improving the Sharpe ratio.

## Validation

*   **Purged K-Fold Cross-Validation**: A variation of K-Fold CV for time series. It "purges" (removes) observations from the training set that overlap with the test set labels to prevent look-ahead bias.
*   **Embargo**: An additional buffer period after the test set to prevent leakage from serial correlation.
*   **Average Uniqueness**: A measure of how much a sample overlaps with other samples in the dataset. Used to weight samples during training (inverse weighting).

## Performance Metrics

*   **Deflated Sharpe Ratio (DSR)**: A Sharpe Ratio adjusted for the "multiple testing problem" (trying many strategies and picking the best). It estimates the probability that the observed SR is positive due to skill rather than luck/overfitting.
*   **Probabilistic Sharpe Ratio (PSR)**: A precursor to DSR, adjusting SR for skewness and kurtosis of returns.
