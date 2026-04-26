# 1. Survivorship bias: Using as investment universe the current one, hence

1. Survivorship bias: Using as investment universe the current one, hence
ignoring that some companies went bankrupt and securities were delisted
along the way.
2. Look-ahead bias: Using information that was not public at the moment
the simulated decision would have been made. Be certain about the
timestamp for each data point. Take into account release dates,
distribution delays, and backfill corrections.
3. Storytelling: Making up a story ex-post to justify some random pattern.
4. Data mining and data snooping: Training the model on the testing set.
5. Transaction costs: Simulating transaction costs is hard because the only
way to be certain about that cost would have been to interact with the
trading book (i.e., to do the actual trade).
6. Outliers: Basing a strategy on a few extreme outcomes that may never
happen again as observed in the past.
7. Shorting: Taking a short position on cash products requires finding a
lender. The cost of lending and the amount available is generally
u

### Code Examples

```julia
include computing performance using a non-
```

```unknown
use of the title of the next section.
```

```unknown
use only an expert can
```

---

false discovery, a statistical fluke that inevitably comes up after you run
multiple tests on the same dataset.
The maddening thing about backtesting is that, the better you become at it, the
more likely false discoveries will pop up. Beginners fall for the seven sins of
Luo et al. [2014] (there are more, but who's counting?). Professionals may
produce flawless backtests, and will still fall for multiple testing, selection bias,
or backtest overfitting (Bailey and López de Prado [2014b]).
11.4 Backtesting Is Not a Research Tool
Chapter 8 discussed substitution effects, joint effects, masking, MDI, MDA,
SFI, parallelized features, stacked features, etc. Even if some features are very
important, it does not mean that they can be monetized through an investment
strategy. Conversely, there are plenty of strategies that will appear to be
profitable even though they are based on irrelevant features. Feature
importance is a true research tool, because it helps us understand the nature of
the 

### Code Examples

```unknown
importance is a true research tool, because it helps us understand the nature of
```

```unknown
importance is derived ex-ante , before the historical
```

```unknown
importance, bet sizing, etc. By the time
use if there was an easy answer to this
```

---

fully specified. If the backtest fails, start all over. If you do that, the chances of
finding a false discovery will drop substantially, but still they will not be zero.
11.5 A Few General Recommendations
Backtest overfitting can be defined as selection bias on multiple backtests.
Backtest overfitting takes place when a strategy is developed to perform well
on a backtest, by monetizing random historical patterns. Because those random
patterns are unlikely to occur again in the future, the strategy so developed will
fail. Every backtested strategy is overfit to some extent as a result of “selection
bias”: The only backtests that most people share are those that portray
supposedly winning investment strategies.
How to address backtest overfitting is arguably the most fundamental question
in quantitative finance. Why? Because if there was an easy answer to this
question, investment firms would achieve high performance with certainty, as
they would invest only in winning backtests. Journa

### Code Examples

```unknown
use those random
use the random sampling will
```

---

the Sharpe ratio may be properly deflated by the number of trials carried
out (Bailey and López de Prado [2014b]).
5. Simulate scenarios rather than history (Chapter 12). A standard backtest is
a historical simulation, which can be easily overfit. History is just the
random path that was realized, and it could have been entirely different.
Your strategy should be profitable under a wide range of scenarios, not
just the anecdotal historical path. It is harder to overfit the outcome of
thousands of “what if” scenarios.
6. If the backtest fails to identify a profitable strategy, start from scratch.
Resist the temptation of reusing those results. Follow the Second Law of
Backtesting.
SNIPPET 11.1 MARCOS’ SECOND LAW OF
BACKTESTING
“Backtesting while researching is like drinking and driving. Do not
research under the influence of a backtest.”
Marcos López de Prado Advances in Financial Machine Learning (2018)
11.6 Strategy Selection
In Chapter 7 we discussed how the presence of serial condit

### Code Examples

```unknown
used to train the model. See Arlot and Celisse [2010] for a survey.
used to choose the “optimal” strategy can be
```

---

that can be repeated over and over until a false positive appears. Like in
standard CV, some randomization is needed to avoid this sort of performance
targeting or backtest optimization, while avoiding the leakage of examples
correlated to the training set into the testing set. Next, we will introduce a CV
method for strategy selection, based on the estimation of the probability of
backtest overfitting (PBO). We leave for Chapter 12 an explanation of CV
methods for backtesting.
Bailey et al. [2017a] estimate the PBO through the combinatorially symmetric
cross-validation (CSCV) method. Schematically, this procedure works as
follows.
First, we form a matrix M by collecting the performance series from the N
trials. In particular, each column n = 1, …, N represents a vector of PnL (mark-
to-market profits and losses) over t = 1, …, T observations associated with a
particular model configuration tried by the researcher. M is therefore a real-
valued matrix of order ( TxN ). The only conditi

---

For instance, if S = 16 , we will form 12,780 combinations. Each combination
c ∈ C S is composed of 
 submatrices M s .
Fourth, for each combination c ∈ C S , we:
1. Form the training set J , by joining the 
 submatrices M s that constitute
c. J is a matrix of order 
 .
2. Form the testing set  , as the complement of J in M. In other words,  is
the 
 matrix formed by all rows of M that are not part of J.
3. Form a vector R of performance statistics of order N , where the n -th item
of R reports the performance associated with the n -th column of J (the
training set).
4. Determine the element n * such that 
 , ∀n = 1, …, N . In other
words, 
 .
5. Form a vector  of performance statistics of order N , where the n -th item
of  reports the performance associated with the n -th column of  (the
testing set).
6. Determine the relative rank of 
 within  . We denote this relative rank
as 
 , where 
 . This is the relative rank of the out-of-sample
(OOS) performance associated with the trial cho

### Code Examples

```javascript
function f (λ) is then estimated as the relative
frequency at which λ occurred across all C S , with 
 . Finally, the
PBO is estimated as 
 , as that is the probability associated
with IS optimal strategies that underperform OOS.
The x-axis of Figure 11.1 shows the Sharpe ratio IS from the best strategy
selected. The y-axis shows the Sharpe ratio OOS for that same best strategy
selected. As it can be appreciated, there is a strong and persistent performance
decay, caused by backtest overfitting. Applying the above algorithm, we can
```

```unknown
used by backtest overfitting. Applying the above algorithm, we can
```

---

derive the PBO associated with this strategy selection process, as displayed in
Figure 11.2 .
Figure 11.1 Best Sharpe ratio in-sample (SR IS) vs Sharpe ratio out-of-sample
(SR OOS)

---

Figure 11.2 Probability of backtest overfitting derived from the distribution of
logits
The observations in each subset preserve the original time sequence. The
random sampling is done on the relatively uncorrelated subsets, rather than on
the observations. See Bailey et al. [2017a] for an experimental analysis of the
accuracy of this methodology.
Exercises
1. 
An analyst fits an RF classifier where some of the features
include seasonally adjusted employment data. He aligns with
January data the seasonally adjusted value of January, etc. What
“sin” has he committed?
2. 
An analyst develops an ML algorithm where he generates a
signal using closing prices, and executed at close. What's the

### Code Examples

```unknown
include seasonally adjusted employment data. He aligns with
```

---

sin?
3. 
There is a 98.51% correlation between total revenue generated
by arcades and computer science doctorates awarded in the
United States. As the number of doctorates is expected to grow,
should we invest in arcades companies? If not, what's the sin?
4. 
The Wall Street Journal has reported that September is the only
month of the year that has negative average stock returns,
looking back 20, 50, and 100 years. Should we sell stocks at the
end of August? If not, what's the sin?
5. 
We download P/E ratios from Bloomberg, rank stocks every
month, sell the top quartile, and buy the long quartile.
Performance is amazing. What's the sin?
References
1. Arlot, S. and A. Celisse (2010): “A survey of cross-validation procedures
for model selection.” Statistics Surveys , Vol. 4, pp. 40–79.
2. Bailey, D., J. Borwein, M. López de Prado, and J. Zhu (2014): “Pseudo-
mathematics and financial charlatanism: The effects of backtest
overfitting on out-of-sample performance.” Notices of the American


---

http://www.iijournals.com/doi/pdfplus/10.3905/jpm .2017.43.4.005 .
8. Luo, Y., M. Alvarez, S. Wang, J. Jussa, A. Wang, and G. Rohal (2014):
“Seven sins of quantitative investing.” White paper, Deutsche Bank
Markets Research, September 8.
9. Sarfati, O. (2015): “Backtesting: A practitioner's guide to assessing
strategies and avoiding pitfalls.” Citi Equity Derivatives. CBOE 2015
Risk Management Conference. Available at
https://www.cboe.com/rmc/2015/olivier-pdf-Backtesting-Full.pdf .
Bibliography
1. Bailey, D., J. Borwein, and M. López de Prado (2016): “Stock portfolio
design and backtest overfitting.” Journal of Investment Management , Vol.
15, No. 1, pp. 1–13. Available at https://ssrn.com/abstract=2739335 .
2. Bailey, D., J. Borwein, M. López de Prado, A. Salehipour, and J. Zhu
(2016): “Backtest overfitting in financial markets.” Automated Trader ,
Vol. 39. Available at https://ssrn.com/abstract=2731886 .
3. Bailey, D., J. Borwein, M. López de Prado, and J. Zhu (2017b):
“Mathematical 

---

