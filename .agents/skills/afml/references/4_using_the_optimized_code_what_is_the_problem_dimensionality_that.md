# 4. Using the optimized code, what is the problem dimensionality that

4. Using the optimized code, what is the problem dimensionality that
could be solved within a year?
5. 
Under what circumstances would the globally dynamic optimal
trajectory match the sequence of local optima?
1. Is that a realistic set of assumptions?
2. If not,
1. could that explain why naïve solutions beat Markowitz's
(Chapter 16)?
2. why do you think so many firms spend so much effort in
computing sequences of local optima?
References
1. Garleanu, N. and L. Pedersen (2012): “Dynamic trading with predictable
returns and transaction costs.” Journal of Finance , Vol. 68, No. 6, pp.
2309–2340.
2. Johansson, F. (2012): “Efficient implementation of the Hardy-Ramanujan-
Rademacher formula,” LMS Journal of Computation and Mathematics ,
Vol. 15, pp. 341–359.
3. Rosenberg, G., P. Haghnegahdar, P. Goddard, P. Carr, K. Wu, and M.
López de Prado (2016): “Solving the optimal trading trajectory problem
using a quantum annealer.” IEEE Journal of Selected Topics in Signal
Processing , Vol. 10, No.

---

22.1 Motivation
This chapter provides an introduction to the Computational Intelligence and
Forecasting Technologies (CIFT) project at Lawrence Berkeley National
Laboratory (LBNL). The main objective of CIFT is to promote the use of high-
performance computing (HPC) tools and techniques for analysis of streaming
data. After noticing the data volume being given as the explanation for the five-
month delay for SEC and CFTC to issue their report on the 2010 Flash Crash,
LBNL started the CIFT project to apply HPC technologies to manage and
analyze financial data. Making timely decisions with streaming data is a
requirement for many business applications, such as avoiding impending
failure in the electric power grid or a liquidity crisis in financial markets. In all
these cases, the HPC tools are well suited in handling the complex data
dependencies and providing a timely solution. Over the years, CIFT has
worked on a number of different forms of streaming data, including those from
vehicle

### Code Examples

```typescript
requirement for many business applications, such as avoiding impending
```

```unknown
used on these systems, and provide examples of streaming data analyses using
use cases (Section 22.6). We conclude with a summary of our vision
```

---

successful use cases (Section 22.6). We conclude with a summary of our vision
and work so far and also provide contact information for interested readers.
22.3 Background
Advances in computing technology have made it considerably easier to look
for complex patterns. This pattern-finding capability is behind a number of
recent scientific breakthroughs, such as the discovery of the Higgs particle
(Aad et al. [2016]) and gravitational waves (Abbot et al. [2016]). This same
capability is also at the core of many internet companies, for example, to match
users with advertisers (Zeff and Aronson [1999], Yen et al. [2009]). However,
the hardware and software used in science and in commerce are quite different.
The HPC tools have some critical advantages that should be useful in a variety
of business applications.
Tools for scientists are typically built around high-performance computing
(HPC) platforms, while the tools for commercial applications are built around
cloud computing platforms. Fo

### Code Examples

```unknown
users with advertisers (Zeff and Aronson [1999], Yen et al. [2009]). However,
```

```unknown
used in science and in commerce are quite different.
```

```unknown
useful patterns, the two approaches have been shown to work well.
```

---

illiquidity events have been identified in the financial research literature;
quickly finding these signs during the active market trading hours could offer
options to prevent shocks to the market and avoid flash crashes. The ability to
prioritize quick turnaround time is essential in these cases.
A data stream is by definition available progressively; therefore, there may not
be a large number of data objects to be processed in parallel. Typically, only a
fixed amount of the most recent data records are available for analysis. In this
case, an effective way to harness the computing power of many central
processing units (CPUs) cores is to divide the analytical work on a single data
object (or a single time-step) to many CPU cores. The HPC ecosystem has
more advanced tools for this kind of work than the cloud ecosystem does.
These are the main points that motivated our work. For a more thorough
comparison of HPC systems and cloud systems, we refer interested readers to
Asanovic et al. 

### Code Examples

```unknown
users to utilize an HPC system and
```

```unknown
include improving
important point about the difference
```

---

the data handling speed by 21-fold, and increasing the speed of computing an
early warning indicator by 720-fold.
22.4 HPC Hardware
Legend has it that the first generation of big data systems was built with the
spare computer components gleaned from a university campus. This is likely
an urban legend, but it underscores an important point about the difference
between HPC systems and cloud systems. Theoretically, a HPC system is built
with custom high-cost components, while cloud systems are built with standard
low-cost commodity components. In practice, since the worldwide investment
in HPC systems is much smaller than that of personal computers, there is no
way for manufacturers to produce custom components just for the HPC market.
The truth is that HPC systems are largely assembled from commodity
components just like cloud systems. However, due to their different target
applications, there are some differences in their choices of the components.
Let us describe the computing elements

