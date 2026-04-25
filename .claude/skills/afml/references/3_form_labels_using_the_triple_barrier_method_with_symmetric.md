# 3. Form labels using the triple-barrier method, with symmetric

3. Form labels using the triple-barrier method, with symmetric
horizontal barriers of twice the daily standard deviation, and a
vertical barrier of 5 days.
4. Fit a bagging classifier of decision trees where:
1. The observed features are bootstrapped using the sequential
method from Chapter 4.
2. On each bootstrapped sample, sample weights are determined
using the techniques from Chapter 4.
References
1. Alexander, C. (2001): Market Models , 1st edition. John Wiley & Sons.
2. Hamilton, J. (1994): Time Series Analysis , 1st ed. Princeton University
Press.
3. Hosking, J. (1981): “Fractional differencing.” Biometrika , Vol. 68, No. 1,
pp. 165–176.
4. Jensen, A. and M. Nielsen (2014): “A fast fractional difference
algorithm.” Journal of Time Series Analysis , Vol. 35, No. 5, pp. 428–436.
5. López de Prado, M. (2015): “The Future of Empirical Finance.” Journal
of Portfolio Management , Vol. 41, No. 4, pp. 140–144. Available at
https://ssrn.com/abstract=2609734 .
Bibliography
1. Cavaliere, G

---

Journal of Economics , Vol. 47, No. 4, pp. 1078–1130.
6. Mackinnon, J. and M. Nielsen, M. (2014): “Numerical distribution
functions of fractional unit root and cointegration tests.” Journal of
Applied Econometrics , Vol. 29, No. 1, pp. 161–171.
PART 2
Modelling
1. Chapter 6 Ensemble Methods
2. Chapter 7 Cross-Validation in Finance
3. Chapter 8 Feature Importance
4. Chapter 9 Hyper-Parameter Tuning with Cross-Validation
CHAPTER 6
Ensemble Methods
6.1 Motivation
In this chapter we will discuss two of the most popular ML ensemble methods.
1 In the references and footnotes you will find books and articles that introduce
these techniques. As everywhere else in this book, the assumption is that you
have already used these approaches. The goal of this chapter is to explain what
makes them effective, and how to avoid common errors that lead to their
misuse in finance.
6.2 The Three Sources of Errors
ML models generally suffer from three errors: 2
1. Bias: This error is caused by unrealistic as

### Code Examples

```unknown
used these approaches. The goal of this chapter is to explain what
```

```unknown
used by unrealistic assumptions. When bias is high,
```

```unknown
important relations between
```

---

set, and that is why even minimal changes in the training set can produce
wildly different predictions. Rather than modelling the general patterns in
the training set, the algorithm has mistaken noise with signal.
3. Noise: This error is caused by the variance of the observed values, like
unpredictable changes or measurement errors. This is the irreducible error,
which cannot be explained by any model.
Consider a training set of observations { x i } i = 1, …, n and real-valued outcomes
{ y i } i = 1, …, n . Suppose a function f [ x ] exists, such that y = f [ x ] + ϵ, where
ϵ is white noise with E[ϵ i ] = 0 and E[ϵ 2 
i ] = σ ϵ 
2 . We would like to estimate
the function 
 that best fits f [ x ], in the sense of making the variance of the
estimation error 
 minimal (the mean squared error cannot be
zero, because of the noise represented by σ 2 
ϵ ). This mean-squared error can be
decomposed as
An ensemble method is a method that combines a set of weak learners, all
based on the same le

### Code Examples

```unknown
use of the noise represented by σ 2
```

---

If you use sklearn's BaggingClassifier class to compute the out-of-bag
accuracy, you should be aware of this bug: https://github.com/scikit-
learn/scikit-learn/issues/8933 . One workaround is to rename the labels in
integer sequential order.
6.3.1 Variance Reduction
Bagging's main advantage is that it reduces forecasts’ variance, hence helping
address overfitting. The variance of the bagged prediction (φ i [ c ]) is a
function of the number of bagged estimators ( N ), the average variance of a
single estimator's prediction (  ), and the average correlation among their
forecasts (  ):
where σ i , j is the covariance of predictions by estimators i , j ; 
 ; and
 
 .
The equation above shows that bagging is only effective to the extent that 
; as 
 . One of the goals of sequential
bootstrapping (Chapter 4) is to produce samples as independent as possible,
thereby reducing  , which should lower the variance of bagging classifiers.

### Code Examples

```php
use sklearn's BaggingClassifier class to compute the out-of-bag
```

```unknown
BaggingClassifier
```

---

Figure 6.1 plots the standard deviation of the bagged prediction as a function of
N ∈ [5, 30], 
 and 
 .
Figure 6.1 Standard deviation of the bagged prediction
6.3.2 Improved Accuracy
Consider a bagging classifier that makes a prediction on k classes by majority
voting among N independent classifiers. We can label the predictions as {0, 1},
where 1 means a correct prediction. The accuracy of a classifier is the
probability p of labeling a prediction as 1. On average we will get Np
predictions labeled as 1, with variance Np (1 − p ). Majority voting makes the
correct prediction when the most forecasted class is observed. For example, for
N = 10 and k = 3, the bagging classifier made a correct prediction when class A
was observed and the cast votes were [ A , B , C ] = [4, 3, 3]. However, the
bagging classifier made an incorrect prediction when class A was observed and
the cast votes were [ A , B , C ] = [4, 1, 5]. A sufficient condition is that the sum

