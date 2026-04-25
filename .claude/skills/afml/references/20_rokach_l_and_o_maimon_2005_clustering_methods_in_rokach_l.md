# 20. Rokach, L. and O. Maimon (2005): “Clustering methods,” in Rokach, L.

20. Rokach, L. and O. Maimon (2005): “Clustering methods,” in Rokach, L.
and O. Maimon, eds., Data Mining and Knowledge Discovery Handbook .
Springer, pp. 321–352.
Notes
1    A short version of this chapter appeared in the Journal of Portfolio
Management, Vo1. 42, No. 4, pp. 59–69, Summer of 2016.
2    For additional metrics see:
http://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.distance.p
dist.html
http://docs.scipy.org/doc/scipy-
0.16.0/reference/generated/scipy.cluster.hierarchy.linkage.html
PART 4
Useful Financial Features
1. Chapter 17 Structural Breaks
2. Chapter 18 Entropy Features
3. Chapter 19 Microstructural Features
CHAPTER 17
Structural Breaks
17.1 Motivation
In developing an ML-based investment strategy, we typically wish to bet when
there is a confluence of factors whose predicted outcome offers a favorable
risk-adjusted return. Structural breaks, like the transition from one market
regime to another, is one example of such a confluence that is of particul

---

many profitable strategies, because the actors on the losing side will typically
become aware of their mistake once it is too late. Before they accept their
losses, they will act irrationally, try to hold the position, and hope for a
comeback. Sometimes they will even increase a losing position, in desperation.
Eventually they will be forced to stop loss or stop out. Structural breaks offer
some of the best risk/rewards. In this chapter, we will review some methods
that measure the likelihood of structural breaks, so that informative features
can be built upon them.
17.2 Types of Structural Break Tests
We can classify structural break tests in two general categories:
CUSUM tests: These test whether the cumulative forecasting errors
significantly deviate from white noise.
Explosiveness tests: Beyond deviation from white noise, these test
whether the process exhibits exponential growth or collapse, as this is
inconsistent with a random walk or stationary process, and it is
unsustainable 

### Code Examples

```unknown
use the actors on the losing side will typically
```

---

which is fit on subsamples ([1, k + 1], [1, k + 2], …, [1, T ]), giving T − k least
squares estimates 
 . We can compute the standardized 1-step ahead
recursive residuals as
The CUSUM statistic is defined as
Under the null hypothesis that β is some constant value, H 0 : β t = β, then S t ∼
N [0, t − k − 1]. One caveat of this procedure is that the starting point is chosen
arbitrarily, and results may be inconsistent due to that.
17.3.2 Chu-Stinchcombe-White CUSUM Test on Levels
This test follows Homm and Breitung [2012]. It simplifies the previous method
by dropping { x t } t = 1, …, T , and assuming that H 0 : β t = 0, that is, we forecast
no change (E t − 1 [Δ y t ] = 0). This will allow us to work directly with y t levels,
hence reducing the computational burden. We compute the standardized
departure of log-price y t relative to the log-price at y n , t > n , as

---

Under the null hypothesis H 0 : β t = 0, then S n , t ∼ N [0, 1]. The time-dependent
critical value for the one-sided test is
These authors derived via Monte Carlo that b 0.05 = 4.6. One disadvantage of
this method is that the reference level y n is set somewhat arbitrarily. To
overcome this pitfall, we could estimate S n , t on a series of backward-shifting
windows n ∈ [1, t ], and pick 
 .
17.4 Explosiveness Tests
Explosiveness tests can be generally divided between those that test for one
bubble and those that test for multiple bubbles. In this context, bubbles are not
limited to price rallies, but they also include sell-offs. Tests that allow for
multiple bubbles are more robust in the sense that a cycle of bubble-burst-
bubble will make the series appear to be stationary to single-bubble tests.
Maddala and Kim [1998], and Breitung [2014] offer good overviews of the
literature.
17.4.1 Chow-Type Dickey-Fuller Test
A family of explosiveness tests was inspired by the work of Gregory C

### Code Examples

```unknown
include sell-offs. Tests that allow for
use they cannot effectively distinguish between a stationary process and a
```

---

fit the following specification,
where D t [τ*] is a dummy variable that takes zero value if t < τ* T , and takes
the value one if t ≥ τ* T . Then, the null hypothesis H 0 : δ = 0 is tested against
the (one-sided) alternative H 1 : δ > 1:
The main drawback of this method is that τ* is unknown. To address this issue,
Andrews [1993] proposed a new test where all possible τ* are tried, within
some interval τ* ∈ [τ 0 , 1 − τ 0 ]. As Breitung [2014] explains, we should leave
out some of the possible τ* at the beginning and end of the sample, to ensure
that either regime is fitted with enough observations (there must be enough
zeros and enough ones in D t [τ*]). The test statistic for an unknown τ* is the
maximum of all T (1 − 2τ 0 ) values of 
 .
