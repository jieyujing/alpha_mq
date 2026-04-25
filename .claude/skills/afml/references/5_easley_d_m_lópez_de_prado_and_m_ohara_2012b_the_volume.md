# 5. Easley, D., M. López de Prado, and M. O'Hara (2012b): “The volume

5. Easley, D., M. López de Prado, and M. O'Hara (2012b): “The volume
clock: Insights into the high frequency paradigm.” Journal of Portfolio
Management , Vol. 39, No. 1, pp. 19–29.
6. Gao, Y., I. Kontoyiannis and E. Bienestock (2008): “Estimating the
entropy of binary time series: Methodology, some theory and a simulation
study.” Working paper, arXiv. Available at
https://arxiv.org/abs/0802.4363v1.
7. Fiedor, Pawel (2014a): “Mutual information rate-based networks in
financial markets.” Working paper, arXiv. Available at
https://arxiv.org/abs/1401.2548.
8. Fiedor, Pawel (2014b): “Information-theoretic approach to lead-lag effect
on financial markets.” Working paper, arXiv. Available at
https://arxiv.org/abs/1402.3820.
9. Fiedor, Pawel (2014c): “Causal non-linear financial networks.” Working
paper, arXiv. Available at https://arxiv.org/abs/1407.5020.
10. Hausser, J. and K. Strimmer (2009): “Entropy inference and the James-
Stein estimator, with application to nonlinear gene association n

---

