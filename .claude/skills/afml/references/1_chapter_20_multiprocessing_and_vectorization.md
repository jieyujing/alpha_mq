# 1. Chapter 20 Multiprocessing and Vectorization

1. Chapter 20 Multiprocessing and Vectorization
2. Chapter 21 Brute Force and Quantum Computers
3. Chapter 22 High-Performance Computational Intelligence and Forecasting
Technologies
CHAPTER 20
Multiprocessing and Vectorization
20.1 Motivation
Multiprocessing is essential to ML. ML algorithms are computationally
intensive, and they will require an efficient use of all your CPUs, servers, and
clusters. For this reason, most of the functions presented throughout this book
were designed for asynchronous multiprocessing. For example, we have made
frequent use of a mysterious function called mpPandasObj , without ever
defining it. In this chapter we will explain what this function does.
Furthermore, we will study in detail how to develop multiprocessing engines.
The structure of the programs presented in this chapter is agnostic to the
hardware architecture used to execute them, whether we employ the cores of a
single server or cores distributed across multiple interconnected servers (e.g.,

### Code Examples

```unknown
use of a mysterious function called mpPandasObj , without ever
```

```unknown
require an efficient use of all your CPUs, servers, and
```

```unknown
used to execute them, whether we employ the cores of a
```

---

A vectorized solution would replace all explicit iterators (e.g., For. . .loops )
with matrix algebra operations or compiled iterators or generators. Snippet 20.2
implements the vectorized version of Snippet 20.1. The vectorized version is
preferable for four reasons: (1) slow nested For. . .loops are replaced with
fast iterators; (2) the code infers the dimensionality of the mesh from the
dimensionality of dict0 ; (3) we could run 100 dimensions without having to
modify the code, or need 100 For. . .loops ; and (4) under the hood, Python
can run operations in C or C + + .
SNIPPET 20.2 VECTORIZED CARTESIAN PRODUCT
20.3 Single-Thread vs. Multithreading vs. Multiprocessing
A modern computer has multiple CPU sockets. Each CPU has many cores
(processors), and each core has several threads. Multithreading is the technique
by which several applications are run in parallel on two or more threads under
the same core. One advantage of multithreading is that, because the
applications share the s

---

hence multiprocessing does not risk writing to the same memory space;
however, that also makes it harder to share objects between processes.
Python functions implemented for running on a single-thread will use only a
fraction of a modern computer's, server's, or cluster's power. Let us see an
example of how a simple task can be run inefficiently when implemented for
single-thread execution. Snippet 20.3 finds the earliest time 10,000 Gaussian
processes of length 1,000 touch a symmetric double barrier of width 50 times
the standard deviation.
SNIPPET 20.3 SINGLE-THREAD IMPLEMENTATION OF A ONE-
TOUCH DOUBLE BARRIER
Compare this implementation with Snippet 20.4. Now the code splits the
previous problem into 24 tasks, one per processor. The tasks are then run

---

asynchronously in parallel, using 24 processors. If you run the same code on a
cluster with 5000 CPUs, the elapsed time will be about 1/5000 of the single-
thread implementation.
SNIPPET 20.4 MULTIPROCESSING IMPLEMENTATION OF A
ONE-TOUCH DOUBLE BARRIER
Moreover, you could implement the same code to multiprocess a vectorized
function, as we did with function applyPtSlOnT1 in Chapter 3, where parallel
processes execute subroutines that include vectorized pandas objects. In this
way, you will achieve two levels of parallelization at once. But why stop there?
You could achieve three levels of parallelization at once by running
multiprocessed instances of vectorized code in an HPC cluster, where each
node in the cluster provides the third level of parallelization. In the next
sections, we will explain how multiprocessing works.
20.4 Atoms and Molecules

### Code Examples

```unknown
include vectorized pandas objects. In this
```

```unknown
applyPtSlOnT1
```

---

When preparing jobs for parallelization, it is useful to distinguish between
atoms and molecules. Atoms are indivisible tasks. Rather than carrying out all
these tasks sequentially in a single thread, we want to group them into
molecules, which can be processed in parallel using multiple processors. Each
molecule is a subset of atoms that will be processed sequentially, by a callback
function, using a single thread. Parallelization takes place at the molecular
level.
20.4.1 Linear Partitions
The simplest way to form molecules is to partition a list of atoms in subsets of
equal size, where the number of subsets is the minimum between the number of
processors and the number of atoms. For N subsets we need to find the N + 1
indices that enclose the partitions. This logic is demonstrated in Snippet 20.5.
SNIPPET 20.5 THE LINPARTS FUNCTION
It is common to encounter operations that involve two nested loops. For
example, computing a SADF series (Chapter 17), evaluating multiple barrier
touche

### Code Examples

```unknown
useful to distinguish between
```

```unknown
use some processors would have to solve a much larger number of
```

---

Figure 20.1 A linear partition of 20 atomic tasks into 6 molecules
20.4.2 Two-Nested Loops Partitions
Consider two nested loops, where the outer loop iterates i = 1, …, N and the
inner loop iterates j = 1, …, i . We can order these atomic tasks {( i , j )|1 ≤ j ≤ i
, i = 1, …, N } as a lower triangular matrix (including the main diagonal). This
entails 
 operations, where 
 are off-
diagonal and N are diagonal. We would like to parallelize these tasks by
partitioning the atomic tasks into M subsets of rows, { S m } m = 1, …, M , each
composed of approximately 
 tasks. The following algorithm
determines the rows that constitute each subset (a molecule).
The first subset, S 1 , is composed of the first r 1 rows, that is, S 1 = {1, …, r 1 },
for a total number of items 
 . Then, r 1 must satisfy the condition
 . Solving for r 1 , we obtain the positive root

---

The second subset contains rows S 2 = { r 1 + 1, …, r 2 }, for a total number of
items 
 . Then, r 2 must satisfy the condition
 . Solving for r 2 , we obtain the positive
root
We can repeat the same argument for a future subset S m = { r m − 1 + 1, …, r m
}, with a total number of items 
 . Then, r m must
satisfy the condition 
 . Solving for r
m , we obtain the positive root
And it is easy to see that r m reduces to r 1 where r m − 1 = r 0 = 0 . Because row
numbers are positive integers, the above results are rounded to the nearest
natural number. This may mean that some partitions’ sizes may deviate slightly
from the 
 target. Snippet 20.6 implements this logic.
SNIPPET 20.6 THE NESTEDPARTS FUNCTION

### Code Examples

```unknown
NESTEDPARTS
upperTriang = True
```

---

If the outer loop iterates i = 1, …, N and the inner loop iterates j = i , …, N , we
can order these atomic tasks {( i , j )|1 ≤ i ≤ j ., j = 1, …, N } as an upper
triangular matrix (including the main diagonal). In this case, the argument
upperTriang = True must be passed to function nestedParts . For the
curious reader, this is a special case of the bin packing problem. Figure 20.2
plots a two-nested loops partition of atoms of increasing complexity into
molecules. Each of the resulting 6 molecules involves a similar amount of
work, even though some atomic tasks are up to 20 times harder than others.

### Code Examples

```unknown
nestedParts
```

---

Figure 20.2 A two-nested loops partition of atoms into molecules
20.5 Multiprocessing Engines
It would be a mistake to write a parallelization wrapper for each
multiprocessed function. Instead, we should develop a library that can
parallelize unknown functions, regardless of their arguments and output
structure. That is the goal of a multiprocessing engine. In this section, we will
study one such engine, and once you understand the logic, you will be ready to
develop your own, including all sorts of customized properties.
20.5.1 Preparing the Jobs
In previous chapters we have made frequent use of the mpPandasObj . That
function receives six arguments, of which four are optional:
func : A callback function, which will be executed in parallel
pdObj : A tuple containing:
The name of the argument used to pass molecules to the callback
function

### Code Examples

```unknown
use of the mpPandasObj . That
```

```unknown
used to pass molecules to the callback
```

```unknown
mpPandasObj
```

---

A list of indivisible tasks (atoms), which will be grouped into
molecules
numThreads : The number of threads that will be used in parallel (one
processor per thread)
mpBatches : Number of parallel batches (jobs per core)
linMols : Whether partitions will be linear or double-nested
kargs : Keyword arguments needed by func
Snippet 20.7 lists how mpPandasObj works. First, atoms are grouped into
molecules, using linParts (equal number of atoms per molecule) or
nestedParts (atoms distributed in a lower-triangular structure). When
mpBatches is greater than 1, there will be more molecules than cores. Suppose
that we divide a task into 10 molecules, where molecule 1 takes twice as long
as the rest. If we run this process in 10 cores, 9 of the cores will be idle half of
the runtime, waiting for the first core to process molecule 1. Alternatively, we
could set mpBatches =10 so as to divide that task in 100 molecules. In doing
so, every core will receive equal workload, even though the first 10 m

### Code Examples

```unknown
used in parallel (one
```

```unknown
use numThreads > 1 . Fourth, we stitch together the output from
```

```unknown
mpPandasObj
```

---

