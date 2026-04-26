# 5. The CV must be purged and embargoed, for the reasons explained in

5. The CV must be purged and embargoed, for the reasons explained in
Chapter 7.
Snippet 8.3 implements MDA feature importance with sample weights, with
purged k-fold CV, and with scoring by negative log-loss or accuracy. It
measures MDA importance as a function of the improvement (from
permutating to not permutating the feature), relative to the maximum possible
score (negative log-loss of 0, or accuracy of 1). Note that, in some cases, the
improvement may be negative, meaning that the feature is actually detrimental
to the forecasting power of the ML algorithm.
SNIPPET 8.3 MDA FEATURE IMPORTANCE

### Code Examples

```typescript
importance as a function of the improvement (from
```

```unknown
importance with sample weights, with
```

---

---

8.4 Feature Importance without Substitution Effects
Substitution effects can lead us to discard important features that happen to be
redundant. This is not generally a problem in the context of prediction, but it
could lead us to wrong conclusions when we are trying to understand, improve,
or simplify a model. For this reason, the following single feature importance
method can be a good complement to MDI and MDA.
8.4.1 Single Feature Importance
Single feature importance (SFI) is a cross-section predictive-importance (out-
of-sample) method. It computes the OOS performance score of each feature in
isolation. A few considerations:
1. This method can be applied to any classifier, not only tree-based
classifiers.
2. SFI is not limited to accuracy as the sole performance score.
3. Unlike MDI and MDA, no substitution effects take place, since only one
feature is taken into consideration at a time.
4. Like MDA, it can conclude that all features are unimportant, because
performance is evaluate

### Code Examples

```sql
useful in explaining the splits from feature A, even if feature B alone is
```

```unknown
important features that happen to be
```

```unknown
importance (SFI) is a cross-section predictive-importance (out-
```

---

8.4.2 Orthogonal Features
As argued in Section 8.3, substitution effects dilute the importance of features
measured by MDI, and significantly underestimate the importance of features
measured by MDA. A partial solution is to orthogonalize the features before
applying MDI and MDA. An orthogonalization procedure such as principal
components analysis (PCA) does not prevent all substitution effects, but at
least it should alleviate the impact of linear substitution effects.
Consider a matrix { X t , n } of stationary features, with observations t = 1, …, T
and variables n = 1, …, N . First, we compute the standardized features matrix
Z , such that Z t , n = σ − 1 
n ( X t , n − μ n ), where μ n is the mean of { X t , n } t = 1,
…, T and σ n is the standard deviation of { X t , n } t = 1, …, T . Second, we compute
the eigenvalues Λ and eigenvectors W such that Z ' ZW = W Λ, where Λ is an
NxN diagonal matrix with main entries sorted in descending order, and W is an
NxN orthonormal matrix. Th

---

Snippet 8.5 computes the smallest number of orthogonal features that explain
at least 95% of the variance of Z .
SNIPPET 8.5 COMPUTATION OF ORTHOGONAL FEATURES
Besides addressing substitution effects, working with orthogonal features
provides two additional benefits: (1) orthogonalization can also be used to
reduce the dimensionality of the features matrix X , by dropping features
associated with small eigenvalues. This usually speeds up the convergence of
ML algorithms; (2) the analysis is conducted on features designed to explain
the structure of the data.

---

Let me stress this latter point. An ubiquitous concern throughout the book is the
risk of overfitting. ML algorithms will always find a pattern, even if that
pattern is a statistical fluke. You should always be skeptical about the
purportedly important features identified by any method, including MDI,
MDA, and SFI. Now, suppose that you derive orthogonal features using PCA.
Your PCA analysis has determined that some features are more “principal” than
others, without any knowledge of the labels (unsupervised learning). That is,
PCA has ranked features without any possible overfitting in a classification
sense. When your MDI, MDA, or SFI analysis selects as most important (using
label information) the same features that PCA chose as principal (ignoring
label information), this constitutes confirmatory evidence that the pattern
identified by the ML algorithm is not entirely overfit. If the features were
entirely random, the PCA ranking would have no correspondance with the
feature importa

