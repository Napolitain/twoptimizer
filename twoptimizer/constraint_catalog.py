"""Browse supported building catalogs without compiling an optimization model."""

import csv
from functools import lru_cache

from twoptimizer.catalog import ROOT, read
from twoptimizer.models import RunConfig


def building_choices(config: RunConfig) -> list[tuple[str, str]]:
    """Catalog candidates; final placement/research checks belong to each engine."""
    return list(_choices(config.game, config.faction, config.religion))


@lru_cache(maxsize=128)
def _choices(game: str, faction: str, religion: str) -> tuple[tuple[str, str], ...]:
    if game == "attila":
        rows = _attila(faction, religion)
    elif game == "rome2":
        rows = _rome(faction)
    elif game == "shogun2":
        rows = _shogun()
    elif game == "three_kingdoms":
        rows = _three_kingdoms(faction)
    else:
        return ()
    return tuple(sorted(rows, key=lambda row: (row[0].casefold(), row[1])))


def _attila(faction, religion):
    if faction == "all":
        with (ROOT / "attila/data/building_culture_variants_table.tsv").open() as stream:
            names = {row[0]: row[4] for row in csv.reader(stream, delimiter="\t")}
        known = read("attila/data/online_buildings.json")["buildings"]
        names = {key: name for key, name in names.items() if key in known}
    else:
        from games.tw.attila.model import load_attila
        from games.tw.models.model_attila import AttilaFactions, AttilaReligion

        parser = load_attila(AttilaFactions(faction), AttilaReligion[religion])
        names = {
            key: building.print_name
            for key, building in parser.buildings["att"].items()
            if building.metadata is not None
        }
    return [
        (f"{name}{' · legendary' if 'legendary' in key else ''} · {key}", key)
        for key, name in names.items()
        if key.startswith("att_bld_")
        and not any(marker in key for marker in ("_barbmigs_", "_nomad_", "_eastmig_", "ruin"))
    ]


def _rome(faction):
    data = read("rome2/data/economy_catalog.json")
    return [
        (f"{row['name']} · {key}", key)
        for key, row in data["buildings"].items()
        if row["level"] <= 4
        and any(faction == "all" or faction in entry["factions"] for entry in row["occurrences"])
    ]


def _shogun():
    from games.tw.shogun2.effects import family, unique_key
    from games.tw.shogun2.model import DEDICATED, TOWN

    return [
        (f"{row['name']}{' · unique' if unique_key(row) else ''} · {key}", key)
        for key, row in read("multigame/data/shogun2.json")["buildings"].items()
        if family(row) in DEDICATED | TOWN
    ]


def _three_kingdoms(faction):
    from games.tw.three_kingdoms.catalog import load_data

    data = load_data()
    chains = None if faction == "all" else set(data["factions"][faction]["chains"])
    return [
        (f"{row['name']} · {key}", key)
        for key, row in data["buildings"].items()
        if chains is None or row["chain"] in chains
    ]
