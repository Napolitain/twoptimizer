"""
Hearts of Iron IV game module.

This module provides data structures and functionality for optimizing
Hearts of Iron IV gameplay, including factory production, infrastructure,
and military production using OR-Tools.
"""

from games.hoi4.core.country import Country
from games.hoi4.examples import (
    create_france_faction,
    create_germany_faction,
    create_soviet_union_faction,
)
from games.hoi4.faction import Faction
from games.hoi4.models.equipment import (
    EQUIPMENT_DATABASE,
    Equipment,
    EquipmentCategory,
    EquipmentType,
)
from games.hoi4.models.focus import Focus, FocusFilterCategory, FocusTree
from games.hoi4.models.game_date import HISTORICAL_DATES, GameClock, GameDate
from games.hoi4.models.idea import Idea, IdeaCategory, IdeaSlot
from games.hoi4.models.production import FactoryType, Production, ProductionLine
from games.hoi4.optimization import ProductionOptimizer
from games.hoi4.state import State, StateCategory

__all__ = [
    "EQUIPMENT_DATABASE",
    "HISTORICAL_DATES",
    "Country",
    "Equipment",
    "EquipmentCategory",
    "EquipmentType",
    "Faction",
    "FactoryType",
    "Focus",
    "FocusFilterCategory",
    "FocusTree",
    "GameClock",
    "GameDate",
    "Idea",
    "IdeaCategory",
    "IdeaSlot",
    "Production",
    "ProductionLine",
    "ProductionOptimizer",
    "State",
    "StateCategory",
    "create_france_faction",
    "create_germany_faction",
    "create_soviet_union_faction",
]
