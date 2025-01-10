import abc
import enum
from collections import defaultdict
from dataclasses import dataclass
from typing import List

from pulp import LpVariable, LpInteger, LpProblem, LpMaximize, lpSum


class AttilaFactions(enum.Enum):
    """
    Enum containing a list of factions in Attila.
    """
    ATTILA_NONE = 0
    ATTILA_ROMAN_EAST = 1
    ATTILA_ROMAN_WEST = 2
    ATTILA_FRANKS = 3
    ATTILA_VANDALS = 4
    ATTILA_VISIGOTHS = 5
    ATTILA_ALAMANS = 6
    ATTILA_SAXONS = 7
    ATTILA_GEPIDS = 8
    ATTILA_LANGOBARDS = 9
    ATTILA_BURGUNDIANS = 10
    ATTILA_OSTROGOTHS = 11
    ATTILA_SUEBI = 12
    ATTILA_HUNS = 13
    ATTILA_ALANS = 14


class Games:
    problem = LpProblem("GDP Maximization", LpMaximize)
    buildings = {}
    current_game = "att"
    faction = AttilaFactions.ATTILA_NONE

class Effect(abc.ABC):
    @abc.abstractmethod
    def gdp(self) -> float:
        pass

    @abc.abstractmethod
    def public_order(self) -> float:
        pass

    @abc.abstractmethod
    def sanitation(self) -> float:
        pass

    @abc.abstractmethod
    def food(self) -> float:
        pass


class Building(Effect):
    """
    A building contains effects that can be applied to a province, region, or building.
    We need to create a Building class that contains a list of effects.
    """
    def __init__(self, name: str):
        self.lp_variable = None
        self.name = name
        self.effects_to_faction = {}
        self.effects_to_province = {}
        self.effects_to_region = {}
        self.effects_to_building = {}

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return self.name == other.name

    def __repr__(self):
        return self.name

    def add_effect(self, effect: str, scope: str, amount: float):
        if scope.startswith('faction'):
            self.effects_to_faction[effect] = amount
        elif scope.startswith('province'):
            self.effects_to_province[effect] = amount
        elif scope.startswith('region'):
            self.effects_to_region[effect] = amount
        elif scope.startswith('building'):
            self.effects_to_building[effect] = amount

    def add_lp_variable(self, low: int = 0, high: int = 1, type = LpInteger):
        self.lp_variable = LpVariable(self.name, low, high, type)

    def gdp(self):
        """
        For every effects dictionaries, if it contains gdp, and it doesn't contain mod, we sum the values.
        :return: sum of gdp values
        """
        etf = sum([amount for effect, amount in self.effects_to_faction.items() if "gdp" in effect and 'mod' not in effect])
        etp = sum([amount for effect, amount in self.effects_to_province.items() if "gdp" in effect and 'mod' not in effect])
        etr = sum([amount for effect, amount in self.effects_to_region.items() if "gdp" in effect and 'mod' not in effect])
        etb = sum([amount for effect, amount in self.effects_to_building.items() if "gdp" in effect and 'mod' not in effect])
        return etf + etp + etr + etb

    def public_order(self):
        """
        For every effects dictionaries, if it contains public_order, we sum the values.
        :return: sum of public_order values
        """
        etf = sum([amount for effect, amount in self.effects_to_faction.items() if "public_order" in effect])
        etp = sum([amount for effect, amount in self.effects_to_province.items() if "public_order" in effect])
        etr = sum([amount for effect, amount in self.effects_to_region.items() if "public_order" in effect])
        etb = sum([amount for effect, amount in self.effects_to_building.items() if "public_order" in effect])
        return etf + etp + etr + etb

    def sanitation(self):
        """
        For every effects dictionaries, if it contains sanitation, we sum the values.
        If it contains squalor, we subtract the values.
        :return: sum of sanitation values minus squalor values
        """
        etf = sum([amount for effect, amount in self.effects_to_faction.items() if 'sanitation' in effect])
        etp = sum([amount for effect, amount in self.effects_to_province.items() if 'sanitation' in effect])
        etr = sum([amount for effect, amount in self.effects_to_region.items() if 'sanitation' in effect])
        etb = sum([amount for effect, amount in self.effects_to_building.items() if 'sanitation' in effect])
        sanitation = etf + etp + etr + etb
        etf = sum([amount for effect, amount in self.effects_to_faction.items() if "squalor" in effect])
        etp = sum([amount for effect, amount in self.effects_to_province.items() if "squalor" in effect])
        etr = sum([amount for effect, amount in self.effects_to_region.items() if "squalor" in effect])
        etb = sum([amount for effect, amount in self.effects_to_building.items() if "squalor" in effect])
        squalor = etf + etp + etr + etb
        return sanitation - squalor

    def food(self):
        """
        For every effects dictionaries, if it contains food and production, we sum the values. If it contains food and consumption, we subtract the values.
        :return: sum of food production values minus food consumption values.
        """
        etf = sum([amount for effect, amount in self.effects_to_faction.items() if "food" in effect and 'production' in effect])
        etp = sum([amount for effect, amount in self.effects_to_province.items() if "food" in effect and 'production' in effect])
        etr = sum([amount for effect, amount in self.effects_to_region.items() if "food" in effect and 'production' in effect])
        etb = sum([amount for effect, amount in self.effects_to_building.items() if "food" in effect and 'production' in effect])
        food_production = etf + etp + etr + etb
        etf = sum([amount for effect, amount in self.effects_to_faction.items() if "food" in effect and 'consumption' in effect])
        etp = sum([amount for effect, amount in self.effects_to_province.items() if "food" in effect and 'consumption' in effect])
        etr = sum([amount for effect, amount in self.effects_to_region.items() if "food" in effect and 'consumption' in effect])
        etb = sum([amount for effect, amount in self.effects_to_building.items() if "food" in effect and 'consumption' in effect])
        food_consumption = etf + etp + etr + etb
        return food_production - food_consumption


