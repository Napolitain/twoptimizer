"""
Building model for HOI4.

Represents buildings and their effects in the game.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum
from .modifier import Modifier, ModifierScope, ModifierManager


class BuildingCategory(Enum):
    """Categories of buildings in HOI4."""
    INFRASTRUCTURE = "infrastructure"
    INDUSTRIAL = "industrial"
    MILITARY = "military"
    NAVAL = "naval"
    AIR = "air"
    FORTIFICATION = "fortification"
    RESOURCE = "resource"
    SPECIAL = "special"


@dataclass
class BuildingType:
    """
    Represents a type of building that can be constructed.
    
    Attributes:
        name: Internal name of the building type
        display_name: Human-readable name
        category: Category this building belongs to
        base_cost: Base construction cost
        construction_time: Base construction time in days
        max_level: Maximum level that can be built (-1 for unlimited)
        is_provincial: Whether this building is built per province vs per state
        modifiers: Modifiers provided by this building
        requirements: Technology or other requirements
    """
    name: str
    display_name: str
    category: BuildingCategory
    base_cost: int = 0
    construction_time: int = 0
    max_level: int = -1
    is_provincial: bool = False
    modifiers: Dict[str, Dict[str, float]] = field(default_factory=dict)
    requirements: List[str] = field(default_factory=list)
    icon_frame: int = 0
    
    def get_cost(self, level: int = 1) -> int:
        """
        Calculate the cost to build this building at a specific level.
        
        Args:
            level: Level to calculate cost for
            
        Returns:
            Construction cost
        """
        # In HOI4, most buildings have linear cost scaling
        return self.base_cost * level
    
    def get_construction_time(self, level: int = 1) -> int:
        """
        Calculate construction time for this building at a specific level.
        
        Args:
            level: Level to calculate time for
            
        Returns:
            Construction time in days
        """
        return self.construction_time * level
    
    def can_build_level(self, current_level: int, target_level: int) -> bool:
        """
        Check if we can build from current level to target level.
        
        Args:
            current_level: Current building level
            target_level: Desired building level
            
        Returns:
            True if construction is possible
        """
        if target_level <= current_level:
            return False
        if self.max_level > 0 and target_level > self.max_level:
            return False
        return True
    
    def get_modifiers_for_level(self, level: int) -> ModifierManager:
        """
        Get all modifiers provided by this building at a specific level.
        
        Args:
            level: Building level
            
        Returns:
            ModifierManager with all applicable modifiers
        """
        manager = ModifierManager()
        
        for scope_name, effects in self.modifiers.items():
            try:
                scope = ModifierScope(scope_name)
            except ValueError:
                continue  # Skip invalid scopes
            
            # Scale effects by level
            scaled_effects = {name: value * level for name, value in effects.items()}
            
            modifier = Modifier(
                name=f"{self.name}_level_{level}",
                scope=scope,
                effects=scaled_effects
            )
            manager.add_modifier(modifier)
        
        return manager


@dataclass
class Building:
    """
    Represents an actual building instance in a state or province.
    
    Attributes:
        building_type: Type of building this is
        level: Current level of the building
        under_construction: Levels currently under construction
        damage: Damage percentage (0.0 to 1.0)
        construction_progress: Progress on current construction (0.0 to 1.0)
    """
    building_type: BuildingType
    level: int = 0
    under_construction: int = 0
    damage: float = 0.0
    construction_progress: float = 0.0
    
    def __post_init__(self):
        """Validate building state."""
        if self.level < 0:
            raise ValueError("Building level cannot be negative")
        if self.under_construction < 0:
            raise ValueError("Under construction levels cannot be negative")
        if not 0.0 <= self.damage <= 1.0:
            raise ValueError("Damage must be between 0.0 and 1.0")
        if not 0.0 <= self.construction_progress <= 1.0:
            raise ValueError("Construction progress must be between 0.0 and 1.0")
    
    @property
    def effective_level(self) -> float:
        """
        Get the effective level considering damage.
        
        Returns:
            Effective level after damage reduction
        """
        return self.level * (1.0 - self.damage)
    
    @property
    def total_level_when_complete(self) -> int:
        """
        Get the total level this building will have when construction completes.
        
        Returns:
            Total level after construction
        """
        return self.level + self.under_construction
    
    def can_construct(self, levels: int = 1) -> bool:
        """
        Check if we can construct additional levels.
        
        Args:
            levels: Number of levels to construct
            
        Returns:
            True if construction is possible
        """
        return self.building_type.can_build_level(
            self.total_level_when_complete,
            self.total_level_when_complete + levels
        )
    
    def start_construction(self, levels: int = 1) -> bool:
        """
        Start construction of additional levels.
        
        Args:
            levels: Number of levels to construct
            
        Returns:
            True if construction was started
        """
        if not self.can_construct(levels):
            return False
        
        self.under_construction += levels
        return True
    
    def complete_construction(self) -> int:
        """
        Complete all construction in progress.
        
        Returns:
            Number of levels that were completed
        """
        completed = self.under_construction
        self.level += completed
        self.under_construction = 0
        self.construction_progress = 0.0
        return completed
    
    def repair(self, amount: float = 1.0) -> float:
        """
        Repair damage to the building.
        
        Args:
            amount: Amount of damage to repair (0.0 to 1.0)
            
        Returns:
            Actual amount repaired
        """
        if self.damage <= 0.0:
            return 0.0
        
        actual_repair = min(amount, self.damage)
        self.damage -= actual_repair
        return actual_repair
    
    def take_damage(self, amount: float) -> float:
        """
        Apply damage to the building.
        
        Args:
            amount: Amount of damage to apply (0.0 to 1.0)
            
        Returns:
            Actual damage taken
        """
        if self.damage >= 1.0:
            return 0.0
        
        actual_damage = min(amount, 1.0 - self.damage)
        self.damage += actual_damage
        return actual_damage
    
    def get_current_modifiers(self) -> ModifierManager:
        """
        Get all modifiers currently provided by this building.
        
        Returns:
            ModifierManager with current modifiers
        """
        return self.building_type.get_modifiers_for_level(int(self.effective_level))
    
    def get_construction_cost(self, levels: int = 1) -> int:
        """
        Get the cost to construct additional levels.
        
        Args:
            levels: Number of levels to construct
            
        Returns:
            Total construction cost
        """
        cost = 0
        current_level = self.total_level_when_complete
        
        for i in range(levels):
            cost += self.building_type.get_cost(current_level + i + 1)
        
        return cost
    
    def get_construction_time(self, levels: int = 1) -> int:
        """
        Get the time to construct additional levels.
        
        Args:
            levels: Number of levels to construct
            
        Returns:
            Construction time in days
        """
        return self.building_type.get_construction_time(levels)
    
    def __str__(self) -> str:
        return f"{self.building_type.display_name} (Level {self.level})"
    
    def __repr__(self) -> str:
        return (f"Building(type='{self.building_type.name}', level={self.level}, "
                f"under_construction={self.under_construction}, damage={self.damage:.2f})")
