# 2. WTI Crude Oil futures

2. WTI Crude Oil futures
3. Are the results significantly different? Does this justify having
execution traders specialized by product?
4. 
Repeat exercise 2 after splitting the time series into two parts:
1. The first time series ends on 3/15/2009.
2. The second time series starts on 3/16/2009.
3. Are the OTRs significantly different?
5. 
How long do you estimate it would take to derive OTRs on the
100 most liquid futures contracts worldwide? Considering the
results from exercise 4, how often do you think you may have to
re-calibrate the OTRs? Does it make sense to pre-compute this
data?
6. 
Parallelize Snippets 13.1 and 13.2 using the mpEngine module
described in Chapter 20.
References
1. Bailey, D. and M. López de Prado (2012): “The Sharpe ratio efficient
frontier.” Journal of Risk , Vol. 15, No. 2, pp. 3–44. Available at
http://ssrn.com/abstract=1821643 .
2. Bailey, D. and M. López de Prado (2013): “Drawdown-based stop-outs
and the triple penance rule.” Journal of Risk , Vol. 18, N

---

http://ssrn.com/abstract=1748633 .
Notes
1    I would like to thank Professor Peter Carr (New York University) for his
contributions to this chapter.
2    The strategy may still be the result of backtest overfitting, but at least the
trading rule would not have contributed to that problem.
3    The trading rule R could be characterized as a function of the three barriers,
instead of the horizontal ones. That change would have no impact on the
procedure. It would merely add one more dimension to the mesh (20 × 20 ×
20). In this chapter we do not consider that setting, because it would make the
visualization of the method less intuitive.
CHAPTER 14
Backtest Statistics
14.1 Motivation
In the previous chapters, we have studied three backtesting paradigms: First,
historical simulations (the walk-forward method, Chapters 11 and 12). Second,
scenario simulations (CV and CPCV methods, Chapter 12). Third, simulations
on synthetic data (Chapter 13). Regardless of the backtesting paradigm you
cho

### Code Examples

```unknown
use it would make the
```

```unknown
use to compare and judge your strategy against competitors. In
```

```unknown
included in the Global
```

---

problematic aspects of the strategy, such as substantial asymmetric risks or low
capacity. Overall, they can be categorized into general characteristics,
performance, runs/drawdowns, implementation shortfall, return/risk efficiency,
classification scores, and attribution.
14.3 General Characteristics
The following statistics inform us about the general characteristics of the
backtest:
Time range: Time range specifies the start and end dates. The period used
to test the strategy should be sufficiently long to include a comprehensive
number of regimes (Bailey and López de Prado [2012]).
Average AUM: This is the average dollar value of the assets under
management. For the purpose of computing this average, the dollar value
of long and short positions is considered to be a positive real number.
Capacity: A strategy's capacity can be measured as the highest AUM that
delivers a target risk-adjusted performance. A minimum AUM is needed
to ensure proper bet sizing (Chapter 10) and risk diversi

---

of trades. A trade count would overestimate the number of independent
opportunities discovered by the strategy.
Average holding period: The average holding period is the average
number of days a bet is held. High-frequency strategies may hold a
position for a fraction of seconds, whereas low frequency strategies may
hold a position for months or even years. Short holding periods may limit
the capacity of the strategy. The holding period is related but different to
the frequency of bets. For example, a strategy may place bets on a
monthly basis, around the release of nonfarm payrolls data, where each
bet is held for only a few minutes.
Annualized turnover: Annualized turnover measures the ratio of the
average dollar amount traded per year to the average annual AUM. High
turnover may occur even with a low number of bets, as the strategy may
require constant tuning of the position. High turnover may also occur with
a low number of trades, if every trade involves flipping the position
betw

### Code Examples

```unknown
require constant tuning of the position. High turnover may also occur with
useful performance measurements include:
```

---

Snippet 14.2 illustrates the implementation of an algorithm that estimates the
average holding period of a strategy, given a pandas series of target positions (
tPos ).
SNIPPET 14.2 IMPLEMENTATION OF A HOLDING PERIOD
ESTIMATOR
14.4 Performance
Performance statistics are dollar and returns numbers without risk adjustments.
Some useful performance measurements include:
PnL: The total amount of dollars (or the equivalent in the currency of
denomination) generated over the entirety of the backtest, including
liquidation costs from the terminal position.
PnL from long positions: The portion of the PnL dollars that was
generated exclusively by long positions. This is an interesting value for
assessing the bias of long-short, market neutral strategies.

