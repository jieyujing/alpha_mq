# 2. Kearns, M. and L. Valiant (1989): “Cryptographic limitations on learning

2. Kearns, M. and L. Valiant (1989): “Cryptographic limitations on learning
Boolean formulae and finite automata.” In Proceedings of the 21st Annual
ACM Symposium on Theory of Computing, pp. 433–444, New York.
Association for Computing Machinery.
3. Schapire, R. (1990): “The strength of weak learnability.” Machine
Learning . Kluwer Academic Publishers. Vol. 5 No. 2, pp. 197–227.
Bibliography
1. Gareth, J., D. Witten, T. Hastie, and R. Tibshirani (2013): An Introduction
to Statistical Learning: With Applications in R , 1st ed. Springer-Verlag.
2. Hackeling, G. (2014): Mastering Machine Learning with Scikit-Learn ,
1st ed. Packt Publishing.
3. Hastie, T., R. Tibshirani and J. Friedman (2016): The Elements of
Statistical Learning , 2nd ed. Springer-Verlag.
4. Hauck, T. (2014): Scikit-Learn Cookbook , 1st ed. Packt Publishing.
5. Raschka, S. (2015): Python Machine Learning , 1st ed. Packt Publishing.
Notes
1    For an introduction to ensemble methods, please visit: http://scikit-
learn.org

---

7.1 Motivation
The purpose of cross-validation (CV) is to determine the generalization error of
an ML algorithm, so as to prevent overfitting. CV is yet another instance where
standard ML techniques fail when applied to financial problems. Overfitting
will take place, and CV will not be able to detect it. In fact, CV will contribute
to overfitting through hyper-parameter tuning. In this chapter we will learn
why standard CV fails in finance, and what can be done about it.
7.2 The Goal of Cross-Validation
One of the purposes of ML is to learn the general structure of the data, so that
we can produce predictions on future, unseen features. When we test an ML
algorithm on the same dataset as was used for training, not surprisingly, we
achieve spectacular results. When ML algorithms are misused that way, they
are no different from file lossy-compression algorithms: They can summarize
the data with extreme fidelity, yet with zero forecasting power.
CV splits observations drawn from an IID p

### Code Examples

```unknown
used for training, not surprisingly, we
```

```unknown
used that way, they
```

---

Figure 7.1 Train/test splits in a 5-fold CV scheme
The outcome from k-fold CV is a kx1 array of cross-validated performance
metrics. For example, in a binary classifier, the model is deemed to have
learned something if the cross-validated accuracy is over 1/2, since that is the
accuracy we would achieve by tossing a fair coin.
In finance, CV is typically used in two settings: model development (like
hyper-parameter tuning) and backtesting. Backtesting is a complex subject that
we will discuss thoroughly in Chapters 10–16. In this chapter, we will focus on
CV for model development.
7.3 Why K-Fold CV Fails in Finance
By now you may have read quite a few papers in finance that present k-fold
CV evidence that an ML algorithm performs well. Unfortunately, it is almost
certain that those results are wrong. One reason k-fold CV fails in finance is
because observations cannot be assumed to be drawn from an IID process. A
second reason for CV's failure is that the testing set is used multiple t

### Code Examples

```sql
use observations cannot be assumed to be drawn from an IID process. A
```

```unknown
used in two settings: model development (like
```

```unknown
used multiple times in
```

---

Leakage takes place when the training set contains information that also
appears in the testing set. Consider a serially correlated feature X that is
associated with labels Y that are formed on overlapping data:
Because of the serial correlation, X t ≈ X t + 1 .
Because labels are derived from overlapping datapoints, Y t ≈ Y t + 1 .
By placing t and t + 1 in different sets, information is leaked. When a classifier
is first trained on ( X t , Y t ), and then it is asked to predict E[ Y t + 1 | X t + 1 ]
based on an observed X t + 1 , this classifier is more likely to achieve Y t + 1 = E[
Y t + 1 | X t + 1 ] even if X is an irrelevant feature.
If X is a predictive feature, leakage will enhance the performance of an already
valuable strategy. The problem is leakage in the presence of irrelevant features,
as this leads to false discoveries. There are at least two ways to reduce the
likelihood of leakage:
1. Drop from the training set any observation i where Y i is a function of
information

