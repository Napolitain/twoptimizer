"""
Idea model for HOI4.

Represents national ideas (national spirits, laws, advisors, etc.) and their effects.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class IdeaCategory(Enum):
    """Categories of ideas in HOI4."""
    COUNTRY = "country"  # National spirits
    ECONOMY = "economy"  # Economic laws
    TRADE = "trade_laws"  # Trade laws
    MANPOWER = "mobilization_laws"  # Manpower/conscription laws
    POLITICAL_ADVISOR = "political_advisor"
    ARMY_CHIEF = "army_chief"
    NAVY_CHIEF = "navy_chief"
    AIR_CHIEF = "air_chief"
    HIGH_COMMAND = "high_command"
    THEORIST = "theorist"
    TANK_MANUFACTURER = "tank_manufacturer"
    NAVAL_MANUFACTURER = "naval_manufacturer"
    AIRCRAFT_MANUFACTURER = "aircraft_manufacturer"
    MATERIEL_MANUFACTURER = "materiel_manufacturer"
    INDUSTRIAL_CONCERN = "industrial_concern"


@dataclass
class Idea:
    """
    Represents a national idea in Hearts of Iron IV.
    
    Ideas include national spirits, laws, advisors, and other modifiers
    that affect a country's capabilities.
    
    Attributes:
        name: Internal name of the idea
        category: Category this idea belongs to
        cost: Political power cost to adopt (for laws and advisors)
        removal_cost: Political power cost to remove
        level: Level/tier of the idea (for some categories)
        allowed: Conditions for the idea to be available
        available: Conditions for the idea to be selectable
        modifier: Dictionary of modifier effects
        rule: Special game rules this idea enables
        allowed_civil_war: Whether this idea is kept during civil war
        cancel_if_invalid: Whether to auto-remove if conditions not met
        picture: Icon/picture reference for UI
    """
    name: str
    category: IdeaCategory
    cost: int = 0
    removal_cost: int = -1
    level: int = 0
    allowed: Dict[str, Any] = field(default_factory=dict)
    available: Dict[str, Any] = field(default_factory=dict)
    modifier: Dict[str, float] = field(default_factory=dict)
    rule: Dict[str, Any] = field(default_factory=dict)
    allowed_civil_war: Optional[bool] = None
    cancel_if_invalid: bool = True
    picture: Optional[str] = None
    
    def get_modifier_value(self, modifier_name: str) -> float:
        """
        Get the value of a specific modifier.
        
        Args:
            modifier_name: Name of the modifier
            
        Returns:
            Modifier value, or 0.0 if not present
        """
        return self.modifier.get(modifier_name, 0.0)
    
    def has_modifier(self, modifier_name: str) -> bool:
        """
        Check if this idea has a specific modifier.
        
        Args:
            modifier_name: Name of the modifier to check
            
        Returns:
            True if the modifier exists
        """
        return modifier_name in self.modifier
    
    def get_all_modifiers(self) -> Dict[str, float]:
        """
        Get all modifiers of this idea.
        
        Returns:
            Copy of the modifiers dictionary
        """
        return self.modifier.copy()
    
    def is_law(self) -> bool:
        """
        Check if this idea is a law (economy, trade, or manpower).
        
        Returns:
            True if this is a law
        """
        return self.category in [
            IdeaCategory.ECONOMY,
            IdeaCategory.TRADE,
            IdeaCategory.MANPOWER
        ]
    
    def is_advisor(self) -> bool:
        """
        Check if this idea is an advisor.
        
        Returns:
            True if this is an advisor
        """
        return self.category in [
            IdeaCategory.POLITICAL_ADVISOR,
            IdeaCategory.ARMY_CHIEF,
            IdeaCategory.NAVY_CHIEF,
            IdeaCategory.AIR_CHIEF,
            IdeaCategory.HIGH_COMMAND,
            IdeaCategory.THEORIST
        ]
    
    def is_company(self) -> bool:
        """
        Check if this idea is a company (manufacturer/concern).
        
        Returns:
            True if this is a company
        """
        return self.category in [
            IdeaCategory.TANK_MANUFACTURER,
            IdeaCategory.NAVAL_MANUFACTURER,
            IdeaCategory.AIRCRAFT_MANUFACTURER,
            IdeaCategory.MATERIEL_MANUFACTURER,
            IdeaCategory.INDUSTRIAL_CONCERN
        ]
    
    def __str__(self) -> str:
        return f"Idea({self.name}, {self.category.value})"
    
    def __repr__(self) -> str:
        return (f"Idea(name='{self.name}', category={self.category}, "
                f"modifiers={len(self.modifier)})")


@dataclass
class IdeaSlot:
    """
    Represents a slot that can hold ideas of a specific category.
    
    Attributes:
        category: Category of ideas this slot accepts
        current_idea: Currently active idea in this slot
    """
    category: IdeaCategory
    current_idea: Optional[Idea] = None
    
    def can_accept(self, idea: Idea) -> bool:
        """
        Check if this slot can accept a given idea.
        
        Args:
            idea: The idea to check
            
        Returns:
            True if the idea's category matches this slot
        """
        return idea.category == self.category
    
    def set_idea(self, idea: Idea) -> bool:
        """
        Set the current idea in this slot.
        
        Args:
            idea: The idea to set
            
        Returns:
            True if the idea was set successfully
            
        Raises:
            ValueError: If the idea's category doesn't match the slot
        """
        if not self.can_accept(idea):
            raise ValueError(
                f"Cannot set {idea.category} idea in {self.category} slot"
            )
        self.current_idea = idea
        return True
    
    def clear(self) -> None:
        """Clear the current idea from this slot."""
        self.current_idea = None
    
    def get_modifiers(self) -> Dict[str, float]:
        """
        Get all modifiers from the current idea.
        
        Returns:
            Dictionary of modifiers, empty if no idea is set
        """
        if self.current_idea:
            return self.current_idea.get_all_modifiers()
        return {}
