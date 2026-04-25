# 4. López de Prado, M. and A. Peijan (2004): “Measuring loss potential of

4. López de Prado, M. and A. Peijan (2004): “Measuring loss potential of
hedge fund strategies.” Journal of Alternative Investments , Vol. 7, No. 1
(Summer), pp. 7–31. Available at http://ssrn.com/abstract=641702 .
CHAPTER 16
Machine Learning Asset Allocation
16.1 Motivation
This chapter introduces the Hierarchical Risk Parity (HRP) approach. 1 HRP
portfolios address three major concerns of quadratic optimizers in general and
Markowitz's Critical Line Algorithm (CLA) in particular: instability,
concentration, and underperformance. HRP applies modern mathematics
(graph theory and machine learning techniques) to build a diversified portfolio
based on the information contained in the covariance matrix. However, unlike
quadratic optimizers, HRP does not require the invertibility of the covariance
matrix. In fact, HRP can compute a portfolio on an ill-degenerated or even a
singular covariance matrix, an impossible feat for quadratic optimizers. Monte
Carlo experiments show that HRP delivers

### Code Examples

```unknown
require the invertibility of the covariance
use CLA to produce very different
```

---

expected returns. Instead, we should take into account the correlations across
alternative investments in order to build a diversified portfolio.
Before earning his PhD in 1954, Markowitz left academia to work for the
RAND Corporation, where he developed the Critical Line Algorithm. CLA is a
quadratic optimization procedure specifically designed for inequality-
constrained portfolio optimization problems. This algorithm is notable in that it
guarantees that the exact solution is found after a known number of iterations,
and that it ingeniously circumvents the Karush-Kuhn-Tucker conditions (Kuhn
and Tucker [1951]). A description and open-source implementation of this
algorithm can be found in Bailey and López de Prado [2013]. Surprisingly,
most financial practitioners still seem unaware of CLA, as they often rely on
generic-purpose quadratic programming methods that do not guarantee the
correct solution or a stopping time.
Despite of the brilliance of Markowitz's theory, a number of pra

### Code Examples

```unknown
require the inversion
```

---

unstable: A small change on any entry will lead to a very different inverse. This
is Markowitz's curse: The more correlated the investments, the greater the need
for diversification, and yet the more likely we will receive unstable solutions.
The benefits of diversification often are more than offset by estimation errors.
Figure 16.1 Visualization of Markowitz's curse
A diagonal correlation matrix has the lowest condition number. As we add
correlated investments, the maximum eigenvalue is greater and the minimum
eigenvalue is lower. The condition number rises quickly, leading to unstable
inverse correlation matrices. At some point, the benefits of diversification are
more than offset by estimation errors.
Increasing the size of the covariance matrix will only make matters worse, as
each covariance coefficient is estimated with fewer degrees of freedom. In
general, we need at least 
 independent and identically distributed
(IID) observations in order to estimate a covariance matrix of s

---

singular. For example, estimating an invertible covariance matrix of size 50
requires, at the very least, 5 years of daily IID data. As most investors know,
correlation structures do not remain invariant over such long periods by any
reasonable confidence level. The severity of these challenges is epitomized by
the fact that even naïve (equally-weighted) portfolios have been shown to beat
mean-variance and risk-based optimization out-of-sample (De Miguel et al.
[2009]).
16.4 From Geometric to Hierarchical Relationships
These instability concerns have received substantial attention in recent years,
as Kolm et al. [2014] have carefully documented. Most alternatives attempt to
achieve robustness by incorporating additional constraints (Clarke et al.
[2002]), introducing Bayesian priors (Black and Litterman [1992]), or
improving the numerical stability of the covariance matrix's inverse (Ledoit
and Wolf [2003]).
All the methods discussed so far, although published in recent years, are
deri

### Code Examples

```typescript
requires, at the very least, 5 years of daily IID data. As most investors know,
```

---

Figure 16.2 The complete-graph (top) and the tree-graph (bottom) structures
Correlation matrices can be represented as complete graphs, which lack the
notion of hierarchy: Each investment is substitutable with another. In contrast,
tree structures incorporate hierarchical relationships.
Let us consider for a moment the practical implications of such a topological
structure. Suppose that an investor wishes to build a diversified portfolio of
securities, including hundreds of stocks, bonds, hedge funds, real estate, private
placements, etc. Some investments seem closer substitutes of one another, and
other investments seem complementary to one another. For example, stocks
could be grouped in terms of liquidity, size, industry, and region, where stocks
within a given group compete for allocations. In deciding the allocation to a
large publicly traded U.S. financial stock like J. P. Morgan, we will consider
adding or reducing the allocation to another large publicly traded U.S. bank
like G

---

