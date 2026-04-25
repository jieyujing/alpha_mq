# 9. Praestgaard, J. and J. Wellner (1993): “Exchangeably weighted bootstraps

9. Praestgaard, J. and J. Wellner (1993): “Exchangeably weighted bootstraps
of the general empirical process.” Annals of Probability , Vol. 21, pp.
2053–2086.
10. Rao, C., P. Pathak and V. Koltchinskii (1997): “Bootstrap by sequential
resampling.” Journal of Statistical Planning and Inference , Vol. 64, No.
2, pp. 257–281.
CHAPTER 5
Fractionally Differentiated Features
5.1 Motivation
It is known that, as a consequence of arbitrage forces, financial series exhibit
low signal-to-noise ratios (López de Prado [2015]). To make matters worse,
standard stationarity transformations, like integer differentiation, further reduce
that signal by removing memory. Price series have memory, because every
value is dependent upon a long history of previous levels. In contrast, integer
differentiated series, like returns, have a memory cut-off, in the sense that
history is disregarded entirely after a finite sample window. Once stationarity
transformations have wiped out all memory from the data, statis

---

that memory is the basis for the model's predictive power. For example,
equilibrium (stationary) models need some memory to assess how far the price
process has drifted away from the long-term expected value in order to
generate a forecast. The dilemma is that returns are stationary, however
memory-less, and prices have memory, however they are non-stationary. The
question arises: What is the minimum amount of differentiation that makes a
price series stationary while preserving as much memory as possible?
Accordingly, we would like to generalize the notion of returns to consider
stationary series where not all memory is erased. Under this framework,
returns are just one kind of (and in most cases suboptimal) price transformation
among many other possibilities.
Part of the importance of cointegration methods is their ability to model series
with memory. But why would the particular case of zero differentiation deliver
best outcomes? Zero differentiation is as arbitrary as 1-step differ

### Code Examples

```unknown
importance of cointegration methods is their ability to model series
```

```unknown
require stationary features. The reason
```

```unknown
used for computing returns on log-prices)
useful because fractionally differenced
```

---

be optimal? (2) Is over-differentiation one reason why the literature has been so
biased in favor of the efficient markets hypothesis?
The notion of fractional differentiation applied to the predictive time series
analysis dates back at least to Hosking [1981]. In that paper, a family of
ARIMA processes was generalized by permitting the degree of differencing to
take fractional values. This was useful because fractionally differenced
processes exhibit long-term persistence and antipersistence, hence enhancing
the forecasting power compared to the standard ARIMA approach. In the same
paper, Hosking states: “Apart from a passing reference by Granger (1978),
fractional differencing does not appear to have been previously mentioned in
connection with time series analysis.”
After Hosking's paper, the literature on this subject has been surprisingly
scarce, adding up to eight journal articles written by only nine authors:
Hosking, Johansen, Nielsen, MacKinnon, Jensen, Jones, Popiel, Cavalier

---

5.4.1 Long Memory
Let us see how a real (non-integer) positive d preserves memory. This
arithmetic series consists of a dot product
with weights ω
and values X
When d is a positive integer number, 
 , and memory
beyond that point is cancelled. For example, d = 1 is used to compute returns,
where 
 , and ω = {1, −1, 0, 0, …}.
5.4.2 Iterative Estimation
Looking at the sequence of weights, ω, we can appreciate that for k = 0, …, ∞,
with ω 0 = 1, the weights can be generated iteratively as:

### Code Examples

```unknown
used to compute returns,
used to compute each value of the
```

---

Figure 5.1 plots the sequence of weights used to compute each value of the
fractionally differentiated series. The legend reports the value of d used to
generate each sequence, the x-axis indicates the value of k , and the y-axis
shows the value of ω k . For example, for d = 0, all weights are 0 except for ω 0
= 1 . That is the case where the differentiated series coincides with the original
one. For d = 1, all weights are 0 except for ω 0 = 1 and ω 1 = −1 . That is the
standard first-order integer differentiation, which is used to derive log-price
returns. Anywhere in between these two cases, all weights after ω 0 = 1 are
negative and greater than −1.
Figure 5.1 ω k (y-axis) as k increases (x-axis). Each line is associated with a
particular value of d ∈ [0,1], in 0.1 increments.
Figure 5.2 plots the sequence of weights where d ∈ [1, 2], at increments of
0.1. For d > 1, we observe ω 1 < −1 and ω k > 0, ∀ k ≥ 2 .

### Code Examples

```unknown
used to derive log-price
used to generate these plots.
```

---

Figure 5.2 ω k (y-axis) as k increases (x-axis). Each line is associated with a
particular value of d ∈ [1,2], in 0.1 increments.
Snippet 5.1 lists the code used to generate these plots.
SNIPPET 5.1 WEIGHTING FUNCTION

---

5.4.3 Convergence
Let us consider the convergence of the weights. From the above result, we can
see that for k > d , if ω k − 1 ≠ 0, then 
 , and ω k = 0
otherwise. Consequently, the weights converge asymptotically to zero, as an
infinite product of factors within the unit circle. Also, for a positive d and k < d
+ 1, we have 
 , which makes the initial weights alternate in sign. For
a non-integer d , once k ≥ d + 1, ω k will be negative if int[ d ] is even, and
positive otherwise. Summarizing, 
 (converges to zero from the
left) when int[ d ] is even, and 
 (converges to zero from the right)

---

when Int[ d ] is odd. In the special case d ∈ (0, 1), this means that − 1 < ω k <
0, ∀ k > 0 . This alternation of weight signs is necessary to make 
stationary, as memory wanes or is offset over the long run.
5.5 Implementation
In this section we will explore two alternative implementations of fractional
differentiation: the standard “expanding window” method, and a new method
that I call “fixed-width window fracdiff” (FFD).
5.5.1 Expanding Window
Let us discuss how to fractionally differentiate a (finite) time series in practice.
Suppose a time series with T real observations, { X t },  t = 1, …, T . Because of
data limitations, the fractionally differentiated value 
 cannot be computed on
an infinite series of weights. For instance, the last point 
 will use weights {ω
k },  k = 0, …, T − 1, and 
 will use weights {ω k },  k = 0, …, T − l − 1. This
means that the initial points will have a different amount of memory compared
to the final points. For each l , we can determine the rel

### Code Examples

```unknown
use weights {ω k },  k = 0, …, T − l − 1. This
used by the negative weights that are added
```

---

Figure 5.3 Fractional differentiation without controlling for weight loss (top
plot) and after controlling for weight loss with an expanding window (bottom
plot)
The negative drift in both plots is caused by the negative weights that are added
to the initial observations as the window is expanded. When we do not control
for weight loss, the negative drift is extreme, to the point that only that trend is
visible. The negative drift is somewhat more moderate in the right plot, after
controlling for the weight loss, however, it is still substantial, because values
 are computed on an expanding window. This problem can be
corrected by a fixed-width window, implemented in Snippet 5.2.

---

SNIPPET 5.2 STANDARD FRACDIFF (EXPANDING WINDOW)
5.5.2 Fixed-Width Window Fracdiff
Alternatively, fractional differentiation can be computed using a fixed-width
window, that is, dropping the weights after their modulus (|ω k |) falls below a
given threshold value (τ) . This is equivalent to finding the first l * such that
 and 
 , setting a new variable

---

