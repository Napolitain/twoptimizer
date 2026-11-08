"""Reproducible public-data Shogun 2 comparisons and independent solver checks."""

import argparse
import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from games.tw.shogun2.catalog import CATALOG_PATH, RULES_PATH, load_data
from games.tw.shogun2.effects import family, parse
from twoptimizer import service
from twoptimizer.cli_constraints import (
    add_constraint_options,
    constraint_csv,
    constraint_metadata,
    read_constraints,
)
from twoptimizer.models import RunConfig, RunRequest
from twoptimizer.session import RunSession


def assumptions(*, joint=True):
    return {
        "objective": (
            "Current domestic provincial tax receipts in koku per turn; not GDP, "
            "total campaign income or treasury profit."
        ),
        "ownership": (
            "The selected provinces are jointly owned; food and unique-building "
            "limits are faction-wide."
        )
        if joint
        else (
            "Each selected province is optimized as a separate hypothetical holding; "
            "food and unique-building limits reset for each case. Independent results "
            "must not be added as one legal faction layout."
        ),
        "adjacency": (
            "The imported neighboring-province effects are religious zeal, not direct "
            "income bonuses. Conversion dynamics are excluded under the explicit full "
            "state-religion adherence assumption; no adjacency income is invented."
        ),
        "town_wealth": (
            "Explicit, fixed scenario input. Default zero isolates income from "
            "chosen buildings; it is not a historical start state."
        ),
        "tax_and_order": (
            "Common base tax rate 30%, administration multiplier 1, normal-tax "
            "unrest -4, minimum public order 0 unless overridden. No governors, "
            "agents, garrisons, honour or difficulty bonuses."
        ),
        "religion": (
            "Each clan's native faith unless explicitly overridden, 100% local adherence. "
            "No conversion timeline or religious unrest at this snapshot."
        ),
        "research_and_resources": (
            "All imported arts researched, all prerequisite construction "
            "resources accessible; no construction budget or sequencing. Arts "
            "food is counted once per faction."
        ),
        "eligibility": (
            "Selected-faith religious chains, Otomo-specific Christian branch, "
            "location-specific specialty and port plots, one chain per town slot,"
            " castle-level slot capacity, one new legendary town building of each"
            " chain per faction, one new Nanban chain. No captured unique "
            "duplicates; Jesuit Colleges are not legendary."
        ),
        "growth": (
            "Building, arts and shared-food growth components are reported, not "
            "valued in the current-income objective. Tax-induced growth penalties"
            " and future wealth dynamics are not simulated. Tied layouts can have"
            " different growth."
        ),
        "excluded_income_and_costs": (
            "Trade/export/tribute income, the common clan stipend, military/agent"
            " expenses, first-construction race rewards and campaign bonuses "
            "excluded. Uesugi's trade trait therefore has no contribution. "
            "One-off Portuguese land sale excluded. Military-only buildings "
            "cannot improve this objective and are omitted."
        ),
        "validation_limit": (
            "Optimality applies to this public-reference static model, not an "
            "exhaustive or installed-build-verified campaign simulation. Province"
            " prose yields do not override structured building effects."
        ),
    }