investments are potential substitutes to one another. In other words, correlation
matrices lack the notion of hierarchy. This lack of hierarchical structure allows
weights to vary freely in unintended ways, which is a root cause of CLA's
instability. Figure 16.2 (b) visualizes a hierarchical structure known as a tree. A
tree structure introduces two desirable features: (1) It has only N − 1 edges to
connect N nodes, so the weights only rebalance among peers at various
hierarchical levels; and (2) the weights are distributed top-down, consistent
with how many asset managers build their portfolios (e.g., from asset class to
sectors to individual securities). For these reasons, hierarchical structures are
better designed to give not only stable but also intuitive results.
In this chapter we will study a new portfolio construction method that
addresses CLA's pitfalls using modern mathematics: graph theory and machine
learning. This Hierarchical Risk Parity method uses the information conta

### Code Examples

```php
class to
sectors to individual securities). For these reasons, hierarchical structures are
better designed to give not only stable but also intuitive results.
In this chapter we will study a new portfolio construction method that
addresses CLA's pitfalls using modern mathematics: graph theory and machine
learning. This Hierarchical Risk Parity method uses the information contained
in the covariance matrix without requiring its inversion or positive-
definitiveness. HRP can even compute a portfolio based on a singular
covariance matrix. The algorithm operates in three stages: tree clustering,
quasi-diagonalization, and recursive bisection.
16.4.1 Tree Clustering
Consider a TxN matrix of observations X , such as returns series of N variables
over T periods. We would like to combine these N column-vectors into a
hierarchical structure of clusters, so that allocations can flow downstream
through a tree graph.
First, we compute an NxN correlation matrix with entries ρ = {ρ i , j }
```

```unknown
uses the information contained
```

---

Example 16.1 Encoding a correlation matrix ρ as a distance matrix D
Second, we compute the Euclidean distance between any two column-vectors
of D , 
 , 
 .
Note the difference between distance metrics d i , j and 
 . Whereas d i , j is
defined on column-vectors of X , 
 is defined on column-vectors of D (a
distance of distances). Therefore,  is a distance defined over the entire metric
space D , as each 
 is a function of the entire correlation matrix (rather than a
particular cross-correlation pair). See Example 16.2.
Example 16.2 Euclidean distance of correlation distances
Third, we cluster together the pair of columns ( i *, j *) such that
 , and denote this cluster as u [1]. See Example 16.3.
Example 16.3 Clustering items
Fourth, we need to define the distance between a newly formed cluster u [1]
and the single (unclustered) items, so that 
 may be updated. In hierarchical
clustering analysis, this is known as the “linkage criterion.” For example, we

---

can define the distance between an item i of  and the new cluster u [1] as
 (the nearest point algorithm). See Example 16.4.
Example 16.4 Updating matrix 
 with the new cluster u
Fifth, matrix 
 is updated by appending 
 and dropping the clustered
columns and rows j ∈ u [1]. See Example 16.5.
Example 16.5 Updating matrix 
 with the new cluster u
Sixth, applied recursively, steps 3, 4, and 5 allow us to append N − 1 such
clusters to matrix D , at which point the final cluster contains all of the original
items, and the clustering algorithm stops. See Example 16.6.
Example 16.6 Recursion in search of remaining clusters

---

Figure 16.3 displays the clusters formed at each iteration for this example, as
well as the distances 
 that triggered every cluster (third step). This
procedure can be applied to a wide array of distance metrics d i , j , 
 and 
 ,
beyond those illustrated in this chapter. See Rokach and Maimon [2005] for
alternative metrics, the discussion on Fiedler's vector and Stewart's spectral
clustering method in Brualdi [2010], as well as algorithms in the scipy library. 2
Snippet 16.1 provides an example of tree clustering using scipy functionality.
Figure 16.3 Sequence of cluster formation
A tree structure derived from our numerical example, here plotted as a
dendogram. The y-axis measures the distance between the two merging leaves.
SNIPPET 16.1 TREE CLUSTERING USING SCIPY
FUNCTIONALITY

---

This stage allows us to define a linkage matrix as an ( N − 1) x 4 matrix with
structure Y = {( y m , 1 , y m , 2 , y m , 3 , y m , 4 )} m = 1, …, N − 1 (i.e., with one 4-tuple
per cluster). Items ( y m , 1 , y m , 2 ) report the constituents. Item y m , 3 reports the
distance between y m , 1 and y m , 2 , that is 
 . Item y m , 4 ≤ N
reports the number of original items included in cluster m .
16.4.2 Quasi-Diagonalization
This stage reorganizes the rows and columns of the covariance matrix, so that
the largest values lie along the diagonal. This quasi-diagonalization of the
covariance matrix (without requiring a change of basis) renders a useful
property: Similar investments are placed together, and dissimilar investments
are placed far apart (see Figures 16.5 and 16.6 for an example). The algorithm
works as follows: We know that each row of the linkage matrix merges two
branches into one. We replace clusters in ( y N − 1, 1 , y N − 1, 2 ) with their
constituents recursively, until no

### Code Examples

```unknown
included in cluster m .
```

---