---

of these labels is 
 . A necessary (non-sufficient) condition is that 
 ,
which occurs with probability
The implication is that for a sufficiently large N , say 
 , then
 , hence the bagging classifier's accuracy exceeds the
average accuracy of the individual classifiers. Snippet 6.1 implements this
calculation.
SNIPPET 6.1 ACCURACY OF THE BAGGING CLASSIFIER
This is a strong argument in favor of bagging any classifier in general, when
computational requirements permit it. However, unlike boosting, bagging
cannot improve the accuracy of poor classifiers: If the individual learners are
poor classifiers ( 
 ), majority voting will still perform poorly (although
with lower variance). Figure 6.2 illustrates these facts. Because it is easier to
achieve 
 than 
 , bagging is more likely to be successful in reducing
variance than in reducing bias.
For further analysis on this topic, the reader is directed to Condorcet's Jury
Theorem. Although the theorem is derived for the purposes of majority

### Code Examples

```unknown
requirements permit it. However, unlike boosting, bagging
```

```unknown
use it is easier to
```

---

Figure 6.2 Accuracy of a bagging classifier as a function of the individual
estimator's accuracy (P ), the number of estimators (N ), and k  = 2
6.3.3 Observation Redundancy
In Chapter 4 we studied one reason why financial observations cannot be
assumed to be IID. Redundant observations have two detrimental effects on
bagging. First, the samples drawn with replacement are more likely to be
virtually identical, even if they do not share the same observations. This makes
 , and bagging will not reduce variance, regardless of N. For example, if
each observation at t is labeled according to the return between t and t + 100 ,
we should sample 1% of the observations per bagged estimator, but not more.
Chapter 4, Section 4.5 recommended three alternative solutions, one of which
consisted of setting max_samples=out[‘tW’].mean() in sklearn's
implementation of the bagging classifier class. Another (better) solution was to
apply the sequential bootstrap method.

### Code Examples

```unknown
max_samples=out[‘tW’].mean()
StratifiedKFold(n_splits=k,
```

---

The second detrimental effect from observation redundancy is that out-of-bag
accuracy will be inflated. This happens because random sampling with
replacement places in the training set samples that are very similar to those out-
of-bag. In such a case, a proper stratified k-fold cross-validation without
shuffling before partitioning will show a much lower testing-set accuracy than
the one estimated out-of-bag. For this reason, it is advisable to set
StratifiedKFold(n_splits=k, shuffle=False) when using that sklearn
class, cross-validate the bagging classifier, and ignore the out-of-bag accuracy
results. A low number k is preferred to a high one, as excessive partitioning
would again place in the testing set samples too similar to those used in the
training set.
6.4 Random Forest
Decision trees are known to be prone to overfitting, which increases the
variance of the forecasts. 3 In order to address this concern, the random forest
(RF) method was designed to produce ensemble forecasts w

### Code Examples

```unknown
use random sampling with
```

```unknown
shuffle=False)
clf=DecisionTreeClassifier(criterion=‘entropy’,max_features=‘auto’,class_weight=‘balanced’)
```

---

illustration purposes, I will refer to sklearn's classes; however, these solutions
can be applied to any implementation:
1. Set a parameter max_features to a lower value, as a way of forcing
discrepancy between trees.
2. Early stopping: Set the regularization parameter
min_weight_fraction_leaf to a sufficiently large value (e.g., 5%) such
that out-of-bag accuracy converges to out-of-sample (k-fold) accuracy.
3. Use BaggingClassifier on DecisionTreeClassifier where
max_samples is set to the average uniqueness (avgU ) between samples.
1. clf=DecisionTreeClassifier(criterion=‘entropy’,max_feature
s=‘auto’,class_weight=‘balanced’)
2. bc=BaggingClassifier(base_estimator=clf,n_estimators=1000,
max_samples=avgU,max_features=1.)
4. Use BaggingClassifier on RandomForestClassifier where
max_samples is set to the average uniqueness (avgU ) between samples.
1. clf=RandomForestClassifier(n_estimators=1,criterion=‘entro
py’,bootstrap=False,class_weight=‘balanced_subsample’)
2. bc=BaggingClassifier(b

### Code Examples

```unknown
bc=BaggingClassifier(base_estimator=clf,n_estimators=1000,max_samples=avgU,max_features=1.)
```

```unknown
clf=RandomForestClassifier(n_estimators=1,criterion=‘entropy’,bootstrap=False,class_weight=‘balanced_subsample’)
```

```unknown
min_weight_fraction_leaf
```

---

When fitting decision trees, a rotation of the features space in a direction that
aligns with the axes typically reduces the number of levels needed by the tree.
For this reason, I suggest you fit RF on a PCA of the features, as that may
speed up calculations and reduce some overfitting (more on this in Chapter 8).
Also, as discussed in Chapter 4, Section 4.8,
class_weight=‘balanced_subsample’ will help you prevent the trees from
misclassifying minority classes.
6.5 Boosting
Kearns and Valiant [1989] were among the first to ask whether one could
combine weak estimators in order to achieve one with high accuracy. Shortly
after, Schapire [1990] demonstrated that the answer to that question was
affirmative, using the procedure we today call boosting. In general terms, it
works as follows: First, generate one training set by random sampling with
replacement, according to some sample weights (initialized with uniform
weights). Second, fit one estimator using that training set. Third, if the

---