---

Annualized rate of return: The time-weighted average annual rate of
total return, including dividends, coupons, costs, etc.
Hit ratio: The fraction of bets that resulted in a positive PnL.
Average return from hits: The average return from bets that generated a
profit.
Average return from misses: The average return from bets that generated
a loss.
14.4.1 Time-Weighted Rate of Return
Total return is the rate of return from realized and unrealized gains and losses,
including accrued interest, paid coupons, and dividends for the measurement
period. GIPS rules calculate time-weighted rate of returns (TWRR), adjusted
for external cash flows (CFA Institute [2010]). Periodic and sub-periodic
returns are geometrically linked. For periods beginning on or after January 1,
2005, GIPS rules mandate calculating portfolio returns that adjust for daily-
weighted external cash flows.
We can compute the TWRR by determining the value of the portfolio at the
time of each external cash flow. 2 The TWRR for

---

A j , t is the interest accrued or dividend paid by one unit of instrument j at
time t.
P j , t is the clean price of security j at time t.
θ i , j , t are the holdings of portfolio i on security j at time t.
 is the dirty price of security j at time t.
 is the average transacted clean price of portfolio i on security j over
subperiod t.
 is the average transacted dirty price of portfolio i on security j over
subperiod t.
Cash inflows are assumed to occur at the beginning of the day, and cash
outflows are assumed to occur at the end of the day. These sub-period returns
are then linked geometrically as
The variable φ i , T can be understood as the performance of one dollar invested
in portfolio i over its entire life, t = 1, …, T . Finally, the annualized rate of
return of portfolio i is
where y i is the number of years elapsed between r i , 1 and r i , T .
14.5 Runs
Investment strategies rarely generate returns drawn from an IID process. In the
absence of this property, strategy return

---

Inspired by the Herfindahl-Hirschman Index (HHI), for || w + || > 1, where ||.|| is
the size of the vector, we define the concentration of positive returns as
and the equivalent for concentration of negative returns, for || w − || > 1, as
From Jensen's inequality, we know that E[ r + 
t ] 2 ≤ E[( r t 
+ ) 2 ]. And because
 , we deduce that E[ r + 
t ] 2 ≤ E[( r t 
+ ) 2 ] ≤ E[ r + 
t ] 2 || r + ||, with
an equivalent boundary on negative bet returns. These definitions have a few
interesting properties:
1. 0 ≤ h + ≤ 1
2. h + = 0⇔w + 
t = ||w + || − 1 , ∀t (uniform returns)
3. 
 (only one non-zero return)

---

It is easy to derive a similar expression for the concentration of bets across
months, h [ t ]. Snippet 14.3 implements these concepts. Ideally, we are
interested in strategies where bets ’ returns exhibit:
high Sharpe ratio
high number of bets per year, ||r + || + ||r − || = T
high hit ratio (relatively low ||r − ||)
low h + (no right fat-tail)
low h − (no left fat-tail)
low h [t ] (bets are not concentrated in time)
SNIPPET 14.3 ALGORITHM FOR DERIVING HHI
CONCENTRATION
14.5.2 Drawdown and Time under Water
Intuitively, a drawdown (DD) is the maximum loss suffered by an investment
between two consecutive high-watermarks (HWMs). The time under water
(TuW) is the time elapsed between an HWM and the moment the PnL exceeds
the previous maximum PnL. These concepts are best understood by reading
Snippet 14.4. This code derives both DD and TuW series from either (1) the
series of returns ( dollars = False ) or; (2) the series of dollar performance (
dollar = True ). Figure 14.1 provides an ex

### Code Examples

```unknown
dollars = False
```

```unknown
dollar = True
```

---

Figure 14.1 Examples of drawdown (DD) and time under water + (TuW)
SNIPPET 14.4 DERIVING THE SEQUENCE OF DD AND TuW

---

