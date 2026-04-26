# 1. Sample bars using the CUSUM filter, where {y t } are absolute returns and h =

1. Sample bars using the CUSUM filter, where {y t } are absolute returns and h =
0.05.
2. Compute the rolling standard deviation of the sampled bars.
3. Compare this result with the results from exercise 4. What procedure delivered
the least heteroscedastic sample? Why?
References
1. Ané, T. and H. Geman (2000): “Order flow, transaction clock and normality of asset
returns.” Journal of Finance , Vol. 55, pp. 2259–2284.
2. Bailey, David H., and M. López de Prado (2012): “Balanced baskets: A new approach
to trading and hedging risks.” Journal of Investment Strategies (Risk Journals) , Vol.
1, No. 4 (Fall), pp. 21–62.
3. Clark, P. K. (1973): “A subordinated stochastic process model with finite variance for
speculative prices.” Econometrica , Vol. 41, pp. 135–155.
4. Easley, D., M. López de Prado, and M. O'Hara (2011): “The volume clock: Insights
into the high frequency paradigm.” Journal of Portfolio Management , Vol. 37, No. 2,
pp. 118–128.
5. Easley, D., M. López de Prado, and M. O'Hara

---

labels or values y , so that those labels or values can be predicted on unseen features
samples. In this chapter we will discuss ways to label financial data.
3.2 The Fixed-Time Horizon Method
As it relates to finance, virtually all ML papers label observations using the fixed-time
horizon method. This method can be described as follows. Consider a features matrix X
with I rows, { X i } i = 1, …, I , drawn from some bars with index t = 1, …, T , where I ≤ T .
Chapter 2, Section 2.5 discussed sampling methods that produce the set of features { X i } i
= 1, …, I . An observation X i is assigned a label y i ∈ { − 1, 0, 1},
where τ is a pre-defined constant threshold, t i , 0 is the index of the bar immediately after X
i takes place, t i , 0 + h is the index of the h -th bar after t i , 0 , and 
 is the price return
over a bar horizon h ,
Because the literature almost always works with time bars, h implies a fixed-time horizon.
The bibliography section lists multiple ML studies, of which D

### Code Examples

```typescript
use volume or dollar bars, as their volatilities are much closer to constant
```

```unknown
use the literature almost always works with time bars, h implies a fixed-time horizon.
use the output of this function to set default profit taking and stop-loss limits
```

---

publication accounts for that when labeling observations tells you something about the
current state of the investment literature.
3.3 Computing Dynamic Thresholds
As argued in the previous section, in practice we want to set profit taking and stop-loss
limits that are a function of the risks involved in a bet. Otherwise, sometimes we will be
aiming too high ( 
 ), and sometimes too low ( 
 ), considering the prevailing
volatility.
Snippet 3.1 computes the daily volatility at intraday estimation points, applying a span of
span0 days to an exponentially weighted moving standard deviation. See the pandas
documentation for details on the pandas.Series.ewm function.
SNIPPET 3.1 DAILY VOLATILITY ESTIMATES
We can use the output of this function to set default profit taking and stop-loss limits
throughout the rest of this chapter.
3.4 The Triple-Barrier Method
Here I will introduce an alternative labeling method that I have not found in the literature.
If you are an investment professional, I

### Code Examples

```unknown
use it labels an observation according to the first barrier
```

```unknown
pandas.Series.ewm
```

---

defines the vertical barrier (the expiration limit). We will denote t i , 1 the time of the first
barrier touch, and the return associated with the observed feature is 
 . For the sake of
clarity, t i , 1 ≤ t i , 0 + h and the horizontal barriers are not necessarily symmetric.
Snippet 3.2 implements the triple-barrier method. The function receives four arguments:
close : A pandas series of prices.
events : A pandas dataframe, with columns,
t1 : The timestamp of vertical barrier. When the value is np.nan , there will not
be a vertical barrier.
trgt : The unit width of the horizontal barriers.
ptSl : A list of two non-negative float values:
ptSl[0] : The factor that multiplies trgt to set the width of the upper barrier. If
0, there will not be an upper barrier.
ptSl[1] : The factor that multiplies trgt to set the width of the lower barrier. If
0, there will not be a lower barrier.
molecule : A list with the subset of event indices that will be processed by a single
thread. Its use will b

### Code Examples

```unknown
use will become clear later on in the chapter.
```

```unknown
useful configurations:
```

---

