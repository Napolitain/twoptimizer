# Cost of optional requirements: worked examples

These are functional checks of the CLI and isolated worker on 2026-11-08, using
Python 3.14.9, OR-Tools 9.15.6755, CP-SAT, one worker and an explicit 10-second
solver allowance **for each side**. All six comparisons (CLI and worker for each game)
proved both incomes optimal. CLI and worker incomes agreed. These values describe
different static scenarios; they are not a ranking across games or a speed test.

The [machine-readable evidence](../reports/constraint-cost-examples.json) records
requests, solver statuses, bounds, changed building IDs, source hashes and output
digests. The baseline removes only optional required/forbidden buildings and the
religious-influence minimum. It keeps the same available candidates, faith,
Nanban contact, advanced campaign rules and other scenario inputs.

| Scenario and requirement | Baseline income | Required income | Proven loss | Loss / baseline | Cost bounds |
| --- | ---: | ---: | ---: | ---: | --- |
| Attila: ERE, Thracia, fertility 5; Greek Chapel and at least 4 Orthodox influence | 24,140.375 | 20,808.0625 | 3,332.3125 | 13.80% | [3,332.3125, 3,332.3125] |
| Rome II: Rome, coastal reference; Shrine of Jupiter | 4,182.7 | 3,860.6 | 322.1 | 7.70% | [322.1, 322.1] |
| Shogun 2: Oda, Owari + Settsu jointly; Famous Temple | 5,663.84 | 5,663.84 | 0 | 0% | [0, 0] |

All rows have baseline status `OPTIMAL`, constrained status `OPTIMAL` and comparison
status `exact`. With unfinished solves, use the reported cost interval; an observed
income difference alone is not a proven loss or saving. The configured limit was
only for these checks; ordinary application runs still have no time limit.

The observed building changes were:

| Scenario | Added in the constrained layout | Removed from the baseline layout |
| --- | --- | --- |
| Attila, Constantinopolis | Greek Chapel | Wine Emporium |
| Rome II, Town | Forum Piscarium; Shrine of Jupiter; Civil Colonia | Horreum; Fishing Port; Farming Colonia |
| Shogun 2 | None | None |

Shogun's baseline already selects the Famous Temple in Owari, so requiring it has
zero income cost in this example. Building differences may include alternative
tied optimal layouts. These examples do not resolve missing game rules: in
particular, Attila's exact faction-capital restrictions remain an
[availability gap](attila-special-audit.md), so this proof does not establish
that its layout is attainable in a campaign.

## Reproduce the CLI checks

Run from the repository root after `uv sync --locked`:

```sh
mkdir -p benchmark-results/constraint-cost-examples

uv run --frozen twoptimizer attila --province Thracia --fertility 5 \
  --algorithms cp-sat --require-building att_bld_religion_orthodox_major_1 \
  --minimum-religious-influence 4 --seconds 10 --workers 1 \
  --compare-constraints --output benchmark-results/constraint-cost-examples/attila.json

uv run --frozen twoptimizer rome2 --faction rom_rome --layout coastal \
  --algorithm cp-sat --require-building rome_religious_jupiter_2 \
  --seconds 10 --workers 1 --compare-constraints \
  --output benchmark-results/constraint-cost-examples/rome2.json

uv run --frozen twoptimizer shogun2 --clan oda \
  --province jap_owari --province jap_settsu --joint --soil native \
  --algorithm cp-sat --require-building sho_buddhist_4_legendary_temple \
  --seconds 10 --workers 1 --compare-constraints \
  --output benchmark-results/constraint-cost-examples/shogun2.json
```

The checks read the actual CLI JSON for all games and the CLI CSV for Rome II and
Shogun 2. Attila's CLI writes JSON. The shared session export was also checked for
all three games: its JSON and CSV retained comparison status, income cost and
the original optional requirements.

## Reproduce the isolated worker checks

The worker is the process boundary used by the TUI. This snippet replays each
stored request and writes its full result, including the baseline result:

```sh
uv run --frozen python - <<'PY'
import json
from pathlib import Path
import subprocess
import sys

report = json.loads(Path("reports/constraint-cost-examples.json").read_text())
output = Path("benchmark-results/constraint-cost-examples")
output.mkdir(parents=True, exist_ok=True)
for example in report["examples"]:
    game = example["game"]
    request_path = output / f"{game}-request.json"
    result_path = output / f"{game}-worker.json"
    request_path.write_text(json.dumps(example["request"], indent=2) + "\n")
    subprocess.run(
        [sys.executable, "-m", "twoptimizer.worker", str(request_path), str(result_path)],
        check=True,
    )
    result = json.loads(result_path.read_text())
    comparison = result["raw"]["constraint_comparison"]
    print(game, comparison["status"], comparison["cost_lower"], comparison["cost_upper"])
PY
```

Each side receives its own solver allowance. Some backends charge model conversion
against it, and wall time can exceed it. On another machine a capped replay may
return bounds instead of a proof.
See [usage](usage.md) for uncapped runs, the TUI's **Constraint cost** tab and
resume behavior.
