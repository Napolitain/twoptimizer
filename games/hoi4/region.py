"""
Hearts of Iron IV Region module.

A region in HoI4 represents a geographical area with various attributes
such as civilian factories, military factories, infrastructure, and defenses.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Region:
    """
    Represents a region in Hearts of Iron IV.
    
    Attributes:
        name: The name of the region
        civilian_factories: Number of civilian factories in the region
        military_factories: Number of military factories in the region
        infrastructure: Infrastructure level (affects production and supply)
        bunkers: Number of bunkers/fortifications for defense
        naval_bases: Number of naval bases (optional)
        air_bases: Number of air bases (optional)
    """
    name: str
    civilian_factories: int = 0
    military_factories: int = 0
    infrastructure: int = 0
    bunkers: int = 0
    naval_bases: Optional[int] = None
    air_bases: Optional[int] = None
    
    def __post_init__(self):
        """Validate region attributes."""
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
    
    def total_factories(self) -> int:
        """Calculate the total number of factories in the region."""
        return self.civilian_factories + self.military_factories
    
    def __repr__(self) -> str:
        return (f"Region(name='{self.name}', "
                f"civilian_factories={self.civilian_factories}, "
                f"military_factories={self.military_factories}, "
                f"infrastructure={self.infrastructure}, "
                f"bunkers={self.bunkers})")
