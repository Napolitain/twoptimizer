"""
Hearts of Iron IV Faction module.

A faction in HoI4 represents a nation/country with multiple states.
"""

from dataclasses import dataclass, field
from typing import List
from games.hoi4.state import State


@dataclass
class Faction:
    """
    Represents a faction (nation/country) in Hearts of Iron IV.
    
    A faction consists of multiple states and aggregates their resources.
    
    Attributes:
        name: The name of the faction (e.g., "France", "Germany", "Soviet Union")
        states: List of states controlled by this faction
    """
    name: str
    states: List[State] = field(default_factory=list)

    def add_state(self, state: State) -> None:
        """
        Add a state to the faction.
        
        Args: state: The state to add
        """
        self.states.append(state)
    
    def total_civilian_factories(self) -> int:
        """Calculate total civilian factories across all states."""
        return sum(state.civilian_factories for state in self.states)
    
    def total_military_factories(self) -> int:
        """Calculate total military factories across all states."""
        return sum(state.military_factories for state in self.states)
    
    def total_factories(self) -> int:
        """Calculate total factories (civilian + military) across all states."""
        return self.total_civilian_factories() + self.total_military_factories()
    
    def average_infrastructure(self) -> float:
        """Calculate average infrastructure level across all states."""
        if not self.states:
            return 0.0
        return sum(state.infrastructure for state in self.states) / len(self.states)
    
    def total_bunkers(self) -> int:
        """Calculate total bunkers across all states."""
        return sum(state.bunkers for state in self.states)
    
    def get_state(self, name: str) -> State:
        """
        Get a state by name.
        
        Args:
            name: The name of the state to find
            
        Returns:
            The state with the given name
            
        Raises:
            ValueError: If no state with the given name exists
        """
        for state in self.states:
            if state.name == name:
                return state
        raise ValueError(f"State '{name}' not found in faction '{self.name}'")
    
    def __repr__(self) -> str:
        return (f"Faction(name='{self.name}', "
                f"states={len(self.states)}, "
                f"total_factories={self.total_factories()})")
