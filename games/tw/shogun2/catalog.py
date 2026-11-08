"""Read-only, file-versioned Shogun 2 catalogs."""

from pathlib import Path
from typing import cast

from games.tw.immutable import read_catalog
from games.tw.shogun2.records import Catalog, Rules

ROOT = Path(__file__).parents[1]
CATALOG_PATH = ROOT / "multigame/data/shogun2.json"
RULES_PATH = Path(__file__).parent / "data/rules.json"


def load_data() -> tuple[Catalog, Rules]:
    return cast(Catalog, read_catalog(CATALOG_PATH)), cast(Rules, read_catalog(RULES_PATH))