def coverage(catalog):
    recognized, outside, nonrecurring = [], [], []
    for section in ("buildings", "technologies"):
        for record in catalog[section].values():
            for text in record["facts"] + record.get("clan_facts", []):
                row = {"id": record["id"], "fact": text}
                effect = parse(text)
                if effect:
                    row["kind"] = effect.kind
                    recognized.append(row)
                elif section == "buildings" and family(record) == "portuguese":
                    nonrecurring.append(row)
                else:
                    outside.append(row)
    return {
        "effect_disposition": {
            "wealth": "Current taxable wealth, with soil and farm modifiers",
            "tax_percent": "Percentage points added to the effective tax rate",
            "farm_percent": "Additive farm wealth percentage bonuses",
            "food": "Enforced faction-wide; surplus growth reported in each province",
            "order": "Enforced locally; arts bonuses applied per province",
            "religious_order": "Enforced locally under the explicit 100% adherence assumption",
            "adjacent_religious_zeal": (
                "Recognized neighboring-province conversion effect; outside the static "
                "income model, which assumes 100% state-religion adherence"
            ),
            "building_growth": "Reported only; no future-income objective",
            "arts_growth": "Reported only; no future-income objective",
            "growth_percent": "Reported only; no future-income objective",
            "construction_cost": "Outside the static, unconstrained-budget scenario",
            "tariff_percent": "Recognized but outside the domestic-tax objective",
        },
        "clan_traits": [
            {
                "clan": clan["id"],
                "fact": text,
                "disposition": "Applied: +10% farm wealth"
                if text == "Increased income from farms"
                else (
                    "Outside domestic taxation; no trade, armies, agent actions or "
                    "construction budget modeled"
                ),
            }
            for clan in catalog["factions"].values()
            for text in clan.get("clan_facts", [])
        ],
        "recognized": recognized,
        "first_construction_rewards_outside_scope": [
            {"id": record["id"], "fact": text}
            for record in catalog["buildings"].values()
            for text in record.get("first_construct_facts", [])
        ],
        "outside_static_income_scope": outside,
        "nonrecurring_land_lease": nonrecurring,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--province", action="append", help="Province ID, repeat to select holdings; all selects 65"
    )
    ownership = parser.add_mutually_exclusive_group()
    ownership.add_argument(
        "--joint", dest="joint", action="store_true", help="Optimize selected provinces together"
    )
    ownership.add_argument(
        "--independent",
        dest="joint",
        action="store_false",
        help="Optimize each province separately",
    )
    parser.set_defaults(joint=True)
    add_constraint_options(parser, "shogun2")
    parser.add_argument("--clan", action="append", help="Default: all 12 imported playable clans")
    parser.add_argument(
        "--algorithm",
        action="append",
        choices=["cp-sat", "cbc", "scip"],
        help="Repeat to cross-check exact solvers",
    )
    parser.add_argument("--soil", action="append", choices=["native", "barren", "very_fertile"])
    parser.add_argument("--town-wealth", type=float, default=0)
    parser.add_argument("--tax", type=float, default=30)
    parser.add_argument(
        "--seconds",
        type=float,
        default=None,
        help="Optional time limit per case; default runs to completion",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Optional CPU worker override; default automatic",
    )
    parser.add_argument("--output", type=Path, default=Path("benchmark-results/shogun2/income"))
    args = parser.parse_args(argv)
    catalog, _ = load_data()
    request = request_from_args(args)
    jobs, skipped = service.make_jobs(request)
    for message in skipped:
        print(f"Skipped: {message}", flush=True)
    provinces = list(dict.fromkeys(key for job in jobs for key in job.holdings))
    cases, rows = [], []
    first_results = {}
    session = RunSession()
    for job in jobs:
        case = service.solve_case(job, session=session)
        result = case.raw
        cases.append({"soil": job.soil, "clan_name": case.faction, **result})
        first_results.setdefault((job.soil, job.faction, job.holdings), case)
        print(
            f"{job.soil:13} {job.faction:12} {job.algorithm:6} {case.solver.status:9} "
            f"{case.income} ({case.solver.seconds:.3f}s)",
            flush=True,
        )
    for (soil, _, holdings), first in first_results.items():
        result = first.raw
        rows.append(
            {
                "soil": soil,
                "clan": first.faction,
                "ownership": "joint" if request.joint else "independent",
                "provinces": ";".join(holdings),
                "religion": result.get("religion"),
                "domestic_tax_income": first.income,
                "food_surplus": first.metrics.get("food_surplus"),
                "status": first.solver.status,
                **constraint_csv(args, "shogun2"),
                **{
                    key: result.get("provinces", {}).get(key, {}).get("tax_income")
                    for key in provinces
                },
            }
        )
    payload = {
        "schema_version": 1,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "assumptions": assumptions(joint=request.joint),
        "overrides": {"town_wealth": args.town_wealth, "base_tax_percent": args.tax},
        **constraint_metadata(args, "shogun2"),
        "source_files": {
            str(p.relative_to(Path(__file__).parents[3])): hashlib.sha256(
                p.read_bytes()
            ).hexdigest()
            for p in (CATALOG_PATH, RULES_PATH)
        },
        "coverage": coverage(catalog),
        "cases": cases,
        "skipped": skipped,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix(".json").write_text(json.dumps(payload, indent=2) + "\n")
    with args.output.with_suffix(".csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return payload


def request_from_args(args) -> RunRequest:
    """Preserve jointly owned CLI holdings and research defaults in shared requests."""
    return RunRequest(
        config=RunConfig(
            game="shogun2",
            faction="all",
            province="jap_owari",
            algorithm="cp-sat",
            seconds=args.seconds,
            workers=args.workers,
            research="all",
            town_wealth=args.town_wealth,
            tax=args.tax,
            constraints=read_constraints(args, "shogun2"),
        ),
        factions=tuple(args.clan or ()),
        provinces=tuple(args.province or ("jap_sado", "jap_settsu", "jap_owari")),
        algorithms=tuple(args.algorithm or ()),
        soils=tuple(args.soil or ("native", "barren", "very_fertile")),
        joint=args.joint,
    )


if __name__ == "__main__":
    from twoptimizer.cli import run_cli

    raise SystemExit(run_cli(main))
