# 2. Do the three methods agree on the important features? Why?

2. Do the three methods agree on the important features? Why?
3. 
Take the results from exercise 2:
1. Drop the most important features according to each method, resulting
in a features matrix  .
2. Compute MDI, MDA, and SFI feature importance on 
 , where
the base estimator is RF.
3. Do you appreciate significant changes in the rankings of important
features, relative to the results from exercise 2?
4. 
Using the code presented in Section 8.6:
1. Generate a dataset (X , y ) of 1E6 observations, where 5 features are
informative, 5 are redundant and 10 are noise.
2. Split (X , y ) into 10 datasets {(X i , y i )} i = 1, …, 10 , each of 1E5
observations.
3. Compute the parallelized feature importance (Section 8.5), on each
of the 10 datasets, {(X i , y i )} i = 1, …, 10 .
4. Compute the stacked feature importance on the combined dataset (X ,
y ).
5. What causes the discrepancy between the two? Which one is more
reliable?
5. 
Repeat all MDI calculations from exercises 1–4, but this time
al

### Code Examples

```unknown
important features? Why?
```

```unknown
important features according to each method, resulting
```

```unknown
importance (Section 8.5), on each
```

---

