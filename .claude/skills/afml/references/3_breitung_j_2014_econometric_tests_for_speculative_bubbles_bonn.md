# 3. Breitung, J. (2014): “Econometric tests for speculative bubbles.” Bonn

3. Breitung, J. (2014): “Econometric tests for speculative bubbles.” Bonn
Journal of Economics , Vol. 3, No. 1, pp. 113–127.
4. Brown, R.L., J. Durbin, and J.M. Evans (1975): “Techniques for Testing
the Constancy of Regression Relationships over Time.” Journal of the
Royal Statistical Society, Series B , Vol. 35, pp. 149–192.
5. Chow, G. (1960). “Tests of equality between sets of coefficients in two
linear regressions.” Econometrica , Vol. 28, No. 3, pp. 591–605.
6. Greene, W. (2008): Econometric Analysis , 6th ed. Pearson Prentice Hall.
7. Homm, U. and J. Breitung (2012): “Testing for speculative bubbles in
stock markets: A comparison of alternative methods.” Journal of
Financial Econometrics , Vol. 10, No. 1, 198–231.
8. Maddala, G. and I. Kim (1998): Unit Roots, Cointegration and Structural
Change , 1st ed. Cambridge University Press.
9. Phillips, P., Y. Wu, and J. Yu (2011): “Explosive behavior in the 1990s
Nasdaq: When did exuberance escalate asset values?” International
Economic 

### Code Examples

```unknown
use each observation transmits
```

---

carry a lot of information. In this chapter, we will explore ways to determine
the amount of information contained in a price series.
18.2 Shannon's Entropy
In this section we will review a few concepts from information theory that will
be useful in the remainder of the chapter. The reader can find a complete
exposition in MacKay [2003]. The father of information theory, Claude
Shannon, defined entropy as the average amount of information (over long
messages) produced by a stationary source of data. It is the smallest number of
bits per character required to describe the message in a uniquely decodable
way. Mathematically, Shannon [1948] defined the entropy of a discrete random
variable X with possible values x ∈ A as
with 0 ≤ H [ X ] ≤ log 2 [|| A ||] where: p [ x ] is the probability of x ; H [ X ] =
0⇔∃ x | p [ x ] = 1; 
 for all x ; and || A || is the
size of the set A . This can be interpreted as the probability weighted average of
informational content in X , where the bits of in

### Code Examples

```swift
required to describe the message in a uniquely decodable
```

```unknown
useful in the remainder of the chapter. The reader can find a complete
```

---

The mutual information (MI) is always non-negative, symmetric, and equals
zero if and only if X and Y are independent. For normally distributed variables,
the mutual information is closely related to the familiar Pearson correlation, ρ.
Therefore, mutual information is a natural measure of the association between
variables, regardless of whether they are linear or nonlinear in nature (Hausser
and Strimmer [2009]). The normalized variation of information is a metric
derived from mutual information. For several entropy estimators, see:
In R: http://cran.r-project.org/web/packages/entropy/entropy.pdf
In Python: https://code.google.com/archive/p/pyentropy/
18.3 The Plug-in (or Maximum Likelihood) Estimator
In this section we will follow the exposition of entropy's maximum likelihood
estimator in Gao et al. [2008]. The nomenclature may seem a bit peculiar at
first (no pun intended), but once you become familiar with it you will find it
convenient. Given a data sequence x n 
1 , comprising t

---

than w , so that the empirical distribution of order w is close to the true
distribution. Snippet 18.1 implements the plug-in entropy estimator.
SNIPPET 18.1 PLUG-IN ENTROPY ESTIMATOR
18.4 Lempel-Ziv Estimators
Entropy can be interpreted as a measure of complexity. A complex sequence
contains more information than a regular (predictable) sequence. The Lempel-
Ziv (LZ) algorithm efficiently decomposes a message into non-redundant
substrings (Ziv and Lempel [1978]). We can estimate the compression rate of a
message as a function of the number of items in a Lempel-Ziv dictionary
relative to the length of the message. The intuition here is that complex
messages have high entropy, which will require large dictionaries relative to

### Code Examples

```unknown
require large dictionaries relative to
requires data x i + n − 1
```

---

