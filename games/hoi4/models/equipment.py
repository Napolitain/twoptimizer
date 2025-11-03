"""
Equipment model for HOI4.

Represents military equipment that can be produced and used.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class EquipmentType(Enum):
    """Types of equipment in HOI4."""
    INFANTRY_EQUIPMENT = "infantry_equipment"
    ARTILLERY = "artillery"
    ANTI_TANK = "anti_tank"
    ANTI_AIR = "anti_air"
    
    # Armored
    LIGHT_TANK = "light_tank"
    MEDIUM_TANK = "medium_tank"
    HEAVY_TANK = "heavy_tank"
    MODERN_TANK = "modern_tank"
    
    # Air
    FIGHTER = "fighter"
    CAS = "cas"  # Close Air Support
    NAVAL_BOMBER = "naval_bomber"
    TACTICAL_BOMBER = "tactical_bomber"
    STRATEGIC_BOMBER = "strategic_bomber"
    
    # Naval
    DESTROYER = "destroyer"
    LIGHT_CRUISER = "light_cruiser"
    HEAVY_CRUISER = "heavy_cruiser"
    BATTLESHIP = "battleship"
    CARRIER = "carrier"
    SUBMARINE = "submarine"
    CONVOY = "convoy"
    
    # Support
    SUPPORT_EQUIPMENT = "support_equipment"
    MOTORIZED = "motorized"
    MECHANIZED = "mechanized"


class EquipmentCategory(Enum):
    """Categories for grouping equipment types."""
    INFANTRY = "infantry"
    ARMOR = "armor"
    AIR = "air"
    NAVAL = "naval"
    SUPPORT = "support"


@dataclass
class Equipment:
    """
    Represents a type of military equipment.
    
    Attributes:
        name: Internal name
        display_name: Human-readable name
        equipment_type: Type of equipment
        category: Category this equipment belongs to
        production_cost: Base production cost (IC = Industrial Capacity)
        production_time: Base production time in days
        resource_cost: Dictionary of resource_name -> amount required
        is_archetype: Whether this is an archetype (base type) or variant
        base_variant: Name of base variant if this is an upgrade
        reliability: Equipment reliability (0.0 to 1.0)
        maximum_speed: Maximum speed (relevant for vehicles)
        armor: Armor value (relevant for armored units)
        soft_attack: Attack vs soft targets (infantry)
        hard_attack: Attack vs hard targets (armor)
        air_attack: Anti-air capability
        defense: Defensive value
        breakthrough: Offensive breakthrough value
    """
    name: str
    display_name: str
    equipment_type: EquipmentType
    category: EquipmentCategory
    production_cost: float = 0.0
    production_time: int = 0
    resource_cost: Dict[str, float] = field(default_factory=dict)
    is_archetype: bool = False
    base_variant: Optional[str] = None
    
    # Combat stats
    reliability: float = 0.8
    maximum_speed: float = 0.0
    armor: float = 0.0
    soft_attack: float = 0.0
    hard_attack: float = 0.0
    air_attack: float = 0.0
    defense: float = 0.0
    breakthrough: float = 0.0
    
    def __post_init__(self):
        """Validate equipment attributes."""
        if self.production_cost < 0:
            raise ValueError("Production cost cannot be negative")
        if self.production_time < 0:
            raise ValueError("Production time cannot be negative")
        if not 0.0 <= self.reliability <= 1.0:
            raise ValueError("Reliability must be between 0.0 and 1.0")
    
    def get_daily_production_cost(self) -> float:
        """
        Calculate the daily IC cost for production.
        
        Returns:
            Daily IC requirement
        """
        if self.production_time == 0:
            return 0.0
        return self.production_cost / self.production_time
    
    def has_resource_requirement(self, resource: str) -> bool:
        """
        Check if this equipment requires a specific resource.
        
        Args:
            resource: Resource name (e.g., "steel", "oil")
            
        Returns:
            True if resource is required
        """
        return resource in self.resource_cost and self.resource_cost[resource] > 0
    
    def get_resource_requirement(self, resource: str) -> float:
        """
        Get the amount of a resource required.
        
        Args:
            resource: Resource name
            
        Returns:
            Amount required
        """
        return self.resource_cost.get(resource, 0.0)
    
    def total_resource_cost(self) -> float:
        """
        Calculate total resource requirements.
        
        Returns:
            Sum of all resource costs
        """
        return sum(self.resource_cost.values())
    
    def __str__(self) -> str:
        return f"{self.display_name} ({self.equipment_type.value})"
    
    def __repr__(self) -> str:
        return (f"Equipment(name='{self.name}', type={self.equipment_type}, "
                f"cost={self.production_cost}, time={self.production_time})")


# Factory equipment archetypes
def create_infantry_equipment() -> Equipment:
    """Create basic infantry equipment archetype."""
    return Equipment(
        name="infantry_equipment_1",
        display_name="Infantry Equipment I",
        equipment_type=EquipmentType.INFANTRY_EQUIPMENT,
        category=EquipmentCategory.INFANTRY,
        production_cost=0.5,
        production_time=30,
        resource_cost={"steel": 1.0},
        is_archetype=True,
        reliability=0.8,
        soft_attack=5.0,
        defense=12.0
    )


def create_artillery() -> Equipment:
    """Create basic artillery archetype."""
    return Equipment(
        name="artillery_equipment_1",
        display_name="Artillery I",
        equipment_type=EquipmentType.ARTILLERY,
        category=EquipmentCategory.INFANTRY,
        production_cost=2.0,
        production_time=60,
        resource_cost={"steel": 2.0, "tungsten": 0.5},
        is_archetype=True,
        reliability=0.8,
        soft_attack=25.0,
        defense=2.0
    )


def create_light_tank() -> Equipment:
    """Create basic light tank archetype."""
    return Equipment(
        name="light_tank_chassis_1",
        display_name="Light Tank I",
        equipment_type=EquipmentType.LIGHT_TANK,
        category=EquipmentCategory.ARMOR,
        production_cost=4.0,
        production_time=90,
        resource_cost={"steel": 2.0, "chromium": 1.0},
        is_archetype=True,
        reliability=0.8,
        maximum_speed=8.0,
        armor=10.0,
        soft_attack=7.0,
        hard_attack=3.0,
        defense=3.0,
        breakthrough=10.0
    )


def create_fighter() -> Equipment:
    """Create basic fighter aircraft archetype."""
    return Equipment(
        name="fighter_equipment_1",
        display_name="Fighter I",
        equipment_type=EquipmentType.FIGHTER,
        category=EquipmentCategory.AIR,
        production_cost=5.0,
        production_time=120,
        resource_cost={"aluminum": 2.0, "rubber": 1.0},
        is_archetype=True,
        reliability=0.8,
        maximum_speed=500.0,
        air_attack=15.0,
        defense=12.0
    )


def create_destroyer() -> Equipment:
    """Create basic destroyer archetype."""
    return Equipment(
        name="destroyer_1",
        display_name="Destroyer I",
        equipment_type=EquipmentType.DESTROYER,
        category=EquipmentCategory.NAVAL,
        production_cost=12.0,
        production_time=365,
        resource_cost={"steel": 3.0},
        is_archetype=True,
        reliability=0.85,
        maximum_speed=40.0,
        armor=1.0,
        soft_attack=2.0,
        defense=8.0
    )


# Equipment database
EQUIPMENT_DATABASE = {
    "infantry_equipment_1": create_infantry_equipment(),
    "artillery_equipment_1": create_artillery(),
    "light_tank_chassis_1": create_light_tank(),
    "fighter_equipment_1": create_fighter(),
    "destroyer_1": create_destroyer(),
}


def get_equipment(name: str) -> Optional[Equipment]:
    """
    Get equipment by name from the database.
    
    Args:
        name: Equipment name
        
    Returns:
        Equipment instance or None if not found
    """
    return EQUIPMENT_DATABASE.get(name)


def get_equipment_by_type(equipment_type: EquipmentType) -> List[Equipment]:
    """
    Get all equipment of a specific type.
    
    Args:
        equipment_type: Type to filter by
        
    Returns:
        List of matching equipment
    """
    return [eq for eq in EQUIPMENT_DATABASE.values() if eq.equipment_type == equipment_type]


def get_equipment_by_category(category: EquipmentCategory) -> List[Equipment]:
    """
    Get all equipment in a category.
    
    Args:
        category: Category to filter by
        
    Returns:
        List of matching equipment
    """
    return [eq for eq in EQUIPMENT_DATABASE.values() if eq.category == category]
