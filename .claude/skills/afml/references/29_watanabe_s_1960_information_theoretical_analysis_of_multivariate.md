# 29. Watanabe S. (1960): “Information theoretical analysis of multivariate

29. Watanabe S. (1960): “Information theoretical analysis of multivariate
correlation.” IBM Journal of Research and Development , Vol. 4, pp. 66–
82.
Notes
1    For further details, visit https://www.gipsstandards.org.
2    External cash flows are assets (cash or investments) that enter or exit a
portfolio. Dividend and interest income payments, for example, are not
considered external cash flows.
3    This could be set to a default value of zero (i.e., comparing against no
investment skill).
CHAPTER 15
Understanding Strategy Risk
15.1 Motivation
As we saw in Chapters 3 and 13, investment strategies are often implemented
in terms of positions held until one of two conditions are met: (1) a condition to
exit the position with profits (profit-taking), or (2) a condition to exit the
position with losses (stop-loss). Even when a strategy does not explicitly
declare a stop-loss, there is always an implicit stop-loss limit, at which the
investor can no longer finance her position (margin cal

---

with probability P[ X i = −π] = 1 − p . You can think of p as the precision of a
binary classifier where a positive means betting on an opportunity, and a
negative means passing on an opportunity: True positives are rewarded, false
positives are punished, and negatives (whether true or false) have no payout.
Since the betting outcomes { X i } i = 1, …, n are independent, we will compute
the expected moments per bet. The expected profit from one bet is E[ X i ] = π p
+ ( − π)(1 − p ) = π(2 p − 1). The variance is V[ X i ] = E[ X 2 
i ] − E[ X i ] 2 ,
where E[ X 2 
i ] = π 2 p + ( − π) 2 (1 − p ) = π 2 , thus V[ X i ] = π 2 − π 2 (2 p − 1) 2
= π 2 [1 − (2 p − 1) 2 ] = 4π 2 p (1 − p ). For n IID bets per year, the annualized
Sharpe ratio (θ) is
Note how π cancels out of the above equation, because the payouts are
symmetric. Just as in the Gaussian case, θ[ p , n ] can be understood as a re-
scaled t-value. This illustrates the point that, even for a small 
 , the Sharpe
ratio can be made 

### Code Examples

```unknown
use passing on an opportunity (a negative) is not
```

```unknown
requires 396 bets per year. Snippet 15.1 verifies this result
```

```unknown
use the payouts are
```

---

Figure 15.1 The relation between precision (x-axis) and sharpe ratio (y-axis)
for various bet frequencies (n)
SNIPPET 15.1 TARGETING A SHARPE RATIO AS A FUNCTION
OF THE NUMBER OF BETS
Solving for 0 ≤ p ≤ 1, we obtain 
 , with solution

---

This equation makes explicit the trade-off between precision ( p ) and
frequency ( n ) for a given Sharpe ratio (θ). For example, a strategy that only
produces weekly bets ( n = 52) will need a fairly high precision of p = 0.6336
to deliver an annualized Sharpe of 2.
15.3 Asymmetric Payouts
Consider a strategy that produces n IID bets per year, where the outcome X i of
a bet i ∈ [1, n ] is π + with probability P[ X i = π + ] = p , and an outcome π − , π
− < π + occurs with probability P[ X i = π − ] = 1 − p . The expected profit from
one bet is E[ X i ] = p π + + (1 − p )π − = (π + − π − ) p + π − . The variance is V[ X
i ] = E[ X 2 
i ] − E[ X i ] 2 , where E[ X 2 
i ] = p π + 
2 + (1 − p )π 2 
− = (π + 
2 − π 2 
− ) p
+ π − 
2 , thus V[ X i ] = (π + − π − ) 2 p (1 − p ). For n IID bets per year, the
annualized Sharpe ratio (θ) is
And for π − = −π + we can see that this equation reduces to the symmetric case:
 . For example, for n =
260, π − = −.01, π + = .005, p = .7, we get θ = 1.17

---

SNIPPET 15.2 USING THE SymPy LIBRARY FOR SYMBOLIC
OPERATIONS
The above equation answers the following question: Given a trading rule
characterized by parameters {π − , π + , n }, what is the precision rate p required
to achieve a Sharpe ratio of θ*? For example, for n = 260, π − = −.01, π + = .005,
in order to get θ = 2 we require a p = .72 . Thanks to the large number of bets, a
very small change in p (from p = .7 to p = .72) has propelled the Sharpe ratio
from θ = 1.173 to θ = 2 . On the other hand, this also tells us that the strategy is
vulnerable to small changes in p. Snippet 15.3 implements the derivation of the
implied precision. Figure 15.2 displays the implied precision as a function of n
and π − , where π + = 0.1 and θ* = 1.5 . As π − becomes more negative for a
given n , a higher p is required to achieve θ* for a given π + . As n becomes
smaller for a given π − , a higher p is required to achieve θ* for a given π + .

### Code Examples

```typescript
required to achieve θ* for a given π + . As n becomes
```

```unknown
require a p = .72 . Thanks to the large number of bets, a
```

```unknown
required to achieve θ* for a given π + .
```

---

Figure 15.2 Heat-map of the implied precision as a function of n and π − , with
π + = 0.1 and θ* = 1.5
SNIPPET 15.3 COMPUTING THE IMPLIED PRECISION

---

Snippet 15.4 solves θ[ p , n , π − , π + ] for the implied betting frequency, n.
Figure 15.3 plots the implied frequency as a function of p and π − , where π + =
0.1 and θ* = 1.5 . As π − becomes more negative for a given p , a higher n is
required to achieve θ* for a given π + . As p becomes smaller for a given π − , a
higher n is required to achieve θ* for a given π + .

### Code Examples

```typescript
required to achieve θ* for a given π + . As p becomes smaller for a given π − , a
```

```unknown
required to achieve θ* for a given π + .
```

---

Figure 15.3 Implied frequency as a function of p and, with = 0.1 and = 1.5
SNIPPET 15.4 COMPUTING THE IMPLIED BETTING
FREQUENCY

---

15.4 The Probability of Strategy Failure
In the example above, parameters π − = −.01, π + = .005 are set by the portfolio
manager, and passed to the traders with the execution orders. Parameter n =
260 is also set by the portfolio manager, as she decides what constitutes an
opportunity worth betting on. The two parameters that are not under the control
of the portfolio manager are p (determined by the market) and θ* (the objective
set by the investor). Because p is unknown, we can model it as a random
variable, with expected value E[ p ]. Let us define 
 as the value of p below
which the strategy will underperform a target Sharpe ratio θ*, that is,
 . We can use the equations above (or the binHR function)
to conclude that for 
 , 
 . This highlights the risks
involved in this strategy, because a relatively small drop in p (from p = .7 to p
= .67) will wipe out all the profits. The strategy is intrinsically risky, even if the
holdings are not. That is the critical difference we wish to 

### Code Examples

```unknown
use the equations above (or the binHR function)
```

```sql
use a relatively small drop in p (from p = .7 to p
```

```typescript
use p is unknown, we can model it as a random
```

---

Most firms and investors compute, monitor, and report portfolio risk without
realizing that this tells us nothing about the risk of the strategy itself. Strategy
risk is not the risk of the underlying portfolio, as computed by the chief risk
officer. Strategy risk is the risk that the investment strategy will fail to succeed
over time, a question of far greater relevance to the chief investment officer.
The answer to the question “What is the probability that this strategy will fail?”
is equivalent to computing 
 . The following algorithm will help us
compute the strategy risk.
15.4.1 Algorithm
In this section we will describe a procedure to compute 
 . Given a
time series of bet outcomes {π t } t = 1, …, T , first we estimate π − = E[{π t |π t ≤
0} t = 1, …, T ], and π + = E[{π t |π t > 0} t = 1, …, T ]. Alternatively, {π − , π + } could
be derived from fitting a mixture of two Gaussians, using the EF3M algorithm
(López de Prado and Foreman [2014]). Second, the annual frequency n is g

---

