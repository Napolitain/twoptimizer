"""Read-only source catalogs, cached by file identity and modification time."""

from pathlib import Path
from typing import cast

from games.tw.immutable import read_catalog
from games.tw.rome2.records import Catalog

CATALOG = Path(__file__).parent / "data/economy_catalog.json"


def load_data() -> Catalog:
    return cast(Catalog, read_catalog(CATALOG))