### Code Examples

```unknown
important features identified by any method, including MDI,
```

```unknown
importance ranking. Figure 8.1 displays the scatter plot of eigenvalues
```

```unknown
important (using
use the weightedtau function
```

---

Figure 8.1 Scatter plot of eigenvalues (x-axis) and MDI levels (y-axis) in log-
log scale
I find it useful to compute the weighted Kendall's tau between the feature
importances and their associated eigenvalues (or equivalently, their inverse
PCA rank). The closer this value is to 1, the stronger is the consistency between
PCA ranking and feature importance ranking. One argument for preferring a
weighted Kendall's tau over the standard Kendall is that we want to prioritize
rank concordance among the most importance features. We do not care so
much about rank concordance among irrelevant (likely noisy) features. The
hyperbolic-weighted Kendall's tau for the sample in Figure 8.1 is 0.8206.
Snippet 8.6 shows how to compute this correlation using Scipy. In this
example, sorting the features in descending importance gives us a PCA rank
sequence very close to an ascending list. Because the weightedtau function
gives higher weight to higher values, we compute the correlation on the inverse

### Code Examples

```unknown
useful to compute the weighted Kendall's tau between the feature
importances and their associated eigenvalues (or equivalently, their inverse
```

```unknown
importance ranking. One argument for preferring a
```

```unknown
importance features. We do not care so
```

---

PCA ranking, pcRank**-1 . The resulting weighted Kendall's tau is relatively
high, at 0.8133.
SNIPPET 8.6 COMPUTATION OF WEIGHTED KENDALL'S TAU
BETWEEN FEATURE IMPORTANCE AND INVERSE PCA
RANKING
8.5 Parallelized vs. Stacked Feature Importance
There are at least two research approaches to feature importance. First, for each
security i in an investment universe i = 1, …, I , we form a dataset ( X i , y i ),
and derive the feature importance in parallel. For example, let us denote λ i , j , k
the importance of feature j on instrument i according to criterion k. Then we
can aggregate all results across the entire universe to derive a combined Λ j , k
importance of feature j according to criterion k. Features that are important
across a wide variety of instruments are more likely to be associated with an
underlying phenomenon, particularly when these feature importances exhibit
high rank correlation across the criteria. It may be worth studying in-depth the
theoretical mechanism that makes 

### Code Examples

```typescript
important across all instruments simultaneously, as if the
```

```unknown
importance. First, for each
```

```unknown
importance in parallel. For example, let us denote λ i , j , k
```

---

entire investment universe were in fact a single instrument. Features stacking
presents some advantages: (1) The classifier will be fit on a much larger dataset
than the one used with the parallelized (first) approach; (2) the importance is
derived directly, and no weighting scheme is required for combining the
results; (3) conclusions are more general and less biased by outliers or
overfitting; and (4) because importance scores are not averaged across
instruments, substitution effects do not cause the dampening of those scores.
I usually prefer features stacking, not only for features importance but
whenever a classifier can be fit on a set of instruments, including for the
purpose of model prediction. That reduces the likelihood of overfitting an
estimator to a particular instrument or small dataset. The main disadvantage of
stacking is that it may consume a lot of memory and resources, however that is
where a sound knowledge of HPC techniques will come in handy (Chapters
20–22).
8.6

### Code Examples

```unknown
required for combining the
```

```unknown
use importance scores are not averaged across
```

```unknown
use the dampening of those scores.
```

---

Given that we know for certain what feature belongs to each class, we can
evaluate whether these three feature importance methods perform as designed.
Now we need a function that can carry out each analysis on the same dataset.
Snippet 8.8 accomplishes that, using bagged decision trees as default classifier
(Chapter 6).
SNIPPET 8.8 CALLING FEATURE IMPORTANCE FOR
ANY METHOD

### Code Examples

```typescript
importance methods perform as designed.
```

---