[1,1,1]: This is the standard setup, where we define three barrier exit conditions.
We would like to realize a profit, but we have a maximum tolerance for losses
and a holding period.
[0,1,1]: In this setup, we would like to exit after a number of bars, unless we are
stopped-out.
[1,1,0]: Here we would like to take a profit as long as we are not stopped-out.
This is somewhat unrealistic in that we are willing to hold the position for as
long as it takes.
Three less realistic configurations:
[0,0,1]: This is equivalent to the fixed-time horizon method. It may still be useful
when applied to volume-, dollar-, or information-driven bars, and multiple
forecasts are updated within the horizon.
[1,0,1]: A position is held until a profit is made or the maximum holding period
is exceeded, without regard for the intermediate unrealized losses.
[1,0,0]: A position is held until a profit is made. It could mean being locked on a
losing position for years.
Two illogical configurations:
[0,1,0]: Thi

---

Figure 3.1 Two alternative configurations of the triple-barrier method

---

3.5 Learning Side and Size
In this section we will discuss how to label examples so that an ML algorithm
can learn both the side and the size of a bet. We are interested in learning the
side of a bet when we do not have an underlying model to set the sign of our
position (long or short). Under such circumstance, we cannot differentiate
between a profit-taking barrier and a stop-loss barrier, since that requires
knowledge of the side. Learning the side implies that either there are no
horizontal barriers or that the horizontal barriers must be symmetric.
Snippet 3.3 implements the function getEvents , which finds the time of the
first barrier touch. The function receives the following arguments:
close : A pandas series of prices.
tEvents : The pandas timeindex containing the timestamps that will seed
every triple barrier. These are the timestamps selected by the sampling
procedures discussed in Chapter 2, Section 2.5.
ptSl : A non-negative float that sets the width of the two barriers. 

### Code Examples

```unknown
used by the function.
```

```unknown
required for running a triple barrier
use throughout the book.
```

---

Suppose that I = 1 E 6 and h = 1 E 3, then the number of conditions to evaluate
is up to one billion on a single instrument. Many ML tasks are computationally
expensive unless you are familiar with multi-threading, and this is one of them.
Here is where parallel computing comes into play. Chapter 20 discusses a few
multiprocessing functions that we will use throughout the book.
Function mpPandasObj calls a multiprocessing engine, which is explained in
depth in Chapter 20. For the moment, you simply need to know that this
function will execute applyPtSlOnT1 in parallel. Function applyPtSlOnT1
returns the timestamps at which each barrier is touched (if any). Then, the time
of the first touch is the earliest time among the three returned by
applyPtSlOnT1 . Because we must learn the side of the bet, we have passed
ptSl = [ptSl,ptSl] as argument, and we arbitrarily set the side to be always
long (the horizontal barriers are symmetric, so the side is irrelevant to
determining the time of the

### Code Examples

```unknown
use we must learn the side of the bet, we have passed
```

```unknown
used to generate the horizontal barriers.
```

```unknown
ptSl = [ptSl,ptSl]
```

---

Snippet 3.4 shows one way to define a vertical barrier. For each index in
tEvents , it finds the timestamp of the next price bar at or immediately after a
number of days numDays . This vertical barrier can be passed as optional
argument t1 in getEvents .
SNIPPET 3.4 ADDING A VERTICAL BARRIER
Finally, we can label the observations using the getBins function defined in
Snippet 3.5. The arguments are the events dataframe we just discussed, and
the close pandas series of prices. The output is a dataframe with columns:
ret : The return realized at the time of the first touched barrier.
bin : The label, { − 1, 0, 1}, as a function of the sign of the outcome. The
function can be easily adjusted to label as 0 those events when the vertical
barrier was touched first, which we leave as an exercise.
SNIPPET 3.5 LABELING FOR SIDE AND SIZE
3.6 Meta-Labeling
Suppose that you have a model for setting the side of the bet (long or short).
You just need to learn the size of that bet, which includes the 

### Code Examples

```unknown
includes the possibility of no
use we want to build a secondary ML model
```

---

often know whether we want to buy or sell a product, and the only remaining
question is how much money we should risk in such a bet. We do not want the
ML algorithm to learn the side, just to tell us what is the appropriate size. At
this point, it probably does not surprise you to hear that no book or paper has
so far discussed this common problem. Thankfully, that misery ends here. I call
this problem meta-labeling because we want to build a secondary ML model
that learns how to use a primary exogenous model.
Rather than writing an entirely new getEvents function, we will make some
adjustments to the previous code, in order to handle meta-labeling. First, we
accept a new side optional argument (with default None ), which contains the
side of our bets as decided by the primary model. When side is not None , the
function understands that meta-labeling is in play. Second, because now we
know the side, we can effectively discriminate between profit taking and stop
loss. The horizontal bar

### Code Examples

```unknown
use a primary exogenous model.
```

---

