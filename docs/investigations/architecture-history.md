# Earlier architecture measurements

These measurements describe earlier ownership, application and solver-integration
changes. Their original prose, revision identifiers and numbers are retained below.
They are evidence for those revisions and workloads; they do not measure the
current package reorganization. See the [current architecture guide](../architecture.md)
for the maintained boundaries and benchmark command.

## Ownership and compatibility changes

A local Python 3.14.9 comparison against `8a5f157` used three serial ERE/Thracia
runs per revision, full research, fertility 5 and one worker. All six runs proved
income **24140.375** with identical selected buildings and metrics. Median wall
time was **6.03 s before / 5.80 s after**; ranges were **5.69–6.16 s / 5.71–6.23 s**.
These overlapping ranges show no observed slowdown on that workload; they do not
establish a general speedup or predict timings on another machine. Automatic CPU
selection remains the application default; the benchmark pins one worker for a
repeatable comparison.

Removing the compatibility layer was compared separately against `74304d1` on
the same workload: three serial runs per revision had identical result
fingerprints and proved the same optimum. Median wall time was **5.70 s before /
5.50 s after**, with ranges **5.65–6.31 s / 5.40–5.85 s**. These ranges overlap;
the comparison shows no observed regression rather than a general speedup.

## Shared application comparison

The application-layer change was compared with `bb1f142` using Python 3.14.9,
CP-SAT, one worker and no time limit. Six serial runs per revision/game used the
UI's default economic settings; the measurement order was reversed halfway
through. Every run retained the same income, status, objective and bound. These
checks intentionally ignored timing and tied building selections when comparing
semantics.

| Game | Previous median (range), seconds | Shared-service median (range), seconds |
| --- | --- | --- |
| Attila | 0.6564 (0.6211–1.0207) | 0.6314 (0.5950–0.6676) |
| Rome II | 0.9879 (0.9742–1.0142) | 1.0313 (0.9098–1.0746) |
| Shogun 2 | 0.0132 (0.0121–0.0227) | 0.0145 (0.0116–0.0177) |

The ranges overlap. These small samples establish result preservation, not a
general speedup: Rome II's median was slightly higher, and Shogun 2 added about
one millisecond. Profiling the initial Attila adapter found approximately 0.10 s
spent computing an unused model signature; ordinary runs now skip that work,
while faction proof reuse retains the signature and independent validation.

## Solver integration comparison

The integrated architecture was compared against `bd60b0c` with the same locked
Python 3.14 environment, default scenarios, one worker and three serial samples.
All three games produced identical result fingerprints, including income,
status, metrics and selected buildings. Observed median seconds were:

| Game | Incoming solver implementation | Integrated architecture |
| --- | ---: | ---: |
| Attila | 0.705 | 0.684 |
| Rome II | 1.034 | 0.966 |
| Shogun 2 | 0.0152 | 0.0122 |

Sample ranges overlap. These measurements show no observed slowdown on the
checked workloads; they do not establish a general speedup.