class RegionType(enum.Enum):
    ATTILA_REGION_MAJOR = 1
    ATTILA_REGION_MINOR = 2

class RegionHasPort(enum.Enum):
    ATTILA_REGION_NO_PORT = 1
    ATTILA_REGION_PORT = 2

class RegionHasRessource(enum.Enum):
    ATTILA_REGION_NO_RESSOURCE = 1
    ATTILA_REGION_FURS = 2
    ATTILA_REGION_IRON = 3
    ATTILA_REGION_WINE = 4
    ATTILA_REGION_WOOD = 5
    ATTILA_REGION_GOLD = 6
    ATTILA_REGION_MARBLE = 7
    ATTILA_REGION_GEMS = 8
    ATTILA_REGION_SILK = 9
    ATTILA_REGION_SPICE = 10
    ATTILA_REGION_SALT = 11
    ATTILA_REGION_LEAD = 12
    ATTILA_REGION_OLIVES = 13
    ATTILA_REGION_CHURCH = 14

@dataclass
class RegionAttila:
    region_type: RegionType
    has_port: RegionHasPort
    has_ressource: RegionHasRessource


def building_is_major(building_name: str) -> bool:
    """
    Check if a building is major (city or town).
    :param building_name:
    :return:
    """
    if "major" in building_name:
        return True
    return False

def building_is_minor(building_name: str) -> bool:
    """
    Check if a building is minor (village).
    :param building_name:
    :return:
    """
    if "minor" in building_name or "agriculture" in building_name:
        return True
    return False

def building_is_not_of_faction(building_name: str) -> bool:
    """
    Check if a building is of the faction currently assigned in Games.
    :param building_name:
    :return:
    """
    if Games.faction == AttilaFactions.ATTILA_ROMAN_EAST and ("roman" in building_name and "west" not in building_name) or ("orthodox" in building_name) or ("all" in building_name):
        return False
    return True


