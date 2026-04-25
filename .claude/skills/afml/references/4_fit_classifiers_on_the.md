# 4. Fit classifiers on the

4. Fit classifiers on the 
 training sets, and produce forecasts on the
respective 
 testing sets.
5. Compute the φ[N , k ] backtest paths. You can calculate one Sharpe ratio
from each path, and from that derive the empirical distribution of the
strategy's Sharpe ratio (rather than a single Sharpe ratio, like WF or CV).
12.4.3 A Few Examples
For k = 1, we will obtain φ[ N , 1] = 1 path, in which case CPCV reduces to
CV. Thus, CPCV can be understood as a generalization of CV for k > 1 .
For k = 2, we will obtain φ[ N , 2] = N − 1 paths. This is a particularly
interesting case, because while training the classifier on a large portion of the
data, θ = 1 − 2/ N , we can generate almost as many backtest paths as the
number of groups, N − 1 . An easy rule of thumb is to partition the data into N
= φ + 1 groups, where φ is the number of paths we target, and then form 
combinations. In the limit, we can assign one group per observation, N = T ,
and generate φ[ T , 2] = T − 1 paths, while train

### Code Examples

```unknown
use while training the classifier on a large portion of the
```

---

like a martingale, with Sharpe ratios { y i } i = 1, …, I , E[ y i ] = 0, σ 2 [ y i ] > 0,
and 
 . Even though the true Sharpe ratio is zero, we expect to find one
strategy with a Sharpe ratio of
WF backtests exhibit high variance, σ[ y i ] ≫ 0, for at least one reason: A large
portion of the decisions are based on a small portion of the dataset. A few
observations will have a large weight on the Sharpe ratio. Using a warm-up
period will reduce the backtest length, which may contribute to making the
variance even higher. WF's high variance leads to false discoveries, because
researchers will select the backtest with the maximum estimated Sharpe ratio,
even if the true Sharpe ratio is zero. That is the reason it is imperative to
control for the number of trials (I) in the context of WF backtesting. Without
this information, it is not possible to determine the Family-Wise Error Rate
(FWER), False Discovery Rate (FDR), Probability of Backtest Overfitting
(PBO, see Chapter 11) or similar m

---

The more uncorrelated the paths are, 
 , the lower CPCV's variance will
be, and in the limit CPCV will report the true Sharpe ratio E[ y i ] with zero
variance, 
 . There will not be selection bias, because the
strategy selected out of i = 1, …, I will be the one with the highest true Sharpe
ratio.
Of course, we know that zero variance is unachievable, since φ has an upper
bound, 
 . Still, for a large enough number of paths φ, CPCV could
make the variance of the backtest so small as to make the probability of a false
discovery negligible.
In Chapter 11, we argued that backtest overfitting may be the most important
open problem in all of mathematical finance. Let us see how CPCV helps
address this problem in practice. Suppose that a researcher submits a strategy
to a journal, supported by an overfit WF backtest, selected from a large number
of undisclosed trials. The journal could ask the researcher to repeat his
experiments using a CPCV for a given N and k . Because the researcher did

### Code Examples

```unknown
use the researcher did not
```

```unknown
used to reduce the
```

---

3. 
Your strategy achieves a Sharpe ratio of 1.5 on a WF backtest,
but a Sharpe ratio of 0.7 on a CV backtest. You go ahead and
present only the result with the higher Sharpe ratio, arguing that
the WF backtest is historically accurate, while the CV backtest
is a scenario simulation, or an inferential exercise. Is this
selection bias?
4. 
Your strategy produces 100,000 forecasts over time. You would
like to derive the CPCV distribution of Sharpe ratios by
generating 1,000 paths. What are the possible combinations of
parameters ( N , k ) that will allow you to achieve that?
5. 
You discover a strategy that achieves a Sharpe ratio of 1.5 in a
WF backtest. You write a paper explaining the theory that would
justify such result, and submit it to an academic journal. The
editor replies that one referee has requested you repeat your
backtest using a CPCV method with N = 100 and k = 2,
including your code and full datasets. You follow these
instructions, and the mean Sharpe ratio is –1 with a 

---

overfitting on out-of-sample performance.” Notices of the American
Mathematical Society , Vol. 61, No. 5, pp. 458–471. Available at
http://ssrn.com/abstract=2308659 .
4. Bailey, D., J. Borwein, M. López de Prado, and J. Zhu (2017): “The
probability of backtest overfitting.” Journal of Computational Finance ,
Vol. 20, No. 4, pp. 39–70. Available at https://ssrn.com/abstract=2326253
.
CHAPTER 13
Backtesting on Synthetic Data
13.1 Motivation
In this chapter we will study an alternative backtesting method, which uses
history to generate a synthetic dataset with statistical characteristics estimated
from the observed data. This will allow us to backtest a strategy on a large
number of unseen, synthetic testing sets, hence reducing the likelihood that the
strategy has been fit to a particular set of datapoints. 1 This is a very extensive
subject, and in order to reach some depth we will focus on the backtesting of
trading rules.
13.2 Trading Rules
Investment strategies can be defined as algo

### Code Examples

```unknown
use fundamental and accounting information to price securities, or
```

