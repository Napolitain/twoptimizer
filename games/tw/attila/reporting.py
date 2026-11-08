"""Independent layout evaluation and JSON report rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING

from games.tw.attila.records import FinanceTotals, LayoutReport, RegionFinance
from games.tw.immutable import thaw

if TYPE_CHECKING:
    from games.tw.attila.economy import Economy


def evaluate_layout(economy: Economy, selected, mode="income") -> LayoutReport:
    from games.tw.attila.effects import METRICS

    financials: dict[str, RegionFinance] = {}
    for r in economy.regions:
        wealth = economy.evaluate(economy.wealth(r), selected)
        taxable = economy.evaluate(economy.taxable_income(r), selected)
        tax = economy.evaluate(economy.tax_income(r), selected)
        upkeep = economy.evaluate(economy.upkeep(r), selected)
        financials[r.name] = {
            "wealth": wealth,
            "tax_multiplier": economy.evaluate(economy.tax_factor(r), selected),
            "tax_bonus_income": taxable - wealth,
            "corruption_loss": taxable - tax,
            "tax_income": tax,
            "building_upkeep": upkeep,
            "net_income": tax - upkeep,
        }
    exports = economy.evaluate(economy.export_income(), selected)
    totals: FinanceTotals = {
        "wealth": sum(row["wealth"] for row in financials.values()),
        "tax_bonus_income": sum(row["tax_bonus_income"] for row in financials.values()),
        "corruption_loss": sum(row["corruption_loss"] for row in financials.values()),
        "tax_income": sum(row["tax_income"] for row in financials.values()),
        "building_upkeep": sum(row["building_upkeep"] for row in financials.values()),
        "net_income": sum(row["net_income"] for row in financials.values()),
        "trade_income": exports,
        "other_recurring_income": economy.evaluate(economy.other_income(), selected),
    }
    totals["net_income"] += exports + totals["other_recurring_income"]
    report: LayoutReport = {
        "finances": {"total": totals, "regions": financials},
        "faction_traits": economy.traits,
        "catalogue_exclusions": getattr(economy, "catalogue_exclusions", []),
        "imported_modifiers": economy.modifiers,
        "assumptions": {
            "treasury_interest": "excluded_by_requested_objective",
            "province_capitals_held": economy.capitals_held,
            "base_tax_percent_default": 100,
            "base_corruption_percent_default": 0,
            "unsupplied_trade_tribute_and_immigration_baselines": 0,
            "campaign": economy.campaign.to_dict(),
            "technology_economic_bonuses": (
                "imported; see imported_modifiers for active facts and omissions"
            ),
            "religion_economic_bonuses": (
                "imported; conditional religious public order requires scenario input"
            ),
        },
        "state_religion": economy.state_religion,
        "metric_semantics": (
            "Scoped effect totals and capabilities; not a forecast of conversion "
            "or research completion"
        ),
        "targets": [
            {
                **target.to_dict(),
                "actual": economy.evaluate(
                    economy.metric(
                        target.metric,
                        target.scope,
                        target.recipient,
                    ),
                    selected,
                ),
            }
            for target in economy.scenario.targets
        ],
        "weighted_metrics": [
            {
                **target.to_dict(),
                "actual": economy.evaluate(
                    economy.metric(
                        target.metric,
                        target.scope,
                        target.recipient,
                    ),
                    selected,
                ),
            }
            for target in economy.scenario.weights
        ],
        "metrics": {
            metric: economy.evaluate(economy.metric(metric), selected)
            for metric in sorted(METRICS)
            if economy.metric(metric)
        },
        "export_income": economy.evaluate(economy.export_income(), selected),
        "project_cost": economy.evaluate(economy.project_cost(), selected),
        "objective_kind": "weighted_" + mode if economy.scenario.weights else mode,
        "objective": economy.evaluate(economy.objective(mode), selected),
        "regions": {
            r.name: {
                "wealth": economy.evaluate(economy.wealth(r), selected),
                "food": economy.evaluate(economy.food(r), selected),
                "sanitation": economy.evaluate(economy.sanitation(r), selected),
                "fertility": economy.evaluate(economy.fertility(r), selected),
            }
            for r in economy.regions
        },
        "corruption_percent": {
            r.name: 100 * economy.evaluate(economy.corruption(r), selected) for r in economy.regions
        },
        "province_food": {
            p.name: sum(economy.evaluate(economy.food(r), selected) for r in p.regions)
            + economy.scenario.for_province(p).food
            for p in economy.provinces
        },
        "public_order": {
            p.name: economy.evaluate(economy.public_order(p), selected) for p in economy.provinces
        },
    }
    return thaw(report)