class Region(Effect):
    """
    A region contains buildings.
    """
    def __init__(self, n_buildings: int, name: str):
        self.n_buildings = n_buildings  # Number of buildings that can be built in the region. NOT equal to len(buildings).
        self.buildings: List[Building] = []  # List of buildings that are potentially fit for the region.
        self.effects = defaultdict(list)
        self.name = name

    def add_buildings(self, region: RegionAttila):
        """
        Add buildings to the region.
        It should filter buildings based on the region type, port, and resource.
        Adapt constraints accordingly.
        For example, number of free buildings decrease if the region has a port.
        Building must be named region_building.
        :param region:
        :return:
        """
        # Add buildings Lp variables to the region.
        for building in Games.buildings[Games.current_game].values():
            deep_copy = Building(f"{self.name}_{building.name}")
            if building_is_not_of_faction(building.name):
                continue
            if region.region_type == RegionType.ATTILA_REGION_MAJOR and building_is_minor(building.name):
                continue
            if region.region_type == RegionType.ATTILA_REGION_MINOR and building_is_major(building.name):
                continue
            self.buildings.append(deep_copy)
        # Add constraints to the region.
        self.add_type_constraint(region)
        self.add_resource_constraint(region)
        self.add_port_constraint(region)

    def add_port_constraint(self, region: RegionAttila):
        """
        If the region has a port, then we can add a constraint that the number of buildings in the region with "port" is between 1 and 1.
        :param region:
        :return:
        """
        if region.has_port == RegionHasPort.ATTILA_REGION_PORT:
            Games.problem += lpSum(
                building.lp_variable
                for building in self.buildings
                if "port" in building.name and "spice" not in building.name
            ) == 1, "Port_Constraint"
        else:
            Games.problem += lpSum(
                building.lp_variable
                for building in self.buildings
                if "port" in building.name and "spice" not in building.name
            ) == 0, "No_Port_Constraint"

    def add_resource_constraint(self, region: RegionAttila):
        """
        If the region has a resource, then we can add a constraint that the number of buildings in the region with "resource" and "spice" is between 1 and 1. That's because
        spice resource is mandatory (is a port). Any other resource is optional.
        :param region:
        :return:
        """
        if region.has_ressource != RegionHasRessource.ATTILA_REGION_NO_RESSOURCE:
            Games.problem += lpSum(
                building.lp_variable
                for building in self.buildings
                if "resource" in building.name and "spice" in building.name
            ) == 1, "Spice_Resource_Constraint"
        else:
            Games.problem += lpSum(
                building.lp_variable
                for building in self.buildings
                if "resource" in building.name and "port" not in building.name or "spice" in building.name
            ) == 0, "No_Resource_Constraint"

    def add_type_constraint(self, region):
        """
        If the region is major, then we can add a constraint that all buildings with "minor" are between 0 and 0, as well as "agriculture".
        Conversely, disable civic, major buildings in minor regions.
        :param region:
        :return:
        """
        if region.region_type == RegionType.ATTILA_REGION_MAJOR:
            Games.problem += lpSum(
                building.lp_variable
                for building in self.buildings
                if "minor" in building.name or "agriculture" in building.name
            ) == 0, "No_Minor_Constraint"
        else:
            Games.problem += lpSum(
                building.lp_variable
                for building in self.buildings
                if "major" in building.name or "civic" in building.name
            ) == 0, "No_Major_Constraint"

    def gdp(self):
        """
        For a region, we can just sum the gdp of all buildings, for now.
        :return: sum of gdp of all buildings
        """
        return sum([building.gdp() for building in self.buildings])

    def food(self):
        """
        For a region, we can just sum the food of all buildings, for now.
        :return: sum of food of all buildings
        """
        return sum([building.food() for building in self.buildings])

    def sanitation(self):
        """
        For a region, we need to make sure sanitation >= squalor in each building.
        :return: sum of sanitation of all buildings minus squalor of all buildings
        """
        return sum([building.sanitation() for building in self.buildings])

    def public_order(self):
        """
        For a region, we can just sum the public order of all buildings, for now.
        :return: sum of public order of all buildings
        """
        return sum([building.public_order() for building in self.buildings])


class Province(Effect):
    """
    We need to create a Province class that contains a list of regions.
    """
    def __init__(self, n_regions: int, name: str):
        self.regions = []
        self.n_regions = n_regions
        self.name = name

    def add_region(self, region: Region):
        self.regions.append(region)

    def gdp(self):
        """
        We want to maximize the gdp of the province.
        :return: sum of gdp of all regions
        """
        return sum([region.gdp() for region in self.regions])

    def public_order(self):
        """
        We want to satisfy the public order of the province >== x.
        With tax levels, we need to experiment different x values.
        :return: sum of public order of all regions
        """
        return sum([region.public_order() for region in self.regions])

    def food(self):
        """
        We need to satisfy the food of the province >== 0.
        :return:
        """
        return sum([region.food() for region in self.regions])

    def sanitation(self):
        """
        We need to make sure sanitation >= squalor in each region, independently.
        This method is not needed for now.
        :return:
        """
        return
