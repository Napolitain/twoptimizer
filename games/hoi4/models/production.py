"""
Production system for HOI4.

Models factory production, efficiency, and resource consumption.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
from .equipment import Equipment, EquipmentType
from .game_date import GameDate


class FactoryType(Enum):
    """Types of factories in HOI4."""
    CIVILIAN = "civilian"
    MILITARY = "military"
    NAVAL = "naval"


@dataclass
class ProductionLine:
    """
    Represents a production line in a factory.
    
    A production line dedicates factories to producing specific equipment.
    
    Attributes:
        equipment: Equipment being produced
        assigned_factories: Number of factories assigned (can be fractional)
        efficiency: Current production efficiency (0.0 to 1.0+)
        start_date: When production started
        priority: Production priority (1-10, higher = more priority)
    """
    equipment: Equipment
    assigned_factories: float = 0.0
    efficiency: float = 0.1  # Starts at 10% efficiency
    start_date: Optional[GameDate] = None
    priority: int = 5
    
    # Efficiency parameters
    BASE_EFFICIENCY = 0.1  # Starting efficiency
    MAX_EFFICIENCY = 1.0   # Maximum efficiency without bonuses
    EFFICIENCY_GROWTH_PER_DAY = 0.01  # Efficiency gain per day (1% per day)
    
    def __post_init__(self):
        """Validate production line attributes."""
        if self.assigned_factories < 0:
            raise ValueError("Assigned factories cannot be negative")
        if not 0.0 <= self.efficiency <= 2.0:
            raise ValueError("Efficiency must be between 0.0 and 2.0")
        if not 1 <= self.priority <= 10:
            raise ValueError("Priority must be between 1 and 10")
    
    def calculate_efficiency(self, current_date: GameDate, efficiency_modifiers: float = 0.0) -> float:
        """
        Calculate current production efficiency.
        
        Efficiency grows over time as workers gain experience.
        Starts at BASE_EFFICIENCY and grows by EFFICIENCY_GROWTH_PER_DAY.
        
        Args:
            current_date: Current game date
            efficiency_modifiers: Additional efficiency bonuses from ideas, focuses, etc.
            
        Returns:
            Current efficiency (capped at MAX_EFFICIENCY + modifiers)
        """
        if self.start_date is None:
            return self.BASE_EFFICIENCY
        
        # Calculate days of production
        days_producing = self.start_date.days_until(current_date)
        if days_producing < 0:
            return self.BASE_EFFICIENCY
        
        # Calculate base efficiency growth
        base_eff = min(
            self.BASE_EFFICIENCY + (days_producing * self.EFFICIENCY_GROWTH_PER_DAY),
            self.MAX_EFFICIENCY
        )
        
        # Apply modifiers
        modified_eff = base_eff * (1.0 + efficiency_modifiers)
        
        # Cap at reasonable maximum (200%)
        return min(modified_eff, 2.0)
    
    def get_daily_output(self, efficiency_modifiers: float = 0.0, current_date: Optional[GameDate] = None) -> float:
        """
        Calculate daily equipment output.
        
        Output = (factories * efficiency) / production_time_per_unit
        
        Args:
            efficiency_modifiers: Additional efficiency bonuses
            current_date: Current date for efficiency calculation (if provided)
            
        Returns:
            Daily equipment output
        """
        if self.assigned_factories == 0:
            return 0.0
        
        # Use current efficiency or calculate it
        if current_date and self.start_date:
            eff = self.calculate_efficiency(current_date, efficiency_modifiers)
        else:
            eff = self.efficiency * (1.0 + efficiency_modifiers)
        
        # Each factory provides 1 unit of IC per day
        # Daily IC available = factories * efficiency
        daily_ic = self.assigned_factories * eff
        
        # Daily output = IC / production_time
        if self.equipment.production_time == 0:
            return 0.0
        
        return daily_ic * (self.equipment.production_time / self.equipment.production_cost)
    
    def get_daily_resource_consumption(self, efficiency_modifiers: float = 0.0) -> Dict[str, float]:
        """
        Calculate daily resource consumption.
        
        Args:
            efficiency_modifiers: Additional efficiency bonuses
            
        Returns:
            Dictionary of resource_name -> daily_amount
        """
        daily_output = self.get_daily_output(efficiency_modifiers)
        
        consumption = {}
        for resource, amount_per_unit in self.equipment.resource_cost.items():
            consumption[resource] = daily_output * amount_per_unit
        
        return consumption
    
    def calculate_output_by_date(
        self, 
        target_date: GameDate, 
        start_date: Optional[GameDate] = None,
        efficiency_modifiers: float = 0.0
    ) -> float:
        """
        Calculate total equipment produced by a target date.
        
        This is a simplified calculation that assumes constant efficiency growth.
        
        Args:
            target_date: Date to calculate production until
            start_date: Start date (defaults to self.start_date)
            efficiency_modifiers: Additional efficiency bonuses
            
        Returns:
            Total equipment produced
        """
        start = start_date or self.start_date
        if start is None:
            return 0.0
        
        days = start.days_until(target_date)
        if days <= 0:
            return 0.0
        
        # Simplified: use average efficiency over the period
        # This is an approximation; more accurate would integrate over time
        start_eff = self.calculate_efficiency(start, efficiency_modifiers)
        end_eff = self.calculate_efficiency(target_date, efficiency_modifiers)
        avg_eff = (start_eff + end_eff) / 2.0
        
        # Calculate total output
        daily_ic = self.assigned_factories * avg_eff
        total_ic = daily_ic * days
        
        if self.equipment.production_cost == 0:
            return 0.0
        
        return total_ic / self.equipment.production_cost
    
    def set_efficiency(self, efficiency: float) -> None:
        """
        Manually set efficiency (e.g., after switching production).
        
        Args:
            efficiency: New efficiency value
        """
        if not 0.0 <= efficiency <= 2.0:
            raise ValueError("Efficiency must be between 0.0 and 2.0")
        self.efficiency = efficiency
    
    def __str__(self) -> str:
        return (f"ProductionLine({self.equipment.display_name}: "
                f"{self.assigned_factories:.1f} factories @ {self.efficiency*100:.0f}% efficiency)")
    
    def __repr__(self) -> str:
        return (f"ProductionLine(equipment={self.equipment.name}, "
                f"factories={self.assigned_factories}, efficiency={self.efficiency})")


@dataclass
class Production:
    """
    Manages all production for a country.
    
    Tracks factory allocation, production lines, and resource consumption.
    
    Attributes:
        civilian_factories: Total civilian factories
        military_factories: Total military factories
        naval_factories: Total naval factories (dockyards)
        production_lines: List of active production lines
        civilian_factory_construction: Factories dedicated to building civ factories
        military_factory_construction: Factories dedicated to building mil factories
        consumer_goods_factories: Factories allocated to consumer goods (by law)
    """
    civilian_factories: int = 0
    military_factories: int = 0
    naval_factories: int = 0
    production_lines: List[ProductionLine] = field(default_factory=list)
    civilian_factory_construction: float = 0.0
    military_factory_construction: float = 0.0
    consumer_goods_factories: float = 0.0
    
    def __post_init__(self):
        """Validate production attributes."""
        if self.civilian_factories < 0:
            raise ValueError("Civilian factories cannot be negative")
        if self.military_factories < 0:
            raise ValueError("Military factories cannot be negative")
        if self.naval_factories < 0:
            raise ValueError("Naval factories cannot be negative")
    
    def get_available_civilian_factories(self) -> float:
        """
        Get civilian factories available for production.
        
        Returns:
            Available factories after consumer goods and construction
        """
        used = (self.consumer_goods_factories + 
                self.civilian_factory_construction + 
                self.military_factory_construction)
        return max(0.0, self.civilian_factories - used)
    
    def get_available_military_factories(self) -> float:
        """
        Get military factories available for equipment production.
        
        Returns:
            Available military factories
        """
        assigned = sum(pl.assigned_factories for pl in self.production_lines 
                      if pl.equipment.category.value != "naval")
        return max(0.0, self.military_factories - assigned)
    
    def get_available_naval_factories(self) -> float:
        """
        Get naval factories available for ship production.
        
        Returns:
            Available naval factories
        """
        assigned = sum(pl.assigned_factories for pl in self.production_lines 
                      if pl.equipment.category.value == "naval")
        return max(0.0, self.naval_factories - assigned)
    
    def add_production_line(
        self, 
        equipment: Equipment, 
        factories: float,
        start_date: Optional[GameDate] = None,
        priority: int = 5
    ) -> ProductionLine:
        """
        Add a new production line.
        
        Args:
            equipment: Equipment to produce
            factories: Number of factories to assign
            start_date: When production starts
            priority: Production priority
            
        Returns:
            Created production line
        """
        line = ProductionLine(
            equipment=equipment,
            assigned_factories=factories,
            start_date=start_date,
            priority=priority
        )
        self.production_lines.append(line)
        return line
    
    def remove_production_line(self, equipment_name: str) -> bool:
        """
        Remove a production line by equipment name.
        
        Args:
            equipment_name: Name of equipment
            
        Returns:
            True if line was found and removed
        """
        initial_count = len(self.production_lines)
        self.production_lines = [
            pl for pl in self.production_lines 
            if pl.equipment.name != equipment_name
        ]
        return len(self.production_lines) < initial_count
    
    def get_production_line(self, equipment_name: str) -> Optional[ProductionLine]:
        """
        Get production line by equipment name.
        
        Args:
            equipment_name: Name of equipment
            
        Returns:
            Production line or None if not found
        """
        for line in self.production_lines:
            if line.equipment.name == equipment_name:
                return line
        return None
    
    def calculate_total_daily_output(self, efficiency_modifiers: float = 0.0) -> Dict[str, float]:
        """
        Calculate total daily output across all production lines.
        
        Args:
            efficiency_modifiers: Additional efficiency bonuses
            
        Returns:
            Dictionary of equipment_name -> daily_output
        """
        output = {}
        for line in self.production_lines:
            daily = line.get_daily_output(efficiency_modifiers)
            output[line.equipment.name] = output.get(line.equipment.name, 0.0) + daily
        return output
    
    def calculate_total_resource_consumption(self, efficiency_modifiers: float = 0.0) -> Dict[str, float]:
        """
        Calculate total daily resource consumption.
        
        Args:
            efficiency_modifiers: Additional efficiency bonuses
            
        Returns:
            Dictionary of resource_name -> daily_consumption
        """
        consumption = {}
        for line in self.production_lines:
            line_consumption = line.get_daily_resource_consumption(efficiency_modifiers)
            for resource, amount in line_consumption.items():
                consumption[resource] = consumption.get(resource, 0.0) + amount
        return consumption
    
    def __str__(self) -> str:
        return (f"Production(civ={self.civilian_factories}, mil={self.military_factories}, "
                f"naval={self.naval_factories}, lines={len(self.production_lines)})")
    
    def __repr__(self) -> str:
        return (f"Production(civilian_factories={self.civilian_factories}, "
                f"military_factories={self.military_factories}, "
                f"naval_factories={self.naval_factories})")
