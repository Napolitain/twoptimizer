"""Current scoped income compilation and independent regional evaluation.

Historical base-GDP fixtures are retained as source evidence, not executed as
an alternate game model. Exact current coefficients have separate golden cases.
"""

import pytest

from games.optimization.competition import solve
from games.tw.attila.construction import Construction
from games.tw.attila.enums import AttilaFactions, AttilaReligion, NameType
from games.tw.attila.model import SnapshotOptions, compile_scenario, load_attila


@pytest.mark.parametrize("names", [NameType.NAME, NameType.HASH_NAME])
def test_current_income_model_agrees_between_backends_and_replays(names):
    parser = load_attila(
        AttilaFactions.ATT_FACT_EASTERN_ROMAN_EMPIRE,
        AttilaReligion.CHRIST_ORTHODOX,
    )
    parser.context.name_type = names
    province = next(p for p in parser.provinces.values() if p.print_name == "Thracia")
    snapshot = compile_scenario([province], SnapshotOptions(fertility=5))
    assert snapshot.economy is not None
    objectives = []
    for backend in ("cp-sat", "highs"):
        result = solve(snapshot.model, backend, workers=1)
        assert result.status == "OPTIMAL"
        assert snapshot.model.feasible(result.values)
        selected = {
            name
            for name, enabled in zip(snapshot.model.names, result.values, strict=True)
            if enabled > 0.5
        }
        report = snapshot.economy.evaluate_layout(selected)
        assert report["objective"] == pytest.approx(result.objective)
        assert report["finances"]["total"]["net_income"] == pytest.approx(result.objective)
        assert all(value >= 0 for value in report["province_food"].values())
        assert all(value >= 0 for value in report["public_order"].values())
        assert all(row["sanitation"] >= 1 for row in report["regions"].values())
        objectives.append(result.objective)
    assert objectives[0] == pytest.approx(objectives[1])
    assert all(not region.buildings for region in province.regions)


def test_historical_objective_is_rejected_at_the_construction_boundary(context):
    with pytest.raises(ValueError, match="wealth or income"):
        Construction(objective="legacy", context=context)