Bibliography
1. Easley, D., R. Engle, M. O'Hara, and L. Wu (2008): “Time-varying arrival
rates of informed and uninformed traders.” Journal of Financial
Econometrics , Vol. 6, No. 2, pp. 171–207.
2. Easley, D., M. López de Prado, and M. O'Hara (2011): “The
microstructure of the flash crash.” Journal of Portfolio Management , Vol.
37, No. 2, pp. 118–128.
3. Easley, D., M. López de Prado, and M. O'Hara (2012c): “Optimal
execution horizon.” Mathematical Finance , Vol. 25, No. 3, pp. 640–672.
4. Gnedenko, B. and I. Yelnik (2016): “Minimum entropy as a measure of
effective dimensionality.” Working paper. Available at
https://ssrn.com/abstract=2767549.
Note
1    Alternatively, we could have worked with a vector of holdings, should the
covariance matrix had been computed on price changes.
CHAPTER 19
Microstructural Features
19.1 Motivation
Market microstructure studies “the process and outcomes of exchanging assets
under explicit trading rules” (O'Hara [1995]). Microstructural datasets includ

### Code Examples

```unknown
important ingredients for building
used solely price information. The two foundational
```

---

The depth and complexity of market microstructure theories has evolved over
time, as a function of the amount and variety of the data available. The first
generation of models used solely price information. The two foundational
results from those early days are trade classification models (like the tick rule)
and the Roll [1984] model. The second generation of models came after
volume datasets started to become available, and researchers shifted their
attention to study the impact that volume has on prices. Two examples for this
generation of models are Kyle [1985] and Amihud [2002].
The third generation of models came after 1996, when Maureen O'Hara, David
Easley, and others published their “probability of informed trading” (PIN)
theory (Easley et al. [1996]). This constituted a major breakthrough, because
PIN explained the bid-ask spread as the consequence of a sequential strategic
decision between liquidity providers (market makers) and position takers
(informed traders). Essentiall

### Code Examples

```unknown
used by the microstructural
```

---

19.3 First Generation: Price Sequences
The first generation of microstructural models concerned themselves with
estimating the bid-ask spread and volatility as proxies for illiquidity. They did
so with limited data and without imposing a strategic or sequential structure to
the trading process.
19.3.1 The Tick Rule
In a double auction book, quotes are placed for selling a security at various
price levels (offers) or for buying a security at various price levels (bids). Offer
prices always exceed bid prices, because otherwise there would be an instant
match. A trade occurs whenever a buyer matches an offer, or a seller matches a
bid. Every trade has a buyer and a seller, but only one side initiates the trade.
The tick rule is an algorithm used to determine a trade's aggressor side. A buy-
initiated trade is labeled “1”, and a sell-initiated trade is labeled “-1”, according
to this logic:
where p t is the price of the trade indexed by t = 1, …, T , and b 0 is arbitrarily
set to 1. A numb

### Code Examples

```yaml
include: (1) Kalman Filters on its future expected value, E t [ b t
```

```unknown
use otherwise there would be an instant
```

```unknown
used to determine a trade's aggressor side. A buy-
```

---

19.3.2 The Roll Model
Roll [1984] was one of the first models to propose an explanation for the
effective bid-ask spread at which a security trades. This is useful in that bid-ask
spreads are a function of liquidity, hence Roll's model can be seen as an early
attempt to measure the liquidity of a security. Consider a mid-price series { m t
}, where prices follow a Random Walk with no drift,
hence price changes Δ m t = m t − m t − 1 are independently and identically
drawn from a Normal distribution
These assumptions are, of course, against all empirical observations, which
suggest that financial time series have a drift, they are heteroscedastic, exhibit
serial dependency, and their returns distribution is non-Normal. But with a
proper sampling procedure, as we saw in Chapter 2, these assumptions may not
be too unrealistic. The observed prices, { p t }, are the result of sequential
trading against the bid-ask spread:
where c is half the bid-ask spread, and b t ∈ { − 1, 1} is the aggress

---

price changes, and the true (unobserved) price's noise, excluding
microstructural noise, is a function of the observed noise and the serial
covariance of price changes.
The reader may question the need for Roll's model nowadays, when datasets
include bid-ask prices at multiple book levels. One reason the Roll model is
still in use, despite its limitations, is that it offers a relatively direct way to
determine the effective bid-ask spread of securities that are either rarely traded,
or where the published quotes are not representative of the levels at which
market makers’ are willing to provide liquidity (e.g., corporate, municipal, and
agency bonds). Using Roll's estimates, we can derive informative features
regarding the market's liquidity conditions.
19.3.3 High-Low Volatility Estimator
Beckers [1983] shows that volatility estimators based on high-low prices are
more accurate than the standard estimators of volatility based on closing prices.
Parkinson [1980] derives that, for conti

### Code Examples

```unknown
include bid-ask prices at multiple book levels. One reason the Roll model is
```

```unknown
use, despite its limitations, is that it offers a relatively direct way to
used to estimate β t .
```

---

the component of the high-to-low price ratio that is due to volatility increases
proportionately with the time elapsed between two observations.
Corwin and Schultz show that the spread, as a percentage of price, can be
estimated as
where
and H t − 1, t is the high price over 2 bars ( t − 1 and t ), whereas L t − 1, t is the
low price over 2 bars ( t − 1 and t ). Because α t < 0⇒ S t < 0, the authors
recommend setting negative alphas to 0 (see Corwin and Schultz [2012], p.
727). Snippet 19.1 implements this algorithm. The corwinSchultz function
receives two arguments, a series dataframe with columns ( High , Low ), and an
integer value sl that defines the sample length used to estimate β t .
SNIPPET 19.1 IMPLEMENTATION OF THE CORWIN-SCHULTZ
ALGORITHM

### Code Examples

```unknown
use α t < 0⇒ S t < 0, the authors
```

```unknown
corwinSchultz
```

---

---

Note that volatility does not appear in the final Corwin-Schultz equations. The
reason is that volatility has been replaced by its high/low estimator. As a
byproduct of this model, we can derive the Becker-Parkinson volatility as
shown in Snippet 19.2.
SNIPPET 19.2 ESTIMATING VOLATILITY FOR HIGH-LOW
PRICES
This procedure is particularly helpful in the corporate bond market, where there
is no centralized order book, and trades occur through bids wanted in
competition (BWIC). The resulting feature, bid-ask spread S , can be estimated
recursively over a rolling window, and values can be smoothed using a Kalman
filter.
19.4 Second Generation: Strategic Trade Models
Second generation microstructural models focus on understanding and
measuring illiquidity. Illiquidity is an important informative feature in financial
ML models, because it is a risk that has an associated premium. These models
have a stronger theoretical foundation than first-generation models, in that they
explain trading as 

### Code Examples

```unknown
important informative feature in financial
```

```unknown
use it is a risk that has an associated premium. These models
```

---

scaled by the standard deviation of the estimation error, which incorporates
another dimension of information absent in mean estimates.
19.4.1 Kyle's Lambda
Kyle [1985] introduced the following strategic trade model. Consider a risky
asset with terminal value v ∼ N [ p 0 , Σ 0 ], as well as two traders:
A noise trader who trades a quantity u = N [0, σ 2 
u ], independent of v .
An informed trader who knows v and demands a quantity x , through a
market order.
The market maker observes the total order flow y = x + u , and sets a price p
accordingly. In this model, market makers cannot distinguish between orders
from noise traders and informed traders. They adjust prices as a function of the
order flow imbalance, as that may indicate the presence of an informed trader.
Hence, there is a positive relationship between price change and order flow
imbalance, which is called market impact.
The informed trader conjectures that the market maker has a linear price
adjustment function, p = λ y + μ

---