the length of the string to be transmitted. Snippet 18.2 shows an
implementation of the LZ compression algorithm.
SNIPPET 18.2 A LIBRARY BUILT USING THE LZ ALGORITHM
Kontoyiannis [1998] attempts to make a more efficient use of the information
available in a message. What follows is a faithful summary of the exposition in
Gao et al. [2008]. We will reproduce the steps in that paper, while
complementing them with code snippets that implement their ideas. Let us
define L n 
i as 1 plus the length of the longest match found in the n bits prior to i
,
Snippet 18.3 implements the algorithm that determines the length of the longest
match. A few notes worth mentioning:
The value n is constant for a sliding window, and n = i for an expanding
window.
Computing L n 
i requires data x i + n − 1 
i − n . In other words, index i must be
at the center of the window. This is important in order to guarantee that
both matching strings are of the same length. If they are not of the same
length, l will ha

### Code Examples

```unknown
important in order to guarantee that
```

```unknown
use of the information
uses this result to estimate Shannon's entropy rate. He estimates
```

---

SNIPPET 18.3 FUNCTION THAT COMPUTES THE LENGTH OF
THE LONGEST MATCH
Ornstein and Weiss [1993] formally established that
Kontoyiannis uses this result to estimate Shannon's entropy rate. He estimates
the average 
 , and uses the reciprocal of that average to estimate H. The
general intuition is, as we increase the available history, we expect that
messages with high entropy will produce relatively shorter non-redundant
substrings. In contrast, messages with low entropy will produce relatively
longer non-redundant substrings as we parse through the message. Given a data
realization x ∞ 
− ∞ , a window length n ≥ 1, and a number of matches k ≥ 1, the
sliding-window LZ estimator 
 is defined by
Similarly, the increasing window LZ estimator 
 , is defined by

### Code Examples

```unknown
uses the reciprocal of that average to estimate H. The
```

---

The window size n is constant when computing 
 , thus L n 
i . However,
when computing 
 , the window size increases with i , thus L i 
i , with 
 .
In this expanding window case the length of the message N should be an even
number to ensure that all bits are parsed (recall that x i is at the center, so for an
odd-length message the last bit would not be read).
The above expressions have been derived under the assumptions of:
stationarity, ergodicity, that the process takes finitely many values, and that the
process satisfies the Doeblin condition. Intuitively, this condition requires that,
after a finite number of steps r , no matter what has occurred before, anything
can happen with positive probability. It turns out that this Doeblin condition
can be avoided altogether if we consider a modified version of the above
estimators:
One practical question when estimating 
 is how to determine the window
size n. Gao et al. [2008] argue that k + n = N should be approximately equal to
the me

---

SNIPPET 18.4 IMPLEMENTATION OF ALGORITHMS
DISCUSSED IN GAO ET AL. [2008]

---

One caveat of this method is that entropy rate is defined in the limit. In the
words of Kontoyiannis, “we fix a large integer N as the size of our database.”
The theorems used by Kontoyiannis’ paper prove asymptotic convergence;
however, nowhere is a monotonicity property claimed. When a message is
short, a solution may be to repeat the same message multiple times.
A second caveat is that, because the window for matching must be symmetric
(same length for the dictionary as for the substring being matched), the last bit
is only considered for matching if the message's length corresponds to an even
number. One solution is to remove the first bit of a message with odd length.
A third caveat is that some final bits will be dismissed when preceded by
irregular sequences. This is also a consequence of the symmetric matching
window. For example, the entropy rate for “10000111” equals the entropy rate
for “10000110,” meaning that the final bit is irrelevant due to the unmatchable
“11” in the s

### Code Examples

```unknown
used by Kontoyiannis’ paper prove asymptotic convergence;
```

```unknown
use the window for matching must be symmetric
```

```unknown
used, but actually they will be used to potentially match every
```

---

When | r t | can adopt a wide range of outcomes, binary encoding discards
potentially useful information. That is particularly the case when working with
intraday time bars, which are affected by the heteroscedasticity that results
from the inhomogeneous nature of tick data. One way to partially address this
heteroscedasticity is to sample prices according to a subordinated stochastic
process. Examples of that are trade bars and volume bars, which contain a
fixed number of trades or trades for a fixed amount of volume (see Chapter 2).
By operating in this non-chronological, market-driven clock, we sample more
frequently during highly active periods, and less frequently during periods of
less activity, hence regularizing the distribution of | r t | and reducing the need
for a large alphabet.
18.5.2 Quantile Encoding
Unless price bars are used, it is likely that more than two codes will be needed.
One approach consists in assigning a code to each r t according to the quantile
it belongs 

### Code Examples

```unknown
used, it is likely that more than two codes will be needed.
```

```unknown
use codes are not uniformly distributed,
```

```unknown
use spikes in entropy readings.
uses of this result.
```

---