Another drawback of Chow's approach is that it assumes that there is only one
break date τ* T , and that the bubble runs up to the end of the sample (there is
no switch back to a random walk). For situations where three or more regimes
(random walk

---

where we test for H 0 : β ≤ 0, H 1 : β > 0. Inspired by Andrews [1993], Phillips
and Yu [2011] and Phillips, Wu and Yu [2011] proposed the Supremum
Augmented Dickey-Fuller test (SADF). SADF fits the above regression at each
end point t with backwards expanding start points, then computes
where 
 is estimated on a sample that starts at t 0 and ends at t , τ is the
minimum sample length used in the analysis, t 0 is the left bound of the
backwards expanding window, and t = τ, …, T . For the estimation of SADF t ,
the right side of the window is fixed at t . The standard ADF test is a special
case of SADF t , where τ = t − 1.
There are two critical differences between SADF t and SDFC: First, SADF t is
computed at each t ∈ [τ, T ], whereas SDFC is computed only at T . Second,
instead of introducing a dummy variable, SADF recursively expands the
beginning of the sample ( t 0 ∈ [1, t − τ]). By trying all combinations of a
nested double loop on ( t 0 , t ), SADF does not assume a known number 

### Code Examples

```unknown
used in the analysis, t 0 is the left bound of the
```

---

Figure 17.1 Prices (left y-axis) and SADF (right y-axis) over time
17.4.2.1 Raw vs. Log Prices
It is common to find in the literature studies that carry out structural break tests
on raw prices. In this section we will explore why log prices should be
preferred, particularly when working with long time series involving bubbles
and bursts.
For raw prices { y t }, if ADF's null hypotesis is rejected, it means that prices
are stationary, with finite variance. The implication is that returns 
 are
not time invariant, for returns’ volatility must decrease as prices rise and
increase as prices fall in order to keep the price variance constant. When we
run ADF on raw prices, we assume that returns’ variance is not invariant to
price levels. If returns variance happens to be invariant to price levels, the
model will be structurally heteroscedastic.
In contrast, if we work with log prices, the ADF specification will state that

---

Let us make a change of variable, x t = ky t . Now, log[ x t ] = log[ k ] + log[ y t ],
and the ADF specification will state that
Under this alternative specification based on log prices, price levels condition
returns’ mean, not returns’ volatility. The difference may not matter in practice
for small samples, where k ≈ 1, but SADF runs regressions across decades and
bubbles produce levels that are significantly different between regimes ( k ≠ 1).
17.4.2.2 Computational Complexity
The algorithm runs in 
 , as the number of ADF tests that SADF requires
for a total sample length T is
Consider a matrix representation of the ADF specification, where 
and 
 . Solving a single ADF regression involves the floating point
operations (FLOPs) listed in Table 17.1 .
Table 17.1 FLOPs per ADF Estimate
Matrix Operation
FLOPs
o 1 = X 'y
(2T − 1)N
o 2 = X 'X
(2T − 1)N 2
o 3 = o − 1 
2
N 3 + N 2 + N
o 4 = o 3 o 1
2N 2 − N
o 5 = y − Xo 4
T + (2N − 1)T
o 6 = o ' 
5 o 5
2T − 1
2 + N 2

---

1
This gives a total of f ( N , T ) = N 3 + N 2 (2 T + 3) + N (4 T − 1) + 2 T + 2
FLOPs per ADF estimate. A single SADF update requires
 FLOPs ( T − τ operations to find the maximum
ADF stat), and the estimation of a full SADF series requires 
 .
Consider a dollar bar series on E-mini S&P 500 futures. For ( T , N ) =
(356631, 3), an ADF estimate requires 11,412,245 FLOPs, and a SADF update
requires 2,034,979,648,799 operations (roughly 2.035 TFLOPs). A full SADF
time series requires 241,910,974,617,448,672 operations (roughly 242
PFLOPs). This number will increase quickly, as the T continues to grow. And
this estimate excludes notoriously expensive operations like alignment, pre-
processing of data, I/O jobs, etc. Needless to say, this algorithm's double loop
requires a large number of operations. An HPC cluster running an efficiently
parallelized implementation of the algorithm may be needed to estimate the
SADF series within a reasonable amount of time. Chapter 20 will present some
p

### Code Examples

```sql
requires 11,412,245 FLOPs, and a SADF update
requires 2,034,979,648,799 operations (roughly 2.035 TFLOPs). A full SADF
```

```unknown
requires 241,910,974,617,448,672 operations (roughly 242
```

```unknown
requires a large number of operations. An HPC cluster running an efficiently
```

---

Explosive: β > 0, where 
 .
17.4.2.4 Quantile ADF
SADF takes the supremum of a series on t-values,
 . Selecting the extreme value introduces some
robustness problems, where SADF estimates could vary significantly
depending on the sampling frequency and the specific timestamps of the
samples. A more robust estimator of ADF extrema would be the following:
First, let 
 . Second, we define Q t , q = Q [ s t , q ] the q
quantile of s t , as a measure of centrality of high ADF values, where q ∈ [0,
1]. Third, we define 
 , with 0 < v ≤ min{ q , 1 − q }, as a
measure of dispersion of high ADF values. For example, we could set q = 0.95
and v = 0.025. Note that SADF is merely a particular case of QADF, where
SADF t = Q t , 1 and 
 is not defined because q = 1.
17.4.2.5 Conditional ADF
Alternatively, we can address concerns on SADF robustness by computing
conditional moments. Let f [ x ] be the probability distribution function of
 , with x ∈ s t . Then, we define C t , q = K − 1 ∫ ∞ 
Qt , q xf 

---

