# PART 1

PART 1
Data Analysis
1. Chapter 2 Financial Data Structures
2. Chapter 3 Labeling
3. Chapter 4 Sample Weights
4. Chapter 5 Fractionally Differentiated Features
CHAPTER 2
Financial Data Structures
2.1 Motivation
In this chapter we will learn how to work with unstructured financial data, and from that to
derive a structured dataset amenable to ML algorithms. In general, you do not want to
consume someone else's processed dataset, as the likely outcome will be that you discover
what someone else already knows or will figure out soon. Ideally your starting point is a
collection of unstructured, raw data that you are going to process in a way that will lead to
informative features.
2.2 Essential Types of Financial Data
Financial data comes in many shapes and forms. Table 2.1 shows the four essential types of
financial data, ordered from left to right in terms of increasing diversity. Next, we will
discuss their different natures and applications.
Table 2.1 The Four Essential Types of Financ

---

Assets
Liabilities
Sales
Costs/earnings
Macro
variables
. . .
Price/yield/implied
volatility
Volume
Dividend/coupons
Open interest
Quotes/cancellations
Aggressor side
. . .
Analyst
recommendations
Credit ratings
Earnings
expectations
News sentiment
. . .
Satellite/CCTV
images
Google
searches
Twitter/chats
Metadata
. . .
2.2.1 Fundamental Data
Fundamental data encompasses information that can be found in regulatory filings and
business analytics. It is mostly accounting data, reported quarterly. A particular aspect of
this data is that it is reported with a lapse. You must confirm exactly when each data point
was released, so that your analysis uses that information only after it was publicly
available. A common beginner's error is to assume that this data was published at the end
of the reporting period. That is never the case.
For example, fundamental data published by Bloomberg is indexed by the last date
included in the report, which precedes the date of the release (often by 1.5 mo

### Code Examples

```unknown
uses that information only after it was publicly
```

```unknown
included in the report, which precedes the date of the release (often by 1.5 months). In
```

```unknown
use the final released value and assign it to the time of the first release, or
```

---

Market data includes all trading activity that takes place in an exchange (like CME) or
trading venue (like MarketAxess). Ideally, your data provider has given you a raw feed,
with all sorts of unstructured information, like FIX messages that allow you to fully
reconstruct the trading book, or the full collection of BWIC (bids wanted in competition)
responses. Every market participant leaves a characteristic footprint in the trading records,
and with enough patience, you will find a way to anticipate a competitor's next move. For
example, TWAP algorithms leave a very particular footprint that is used by predatory
algorithms to front-run their end-of-day trading (usually hedging) activity (Easley, López
de Prado, and O'Hara [2011]). Human GUI traders often trade in round lots, and you can
use this fact to estimate what percentage of the volume is coming from them at a given
point in time, then associate it with a particular market behavior.
One appealing aspect of FIX data is that it is

### Code Examples

```sql
use this fact to estimate what percentage of the volume is coming from them at a given
```

```unknown
includes all trading activity that takes place in an exchange (like CME) or
```

```unknown
include monitoring of tankers,
```

---

All that spy craft is expensive, and the surveilled company may object, not to mention
bystanders.
Alternative data offers the opportunity to work with truly unique, hard-to-process datasets.
Remember, data that is hard to store, manipulate, and operate is always the most
promising. You will recognize that a dataset may be useful if it annoys your data
infrastructure team. Perhaps your competitors did not try to use it for logistic reasons, gave
up midway, or processed it incorrectly.
2.3 Bars
In order to apply ML algorithms on your unstructured data, we need to parse it, extract
valuable information from it, and store those extractions in a regularized format. Most ML
algorithms assume a table representation of the extracted data. Finance practitioners often
refer to those tables’ rows as “bars.” We can distinguish between two categories of bar
methods: (1) standard bar methods, which are common in the literature, and (2) more
advanced, information-driven methods, which sophisticated 

### Code Examples

```unknown
use it for logistic reasons, gave
```

```unknown
use although they
important, because many statistical methods rely on the
```

---

operated by algorithms that trade with loose human supervision, for which CPU processing
cycles are much more relevant than chronological intervals (Easley, López de Prado, and
O'Hara [2011]). This means that time bars oversample information during low-activity
periods and undersample information during high-activity periods. Second, time-sampled
series often exhibit poor statistical properties, like serial correlation, heteroscedasticity, and
non-normality of returns (Easley, López de Prado, and O'Hara [2012]). GARCH models
were developed, in part, to deal with the heteroscedasticity associated with incorrect
sampling. As we will see next, forming bars as a subordinated process of trading activity
avoids this problem in the first place.
2.3.1.2 Tick Bars
The idea behind tick bars is straightforward: The sample variables listed earlier
(timestamp, VWAP, open price, etc.) will be extracted each time a pre-defined number of
transactions takes place, e.g., 1,000 ticks. This allows us to s

---

addition, matching engine protocols can further split one fill into multiple artificial partial
fills, as a matter of operational convenience.
Volume bars circumvent that problem by sampling every time a pre-defined amount of the
security's units (shares, futures contracts, etc.) have been exchanged. For example, we
could sample prices every time a futures contract exchanges 1,000 units, regardless of the
number of ticks involved.
It is hard to imagine these days, but back in the 1960s vendors rarely published volume
data, as customers were mostly concerned with tick prices. After volume started to be
reported as well, Clark [1973] realized that sampling returns by volume achieved even
better statistical properties (i.e., closer to an IID Gaussian distribution) than sampling by
tick bars. Another reason to prefer volume bars over time bars or tick bars is that several
market microstructure theories study the interaction between prices and volume. Sampling
as a function of one of these 

### Code Examples

```unknown
requires trading
```

---

Figure 2.1 Average daily frequency of tick, volume, and dollar bars
A second argument that makes dollar bars more interesting than time, tick, or volume bars
is that the number of outstanding shares often changes multiple times over the course of a
security's life, as a result of corporate actions. Even after adjusting for splits and reverse
splits, there are other actions that will impact the amount of ticks and volumes, like issuing
new shares or buying back existing shares (a very common practice since the Great
Recession of 2008). Dollar bars tend to be robust in the face of those actions. Still, you
may want to sample dollar bars where the size of the bar is not kept constant over time.
Instead, the bar size could be adjusted dynamically as a function of the free-floating market
capitalization of a company (in the case of stocks), or the outstanding amount of issued
debt (in the case of fixed-income securities).
2.3.2 Information-Driven Bars
The purpose of information-driven bars 

### Code Examples

```typescript
importance to the persistence of imbalanced signed volumes, as that
```

---

prices reach a new equilibrium level. In this section we will explore how to use various
indices of information arrival to sample bars.
2.3.2.1 Tick Imbalance Bars
Consider a sequence of ticks {( p t , v t )} t = 1, …, T , where p t is the price associated with tick
t and v t is the volume associated with tick t. The so-called tick rule defines a sequence { b t
} t = 1, …, T where
with b t ∈ { − 1, 1}, and the boundary condition b 0 is set to match the terminal value b T
from the immediately preceding bar. The idea behind tick imbalance bars (TIBs) is to
sample bars whenever tick imbalances exceed our expectations. We wish to determine the
tick index, T , such that the accumulation of signed ticks (signed according to the tick rule)
exceeds a given threshold. Next, let us discuss the procedure to determine  T.
First, we define the tick imbalance at time T as
Second, we compute the expected value of θ T at the beginning of the bar, E 0 [θ T ] = E 0 [ T
](P[ b t = 1] − P[ b t = −1]), whe

---

containing equal amounts of information (regardless of the volumes, prices, or ticks
traded).
2.3.2.2 Volume/Dollar Imbalance Bars
The idea behind volume imbalance bars (VIBs) and dollar imbalance bars (DIBs) is to
extend the concept of tick imbalance bars (TIBs). We would like to sample bars when
volume or dollar imbalances diverge from our expectations. Based on the same notions of
tick rule and boundary condition b 0 as we discussed for TIBs, we will define a procedure
to determine the index of the next sample, T.
First, we define the imbalance at time T as
where v t may represent either the number of securities traded (VIB) or the dollar amount
exchanged (DIB). Your choice of v t is what determines whether you are sampling
according to the former or the latter.
Second, we compute the expected value of θ T at the beginning of the bar
Let us denote v + = P[ b t = 1]E 0 [ v t | b t = 1], v − = P[ b t = −1]E 0 [ v t | b t = −1], so that
 . You can think of v + and v − as decomposing th

---

where the size of the expected imbalance is implied by |2 v + − E 0 [ v t ]|. When θ T is more
imbalanced than expected, a low T will satisfy these conditions. This is the information-
based analogue of volume and dollar bars, and like its predecessors, it addresses the same
concerns regarding tick fragmentation and outliers. Furthermore, it also addresses the issue
of corporate actions, because the above procedure does not rely on a constant bar size.
Instead, the bar size is adjusted dynamically.
2.3.2.3 Tick Runs Bars
TIBs, VIBs, and DIBs monitor order flow imbalance, as measured in terms of ticks,
volumes, and dollar values exchanged. Large traders will sweep the order book, use
iceberg orders, or slice a parent order into multiple children, all of which leave a trace of
runs in the { b t } t = 1, …, T sequence. For this reason, it can be useful to monitor the
sequence of buys in the overall volume, and take samples when that sequence diverges
from our expectations.
First, we defin

### Code Examples

```unknown
use the above procedure does not rely on a constant bar size.
```

```unknown
useful to monitor the
```

```unknown
useful definition than measuring sequence lengths.
```

---

