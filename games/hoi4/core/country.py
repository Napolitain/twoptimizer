"""
Country class for HOI4.

Extends Faction with national ideas, resources, and country-specific mechanics.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from games.hoi4.faction import Faction
from games.hoi4.state import State
from games.hoi4.models.idea import Idea, IdeaSlot, IdeaCategory
from games.hoi4.models.modifier import ModifierManager


@dataclass
class Country(Faction):
    """
    Represents a country in Hearts of Iron IV.
    
    Extends Faction with national ideas, resources, and country-specific mechanics.
    
    Attributes:
        tag: Three-letter country tag (e.g., "GER", "SOV", "USA")
        national_spirits: List of national spirit ideas
        idea_slots: Dictionary of idea slots by category
        resources: Dictionary of strategic resources (total across all states)
        political_power: Current political power
        stability: Stability level (0.0 to 1.0)
        war_support: War support level (0.0 to 1.0)
        modifier_manager: Manager for all active modifiers
    """
    tag: str = ""
    national_spirits: List[Idea] = field(default_factory=list)
    idea_slots: Dict[IdeaCategory, IdeaSlot] = field(default_factory=dict)
    resources: Dict[str, float] = field(default_factory=dict)
    political_power: float = 0.0
    stability: float = 0.5
    war_support: float = 0.5
    modifier_manager: ModifierManager = field(default_factory=ModifierManager)
    
    def __post_init__(self):
        """Initialize idea slots and validate attributes."""
        # Initialize standard idea slots if not already set
        if not self.idea_slots:
            self.idea_slots = {
                IdeaCategory.ECONOMY: IdeaSlot(IdeaCategory.ECONOMY),
                IdeaCategory.TRADE: IdeaSlot(IdeaCategory.TRADE),
                IdeaCategory.MANPOWER: IdeaSlot(IdeaCategory.MANPOWER),
            }
        
        # Validate levels
        if not 0.0 <= self.stability <= 1.0:
            raise ValueError("Stability must be between 0.0 and 1.0")
        if not 0.0 <= self.war_support <= 1.0:
            raise ValueError("War support must be between 0.0 and 1.0")
    
    def add_national_spirit(self, idea: Idea) -> None:
        """
        Add a national spirit to the country.
        
        Args:
            idea: The national spirit idea to add
        """
        if idea.category != IdeaCategory.COUNTRY:
            raise ValueError(f"Only COUNTRY category ideas can be national spirits")
        
        # Remove existing spirit with same name if it exists
        self.national_spirits = [s for s in self.national_spirits if s.name != idea.name]
        self.national_spirits.append(idea)
        
        # Add modifiers from the idea
        for modifier_name, value in idea.modifier.items():
            self.modifier_manager.add_modifier(
                modifier_name, 
                value, 
                source=f"national_spirit_{idea.name}"
            )
    
    def remove_national_spirit(self, idea_name: str) -> bool:
        """
        Remove a national spirit by name.
        
        Args:
            idea_name: Name of the spirit to remove
            
        Returns:
            True if the spirit was found and removed
        """
        initial_count = len(self.national_spirits)
        self.national_spirits = [s for s in self.national_spirits if s.name != idea_name]
        
        # Remove associated modifiers
        # Note: In a full implementation, we'd track which modifiers came from which spirit
        
        return len(self.national_spirits) < initial_count
    
    def get_national_spirit(self, idea_name: str) -> Optional[Idea]:
        """
        Get a national spirit by name.
        
        Args:
            idea_name: Name of the spirit
            
        Returns:
            The national spirit idea, or None if not found
        """
        for spirit in self.national_spirits:
            if spirit.name == idea_name:
                return spirit
        return None
    
    def set_law(self, idea: Idea) -> bool:
        """
        Set a law (economy, trade, or manpower).
        
        Args:
            idea: The law idea to set
            
        Returns:
            True if the law was set successfully
            
        Raises:
            ValueError: If the idea is not a law or slot doesn't exist
        """
        if not idea.is_law():
            raise ValueError(f"Idea {idea.name} is not a law")
        
        if idea.category not in self.idea_slots:
            raise ValueError(f"No slot for {idea.category}")
        
        # Check political power cost
        if self.political_power < idea.cost:
            return False
        
        slot = self.idea_slots[idea.category]
        
        # Remove old idea's modifiers if there was one
        if slot.current_idea:
            for modifier_name in slot.current_idea.modifier.keys():
                self.modifier_manager.remove_modifier(
                    modifier_name,
                    source=f"{idea.category.value}_{slot.current_idea.name}"
                )
        
        # Set the new idea
        slot.set_idea(idea)
        
        # Deduct political power
        self.political_power -= idea.cost
        
        # Add new idea's modifiers
        for modifier_name, value in idea.modifier.items():
            self.modifier_manager.add_modifier(
                modifier_name,
                value,
                source=f"{idea.category.value}_{idea.name}"
            )
        
        return True
    
    def get_current_law(self, category: IdeaCategory) -> Optional[Idea]:
        """
        Get the currently active law of a specific category.
        
        Args:
            category: The law category
            
        Returns:
            The current law idea, or None if no law is set
        """
        if category not in self.idea_slots:
            return None
        return self.idea_slots[category].current_idea
    
    def total_resources(self) -> Dict[str, float]:
        """
        Calculate total resources across all states.
        
        Returns:
            Dictionary of resource_name -> total_amount
        """
        total = {}
        for state in self.states:
            for resource_name, amount in state.resources.items():
                if resource_name in total:
                    total[resource_name] += amount
                else:
                    total[resource_name] = amount
        return total
    
    def get_resource(self, resource_name: str) -> float:
        """
        Get the total amount of a specific resource.
        
        Args:
            resource_name: Name of the resource
            
        Returns:
            Total amount of the resource across all states
        """
        total = self.total_resources()
        return total.get(resource_name, 0.0)
    
    def total_manpower(self) -> int:
        """
        Calculate total manpower across all states.
        
        Returns:
            Total manpower
        """
        return sum(state.manpower for state in self.states)
    
    def total_victory_points(self) -> int:
        """
        Calculate total victory points across all states.
        
        Returns:
            Total victory points
        """
        return sum(state.victory_points for state in self.states)
    
    def get_all_modifiers(self) -> Dict[str, float]:
        """
        Get all active modifiers from all sources.
        
        Returns:
            Dictionary of modifier_name -> total_value
        """
        return self.modifier_manager.get_all_modifiers()
    
    def get_modifier(self, modifier_name: str) -> float:
        """
        Get the total value of a specific modifier.
        
        Args:
            modifier_name: Name of the modifier
            
        Returns:
            Total modifier value
        """
        return self.modifier_manager.get_modifier(modifier_name)
    
    def __repr__(self) -> str:
        return (f"Country(tag='{self.tag}', name='{self.name}', "
                f"states={len(self.states)}, "
                f"spirits={len(self.national_spirits)})")