### Code Examples

```sql
use labels are derived from overlapping datapoints, Y t ≈ Y t + 1 .
```

```unknown
use of the serial correlation, X t ≈ X t + 1 .
```

```unknown
used to determine Y j , and j belongs to the testing set.
```

---

One way to reduce leakage is to purge from the training set all observations
whose labels overlapped in time with those labels included in the testing set. I
call this process “purging.” In addition, since financial features often
incorporate series that exhibit serial correlation (like ARMA processes), we
should eliminate from the training set observations that immediately follow an
observation in the testing set. I call this process “embargo.”
7.4.1 Purging the Training Set
Suppose a testing observation whose label Y j is decided based on the
information set Φ j . In order to prevent the type of leakage described in the
previous section, we would like to purge from the training set any observation
whose label Y i is decided based on the information set Φ i , such that Φ i ∩Φ j =
∅ .
In particular, we will determine that there is informational overlap between two
observations i and j whenever Y i and Y j are concurrent (see Chapter 4, Section
4.3), in the sense that both labels are co

### Code Examples

```unknown
included in the testing set. I
```

```unknown
use of notation). For example, in the context of the triple-barrier
use we allow the model to recalibrate more
```

---

When leakage takes place, performance improves merely by increasing k → T ,
where T is the number of bars. The reason is that the larger the number of
testing splits, the greater the number of overlapping observations in the training
set. In many cases, purging suffices to prevent leakage: Performance will
improve as we increase k , because we allow the model to recalibrate more
often. But beyond a certain value k *, performance will not improve, indicating
that the backtest is not profiting from leaks. Figure 7.2 plots one partition of the
k-fold CV. The test set is surrounded by two train sets, generating two overlaps
that must be purged to prevent leakage.

---

Figure 7.2 Purging overlap in the training set
7.4.2 Embargo
For those cases where purging is not able to prevent all leakage, we can impose
an embargo on training observations after every test set. The embargo does not
need to affect training observations prior to a test set, because training labels Y i
= f [[ t i , 0 , t i , 1 ]], where t i , 1 < t j , 0 (training ends before testing begins),
contain information that was available at the testing time t j , 0 . In other words,
we are only concerned with training labels Y i = f [[ t i , 0 , t i , 1 ]] that take place
immediately after the test, t j , 1 ≤ t i , 0 ≤ t j , 1 + h. We can implement this
embargo period h by setting Y j = f [[ t j , 0 , t j , 1 + h ]] before purging. A small
value h ≈ .01 T often suffices to prevent all leakage, as can be confirmed by
testing that performance does not improve indefinitely by increasing k → T .
Figure 7.3 illustrates the embargoing of train observations immediately after
the testing set. Snipp

### Code Examples

```unknown
use training labels Y i
```

---

Figure 7.3 Embargo of post-test train observations
SNIPPET 7.2 EMBARGO ON TRAINING OBSERVATIONS

---

7.4.3 The Purged K-Fold Class
In the previous sections we have discussed how to produce training/testing
splits when labels overlap. That introduced the notion of purging and
embargoing, in the particular context of model development. In general, we
need to purge and embargo overlapping training observations whenever we
produce a train/test split, whether it is for hyper-parameter fitting, backtesting,
or performance evaluation. Snippet 7.3 extends scikit-learn's KFold class to
account for the possibility of leakages of testing information into the training
set.
SNIPPET 7.3 CROSS-VALIDATION CLASS WHEN
OBSERVATIONS OVERLAP

---

7.5 Bugs in Sklearn's Cross-Validation
You would think that something as critical as cross-validation would be
perfectly implemented in one of the most popular ML libraries. Unfortunately
that is not the case, and this is one of the reasons you must always read all the
code you run, and a strong point in favor of open source. One of the many
upsides of open-source code is that you can verify everything and adjust it to
your needs. Snippet 7.4 addresses two known sklearn bugs:

---

