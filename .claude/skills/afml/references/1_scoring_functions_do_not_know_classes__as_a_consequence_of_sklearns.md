# 1. Scoring functions do not know classes_ , as a consequence of sklearn's

1. Scoring functions do not know classes_ , as a consequence of sklearn's
reliance on numpy arrays rather than pandas series:
https://github.com/scikit-learn/scikit-learn/issues/6231
2. cross_val_score will give different results because it passes weights to
the fit method, but not to the log_loss method: https://github.com/scikit-
learn/scikit-learn/issues/9144
SNIPPET 7.4 USING THE PURGEDKFOLD CLASS
Please understand that it may take a long time until a fix for these bugs is
agreed upon, implemented, tested, and released. Until then, you should use
cvScore in Snippet 7.4, and avoid running the function cross_val_score .
Exercises

### Code Examples

```unknown
use it passes weights to
```

```unknown
cross_val_score
```

```unknown
PURGEDKFOLD
```

---

1. 
Why is shuffling a dataset before conducting k-fold CV
generally a bad idea in finance? What is the purpose of
shuffling? Why does shuffling defeat the purpose of k-fold CV
in financial datasets?
2. 
Take a pair of matrices ( X , y ), representing observed features
and labels. These could be one of the datasets derived from the
exercises in Chapter 3.
1. Derive the performance from a 10-fold CV of an RF classifier on (X ,
y ), without shuffling.
2. Derive the performance from a 10-fold CV of an RF on (X , y ), with
shuffling.
3. Why are both results so different?
4. How does shuffling leak information?
3. 
Take the same pair of matrices ( X , y ) you used in exercise 2.
1. Derive the performance from a 10-fold purged CV of an RF on (X , y
), with 1% embargo.
2. Why is the performance lower?
3. Why is this result more realistic?
4. 
In this chapter we have focused on one reason why k-fold CV
fails in financial applications, namely the fact that some
information from the testing set 

### Code Examples

```unknown
used on one reason why k-fold CV
```

```unknown
used to evaluate the trained parameters,
```

```unknown
used in exercise 2.
```

---

and the testing is run only on the one configuration chosen in the
validation phase. In what case does this procedure still fail?
3. What is the key to avoiding selection bias?
Bibliography
1. Bharat Rao, R., G. Fung, and R. Rosales (2008): “On the dangers of cross-
validation: An experimental evaluation.” White paper, IKM CKS Siemens
Medical Solutions USA. Available at
http://people.csail.mit.edu/romer/papers/CrossVal_SDM08.pdf .
2. Bishop, C. (1995): Neural Networks for Pattern Recognition , 1st ed.
Oxford University Press.
3. Breiman, L. and P. Spector (1992): “Submodel selection and evaluation in
regression: The X-random case.” White paper, Department of Statistics,
University of California, Berkeley. Available at
http://digitalassets.lib.berkeley.edu/sdtr/ucb/text/197.pdf .
4. Hastie, T., R. Tibshirani, and J. Friedman (2009): The Elements of
Statistical Learning , 1st ed. Springer.
5. James, G., D. Witten, T. Hastie and R. Tibshirani (2013): An Introduction
to Statistical Learnin

---

fact that we are repeating a test over and over on the same data will likely lead
to a false discovery. This methodological error is so notorious among
statisticians that they consider it scientific fraud, and the American Statistical
Association warns against it in its ethical guidelines (American Statistical
Association [2016], Discussion #4). It typically takes about 20 such iterations
to discover a (false) investment strategy subject to the standard significance
level (false positive rate) of 5%. In this chapter we will explore why such an
approach is a waste of time and money, and how feature importance offers an
alternative.
8.2 The Importance of Feature Importance
A striking facet of the financial industry is that so many very seasoned
portfolio managers (including many with a quantitative background) do not
realize how easy it is to overfit a backtest. How to backtest properly is not the
subject of this chapter; we will address that extremely important topic in
Chapters 11–15. 

### Code Examples

```unknown
importance offers an
```

```unknown
importance opens up the proverbial
```

```unknown
important, we can learn more by
```

---

over time? Can those regime switches be predicted? Are those important
features also relevant to other related financial instruments? Are they relevant
to other asset classes? What are the most relevant features across all financial
instruments? What is the subset of features with the highest rank correlation
across the entire investment universe? This is a much better way of researching
strategies than the foolish backtest cycle. Let me state this maxim as one of the
most critical lessons I hope you learn from this book:
Snippet 8.1 Marcos’ First Law of Backtesting—Ignore at your
own peril
“Backtesting is not a research tool. Feature importance is.”
Marcos López de Prado Advances in Financial Machine Learning (2018)
8.3 Feature Importance with Substitution Effects
I find it useful to distinguish between feature importance methods based on
whether they are impacted by substitution effects. In this context, a substitution
effect takes place when the estimated importance of one feature i

### Code Examples

```unknown
importance of one feature is reduced by
```

```unknown
importance analysis on the orthogonal features.
```

```unknown
importance (in-sample,
```

---

