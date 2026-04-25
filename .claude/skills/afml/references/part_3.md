# PART 3

PART 3
Backtesting
1. Chapter 10 Bet Sizing
2. Chapter 11 The Dangers of Backtesting
3. Chapter 12 Backtesting through Cross-Validation
4. Chapter 13 Backtesting on Synthetic Data
5. Chapter 14 Backtest Statistics
6. Chapter 15 Understanding Strategy Risk
7. Chapter 16 Machine Learning Asset Allocation
CHAPTER 10
Bet Sizing
10.1 Motivation
There are fascinating parallels between strategy games and investing. Some of
the best portfolio managers I have worked with are excellent poker players,
perhaps more so than chess players. One reason is bet sizing, for which Texas
Hold'em provides a great analogue and training ground. Your ML algorithm
can achieve high accuracy, but if you do not size your bets properly, your
investment strategy will inevitably lose money. In this chapter we will review a
few approaches to size bets from ML predictions.
10.2 Strategy-Independent Bet Sizing Approaches
Consider two strategies on the same instrument. Let m i , t ∈ [ − 1, 1] be the bet
size of strategy 

---

(the price increased by 25% between p 1 and p 3 ), however the first strategy
made money (0.5) while the second strategy lost money (−.125).
We would prefer to size positions in such way that we reserve some cash for
the possibility that the trading signal strengthens before it weakens. One option
is to compute the series c t = c t , l − c t , s , where c t , l is the number of
concurrent long bets at time t , and c t , s is the number of concurrent short bets
at time t. This bet concurrency is derived, for each side, similarly to how we
computed label concurrency in Chapter 4 (recall the t1 object, with
overlapping time spans). We fit a mixture of two Gaussians on { c t }, applying
a method like the one described in López de Prado and Foreman [2014]. Then,
the bet size is derived as
where F [ x ] is the CDF of the fitted mixture of two Gaussians for a value x .
For example, we could size the bet as 0.9 when the probability of observing a
signal of greater value is only 0.1. The strong

### Code Examples

```unknown
use that probability to derive the bet size. 1 This
```

---

features predictive of false positives (see Chapter 3). Second, the predicted
probability can be directly translated into bet size. Let us see how.
10.3 Bet Sizing from Predicted Probabilities
Let us denote p [ x ] the probability that label x takes place. For two possible
outcomes, x ∈ { − 1, 1}, we would like to test the null hypothesis
 . We compute the test statistic
 , with z ∈ ( − ∞, +∞) and where Z
represents the standard Normal distribution. We derive the bet size as m = 2 Z [
z ] − 1, where m ∈ [ − 1, 1] and Z [.] is the CDF of Z .
For more than two possible outcomes, we follow a one-versus-rest method. Let
X = { − 1, …, 0, …, 1} be various labels associated with bet sizes, and x ∈ X
the predicted label. In other words, the label is identified by the bet size
associated with it. For each label i = 1, …, || X ||, we estimate a probability p i ,
with 
 . We define 
 as the probability of x , and we
would like to test for 
 . 2 We compute the test statistic
 , with z ∈ [0., . + ∞

---

Figure 10.1 Bet size from predicted probabilities
SNIPPET 10.1 FROM PROBABILITIES TO BET SIZE
10.4 Averaging Active Bets

---

Every bet is associated with a holding period, spanning from the time it
originated to the time the first barrier is touched, t1 (see Chapter 3). One
possible approach is to override an old bet as a new bet arrives; however, that
is likely to lead to excessive turnover. A more sensible approach is to average
all sizes across all bets still active at a given point in time. Snippet 10.2
illustrates one possible implementation of this idea.
SNIPPET 10.2 BETS ARE AVERAGED AS LONG AS THEY ARE
STILL ACTIVE
10.5 Size Discretization

---

Averaging reduces some of the excess turnover, but still it is likely that small
trades will be triggered with every prediction. As this jitter would cause
unnecessary overtrading, I suggest you discretize the bet size as
 , where d ∈ (0, ..1] determines the degree of discretization.
Figure 10.2 illustrates the discretization of the bet size. Snippet 10.3
implements this notion.
Figure 10.2 Discretization of the bet size, d = 0.2
SNIPPET 10.3 SIZE DISCRETIZATION TO PREVENT
OVERTRADING

---

10.6 Dynamic Bet Sizes and Limit Prices
Recall the triple-barrier labeling method presented in Chapter 3. Bar i is
formed at time t i , 0 , at which point we forecast the first barrier that will be
touched. That prediction implies a forecasted price, 
 , consistent with
the barriers’ settings. In the period elapsed until the outcome takes place, t ∈ [
t i , 0 , t i , 1 ], the price p t fluctuates and additional forecasts may be formed,
 , where j ∈ [ i + 1, I ] and t j , 0 ≤ t i , 1 . In Sections 10.4 and 10.5 we
discussed methods for averaging the active bets and discretizing the bet size as
new forecasts are formed. In this section we will introduce an approach to
adjust bet sizes as market price p t and forecast price f i fluctuate. In the process,
we will derive the order's limit price.
Let q t be the current position, Q the maximum absolute position size, and 
the target position size associated with forecast f i , such that
where m [ω, x ] is the bet size, x = f i − p t is the di

### Code Examples

```unknown
use the algorithm wants to realize
user-defined pair ( x , m *), such that x = f i − p t and
```

---

We do not need to worry about the case m 2 = 1, because 
 . Since this
function is monotonic, the algorithm cannot realize losses as p t → f i .
Let us calibrate ω. Given a user-defined pair ( x , m *), such that x = f i − p t and
m * = m [ω, x ], the inverse function of m [ω, x ] with respect to ω is
Snippet 10.4 implements the algorithm that computes the dynamic position size
and limit prices as a function of p t and f i . First, we calibrate the sigmoid
function, so that it returns a bet size of m * = .95 for a price divergence of x =
10 . Second, we compute the target position 
 for a maximum position Q =
100, f i = 115 and p t = 100 . If you try f i = 110, you will get 
 ,
consistent with the calibration of ω. Third, the limit price for this order of size
 is p t < 112.3657 < f i , which is between the current price and the
forecasted price.
SNIPPET 10.4 DYNAMIC POSITION SIZE AND LIMIT PRICE

---

As an alternative to the sigmoid function, we could have used a power function
 , where ω ≥ 0, x ∈ [ − 1, 1], which results in
 . This alternative presents the advantages that:

### Code Examples

```unknown
used a power function
```

---

.
Curvature can be directly manipulated through ω.
For ω > 1, the function goes from concave to convex, rather than the other
way around, hence the function is almost flat around the inflexion point.
We leave the derivation of the equations for a power function as an exercise.
Figure 10.3 plots the bet sizes (y-axis) as a function of price divergence f − p t
(x-axis) for both the sigmoid and power functions.
Figure 10.3 f [x ] = sgn [x ]|x | 2 (concave to convex) and f [x ] = x (.1 + x 2 ) − .5
(convex to concave)
Exercises
1. 
Using the formulation in Section 10.3, plot the bet size ( m ) as a
function of the maximum predicted probability ( 
 when || X || =
2, 3, …, 10.

---

