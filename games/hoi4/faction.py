"""
Hearts of Iron IV Faction module.

A faction in HoI4 represents a nation/country with multiple regions.
"""

from dataclasses import dataclass, field
from typing import List
from games.hoi4.region import Region


@dataclass
class Faction:
    """
    Represents a faction (nation/country) in Hearts of Iron IV.
    
    A faction consists of multiple regions and aggregates their resources.
    
    Attributes:
        name: The name of the faction (e.g., "France", "Germany", "Soviet Union")
        regions: List of regions controlled by this faction
    """
    name: str
    regions: List[Region] = field(default_factory=list)
    
    def add_region(self, region: Region) -> None:
        """
        Add a region to the faction.
        
        Args:
            region: The region to add
        """
        self.regions.append(region)
    
    def total_civilian_factories(self) -> int:
        """Calculate total civilian factories across all regions."""
        return sum(region.civilian_factories for region in self.regions)
    
    def total_military_factories(self) -> int:
        """Calculate total military factories across all regions."""
        return sum(region.military_factories for region in self.regions)
    
    def total_factories(self) -> int:
        """Calculate total factories (civilian + military) across all regions."""
        return self.total_civilian_factories() + self.total_military_factories()
    
    def average_infrastructure(self) -> float:
        """Calculate average infrastructure level across all regions."""
        if not self.regions:
            return 0.0
        return sum(region.infrastructure for region in self.regions) / len(self.regions)
    
    def total_bunkers(self) -> int:
        """Calculate total bunkers across all regions."""
        return sum(region.bunkers for region in self.regions)
    
    def get_region(self, name: str) -> Region:
        """
        Get a region by name.
        
        Args:
            name: The name of the region to find
            
        Returns:
            The region with the given name
            
        Raises:
            ValueError: If no region with the given name exists
        """
        for region in self.regions:
            if region.name == name:
                return region
        raise ValueError(f"Region '{name}' not found in faction '{self.name}'")
    
    def __repr__(self) -> str:
        return (f"Faction(name='{self.name}', "
                f"regions={len(self.regions)}, "
                f"total_factories={self.total_factories()})")
