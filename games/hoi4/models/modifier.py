"""
Modifier system for HOI4.

Represents game modifiers that affect various aspects of the game.
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from enum import Enum


class ModifierScope(Enum):
    """Scope where a modifier applies."""
    COUNTRY = "country"
    STATE = "state" 
    PROVINCE = "province"
    UNIT = "unit"


@dataclass
class Modifier:
    """
    Represents a game modifier that affects various game mechanics.
    
    Attributes:
        name: Name of the modifier
        scope: Where the modifier applies (country, state, etc.)
        effects: Dictionary of effect_name -> value
        enable_for_controllers: List of countries that can use this modifier
        duration: How long the modifier lasts (None for permanent)
    """
    name: str
    scope: ModifierScope
    effects: Dict[str, float]
    enable_for_controllers: Optional[List[str]] = None
    duration: Optional[int] = None
    
    def applies_to_country(self, country_tag: str) -> bool:
        """
        Check if this modifier applies to a specific country.
        
        Args:
            country_tag: Country tag (e.g., "GER", "SOV", "USA")
            
        Returns:
            True if modifier applies to this country
        """
        if self.enable_for_controllers is None:
            return True
        return country_tag in self.enable_for_controllers
    
    def get_effect(self, effect_name: str) -> float:
        """
        Get the value of a specific effect.
        
        Args:
            effect_name: Name of the effect
            
        Returns:
            Effect value, or 0.0 if not found
        """
        return self.effects.get(effect_name, 0.0)
    
    def has_effect(self, effect_name: str) -> bool:
        """
        Check if this modifier has a specific effect.
        
        Args:
            effect_name: Name of the effect to check
            
        Returns:
            True if the effect exists
        """
        return effect_name in self.effects
    
    def get_all_effects(self) -> Dict[str, float]:
        """
        Get all effects of this modifier.
        
        Returns:
            Copy of the effects dictionary
        """
        return self.effects.copy()
    
    def combine_with(self, other: 'Modifier') -> 'Modifier':
        """
        Combine this modifier with another modifier.
        
        Args:
            other: Another modifier to combine with
            
        Returns:
            New modifier with combined effects
        """
        if self.scope != other.scope:
            raise ValueError(f"Cannot combine modifiers with different scopes: {self.scope} vs {other.scope}")
        
        combined_effects = self.effects.copy()
        for effect_name, value in other.effects.items():
            if effect_name in combined_effects:
                combined_effects[effect_name] += value
            else:
                combined_effects[effect_name] = value
        
        # Combine enable_for_controllers
        combined_controllers = None
        if self.enable_for_controllers and other.enable_for_controllers:
            combined_controllers = list(set(self.enable_for_controllers + other.enable_for_controllers))
        elif self.enable_for_controllers:
            combined_controllers = self.enable_for_controllers
        elif other.enable_for_controllers:
            combined_controllers = other.enable_for_controllers
        
        return Modifier(
            name=f"{self.name}+{other.name}",
            scope=self.scope,
            effects=combined_effects,
            enable_for_controllers=combined_controllers,
            duration=min(self.duration or float('inf'), other.duration or float('inf'))
        )
    
    def __str__(self) -> str:
        return f"Modifier({self.name}, {self.scope.value}, {len(self.effects)} effects)"
    
    def __repr__(self) -> str:
        return (f"Modifier(name='{self.name}', scope={self.scope}, "
                f"effects={self.effects}, enable_for_controllers={self.enable_for_controllers})")


class ModifierManager:
    """
    Manages collections of modifiers and their effects.
    """
    
    def __init__(self):
        self.modifiers: List[Modifier] = []
        self._simple_modifiers: Dict[str, float] = {}  # For simple key-value modifiers
        self._modifier_sources: Dict[str, str] = {}  # Track source of each modifier
    
    def add_modifier(self, modifier_name: str, value: float = 0.0, source: str = "", modifier_obj: Optional[Modifier] = None) -> None:
        """
        Add a modifier to the collection.
        
        Can be called with either:
        - modifier_name and value for simple modifiers
        - modifier_obj for full Modifier objects (for backward compatibility)
        
        Args:
            modifier_name: Name of the modifier (or Modifier object for backward compat)
            value: Value of the modifier
            source: Source identifier for tracking
            modifier_obj: Full Modifier object (optional, for complex modifiers)
        """
        # Backward compatibility: if first arg is a Modifier object
        if isinstance(modifier_name, Modifier):
            self.modifiers.append(modifier_name)
            return
        
        # Simple modifier case
        if modifier_name in self._simple_modifiers:
            self._simple_modifiers[modifier_name] += value
        else:
            self._simple_modifiers[modifier_name] = value
        
        if source:
            self._modifier_sources[f"{source}_{modifier_name}"] = source
    
    def remove_modifier(self, modifier_name: str, source: str = "") -> bool:
        """
        Remove a modifier by name.
        
        Args:
            modifier_name: Name of modifier to remove
            source: Source identifier for tracking
            
        Returns:
            True if modifier was found and removed
        """
        # Try to remove from simple modifiers
        if modifier_name in self._simple_modifiers:
            del self._simple_modifiers[modifier_name]
            if source:
                key = f"{source}_{modifier_name}"
                if key in self._modifier_sources:
                    del self._modifier_sources[key]
            return True
        
        # Try to remove from complex modifiers
        for i, modifier in enumerate(self.modifiers):
            if modifier.name == modifier_name:
                del self.modifiers[i]
                return True
        return False
    
    def get_modifier(self, modifier_name: str) -> float:
        """
        Get the total value of a simple modifier.
        
        Args:
            modifier_name: Name of the modifier
            
        Returns:
            Total value of the modifier
        """
        return self._simple_modifiers.get(modifier_name, 0.0)
    
    def get_all_modifiers(self) -> Dict[str, float]:
        """
        Get all simple modifiers.
        
        Returns:
            Dictionary of modifier_name -> value
        """
        return self._simple_modifiers.copy()
    
    def get_modifiers_by_scope(self, scope: ModifierScope) -> List[Modifier]:
        """
        Get all modifiers that apply to a specific scope.
        
        Args:
            scope: Scope to filter by
            
        Returns:
            List of matching modifiers
        """
        return [mod for mod in self.modifiers if mod.scope == scope]
    
    def calculate_total_effect(self, effect_name: str, scope: ModifierScope, country_tag: Optional[str] = None) -> float:
        """
        Calculate the total effect of all applicable modifiers.
        
        Args:
            effect_name: Name of the effect to calculate
            scope: Scope to consider
            country_tag: Country tag for controller checks
            
        Returns:
            Total effect value
        """
        total = 0.0
        
        for modifier in self.get_modifiers_by_scope(scope):
            if country_tag and not modifier.applies_to_country(country_tag):
                continue
            total += modifier.get_effect(effect_name)
        
        return total
    
    def get_all_effects(self, scope: ModifierScope, country_tag: Optional[str] = None) -> Dict[str, float]:
        """
        Get all effects for a given scope, summed across all applicable modifiers.
        
        Args:
            scope: Scope to consider
            country_tag: Country tag for controller checks
            
        Returns:
            Dictionary of effect_name -> total_value
        """
        all_effects = {}
        
        for modifier in self.get_modifiers_by_scope(scope):
            if country_tag and not modifier.applies_to_country(country_tag):
                continue
                
            for effect_name, value in modifier.effects.items():
                if effect_name in all_effects:
                    all_effects[effect_name] += value
                else:
                    all_effects[effect_name] = value
        
        return all_effects
    
    def clear(self) -> None:
        """Clear all modifiers."""
        self.modifiers.clear()
    
    def __len__(self) -> int:
        return len(self.modifiers)
    
    def __iter__(self):
        return iter(self.modifiers)
