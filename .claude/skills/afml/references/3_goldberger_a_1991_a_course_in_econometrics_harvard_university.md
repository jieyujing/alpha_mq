# 3. Goldberger, A. (1991): A Course in Econometrics . Harvard University

3. Goldberger, A. (1991): A Course in Econometrics . Harvard University
Press, 1st edition.
4. Hill, R. and L. Adkins (2001): “Collinearity.” In Baltagi, Badi H. A
Companion to Theoretical Econometrics , 1st ed. Blackwell, pp. 256–278.
5. Louppe, G., L. Wehenkel, A. Sutera, and P. Geurts (2013):
“Understanding variable importances in forests of randomized trees.”
Proceedings of the 26th International Conference on Neural Information
Processing Systems, pp. 431–439.
6. Strobl, C., A. Boulesteix, A. Zeileis, and T. Hothorn (2007): “Bias in
random forest variable importance measures: Illustrations, sources and a
solution.” BMC Bioinformatics , Vol. 8, No. 25, pp. 1–11.
7. White, A. and W. Liu (1994): “Technical note: Bias in information-based
measures in decision tree induction.” Machine Learning , Vol. 15, No. 3,
pp. 321–329.
Note
1     http://blog.datadive.net/selecting-good-features-part-iii-random-forests/ .
CHAPTER 9
Hyper-Parameter Tuning with Cross-Validation
9.1 Motivation
Hyper-p

### Code Examples

```unknown
importances in forests of randomized trees.”
```

```unknown
importance measures: Illustrations, sources and a
used to pass sample_weight
```

---

Grid search cross-validation conducts an exhaustive search for the combination
of parameters that maximizes the CV performance, according to some user-
defined score function. When we do not know much about the underlying
structure of the data, this is a reasonable first approach. Scikit-learn has
implemented this logic in the function GridSearchCV , which accepts a CV
generator as an argument. For the reasons explained in Chapter 7, we need to
pass our PurgedKFold class (Snippet 7.3) in order to prevent that
GridSearchCV overfits the ML estimator to leaked information.
SNIPPET 9.1 GRID SEARCH WITH PURGED K-FOLD CROSS-
VALIDATION
Snippet 9.1 lists function clfHyperFit , which implements a purged
GridSearchCV . The argument fit_params can be used to pass sample_weight
, and param_grid contains the values that will be combined into a grid. In
addition, this function allows for the bagging of the tuned estimator. Bagging
an estimator is generally a good idea for the reasons explained in C

### Code Examples

```unknown
GridSearchCV
```

```unknown
PurgedKFold
```

```unknown
clfHyperFit
```

---

I advise you to use scoring=‘f1’ in the context of meta-labeling applications,
for the following reason. Suppose a sample with a very large number of
negative (i.e., label ‘0’) cases. A classifier that predicts all cases to be negative
will achieve high ‘accuracy’ or ‘neg_log_loss’ , even though it has not
learned from the features how to discriminate between cases. In fact, such a
model achieves zero recall and undefined precision (see Chapter 3, Section
3.7). The ‘f1’ score corrects for that performance inflation by scoring the
classifier in terms of precision and recall (see Chapter 14, Section 14.8).
For other (non-meta-labeling) applications, it is fine to use ‘accuracy’ or
‘neg_log_loss’ , because we are equally interested in predicting all cases.
Note that a relabeling of cases has no impact on ‘accuracy’ or
‘neg_log_loss’ , however it will have an impact on ‘f1’ .
This example introduces nicely one limitation of sklearn's Pipelines : Their fit
method does not expect a sample_we

### Code Examples

```unknown
use scoring=‘f1’ in the context of meta-labeling applications,
```

```unknown
use we are equally interested in predicting all cases.
```

```unknown
use the workaround in
```

---

For ML algorithms with a large number of parameters, a grid search cross-
validation (CV) becomes computationally intractable. In this case, an
alternative with good statistical properties is to sample each parameter from a
distribution (Begstra et al. [2011, 2012]). This has two benefits: First, we can
control for the number of combinations we will search for, regardless of the
dimensionality of the problem (the equivalent to a computational budget).
Second, having parameters that are relatively irrelevant performance-wise will
not substantially increase our search time, as would be the case with grid
search CV.
Rather than writing a new function to work with RandomizedSearchCV , let us
expand Snippet 9.1 to incorporate an option to this purpose. A possible
implementation is Snippet 9.3.
SNIPPET 9.3 RANDOMIZED SEARCH WITH PURGED K-FOLD
CV

### Code Examples

```unknown
RandomizedSearchCV
```

---

