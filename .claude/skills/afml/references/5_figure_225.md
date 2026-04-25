# 5. Figure 22.5

5. Figure 22.5
6. Figure 22.6
7. Figure 22.7
8. Figure 22.8
9. Figure 22.9
10. Figure 22.10
About the Author
Marcos López de Prado manages several multibillion-dollar funds for institutional
investors using machine learning algorithms. Over the past 20 years, his work has
combined advanced mathematics with supercomputing technologies to deliver billions of
dollars in net profits for investors and firms. A proponent of research by collaboration,
Marcos has published with more than 30 leading academics, resulting in some of the most-
read papers in finance.
Since 2010, Marcos has also been a Research Fellow at Lawrence Berkeley National
Laboratory (U.S. Department of Energy's Office of Science), where he conducts research
focused on the mathematics of large-scale financial problems and high-performance
computing at the Computational Research department. For the past seven years he has
lectured at Cornell University, where he currently teaches a graduate course in financial big
data and m

### Code Examples

```unknown
used on the mathematics of large-scale financial problems and high-performance
```

---

transform how everyone invests for generations. This book explains scientifically sound
ML tools that have worked for me over the course of two decades, and have helped me to
manage large pools of funds for some of the most demanding institutional investors.
Books about investments largely fall in one of two categories. On one hand we find books
written by authors who have not practiced what they teach. They contain extremely elegant
mathematics that describes a world that does not exist. Just because a theorem is true in a
logical sense does not mean it is true in a physical sense. On the other hand we find books
written by authors who offer explanations absent of any rigorous academic theory. They
misuse mathematical tools to describe actual observations. Their models are overfit and fail
when implemented. Academic investigation and publication are divorced from practical
application to financial markets, and many applications in the trading/investment world are
not grounded in prope

### Code Examples

```sql
imported from academia or Silicon
```

```unknown
use a theorem is true in a
```

```unknown
use mathematical tools to describe actual observations. Their models are overfit and fail
```

---

performance to their investors. However, that is a rare outcome, for reasons explained in
this book. Over the past two decades, I have seen many faces come and go, firms started
and shut down. In my experience, there is one critical mistake that underlies all those
failures.
1.2.1 The Sisyphus Paradigm
Discretionary portfolio managers (PMs) make investment decisions that do not follow a
particular theory or rationale (if there were one, they would be systematic PMs). They
consume raw news and analyses, but mostly rely on their judgment or intuition. They may
rationalize those decisions based on some story, but there is always a story for every
decision. Because nobody fully understands the logic behind their bets, investment firms
ask them to work independently from one another, in silos, to ensure diversification. If you
have ever attended a meeting of discretionary PMs, you probably noticed how long and
aimless they can be. Each attendee seems obsessed about one particular piece of a

---

Every successful quantitative firm I am aware of applies the meta-strategy paradigm
(López de Prado [2014]). Accordingly, this book was written as a research manual for
teams, not for individuals. Through its chapters you will learn how to set up a research
factory, as well as the various stations of the assembly line. The role of each quant is to
specialize in a particular task, to become the best there is at it, while having a holistic view
of the entire process. This book outlines the factory plan, where teamwork yields
discoveries at a predictable rate, with no reliance on lucky strikes. This is how Berkeley
Lab and other U.S. National Laboratories routinely make scientific discoveries, such as
adding 16 elements to the periodic table, or laying out the groundwork for MRIs and PET
scans. 1 No particular individual is responsible for these discoveries, as they are the
outcome of team efforts where everyone contributes. Of course, setting up these financial
laboratories takes time, a

### Code Examples

```unknown
requires people who know what they are doing and have done
```

```unknown
requires a lot of computational power, so Part 5 wraps up the book with some useful HPC
useful to a multiplicity of stations. Chapters 2–9 and 17–19 are dedicated to this all-
important station.
```

---

The discovery of investment strategies has undergone a similar evolution. If a decade ago it
was relatively common for an individual to discover macroscopic alpha (i.e., using simple
mathematical tools like econometrics), currently the chances of that happening are quickly
converging to zero. Individuals searching nowadays for macroscopic alpha, regardless of
their experience or knowledge, are fighting overwhelming odds. The only true alpha left is
microscopic, and finding it requires capital-intensive industrial methods. Just like with
gold, microscopic alpha does not mean smaller overall profits. Microscopic alpha today is
much more abundant than macroscopic alpha has ever been in history. There is a lot of
money to be made, but you will need to use heavy ML tools.
Let us review some of the stations involved in the chain of production within a modern
asset manager.
1.3.1.1 Data Curators
This is the station responsible for collecting, cleaning, indexing, storing, adjusting, and
delive

### Code Examples

```unknown
requires capital-intensive industrial methods. Just like with
```

```unknown
importance techniques. For example, feature analysts
```

```unknown
used in alternative ways: execution, monitoring of liquidity
```

---

In this station, informative features are transformed into actual investment algorithms. A
strategist will parse through the libraries of features looking for ideas to develop an
investment strategy. These features were discovered by different analysts studying a wide
range of instruments and asset classes. The goal of the strategist is to make sense of all
these observations and to formulate a general theory that explains them. Therefore, the
strategy is merely the experiment designed to test the validity of this theory. Team
members are data scientists with a deep knowledge of financial markets and the economy.
Remember, the theory needs to explain a large collection of important features. In
particular, a theory must identify the economic mechanism that causes an agent to lose
money to us. Is it a behavioral bias? Asymmetric information? Regulatory constraints?
Features may be discovered by a black box, but the strategy is developed in a white box.
Gluing together a number of catalo

### Code Examples

```unknown
uses an agent to lose
```

```unknown
used by other stations, for reasons that will become
```

```unknown
used by multiple strategies, especially when they share
```

---

1.3.1.6 Portfolio Oversight
Once a strategy is deployed, it follows a cursus honorum , which entails the following
stages or lifecycle:
1. Embargo: Initially, the strategy is run on data observed after the end date of the
backtest. Such a period may have been reserved by the backtesters, or it may be the
result of implementation delays. If embargoed performance is consistent with backtest
results, the strategy is promoted to the next stage.
2. Paper trading: At this point, the strategy is run on a live, real-time feed. In this way,
performance will account for data parsing latencies, calculation latencies, execution
delays, and other time lapses between observation and positioning. Paper trading will
take place for as long as it is needed to gather enough evidence that the strategy
performs as expected.
3. Graduation: At this stage, the strategy manages a real position, whether in isolation
or as part of an ensemble. Performance is evaluated precisely, including attributed
risk, return

---

Part
Chapter Fin. data Software Hardware Math Meta-Strat Overfitting
1
2
X
X
1
3
X
X
1
4
X
X
1
5
X
X
X
2
6
X
2
7
X
X
X
2
8
X
X
2
9
X
X
3
10
X
X
3
11
X
X
X
3
12
X
X
X
3
13
X
X
X
3
14
X
X
X

---

3
15
X
X
X
3
16
X
X
X
X
4
17
X
X
X
4
18
X
X
X
4
19
X
X
5
20
X
X
X
5
21
X
X
X
5
22
X
X
X
Throughout the book, you will find many references to journal articles I have published
over the years. Rather than repeating myself, I will often refer you to one of them, where
you will find a detailed analysis of the subject at hand. All of my cited papers can be
downloaded for free, in pre-print format, from my website: www.QuantResearch.org .
1.3.2.1 Data
Problem: Garbage in, garbage out.
Solution: Work with unique, hard-to-manipulate data. If you are the only user of this
data, whatever its value, it is all for you.
How:
Chapter 2: Structure your data correctly.
Chapter 3: Produce informative labels.
Chapters 4 and 5: Model non-IID series properly.
Chapters 17–19: Find predictive features.
1.3.2.2 Software
Problem: A specialized task requires customized tools.

### Code Examples

```unknown
requires customized tools.
used among others by
```

---

Solution: Develop your own classes. Using popular libraries means more competitors
tapping the same well.
How:
Chapters 2–22: Throughout the book, for each chapter, we develop our own
functions. For your particular problems, you will have to do the same, following
the examples in the book.
1.3.2.3 Hardware
Problem: ML involves some of the most computationally intensive tasks in all of
mathematics.
Solution: Become an HPC expert. If possible, partner with a National Laboratory to
build a supercomputer.
How:
Chapters 20 and 22: Learn how to think in terms of multiprocessing
architectures. Whenever you code a library, structure it in such a way that
functions can be called in parallel. You will find plenty of examples in the book.
Chapter 21: Develop algorithms for quantum computers.
1.3.2.4 Math
Problem: Mathematical proofs can take years, decades, and centuries. No investor will
wait that long.
Solution: Use experimental math. Solve hard, intractable problems, not by proof but
by experi

---

