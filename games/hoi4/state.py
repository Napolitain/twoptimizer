"""
Hearts of Iron IV State module.

A state in HoI4 represents a geographical area with various attributes
such as civilian factories, military factories, infrastructure, and defenses.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List
from enum import Enum


class StateCategory(Enum):
    """State categories that determine building slot capacity."""
    WASTELAND = ("wasteland", 0)
    ENCLAVE = ("enclave", 1)
    TINY_ISLAND = ("tiny_island", 1)
    SMALL_ISLAND = ("small_island", 2)
    PASTORAL = ("pastoral", 2)
    RURAL = ("rural", 4)
    TOWN = ("town", 5)
    LARGE_TOWN = ("large_town", 6)
    CITY = ("city", 8)
    LARGE_CITY = ("large_city", 10)
    METROPOLIS = ("metropolis", 11)
    MEGALOPOLIS = ("megalopolis", 12)
    
    def __init__(self, category_name: str, building_slots: int):
        self.category_name = category_name
        self.building_slots = building_slots


@dataclass
class State:
    """
    Represents a state in Hearts of Iron IV.
    
    Attributes:
        name: The name of the state
        civilian_factories: Number of civilian factories in the state
        military_factories: Number of military factories in the state
        infrastructure: Infrastructure level (affects production and supply)
        bunkers: Number of bunkers/fortifications for defense
        naval_bases: Number of naval bases (optional)
        air_bases: Number of air bases (optional)
        state_category: Category determining building slot capacity
        manpower: Available manpower in the state
        victory_points: Victory points value of the state
        resources: Dictionary of resource_name -> amount (oil, steel, aluminum, etc.)
        building_slots: Maximum building slots (calculated from category if not specified)
        state_modifiers: Dictionary of state-level modifiers
        provinces: List of province IDs in this state
    """
    name: str
    civilian_factories: int = 0
    military_factories: int = 0
    infrastructure: int = 0
    bunkers: int = 0
    naval_bases: Optional[int] = None
    air_bases: Optional[int] = None
    state_category: Optional[StateCategory] = None
    manpower: int = 0
    victory_points: int = 0
    resources: Dict[str, float] = field(default_factory=dict)
    building_slots: Optional[int] = None
    state_modifiers: Dict[str, float] = field(default_factory=dict)
    provinces: List[int] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate state attributes."""
        if self.civilian_factories < 0:
            raise ValueError("Civilian factories cannot be negative")
        if self.military_factories < 0:
            raise ValueError("Military factories cannot be negative")
        if self.infrastructure < 0:
            raise ValueError("Infrastructure cannot be negative")
        if self.bunkers < 0:
            raise ValueError("Bunkers cannot be negative")
        if self.naval_bases is not None and self.naval_bases < 0:
            raise ValueError("Naval bases cannot be negative")
        if self.air_bases is not None and self.air_bases < 0:
            raise ValueError("Air bases cannot be negative")
        if self.manpower < 0:
            raise ValueError("Manpower cannot be negative")
        if self.victory_points < 0:
            raise ValueError("Victory points cannot be negative")
        
        # Auto-calculate building slots from category if not specified
        if self.building_slots is None and self.state_category is not None:
            self.building_slots = self.state_category.building_slots
    
    def total_factories(self) -> int:
        """Calculate the total number of factories in the state."""
        return self.civilian_factories + self.military_factories
    
    def get_max_building_slots(self) -> int:
        """
        Get the maximum number of building slots available.
        
        Returns:
            Maximum building slots, accounting for infrastructure bonus
        """
        base_slots = self.building_slots if self.building_slots is not None else 0
        
        # Infrastructure provides additional building slots
        # In HOI4, each infrastructure level provides +0.5 building slots
        infrastructure_bonus = self.infrastructure * 0.5
        
        return int(base_slots + infrastructure_bonus)
    
    def get_used_building_slots(self) -> int:
        """
        Calculate how many building slots are currently used.
        
        Returns:
            Number of used building slots
        """
        # Count factories and infrastructure as using slots
        used = self.civilian_factories + self.military_factories
        
        # Add other buildings that use slots
        if self.naval_bases:
            used += self.naval_bases
        if self.air_bases:
            used += self.air_bases
        
        return used
    
    def get_free_building_slots(self) -> int:
        """
        Calculate how many building slots are still available.
        
        Returns:
            Number of free building slots
        """
        return max(0, self.get_max_building_slots() - self.get_used_building_slots())
    
    def can_build(self, slots_required: int = 1) -> bool:
        """
        Check if there are enough free building slots.
        
        Args:
            slots_required: Number of slots needed
            
        Returns:
            True if enough slots are available
        """
        return self.get_free_building_slots() >= slots_required
    
    def get_resource(self, resource_name: str) -> float:
        """
        Get the amount of a specific resource.
        
        Args:
            resource_name: Name of the resource (e.g., "oil", "steel")
            
        Returns:
            Amount of the resource, 0.0 if not present
        """
        return self.resources.get(resource_name, 0.0)
    
    def set_resource(self, resource_name: str, amount: float) -> None:
        """
        Set the amount of a specific resource.
        
        Args:
            resource_name: Name of the resource
            amount: Amount to set
        """
        if amount < 0:
            raise ValueError(f"Resource amount cannot be negative: {resource_name}")
        self.resources[resource_name] = amount
    
    def add_resource(self, resource_name: str, amount: float) -> None:
        """
        Add to the amount of a specific resource.
        
        Args:
            resource_name: Name of the resource
            amount: Amount to add (can be negative to subtract)
        """
        current = self.get_resource(resource_name)
        new_amount = current + amount
        if new_amount < 0:
            raise ValueError(f"Cannot reduce {resource_name} below zero")
        self.resources[resource_name] = new_amount
    
    def get_modifier(self, modifier_name: str) -> float:
        """
        Get the value of a specific state modifier.
        
        Args:
            modifier_name: Name of the modifier
            
        Returns:
            Modifier value, 0.0 if not present
        """
        return self.state_modifiers.get(modifier_name, 0.0)
    
    def set_modifier(self, modifier_name: str, value: float) -> None:
        """
        Set a state modifier.
        
        Args:
            modifier_name: Name of the modifier
            value: Value to set
        """
        self.state_modifiers[modifier_name] = value
    
    def add_modifier(self, modifier_name: str, value: float) -> None:
        """
        Add to a state modifier.
        
        Args:
            modifier_name: Name of the modifier
            value: Value to add
        """
        current = self.get_modifier(modifier_name)
        self.state_modifiers[modifier_name] = current + value
    
    def __repr__(self) -> str:
        return (f"state(name='{self.name}', "
                f"civilian_factories={self.civilian_factories}, "
                f"military_factories={self.military_factories}, "
                f"infrastructure={self.infrastructure}, "
                f"bunkers={self.bunkers})")
