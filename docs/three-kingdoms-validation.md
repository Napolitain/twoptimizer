# Three Kingdoms reference validation

The historical 1.2.0 model runs through the shared CLI, terminal UI and worker
with both CP-SAT and HiGHS. This validates the implemented static model; it does
not establish agreement with a current installed game.

These measurements used the original **fixed city level 5** comparison. New
CLI/TUI runs optimize city levels by default; use `--city-level 5` to reproduce
the scenarios below. Infeasibility here does not imply that a smaller city fails.

The [automatic-city validation](../reports/three-kingdoms-city-levels.json) checks
all 70 commanderies again with both solvers and unchanged population, food and
public-order inputs. All 70 now have proved optima. The 25 previously infeasible
cases select level-4 cities; 15 previously feasible cases also improve their
income by choosing larger cities. Explicit level-5 runs reproduce every original
result. Concrete low-tier layouts also independently validate feasibility across
all 15 factions and the full map in the regression suite.

Automatic sizing enlarges joint models. In separate single 15-second functional
checks, CP-SAT returned a validated all-70 layout with income 52,138.25, while
HiGHS returned `UNKNOWN` without an incumbent. That timeout is not an
infeasibility proof; the smaller-city feasible layouts are known. Neither check
establishes time to optimality or a speed comparison with the fixed-level runs.

The [public-data audit](../reports/three-kingdoms-historical-readiness.json)
records 424 buildings, 15 faction profiles, 143 reforms, 70 commanderies and
187 counties. The separate pinned reference recovers effects for 139 buildings
whose undated Honga pages reported no effects. Numerical values from those
different versions are not merged.

The [installed-wheel results](../reports/three-kingdoms-validation.json) include
complete requests, source hashes, timings, memory and backend comparisons:

- All 15 factions in the default Yingchuan snapshot: both backends proved the
  same optimum for each faction.
- All 70 commanderies independently, using Cao Cao and the common defaults:
  both backends agreed on every case, with 45 optimal and 25 infeasible.
- All 70 commanderies together: both backends returned independently validated
  feasible layouts in each 30-second test, without proving optimality.

The independent infeasibilities are under the specified city level, research,
population and local food supply. For example, default Chang'an becomes feasible
with six units of external food. Joint ownership can supply food from other
commanderies and therefore solves a different economic problem.

| Installed-wheel workload | Solver | Income per turn | Remaining gap | Wall time |
| --- | --- | ---: | ---: | ---: |
| Cao Cao, Yingchuan | CP-SAT | 627.75, optimal | 0% | Median 0.67 s |
| Cao Cao, Yingchuan | HiGHS | 627.75, optimal | 0% | Median 0.72 s |
| All 70 together | CP-SAT | 60,694.50–61,626.00 | 19.13–20.17% | 30.72–30.86 s |
| All 70 together | HiGHS | 68,007.00 | 15.34% | 30.94–30.98 s |

The gap is `(upper bound − income) / max(1, abs(upper bound))`. These are bounds
on the modeled optimum, not estimates of time remaining. HiGHS found better
income in this particular bounded joint test; that supports keeping both
backends available, rather than claiming that one always supersedes the other.
No run-to-optimal timing is established for the full holding.

Measurements used Python 3.14.9, OR-Tools 9.15.6755 and four workers, serially in
fresh processes outside the checkout. The installed dependency versions matched
the lock file. Source hashes from every measured process matched the working
tree. Each backend had three single-commandery samples and two joint samples.
Wall time includes imports and the shared application solve, excluding package
installation and shell startup. The first CP-SAT sample included cold cache and
bytecode effects and took 2.72 seconds; the other two took 0.64–0.67 seconds.
Joint peak memory was 316 MiB for CP-SAT and 325–327 MiB for HiGHS.

Reproduce the numerical workloads with:

```sh
uv run --locked twoptimizer three-kingdoms --faction all \
  --commandery Yingchuan --city-level 5 --algorithm cp-sat --algorithm highs --workers 4 --seconds 5
uv run --locked twoptimizer three-kingdoms --commandery all \
  --city-level 5 --algorithm cp-sat --algorithm highs --workers 4 --seconds 5
uv run --locked twoptimizer three-kingdoms --commandery all --joint \
  --city-level 5 --algorithm cp-sat --algorithm highs --workers 4 --seconds 30
```

Use a different `--output` stem for each report, or `--overwrite` when replacing
an existing export. The application normally runs without a time limit; these
limits are explicit validation settings. These comparisons use city level 5, one million
people per commandery, zero base corruption, normal tax/fertility/non-harvest,
no reforms and the original leader profile. The
[model documentation](../games/tw/three_kingdoms/README.md) describes the missing
historical borders and other remaining coverage limits.
