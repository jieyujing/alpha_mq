# 1. Masking effects take place when some features are systematically ignored

1. Masking effects take place when some features are systematically ignored
by tree-based classifiers in favor of others. In order to avoid them, set
max_features=int(1) when using sklearn's RF class. In this way, only
one random feature is considered per level.
1. Every feature is given a chance (at some random levels of some
random trees) to reduce impurity.
2. Make sure that features with zero importance are not averaged, since
the only reason for a 0 is that the feature was not randomly chosen.
Replace those values with np.nan .
2. The procedure is obviously IS. Every feature will have some importance,
even if they have no predictive power whatsoever.
3. MDI cannot be generalized to other non-tree based classifiers.
4. By construction, MDI has the nice property that feature importances add
up to 1, and every feature importance is bounded between 0 and 1.
5. The method does not address substitution effects in the presence of
correlated features. MDI dilutes the importance of substit

### Code Examples

```unknown
importance is bounded between 0 and 1.
```

```unknown
importance of substitute features,
```

```unknown
use of their interchangeability: The importance of two identical
```

---

8.3.2 Mean Decrease Accuracy
Mean decrease accuracy (MDA) is a slow, predictive-importance (out-of-
sample, OOS) method. First, it fits a classifier; second, it derives its
performance OOS according to some performance score (accuracy, negative
log-loss, etc.); third, it permutates each column of the features matrix ( X ), one
column at a time, deriving the performance OOS after each column's
permutation. The importance of a feature is a function of the loss in
performance caused by its column's permutation. Some relevant considerations
include:
1. This method can be applied to any classifier, not only tree-based
classifiers.
2. MDA is not limited to accuracy as the sole performance score. For
example, in the context of meta-labeling applications, we may prefer to
score a classifier with F1 rather than accuracy (see Chapter 14,
Section 14.8 for an explanation). That is one reason a better descriptive
name would have been “permutation importance.” When the scoring
function does not corr

### Code Examples

```yaml
used by its column's permutation. Some relevant considerations
include:
```

```unknown
importance of a feature is a function of the loss in
```

```unknown
importance.” When the scoring
```

---