### Code Examples

```unknown
include both CPUs and
includes both rotating disks and flash storage.
```

---

Figure 22.1 Schematic of the Magellan cluster (circa 2010), an example of
HPC computer cluster
The networking system consists of two parts: the InfiniBand network
connecting the components within the cluster, and the switched network
connection to the outside world. In this particular example, the outside
connections are labeled “ESNet” and “ANI.” The InfiniBand network switches
are also common in cloud computing systems.
The storage system in Figure 1 includes both rotating disks and flash storage.
This combination is also common. What is different is that a HPC system
typically has its storage system concentrated outside of the computer nodes,
while a typical cloud computing system has its storage system distributed
among the compute nodes. These two approaches have their own advantages
and disadvantages. For example, the concentrated storage is typically exported
as a global file system to all computer nodes, which makes it easier to deal with
data stored in files. However, this req

### Code Examples

```unknown
requires a highly capable network connecting
```

```unknown
use there is some storage that is close to each CPU.
use of application performance difference. In the next
```

---

In short, the current generation of HPC systems and cloud systems use pretty
much the same commercial hardware components. Their differences are
primarily in the arrangement of the storage systems and networking systems.
Clearly, the difference in the storage system designs could affect the
application performance. However, the virtualization layer of the cloud systems
is likely the bigger cause of application performance difference. In the next
section, we will discuss another factor that could have an even larger impact,
namely software tools and libraries.
Virtualization is generally used in the cloud computing environment to make
the same hardware available to multiple users and to insulate one software
environment from another. This is one of the more prominent features
distinguishing the cloud computing environment from the HPC environment.
In most cases, all three basic components of a computer system—CPU,
storage, and networking—are all virtualized. This virtualization has many

### Code Examples

```unknown
used in the cloud computing environment to make
```

```unknown
users and to insulate one software
```

```unknown
users can share the same hardware; hardware faults could
```

---

Figure 22.2 The cloud ran scientific applications considerably slower than on
HPC systems (circa 2010)
Figure 22.3 shows a study of the main factor causing the slowdown with the
software package PARATEC. In Figure 2, we see that PARATEC took 53 times
longer to complete on the commercial cloud than on an HPC system. We
observe from Figure 3 that, as the number of cores (horizontal axis) increases,
the differences among the measured performances (measured in TFLOP/s)
become larger. In particular, the line labeled “10G- TCPoEth Vm” barely
increases as the number of cores grows. This is the case where the network
instance is using virtualized networking (TCP over Ethernet). It clearly shows
that the networking virtualization overhead is significant, to the point of
rendering the cloud useless.

---

Figure 22.3 As the number of cores increases (horizontal axis), the
virtualization overhead becomes much more significant (circa 2010)
The issue of virtualization overhead is widely recognized (Chen et al. [2015]).
There has been considerable research aimed at addressing both the I/O
virtualization overhead (Gordon et al. [2012]) as well as the networking
virtualization overhead (Dong et al. [2012]). As these state-of-the-art
techniques are gradually being moved into commercial products, we anticipate
the overhead will decrease in the future, but some overhead will inevitably
remain.
To wrap up this section, we briefly touch on the economics of HPC versus
cloud. Typically, HPC systems are run by nonprofit research organizations and
universities, while cloud systems are provided by commercial companies.
Profit, customer retention, and many other factors affect the cost of a cloud
system (Armburst et al. [2010]). In 2011, the Magellan project report stated
that “Cost analysis shows that 

---

A group of high-energy physicists thought their use case was well-suited for
cloud computing and conducted a detailed study of a comparison study
(Holzman et al. [2017]). Their cost comparisons still show the commercial
cloud offerings as approximately 50% more expensive than dedicated HPC
systems for comparable computing tasks; however, the authors worked with
severe limitations on data ingress and egress to avoid potentially hefty charges
on data movement. For complex workloads, such as the streaming data
analyses discussed in this book, we anticipate that this HPC cost advantage will
remain in the future. A 2016 National Academy of Sciences study came to the
same conclusion that even a long-term lease from Amazon is likely 2 to 3 times
more expensive than HPC systems to handle the expected science workload
from NSF (Box 6.2 from National Academies of Sciences, [2016]).
22.5 HPC Software
Ironically, the real power of a supercomputer is in its specialized software.
There are a wide va

### Code Examples

```unknown
use case was well-suited for
user community at the 1994 Supercomputing Conference.
```

---

