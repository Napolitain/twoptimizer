"""
Hearts of Iron IV game module.

This module provides data structures and functionality for optimizing
Hearts of Iron IV gameplay, including factory production, infrastructure,
and military production using OR-Tools.
"""

from games.hoi4.state import State, StateCategory
from games.hoi4.faction import Faction
from games.hoi4.core.country import Country
from games.hoi4.models.idea import Idea, IdeaCategory, IdeaSlot
from games.hoi4.models.focus import Focus, FocusTree, FocusFilterCategory
from games.hoi4.models.game_date import GameDate, GameClock, HISTORICAL_DATES
from games.hoi4.models.equipment import (
    Equipment, EquipmentType, EquipmentCategory, EQUIPMENT_DATABASE
)
from games.hoi4.models.production import Production, ProductionLine, FactoryType
from games.hoi4.optimization import ProductionOptimizer
from games.hoi4.examples import (
    create_france_faction,
    create_germany_faction,
    create_soviet_union_faction,
)

__all__ = [
    "State",
    "StateCategory",
    "Faction",
    "Country",
    "Idea",
    "IdeaCategory",
    "IdeaSlot",
    "Focus",
    "FocusTree",
    "FocusFilterCategory",
    "GameDate",
    "GameClock",
    "HISTORICAL_DATES",
    "Equipment",
    "EquipmentType",
    "EquipmentCategory",
    "EQUIPMENT_DATABASE",
    "Production",
    "ProductionLine",
    "FactoryType",
    "ProductionOptimizer",
    "create_france_faction",
    "create_germany_faction",
    "create_soviet_union_faction",
]
