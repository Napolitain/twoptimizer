"""
Focus model for HOI4 national focus trees.

Represents national focuses and focus trees.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class FocusFilterCategory(Enum):
    """Categories for focus filtering/searching."""
    POLITICAL = "FOCUS_FILTER_POLITICAL"
    RESEARCH = "FOCUS_FILTER_RESEARCH"
    INDUSTRY = "FOCUS_FILTER_INDUSTRY"
    STABILITY = "FOCUS_FILTER_STABILITY"
    WAR_SUPPORT = "FOCUS_FILTER_WAR_SUPPORT"
    MANPOWER = "FOCUS_FILTER_MANPOWER"
    ANNEXATION = "FOCUS_FILTER_ANNEXATION"
    MILITARY = "FOCUS_FILTER_MILITARY"


@dataclass
class Focus:
    """
    Represents a national focus in Hearts of Iron IV.
    
    A focus is a strategic objective that a country can complete,
    providing various rewards and unlocking other focuses.
    
    Attributes:
        id: Unique identifier for the focus
        icon: Icon/graphic reference
        x: X position in focus tree UI
        y: Y position in focus tree UI
        cost: Time cost in days (usually 70 days = 10 weeks)
        prerequisites: List of focus IDs that must be completed first
        mutually_exclusive: List of focus IDs that can't be taken with this one
        relative_position_id: Focus ID that this focus's position is relative to
        available: Conditions that must be met to select this focus
        bypass: Conditions that allow bypassing this focus
        cancel_if_invalid: Whether to cancel if conditions become invalid
        completion_reward: Effects applied when focus completes
        ai_will_do: AI weight/priority for selecting this focus
        search_filters: Categories for UI filtering
        available_if_capitulated: Whether available after capitulation
        continue_if_invalid: Whether to continue if conditions become invalid
        allow_branch: Conditions for this branch to be available
    """
    id: str
    icon: str = ""
    x: int = 0
    y: int = 0
    cost: int = 70  # Default 10 weeks
    prerequisites: List[str] = field(default_factory=list)
    mutually_exclusive: List[str] = field(default_factory=list)
    relative_position_id: Optional[str] = None
    available: Dict[str, Any] = field(default_factory=dict)
    bypass: Dict[str, Any] = field(default_factory=dict)
    cancel_if_invalid: bool = True
    completion_reward: Dict[str, Any] = field(default_factory=dict)
    ai_will_do: Dict[str, Any] = field(default_factory=dict)
    search_filters: List[FocusFilterCategory] = field(default_factory=list)
    available_if_capitulated: bool = False
    continue_if_invalid: bool = False
    allow_branch: Dict[str, Any] = field(default_factory=dict)
    
    def can_complete(self, completed_focuses: List[str]) -> bool:
        """
        Check if this focus can be completed given already completed focuses.
        
        Args:
            completed_focuses: List of focus IDs already completed
            
        Returns:
            True if all prerequisites are met and no mutex conflicts
        """
        # Check prerequisites
        for prereq in self.prerequisites:
            if prereq not in completed_focuses:
                return False
        
        # Check mutually exclusive
        for mutex in self.mutually_exclusive:
            if mutex in completed_focuses:
                return False
        
        return True
    
    def get_time_cost_days(self) -> int:
        """
        Get the time cost in days.
        
        Returns:
            Time cost in days
        """
        return self.cost * 7  # Each cost point is 1 week (7 days)
    
    def has_prerequisites(self) -> bool:
        """Check if this focus has any prerequisites."""
        return len(self.prerequisites) > 0
    
    def is_starting_focus(self) -> bool:
        """Check if this is a starting focus (no prerequisites)."""
        return not self.has_prerequisites()
    
    def __str__(self) -> str:
        return f"Focus({self.id})"
    
    def __repr__(self) -> str:
        return (f"Focus(id='{self.id}', cost={self.cost}, "
                f"prereqs={len(self.prerequisites)}, "
                f"mutex={len(self.mutually_exclusive)})")


@dataclass
class FocusTree:
    """
    Represents a national focus tree for a country.
    
    A focus tree contains all the focuses available to a country
    and defines their relationships and progression paths.
    
    Attributes:
        id: Unique identifier for the focus tree
        country_tags: List of country tags this tree applies to
        focuses: Dictionary of focus_id -> Focus
        shared_focuses: List of focus IDs that are shared from other trees
        default: Whether this is the default tree for the country
        continuous_focus_position: Position for continuous focuses in UI
    """
    id: str
    country_tags: List[str] = field(default_factory=list)
    focuses: Dict[str, Focus] = field(default_factory=dict)
    shared_focuses: List[str] = field(default_factory=list)
    default: bool = False
    continuous_focus_position: Dict[str, int] = field(default_factory=dict)
    
    def add_focus(self, focus: Focus) -> None:
        """
        Add a focus to the tree.
        
        Args:
            focus: The focus to add
        """
        self.focuses[focus.id] = focus
    
    def get_focus(self, focus_id: str) -> Optional[Focus]:
        """
        Get a focus by ID.
        
        Args:
            focus_id: ID of the focus
            
        Returns:
            The focus if found, None otherwise
        """
        return self.focuses.get(focus_id)
    
    def get_starting_focuses(self) -> List[Focus]:
        """
        Get all focuses that have no prerequisites (starting focuses).
        
        Returns:
            List of starting focuses
        """
        return [f for f in self.focuses.values() if f.is_starting_focus()]
    
    def get_available_focuses(self, completed_focuses: List[str]) -> List[Focus]:
        """
        Get all focuses that can currently be selected.
        
        Args:
            completed_focuses: List of focus IDs already completed
            
        Returns:
            List of available focuses
        """
        available = []
        for focus in self.focuses.values():
            if focus.id not in completed_focuses and focus.can_complete(completed_focuses):
                available.append(focus)
        return available
    
    def get_focus_chain_length(self, focus_id: str) -> int:
        """
        Get the length of the prerequisite chain for a focus.
        
        Args:
            focus_id: ID of the focus
            
        Returns:
            Number of prerequisites in the longest chain
        """
        focus = self.get_focus(focus_id)
        if not focus or not focus.has_prerequisites():
            return 0
        
        max_depth = 0
        for prereq in focus.prerequisites:
            depth = self.get_focus_chain_length(prereq)
            max_depth = max(max_depth, depth)
        
        return max_depth + 1
    
    def get_total_cost_to_focus(self, focus_id: str) -> int:
        """
        Get the total time cost to reach a focus (including all prerequisites).
        
        Args:
            focus_id: ID of the focus
            
        Returns:
            Total time cost in days
        """
        focus = self.get_focus(focus_id)
        if not focus:
            return 0
        
        total_cost = focus.get_time_cost_days()
        
        # Add cost of prerequisites (use max if multiple paths)
        if focus.has_prerequisites():
            max_prereq_cost = 0
            for prereq in focus.prerequisites:
                prereq_cost = self.get_total_cost_to_focus(prereq)
                max_prereq_cost = max(max_prereq_cost, prereq_cost)
            total_cost += max_prereq_cost
        
        return total_cost
    
    def validate_tree(self) -> List[str]:
        """
        Validate the focus tree for common issues.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        for focus in self.focuses.values():
            # Check that prerequisites exist
            for prereq in focus.prerequisites:
                if prereq not in self.focuses:
                    errors.append(f"Focus {focus.id} has unknown prerequisite {prereq}")
            
            # Check that mutex focuses exist
            for mutex in focus.mutually_exclusive:
                if mutex not in self.focuses:
                    errors.append(f"Focus {focus.id} has unknown mutex {mutex}")
        
        return errors
    
    def __len__(self) -> int:
        return len(self.focuses)
    
    def __repr__(self) -> str:
        return (f"FocusTree(id='{self.id}', "
                f"focuses={len(self.focuses)}, "
                f"countries={len(self.country_tags)})")
