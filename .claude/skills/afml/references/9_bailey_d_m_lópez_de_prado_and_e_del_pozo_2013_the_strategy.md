# 9. Bailey, D., M. López de Prado, and E. del Pozo (2013): “The strategy

9. Bailey, D., M. López de Prado, and E. del Pozo (2013): “The strategy
approval decision: A Sharpe ratio indifference curve approach.”
Algorithmic Finance , Vol. 2, No. 1, pp. 99–109. Available at
https://ssrn.com/abstract=2003638 .
10. Carr, P. and M. López de Prado (2014): “Determining optimal trading
rules without backtesting.” Working paper. Available at
https://ssrn.com/abstract=2658641 .
11. López de Prado, M. (2012a): “Portfolio oversight: An evolutionary
approach.” Lecture at Cornell University. Available at
https://ssrn.com/abstract=2172468 .
12. López de Prado, M. (2012b): “The sharp razor: Performance evaluation
with non-normal returns.” Lecture at Cornell University. Available at
https://ssrn.com/abstract=2150879 .
13. López de Prado, M. (2013): “What to look for in a backtest.” Lecture at
Cornell University. Available at https://ssrn.com/abstract=2308682 .
14. López de Prado, M. (2014a): “Optimal trading rules without backtesting.”
Lecture at Cornell University. Available

---

No. 4, pp. 59–69. Available at https://ssrn.com/ abstract=2708678 .
23. López de Prado, M. and M. Foreman (2014): “A mixture of Gaussians
approach to mathematical portfolio oversight: The EF3M algorithm.”
Quantitative Finance , Vol. 14, No. 5, pp. 913–930. Available at
https://ssrn.com/abstract=1931734 .
24. López de Prado, M. and A. Peijan (2004): “Measuring loss potential of
hedge fund strategies.” Journal of Alternative Investments , Vol. 7, No. 1,
pp. 7–31, Summer 2004. Available at https://ssrn.com/abstract=641702 .
25. López de Prado, M., R. Vince, and J. Zhu (2015): “Risk adjusted growth
portfolio in a finite investment horizon.” Lecture at Cornell University.
Available at https://ssrn.com/abstract=2624329 .
Note
1     http://papers.ssrn.com/sol3/cf_dev/AbsByAuth.cfm?per_id=434076 ;
http://www.QuantResearch.org/ .
CHAPTER 12
Backtesting through Cross-Validation
12.1 Motivation
A backtest evaluates out-of-sample the performance of an investment strategy
using past observations. T

### Code Examples

```unknown
used in two ways: (1)
requires extreme knowledge of the data sources, market
```

---

performed in past. Each strategy decision is based on observations that predate
that decision. As we saw in Chapter 11, carrying out a flawless WF simulation
is a daunting task that requires extreme knowledge of the data sources, market
microstructure, risk management, performance measurement standards (e.g.,
GIPS), multiple testing methods, experimental mathematics, etc. Unfortunately,
there is no generic recipe to conduct a backtest. To be accurate and
representative, each backtest must be customized to evaluate the assumptions
of a particular strategy.
WF enjoys two key advantages: (1) WF has a clear historical interpretation. Its
performance can be reconciled with paper trading. (2) History is a filtration;
hence, using trailing data guarantees that the testing set is out-of-sample (no
leakage), as long as purging has been properly implemented (see Chapter 7,
Section 7.4.1). It is a common mistake to find leakage in WF backtests, where
t1.index falls within the training set, but t1

---

sell forecasts. The performance would be very different had we played the
information backwards, from January 1, 2017 to January 1, 2007 (a long rally
followed by a sharp sell-off). By exploiting a particular sequence, a strategy
selected by WF may set us up for a debacle.
The third disadvantage of WF is that the initial decisions are made on a smaller
portion of the total sample. Even if a warm-up period is set, most of the
information is used by only a small portion of the decisions. Consider a
strategy with a warm-up period that uses t 0 observations out of T. This strategy
makes half of its decisions 
 on an average number of datapoints,
which is only a 
 fraction of the observations. Although this problem is
attenuated by increasing the warm-up period, doing so also reduces the length
of the backtest.
12.3 The Cross-Validation Method
Investors often ask how a strategy would perform if subjected to a stress
scenario as unforeseeable as the 2008 crisis, or the dot-com bubble, or the

### Code Examples

```unknown
used by only a small portion of the decisions. Consider a
```

```unknown
uses t 0 observations out of T. This strategy
useful result in its
```

---

Advantages
1. The test is not the result of a particular (historical) scenario. In fact, CV
tests k alternative scenarios, of which only one corresponds with the
historical sequence.
2. Every decision is made on sets of equal size. This makes outcomes
comparable across periods, in terms of the amount of information used to
make those decisions.
3. Every observation is part of one and only one testing set. There is no
warm-up subset, thereby achieving the longest possible out-of-sample
simulation.
Disadvantages
1. Like WF, a single backtest path is simulated (although not the historical
one). There is one and only one forecast generated per observation.
2. CV has no clear historical interpretation. The output does not simulate
how the strategy would have performed in the past, but how it may
perform in the future under various stress scenarios (a useful result in its
own right).
3. Because the training set does not trail the testing set, leakage is possible.
Extreme care must be taken t

### Code Examples

```unknown
use the training set does not trail the testing set, leakage is possible.
included in the testing set, and leaves
```

---

Consider T observations partitioned into N groups without shuffling, where
groups n = 1, …, N − 1 are of size ⌊ T / N ⌋, the N th group is of size T − ⌊ T / N
⌋( N − 1), and ⌊.⌋ is the floor or integer function. For a testing set of size k
groups, the number of possible training/testing splits is
Since each combination involves k tested groups, the total number of tested
groups is 
 . And since we have computed all possible combinations,
these tested groups are uniformly distributed across all N (each group belongs
to the same number of training and testing sets). The implication is that from k
-sized testing sets on N groups we can backtest a total number of paths φ[ N , k
],
Figure 12.1 illustrates the composition of train/test splits for N = 6 and k = 2 .
There are 
 splits, indexed as S1, … ,S15. For each split, the figure
marks with a cross ( x ) the groups included in the testing set, and leaves
unmarked the groups that form the training set. Each group forms part of φ[6,
2] = 5 

---

G 2, S 1), ( G 3, S 2), ( G 4, S 3), ( G 5, S 4) and ( G 6, S 5). Path 2 is the result
of combining forecasts from ( G 1, S 2), ( G 2, S 6), ( G 3, S 6), ( G 4, S 7), ( G
5, S 8) and ( G 6, S 9), and so on.
Figure 12.2 Assignment of testing groups to each of the 5 paths
These paths are generated by training the classifier on a portion θ = 1 − k / N of
the data for each combination. Although it is theoretically possible to train on a
portion θ < 1/2, in practice we will assume that k ≤ N /2 . The portion of data in
the training set θ increases with N → T but it decreases with k → N /2 . The
number of paths φ[ N , k ] increases with N → T and with k → N /2 . In the
limit, the largest number of paths is achieved by setting N = T and k = N /2 = T
/2, at the expense of training the classifier on only half of the data for each
combination (θ = 1/2).
12.4.2 The Combinatorial Purged Cross-Validation Backtesting
Algorithm
In Chapter 7 we introduced the concepts of purging and embargoing in the


### Code Examples

```php
used to determine label y j . This class will also apply
```

```unknown
use these concepts for backtesting through CV. The
```

```unknown
PurgedKFold
```

---

