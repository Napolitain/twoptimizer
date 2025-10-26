"""
Hearts of Iron IV game module.

This module provides data structures and functionality for optimizing
Hearts of Iron IV gameplay, including factory production, infrastructure,
and military production using OR-Tools.
"""

from games.hoi4.region import Region
from games.hoi4.faction import Faction
from games.hoi4.examples import (
    create_france_faction,
    create_germany_faction,
    create_soviet_union_faction,
)

__all__ = [
    "Region",
    "Faction",
    "create_france_faction",
    "create_germany_faction",
    "create_soviet_union_faction",
]
