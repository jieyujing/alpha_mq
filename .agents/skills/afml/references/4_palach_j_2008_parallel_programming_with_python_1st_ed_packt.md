# 4. Palach, J. (2008): Parallel Programming with Python , 1st ed. Packt

4. Palach, J. (2008): Parallel Programming with Python , 1st ed. Packt
Publishing.
5. Summerfield, M. (2013): Python in Practice: Create Better Programs
Using Concurrency, Libraries, and Patterns , 1st ed. Addison-Wesley.
6. Zaccone, G. (2015): Python Parallel Programming Cookbook , 1st ed.
Packt Publishing.
Notes
1    Heisenbugs , named after Heisenberg's uncertainty principle, describe bugs
that change their behavior when scrutinized. Multiprocessing bugs are a prime
example.
2     https://pypi.python.org/pypi/joblib .
3     http://scikit-learn.org/stable/developers/performance.html#multi-core-
parallelism-using-joblib-parallel .
4     http://stackoverflow.com/questions/1816958/cant-pickle-type-
instancemethod-when-using-pythons-multiprocessing-pool-ma .
CHAPTER 21
Brute Force and Quantum Computers
21.1 Motivation
Discrete mathematics appears naturally in multiple ML problems, including
hierarchical clustering, grid searches, decisions based on thresholds, and
integer optimization. S

---

21.2 Combinatorial Optimization
Combinatorial optimization problems can be described as problems where
there is a finite number of feasible solutions, which result from combining the
discrete values of a finite number of variables. As the number of feasible
combinations grows, an exhaustive search becomes impractical. The traveling
salesman problem is an example of a combinatorial optimization problem that
is known to be NP hard (Woeginger [2003]), that is, the category of problems
that are at least as hard as the hardest problems solvable is nondeterministic
polynomial time.
What makes an exhaustive search impractical is that standard computers
evaluate and store the feasible solutions sequentially. But what if we could
evaluate and store all feasible solutions at once? That is the goal of quantum
computers. Whereas the bits of a standard computer can only adopt one of two
possible states ({0, 1}) at once, quantum computers rely on qubits, which are
memory elements that may hold a lin

---

We define a trading trajectory as an NxH matrix ω that determines the
proportion of capital allocated to each of the N assets over each of the H
horizons. At a particular horizon h = 1, …, H , we have a forecasted mean μ h ,
a forecasted variance V h and a forecasted transaction cost function τ h [ω]. This
means that, given a trading trajectory ω, we can compute a vector of expected
investment returns r , as
where τ[ω] can adopt any functional form. Without loss of generality, consider
the following:
 , for h = 2, …, H
ω* n is the initial allocation to instrument n, n = 1, …, N
τ[ω] is an Hx1 vector of transaction costs. In words, the transaction costs
associated with each asset are the sum of the square roots of the changes in
capital allocations, re-scaled by an asset-specific factor C h = { c n , h } n = 1, …, N
that changes with h. Thus, C h is an Nx1 vector that determines the relative
transaction cost across assets.
The Sharpe Ratio (Chapter 14) associated with r can be computed 

---

This problem attempts to compute a global dynamic optimum, in contrast to
the static optimum derived by mean-variance optimizers (see Chapter 16). Note
that non-continuous transaction costs are embedded in r . Compared to
standard portfolio optimization applications, this is not a convex (quadratic)
programming problem for at least three reasons: (1) Returns are not identically
distributed, because μ h and V h change with h. (2) Transaction costs τ h [ω] are
non-continuous and changing with h. (3) The objective function SR [ r ] is not
convex. Next, we will show how to calculate solutions without making use of
any analytical property of the objective function (hence the generalized nature
of this approach).
21.5 An Integer Optimization Approach
The generality of this problem makes it intractable to standard convex
optimization techniques. Our solution strategy is to discretize it so that it
becomes amenable to integer optimization. This in turn allows us to use
quantum computing techno

### Code Examples

```unknown
use μ h and V h change with h. (2) Transaction costs τ h [ω] are
```

```unknown
important when allocating 6 units of capital to 3 different assets. This means
use Stirling's approximation to easily arrive at an estimate.
```

---

may still be computationally intensive to find as K and N grow large. However,
we can use Stirling's approximation to easily arrive at an estimate.
Figure 21.1 Partitions (1, 2, 3) and (3, 2, 1) must be treated as different
Snippet 21.1 provides an efficient algorithm to generate the set of all partitions,
 , where 
 are the natural numbers
including zero (whole numbers).
SNIPPET 21.1 PARTITIONS OF K OBJECTS INTO N SLOTS

---

21.5.2 Feasible Static Solutions
We would like to compute the set of all feasible solutions at any given horizon
h , which we denote Ω. Consider a partition set of K units into N assets, p K , N .
For each partition { p i } i = 1, …, N ∈ p K , N , we can define a vector of absolute
weights such that 
 , where 
 (the full-investment
constraint). This full-investment (without leverage) constraint implies that
every weight can be either positive or negative, so for every vector of absolute
weights {|ω i |} i = 1, …, N we can generate 2 N vectors of (signed) weights. This is
accomplished by multiplying the items in {|ω i |} i = 1, …, N with the items of the
Cartesian product of { − 1, 1} with N repetitions. Snippet 21.2 shows how to
generate the set Ω of all vectors of weights associated with all partitions,
 .
SNIPPET 21.2 SET Ω OF ALL VECTORS ASSOCIATED WITH
ALL PARTITIONS

---

21.5.3 Evaluating Trajectories
Given the set of all vectors Ω, we define the set of all possible trajectories Φ as
the Cartesian product of Ω with H repetitions. Then, for every trajectory we
can evaluate its transaction costs and SR, and select the trajectory with optimal
performance across Φ. Snippet 21.3 implements this functionality. The object
params is a list of dictionaries that contain the values of C , μ, V.
SNIPPET 21.3 EVALUATING ALL TRAJECTORIES

---

---

Note that this procedure selects an globally optimal trajectory without relying
on convex optimization. A solution will be found even if the covariance
matrices are ill-conditioned, transaction cost functions are non-continuous, etc.
The price we pay for this generality is that calculating the solution is extremely
computationally intensive. Indeed, evaluating all trajectories is similar to the
traveling-salesman problem. Digital computers are inadequate for this sort of
NP-complete or NP-hard problems; however, quantum computers have the
advantage of evaluating multiple solutions at once, thanks to the property of
linear superposition.
The approach presented in this chapter set the foundation for Rosenberg et al.
[2016], which solved the optimal trading trajectory problem using a quantum
annealer. The same logic can be applied to a wide range on financial problems
involving path dependency, such as a trading trajectory. Intractable ML
algorithm can be discretized and translated into a

### Code Examples

```unknown
useful in many applications (see exercises). You may want to consider
```

---

Snippet 21.5 generates H vectors of means, covariance matrices, and
transaction cost factors, C , μ, V. These variables are stored in a params list.
SNIPPET 21.5 GENERATE THE PROBLEM'S PARAMETERS

---