```unknown
requires an implementation tactic, often referred to as “trading rules.”
use these parameters target specific observations in-
```

---

must be followed to enter and exit a position. For example, a position will be
entered when the strategy's signal reaches a certain value. Conditions for
exiting a position are often defined through thresholds for profit-taking and
stop-losses. These entry and exit rules rely on parameters that are usually
calibrated via historical simulations. This practice leads to the problem of
backtest overfitting , because these parameters target specific observations in-
sample, to the point that the investment strategy is so attached to the past that it
becomes unfit for the future.
An important clarification is that we are interested in the exit corridor
conditions that maximize performance. In other words, the position already
exists, and the question is how to exit it optimally. This is the dilemma often
faced by execution traders, and it should not be mistaken with the
determination of entry and exit thresholds for investing in a security. For a
study of that alternative question, see, for 

### Code Examples

```unknown
important clarification is that we are interested in the exit corridor
```

```unknown
useful tool to discard superfluous investment strategies, it would
use we count with two
```

---

observed in the market after t transactions. Accordingly, we can compute the
MtM profit/loss of opportunity i after t transactions as π i , t = m i ( P i , t − P i , 0 ).
A standard trading rule provides the logic for exiting opportunity i at t = T i .
This occurs as soon as one of two conditions is verified:
 , where 
 is the profit-taking threshold.
 , where 
 is the stop-loss threshold.
These thresholds are equivalent to the horizontal barriers we discussed in the
context of meta-labelling (Chapter 3). Because 
 , one and only one of the
two exit conditions can trigger the exit from opportunity i. Assuming that
opportunity i can be exited at T i , its final profit/loss is 
 . At the onset of
each opportunity, the goal is to realize an expected profit
 , where 
 is the forecasted price and P i , 0
is the entry level of opportunity i.
Definition 1: Trading Rule: A trading rule for strategy S is defined by the
set of parameters 
 .
One way to calibrate (by brute force) the trading rule

---

variables to maximize SR R over a sample of size I , it is easy to overfit R. A
trivial overfit occurs when a pair 
 targets a few outliers. Bailey et al.
[2017] provide a rigorous definition of backtest overfitting, which can be
applied to our study of trading rules as follows.
Definition 2: Overfit Trading Rule: R * is overfit if
 , where j = I + 1, … J and Me Ω [.]
is the median.
Intuitively, an optimal in-sample (IS, i ∈ [1, I ]) trading rule R * is overfit
when it is expected to underperform the median of alternative trading rules R
∈ Ω out-of-sample (OOS, j ∈ [ I + 1, J ]). This is essentially the same
definition we used in chapter 11 to derive PBO. Bailey et al. [2014] argue that
it is hard not to overfit a backtest, particularly when there are free variables
able to target specific observations IS, or the number of elements in Ω is large.
A trading rule introduces such free variables, because R * can be determined
independently from S. The outcome is that the backtest profits f

### Code Examples

```unknown
used in chapter 11 to derive PBO. Bailey et al. [2014] argue that
```

```unknown
useful method to evaluate to what extent a
```

```unknown
use R * can be determined
used an O-U specification to characterize the
```

---

= m i ( P i , t − P i , 0 ), equation ( 13.2 ) implies that the performance of
opportunity i is characterized by the process
(13.3)
From the proof to Proposition 4 in Bailey and López de Prado [2013], it can be
shown that the distribution of the process specified in equation ( 13.2 ) is
Gaussian with parameters
(13.4)
and a necessary and sufficient condition for its stationarity is that φ ∈ ( − 1, 1).
Given a set of input parameters {σ, φ} and initial conditions 
associated with opportunity i , is there an OTR 
 ? Similarly, should
strategy S predict a profit target  , can we compute the optimal stop-loss 
given the input values {σ, φ}? If the answer to these questions is affirmative,
no backtest would be needed in order to determine R *, thus avoiding the
problem of overfitting the trading rule. In the next section we will show how to
answer these questions experimentally.
13.5 Numerical Determination of Optimal Trading Rules
In the previous section we used an O-U specification to cha

---

We can then form vectors X and Y by sequencing opportunities:
(13.6)
Applying OLS on equation ( 13.5 ), we can estimate the original O-U
parameters as,
(13.7)
where cov[ ·, ·] is the covariance operator.
Step 2 : We construct a mesh of stop-loss and profit-taking pairs, 
 .
For example, a Cartesian product of 
 and
 give us 20 × 20 nodes, each constituting an
alternative trading rule R ∈ Ω.
Step 3 : We generate a large number of paths (e.g., 100,000) for π i , t
applying our estimates 
 . As seed values, we use the observed initial
conditions 
 associated with an opportunity i. Because a
position cannot be held for an unlimited period of time, we can impose a
maximum holding period (e.g., 100 observations) at which point the
position is exited even though 
 . This maximum holding
period is equivalent to the vertical bar of the triple-barrier method
(Chapter 3). 3
Step 4 : We apply the 100,000 paths generated in Step 3 on each node of
the 20 × 20 mesh 
 generated in Step 2. For each nod

### Code Examples

```unknown
use the observed initial
```

---

