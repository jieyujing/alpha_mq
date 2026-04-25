# 2. Shift every observation by the same positive value. Compute the

2. Shift every observation by the same positive value. Compute the
cumulative sum of the observations. This is a non-stationary series
with memory.
1. Compute the ADF statistic on this series. What is the p-value?
2. Apply an expanding window fracdiff, with τ = 1E − 2. For what
minimum d value do you get a p-value below 5%?
3. Apply FFD, with τ = 1E − 5. For what minimum d value do you
get a p-value below 5%?
3. 
Take the series from exercise 2.b:
1. Fit the series to a sine function. What is the R-squared?
2. Apply FFD(d = 1 ). Fit the series to a sine function. What is the R-
squared?
3. What value of d maximizes the R-squared of a sinusoidal fit on
FFD(d ). Why?
4. 
Take the dollar bar series on E-mini S&P 500 futures. Using the
code in Snippet 5.3, for some d ∈ [0, 2], compute
fracDiff_FFD(fracDiff_FFD(series,d),-d) . What do you
get? Why?
5. 
Take the dollar bar series on E-mini S&P 500 futures.
1. Form a new series as a cumulative sum of log-prices.
2. Apply FFD, with τ = 1E − 5.

### Code Examples

```unknown
fracDiff_FFD(fracDiff_FFD(series,d),-d)
```

---

