# 2. Bid-ask spread: The cost

2. Bid-ask spread: The cost 
 of buying or selling one unit of this virtual ETF is
 . When a unit is bought or sold, the strategy must charge this
cost  , which is the equivalent to crossing the bid-ask spread of this virtual ETF.
3. Volume: The volume traded {v t } is determined by the least active member in the
basket. Let v i , t be the volume traded by instrument i over bar t. The number of
tradeable basket units is 
 .
Transaction costs functions are not necessarily linear, and those non-linear costs can be
simulated by the strategy based on the above information. Thanks to the ETF trick, we can
model a basket of futures (or a single futures) as if it was a single non-expiring cash
product.
2.4.2 PCA Weights
The interested reader will find many practical ways of computing hedging weights in
López de Prado and Leinweber [2012] and Bailey and López de Prado [2012]. For the sake
of completeness, let us review one way to derive the vector {ω t } used in the previous
section. Consider 

### Code Examples

```unknown
user-defined risk distribution
user-defined risk distribution R is passed
```

---

Figure 2.2 Contribution to risk per principal component
Snippet 2.1 implements this method, where the user-defined risk distribution R is passed
through argument riskDist (optional None). If riskDist is None, the code will assume all
risk must be allocated to the principal component with smallest eigenvalue, and the
weights will be the last eigenvector re-scaled to match σ ( riskTarget ).
SNIPPET 2.1 PCA WEIGHTS FROM A RISK DISTRIBUTION R

---

2.4.3 Single Future Roll
The ETF trick can handle the rolls of a single futures contract, as a particular case of a 1-
legged spread. However, when dealing with a single futures contract, an equivalent and
more direct approach is to form a time series of cumulative roll gaps, and detract that gaps
series from the price series. Snippet 2.2 shows a possible implementation of this logic,
using a series of tick bars downloaded from Bloomberg and stored in a HDF5 table. The
meaning of the Bloomberg fields is as follows:
FUT_CUR_GEN_TICKER : It identifies the contract associated with that price. Its value
changes with every roll.
PX_OPEN : The open price associated with that bar.
PX_LAST : The close price associated with the bar.
VWAP : The volume-weighted average price associated with that bar.
The argument matchEnd in function rollGaps determines whether the futures series should
be rolled forward ( matchEnd=False ) or backward ( matchEnd=True ). In a forward roll,
the price at the start o

### Code Examples

```unknown
matchEnd=False
```

```unknown
matchEnd=True
```

```unknown
FUT_CUR_GEN_TICKER
```

---

Rolled prices are used for simulating PnL and portfolio mark-to-market values. However,
raw prices should still be used to size positions and determine capital consumption. Keep
in mind, rolled prices can indeed become negative, particularly in futures contracts that
sold off while in contango. To see this, run Snippet 2.2 on a series of Cotton #2 futures or
Natural Gas futures.
In general, we wish to work with non-negative rolled series, in which case we can derive
the price series of a $1 investment as follows: (1) Compute a time series of rolled futures
prices, (2) compute the return ( r ) as rolled price change divided by the previous raw price,
and (3) form a price series using those returns (i.e., (1+r).cumprod() ). Snippet 2.3
illustrates this logic.
SNIPPET 2.3 NON-NEGATIVE ROLLED PRICE SERIES

### Code Examples

```unknown
used for simulating PnL and portfolio mark-to-market values. However,
```

```unknown
used to size positions and determine capital consumption. Keep
```

```unknown
(1+r).cumprod()
```

---

2.5 Sampling Features
So far we have learned how to produce a continuous, homogeneous, and structured dataset
from a collection of unstructured financial data. Although you could attempt to apply an
ML algorithm on such a dataset, in general that would not be a good idea, for a couple of
reasons. First, several ML algorithms do not scale well with sample size (e.g., SVMs).
Second, ML algorithms achieve highest accuracy when they attempt to learn from relevant
examples. Suppose that you wish to predict whether the next 5% absolute return will be
positive (a 5% rally) or negative (a 5% sell-off). At any random time, the accuracy of such
a prediction will be low. However, if we ask a classifier to predict the sign of the next 5%
absolute return after certain catalytic conditions, we are more likely to find informative
features that will help us achieve a more accurate prediction. In this section we discuss
ways of sampling bars to produce a features matrix with relevant training examples.

### Code Examples

```unknown
used to fit the ML algorithm. This operation is also referred to
```

```unknown
useful event-based
include run-downs, giving us a symmetric
```

---

arising from a locally stationary process. We define the cumulative sums
with boundary condition S 0 = 0 . This procedure would recommend an action at the first t
satisfying S t ≥ h , for some threshold h (the filter size). Note that S t = 0 whenever y t ≤ E t −
1 [ y t ] − S t − 1 . This zero floor means that we will skip some downward deviations that
otherwise would make S t negative. The reason is, the filter is set up to identify a sequence
of upside divergences from any reset level zero. In particular, the threshold is activated
when
This concept of run-ups can be extended to include run-downs, giving us a symmetric
CUSUM filter:
Lam and Yam [1997] propose an investment strategy whereby alternating buy-sell signals
are generated when an absolute return h is observed relative to a prior high or low. Those
authors demonstrate that such strategy is equivalent to the so-called “filter trading strategy”
studied by Fama and Blume [1966]. Our use of the CUSUM filter is different: We will

### Code Examples

```unknown
use of the CUSUM filter is different: We will
require a full run
```

---

The function getTEvents receives two arguments: the raw time series we wish to filter (
gRaw ) and the threshold, h . One practical aspect that makes CUSUM filters appealing is
that multiple events are not triggered by gRaw hovering around a threshold level, which is a
flaw suffered by popular market signals such as Bollinger bands. It will require a full run
of length h for gRaw to trigger an event. Figure 2.3 illustrates the samples taken by a
CUSUM filter on a price series.
Figure 2.3 CUSUM sampling of a price series

---

Variable S t could be based on any of the features we will discuss in Chapters 17–19, like
structural break statistics, entropy, or market microstructure measurements. For example,
we could declare an event whenever SADF departs sufficiently from a previous reset level
(to be defined in Chapter 17). Once we have obtained this subset of event-driven bars, we
will let the ML algorithm determine whether the occurrence of such events constitutes
actionable intelligence.
Exercises
1. 
On a series of E-mini S&P 500 futures tick data:
1. Form tick, volume, and dollar bars. Use the ETF trick to deal with the roll.
2. Count the number of bars produced by tick, volume, and dollar bars on a weekly
basis. Plot a time series of that bar count. What bar type produces the most stable
weekly count? Why?
3. Compute the serial correlation of returns for the three bar types. What bar
method has the lowest serial correlation?
4. Partition the bar series into monthly subsets. Compute the variance of return

### Code Examples

```unknown
used by the ETF trick. (Hint: You
require that the rows in X are associated with an array of
```

---

