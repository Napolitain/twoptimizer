"""
Heart of Iron 4 example factions module.

Provides pre-configured factions for testing and demonstration purposes.
"""

from games.hoi4.faction import Faction
from games.hoi4.region import Region


def create_france_faction() -> Faction:
    """
    Create a France faction with historical starting conditions (simplified).
    
    This is a simplified representation of France at the start of HoI4,
    focusing on key industrial regions.
    
    Returns:
        A Faction object representing France
    """
    france = Faction(name="France")
    
    # Paris region - capital, high industry
    paris = Region(
        name="Paris",
        civilian_factories=8,
        military_factories=4,
        infrastructure=7,
        bunkers=0,
        air_bases=5
    )
    
    # Normandy - coastal region with naval access
    normandy = Region(
        name="Normandy",
        civilian_factories=3,
        military_factories=2,
        infrastructure=5,
        bunkers=0,
        naval_bases=3,
        air_bases=2
    )
    
    # Lorraine - industrial region near German border
    lorraine = Region(
        name="Lorraine",
        civilian_factories=4,
        military_factories=2,
        infrastructure=6,
        bunkers=2,
        air_bases=2
    )
    
    # Provence - southern coastal region
    provence = Region(
        name="Provence",
        civilian_factories=3,
        military_factories=1,
        infrastructure=5,
        bunkers=0,
        naval_bases=2,
        air_bases=2
    )
    
    # Brittany - western coastal region
    brittany = Region(
        name="Brittany",
        civilian_factories=2,
        military_factories=1,
        infrastructure=4,
        bunkers=0,
        naval_bases=2,
        air_bases=1
    )
    
    france.add_region(paris)
    france.add_region(normandy)
    france.add_region(lorraine)
    france.add_region(provence)
    france.add_region(brittany)
    
    return france


def create_germany_faction() -> Faction:
    """
    Create a Germany faction with historical starting conditions (simplified).
    
    Returns:
        A Faction object representing Germany
    """
    germany = Faction(name="Germany")
    
    # Berlin - capital
    berlin = Region(
        name="Berlin",
        civilian_factories=10,
        military_factories=7,
        infrastructure=8,
        bunkers=0,
        air_bases=5
    )
    
    # Ruhr - industrial heartland
    ruhr = Region(
        name="Ruhr",
        civilian_factories=8,
        military_factories=6,
        infrastructure=8,
        bunkers=0,
        air_bases=3
    )
    
    # Bavaria - southern region
    bavaria = Region(
        name="Bavaria",
        civilian_factories=5,
        military_factories=3,
        infrastructure=7,
        bunkers=0,
        air_bases=3
    )
    
    germany.add_region(berlin)
    germany.add_region(ruhr)
    germany.add_region(bavaria)
    
    return germany


def create_soviet_union_faction() -> Faction:
    """
    Create a Soviet Union faction with historical starting conditions (simplified).
    
    Returns:
        A Faction object representing the Soviet Union
    """
    soviet_union = Faction(name="Soviet Union")
    
    # Moscow - capital
    moscow = Region(
        name="Moscow",
        civilian_factories=12,
        military_factories=8,
        infrastructure=6,
        bunkers=0,
        air_bases=5
    )
    
    # Leningrad - northern industrial center
    leningrad = Region(
        name="Leningrad",
        civilian_factories=7,
        military_factories=5,
        infrastructure=6,
        bunkers=0,
        naval_bases=3,
        air_bases=3
    )
    
    # Stalingrad - southern industrial center
    stalingrad = Region(
        name="Stalingrad",
        civilian_factories=6,
        military_factories=4,
        infrastructure=5,
        bunkers=0,
        air_bases=2
    )
    
    # Urals - eastern industrial region
    urals = Region(
        name="Urals",
        civilian_factories=8,
        military_factories=6,
        infrastructure=4,
        bunkers=0,
        air_bases=2
    )
    
    soviet_union.add_region(moscow)
    soviet_union.add_region(leningrad)
    soviet_union.add_region(stalingrad)
    soviet_union.add_region(urals)
    
    return soviet_union