9.3.1 Log-Uniform Distribution
It is common for some ML algorithms to accept non-negative hyper-parameters
only. That is the case of some very popular parameters, such as C in the SVC
classifier and gamma in the RBF kernel. 1 We could draw random numbers from
a uniform distribution bounded between 0 and some large value, say 100. That
would mean that 99% of the values would be expected to be greater than 1.
That is not necessarily the most effective way of exploring the feasibility
region of parameters whose functions do not respond linearly. For example, an
SVC can be as responsive to an increase in C from 0.01 to 1 as to an increase in
C from 1 to 100. 2 So sampling C from a U [0, 100] (uniform) distribution will
be inefficient. In those instances, it seems more effective to draw values from a

---

distribution where the logarithm of those draws will be distributed uniformly. I
call that a “log-uniform distribution,” and since I could not find it in the
literature, I must define it properly.
A random variable x follows a log-uniform distribution between a > 0 and b >
a if and only if log [ x ] ∼ U [log [ a ], log [ b ]]. This distribution has a CDF:
From this, we derive a PDF:

---

Figure 9.1 Result from testing the logUniform_gen class
Note that the CDF is invariant to the base of the logarithm, since
 for any base c , thus the random variable is not a function of c.
Snippet 9.4 implements (and tests) in scipy.stats a random variable where [
a , b ] = [1 E − 3, 1 E 3], hence log [ x ] ∼ U [log [1 E − 3], log [1 E 3]]. Figure
9.1 illustrates the uniformity of the samples in log-scale.
SNIPPET 9.4 THE LOGUNIFORM_GEN CLASS

### Code Examples

```unknown
scipy.stats
```

```unknown
logUniform_gen
```

```unknown
LOGUNIFORM_GEN
scoring=‘neg_log_loss’
```

---

9.4 Scoring and Hyper-parameter Tuning
Snippets 9.1 and 9.3 set scoring=‘f1’ for meta-labeling applications. For
other applications, they set scoring=‘neg_log_loss’ rather than the standard
scoring=‘accuracy’ . Although accuracy has a more intuitive interpretation, I
suggest that you use neg_log_loss when you are tuning hyper-parameters for
an investment strategy. Let me explain my reasoning.
Suppose that your ML investment strategy predicts that you should buy a
security, with high probability. You will enter a large long position, as a
function of the strategy's confidence. If the prediction was erroneous, and the
market sells off instead, you will lose a lot of money. And yet, accuracy
accounts equally for an erroneous buy prediction with high probability and for
an erroneous buy prediction with low probability. Moreover, accuracy can
offset a miss with high probability with a hit with low probability.
Investment strategies profit from predicting the right label with high
confidence

### Code Examples

```unknown
use neg_log_loss when you are tuning hyper-parameters for
```

```unknown
scoring=‘accuracy’
```

```unknown
scoring=‘f1’
```

---

figure, log loss is large due to misses with high probability, even though the
accuracy is 50% in all cases.
Figure 9.2 Log loss as a function of predicted probabilities of hit and miss
There is a second reason to prefer cross-entropy loss over accuracy. CV scores
a classifier by applying sample weights (see Chapter 7, Section 7.5). As you
may recall from Chapter 4, observation weights were determined as a function
of the observation's absolute return. The implication is that sample weighted
cross-entropy loss estimates the classifier's performance in terms of variables
involved in a PnL (mark-to-market profit and losses) calculation: It uses the
correct label for the side, probability for the position size, and sample weight

---

for the observation's return/outcome. That is the right ML performance metric
for hyper-parameter tuning of financial applications, not accuracy.
When we use log loss as a scoring statistic, we often prefer to change its sign,
hence referring to “neg log loss . ” The reason for this change is cosmetic,
driven by intuition: A high neg log loss value is preferred to a low neg log loss
value, just as with accuracy. Keep in mind this sklearn bug when you use
neg_log_loss : https://github.com/scikit-learn/scikit-learn/issues/9144 . To
circumvent this bug, you should use the cvScore function presented in Chapter
7.
Exercises
1. 
Using the function getTestData from Chapter 8, form a
synthetic dataset of 10,000 observations with 10 features, where
5 are informative and 5 are noise.
1. Use GridSearchCV on 10-fold CV to find the C , gamma optimal
hyper-parameters on a SVC with RBF kernel, where
param_grid = {'C':[1E-2,1E-1,1,10,100],'gamma':[1E-2,1E-
1,1,10,100]} and the scoring function is neg_

### Code Examples

```unknown
use the cvScore function presented in Chapter
```

```typescript
use log loss as a scoring statistic, we often prefer to change its sign,
```

```unknown
param_distributions = {‘C’:logUniform(a = 1E-2,b =1E2),‘gamma’:logUniform(a = 1E-2,b = 1E2)},n_iter = 25
```

---

