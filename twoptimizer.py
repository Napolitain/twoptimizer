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


class Scope(enum.Enum):
    FACTION = 1
    PROVINCE = 2
    REGION = 3
    BUILDING = 4


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

    def __copy__(self):
        new_building = Building(self.name)
        new_building.lp_variable = self.lp_variable
        new_building.effects_to_faction = self.effects_to_faction.copy()
        new_building.effects_to_province = self.effects_to_province.copy()
        new_building.effects_to_region = self.effects_to_region.copy()
        new_building.effects_to_building = self.effects_to_building.copy()
        return new_building

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return self.name == other.name

    def __repr__(self):
        return [self.name, self.gdp(), self.public_order(), self.sanitation(), self.food()]

    def __str__(self):
        return f"{self.name}, GDP: {self.gdp()}, Public Order: {self.public_order()}, Sanitation: {self.sanitation()}, Food: {self.food()}"

    def add_effect(self, effect: str, scope: str, amount: float):
        if scope.startswith('faction'):
            self.effects_to_faction[effect] = amount
        elif scope.startswith('province'):
            self.effects_to_province[effect] = amount
        elif scope.startswith('region'):
            self.effects_to_region[effect] = amount
        elif scope.startswith('building'):
            self.effects_to_building[effect] = amount

    def gdp(self):
        """
        For every effects dictionaries, if it contains gdp, and it doesn't contain mod, we sum the values.
        :return: sum of gdp values
        """
        etf = sum(
            [amount for effect, amount in self.effects_to_faction.items() if "gdp" in effect and 'mod' not in effect])
        etp = sum(
            [amount for effect, amount in self.effects_to_province.items() if "gdp" in effect and 'mod' not in effect])
        etr = sum(
            [amount for effect, amount in self.effects_to_region.items() if "gdp" in effect and 'mod' not in effect])
        etb = sum(
            [amount for effect, amount in self.effects_to_building.items() if "gdp" in effect and 'mod' not in effect])
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
        etr = sum([amount for effect, amount in self.effects_to_region.items() if 'sanitation_buildings' in effect])
        etb = sum([amount for effect, amount in self.effects_to_building.items() if 'sanitation_buildings' in effect])
        sanitation = etr + etb
        etr = sum([amount for effect, amount in self.effects_to_region.items() if "squalor" in effect])
        etb = sum([amount for effect, amount in self.effects_to_building.items() if "squalor" in effect])
        squalor = etr + etb
        # Province scope will be handled in province class.
        return sanitation - squalor

    def sanitation_scope(self, scope: Scope) -> float:
        """
        For every effects dictionaries, if it contains sanitation, we sum the values.
        :param scope: Scope of the sanitation.
        :return: sum of sanitation values
        """
        if scope == Scope.FACTION:
            sanitation = sum(
                [amount for effect, amount in self.effects_to_faction.items() if 'sanitation_buildings' in effect])
            squalor = sum([amount for effect, amount in self.effects_to_faction.items() if "squalor" in effect])
            return sanitation - squalor
        elif scope == Scope.PROVINCE:
            sanitation = sum(
                [amount for effect, amount in self.effects_to_province.items() if 'sanitation_buildings' in effect])
            squalor = sum([amount for effect, amount in self.effects_to_province.items() if "squalor" in effect])
            return sanitation - squalor
        else:
            sanitation = sum(
                [amount for effect, amount in self.effects_to_region.items() if 'sanitation_buildings' in effect])
            squalor = sum([amount for effect, amount in self.effects_to_region.items() if "squalor" in effect])
            sanitation += sum(
                [amount for effect, amount in self.effects_to_building.items() if 'sanitation_buildings' in effect])
            squalor += sum([amount for effect, amount in self.effects_to_building.items() if "squalor" in effect])
            return sanitation - squalor

    def food(self):
        """
        For every effects dictionaries, if it contains food and production, we sum the values. If it contains food and consumption, we subtract the values.
        :return: sum of food production values minus food consumption values.
        """
        etf = sum([amount for effect, amount in self.effects_to_faction.items() if
                   "food" in effect and 'production' in effect])
        etp = sum([amount for effect, amount in self.effects_to_province.items() if
                   "food" in effect and 'production' in effect])
        etr = sum([amount for effect, amount in self.effects_to_region.items() if
                   "food" in effect and 'production' in effect])
        etb = sum([amount for effect, amount in self.effects_to_building.items() if
                   "food" in effect and 'production' in effect])
        food_production = etf + etp + etr + etb
        etf = sum([amount for effect, amount in self.effects_to_faction.items() if
                   "food" in effect and 'consumption' in effect])
        etp = sum([amount for effect, amount in self.effects_to_province.items() if
                   "food" in effect and 'consumption' in effect])
        etr = sum([amount for effect, amount in self.effects_to_region.items() if
                   "food" in effect and 'consumption' in effect])
        etb = sum([amount for effect, amount in self.effects_to_building.items() if
                   "food" in effect and 'consumption' in effect])
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
    if "major" in building_name or "civic" in building_name or "military_upgrade" in building_name or "aqueducts" in building_name or "sewers" in building_name:
        return True
    return False


def building_is_minor(building_name: str) -> bool:
    """
    Check if a building is minor (village).
    :param building_name:
    :return:
    """
    if "minor" in building_name or "agriculture" in building_name or "livestock" in building_name:
        return True
    return False


def building_is_not_of_faction(building_name: str) -> bool:
    """
    Check if a building is of the faction currently assigned in Games.
    :param building_name:
    :return:
    """
    if Games.faction == AttilaFactions.ATTILA_ROMAN_EAST and (
            "roman" in building_name and "west" not in building_name) or ("orthodox" in building_name) or (
            "all" in building_name and "camel" not in building_name):
        return False
    return True


def building_is_resource(building):
    """
    Check if a building is a resource building.
    If the building contains resource but not port, it is a resource building.
    If the building contains spice, it is a resource building.
    :param building:
    :return:
    """
    return ("resource" in building.name and "port" not in building.name) or "spice" in building.name


class Region:
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
            # Filter out buildings that are not of the faction to reduce the number of LpVariables.
            if building_is_not_of_faction(building.name):
                continue
            if region.region_type == RegionType.ATTILA_REGION_MAJOR and building_is_minor(building.name):
                continue
            if region.region_type == RegionType.ATTILA_REGION_MINOR and building_is_major(building.name):
                continue
            if "ruin" in building.name:
                continue
            deep_copy = building.__copy__()
            deep_copy.name = f"{self.name}_{building.name}"
            deep_copy.lp_variable = LpVariable(deep_copy.name, 0, 1, LpInteger)
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
            ) == 1, f"{self.name}_Port_Constraint"
        else:
            # Filter out all ports that are not spice if the region has no port to reduce the number of LpVariables.
            for i, building in reversed(list(enumerate(self.buildings))):
                if "port" in building.name and "spice" not in building.name:
                    self.buildings.pop(i)

    def add_resource_constraint(self, region: RegionAttila):
        """
        If the region has a resource, then we can add a constraint that the number of buildings in the region with "resource" and "spice" is between 1 and 1. That's because
        spice resource is mandatory (is a port). Any other resource is optional.
        :param region:
        :return:
        """
        # Remove buildings that are illegal
        resource_constraints = {
            RegionHasRessource.ATTILA_REGION_SPICE: ("spice", True),
            RegionHasRessource.ATTILA_REGION_FURS: ("furs", False),
            RegionHasRessource.ATTILA_REGION_IRON: ("iron", False),
            RegionHasRessource.ATTILA_REGION_WINE: ("wine", False),
            RegionHasRessource.ATTILA_REGION_WOOD: ("wood", False),
            RegionHasRessource.ATTILA_REGION_GOLD: ("gold", False),
            RegionHasRessource.ATTILA_REGION_MARBLE: ("marble", False),
            RegionHasRessource.ATTILA_REGION_GEMS: ("gems", False),
            RegionHasRessource.ATTILA_REGION_SILK: ("silk", False),
            RegionHasRessource.ATTILA_REGION_SALT: ("salt", False),
            RegionHasRessource.ATTILA_REGION_LEAD: ("lead", False),
            RegionHasRessource.ATTILA_REGION_OLIVES: ("olives", False),
            RegionHasRessource.ATTILA_REGION_CHURCH: ("legendary", True),
        }
        resources = {k: v[0] for k, v in resource_constraints.items()}

        for i, building in reversed(list(enumerate(self.buildings))):
            if region.has_ressource != RegionHasRessource.ATTILA_REGION_CHURCH and "religion" in building.name and "legendary" in building.name:
                self.buildings.pop(i)
            elif region.has_ressource == RegionHasRessource.ATTILA_REGION_NO_RESSOURCE and building_is_resource(
                    building):
                self.buildings.pop(i)
            elif region.has_ressource in resources:
                resource = resources[region.has_ressource]
                if (
                        "resource" in building.name
                        and resource not in building.name
                        and "port" not in building.name
                ) or "spice" in building.name:
                    self.buildings.pop(i)
            elif region.has_ressource == RegionHasRessource.ATTILA_REGION_CHURCH:
                if ("resource" in building.name and "port" not in building.name) or "spice" in building.name:
                    self.buildings.pop(i)

        # Add constraints dynamically based on the resource type
        if region.has_ressource in resource_constraints:
            chain_name, chain_is_mandatory = resource_constraints[region.has_ressource]
            constraint = (
                lpSum(
                    building.lp_variable
                    for building in self.buildings
                    if "resource" in building.name and chain_name in building.name
                )
            )
            if chain_is_mandatory:
                Games.problem += constraint == 1, f"{self.name}_{chain_name.capitalize()}_Resource_Constraint"
            else:
                Games.problem += constraint <= 1, f"{self.name}_{chain_name.capitalize()}_Resource_Constraint"

    def add_type_constraint(self, region: RegionAttila):
        """
        If the region is major, then we can add a constraint that all buildings with "minor" are between 0 and 0, as well as "agriculture".
        Conversely, disable civic, major buildings in minor regions.
        :param region:
        :return:
        """
        for i, building in reversed(list(enumerate(self.buildings))):
            if region.region_type == RegionType.ATTILA_REGION_MAJOR and building_is_minor(building.name):
                self.buildings.pop(i)
            elif region.region_type == RegionType.ATTILA_REGION_MINOR and building_is_major(building.name):
                self.buildings.pop(i)
        if region.region_type == RegionType.ATTILA_REGION_MAJOR:
            Games.problem += lpSum(
                building.lp_variable
                for building in self.buildings
                if "city_major" in building.name
            ) == 1, f"{self.name}_Major_Constraint"
        else:
            Games.problem += lpSum(
                building.lp_variable
                for building in self.buildings
                if "city_minor" in building.name
            ) == 1, f"{self.name}_Minor_Constraint"

    def add_chain_constraint(self):
        """
        Add chain constraint to the region. buildingX_1 and buildingX_2 are exclusive, because it is an upgrade.

        :return:
        """
        dictionary = defaultdict(list[Building])
        for building in self.buildings:
            # name is everything until last underscore
            name = building.name.split("_")[:-1]
            dictionary["_".join(name)].append(building)
        for building_chain, building_list in dictionary.items():
            Games.problem += lpSum(
                building.lp_variable
                for building in building_list
            ) <= 1, f"{self.name}_Chain_Constraint_{building_chain}"

    def add_building_count_constraint(self):
        """
        Add building count constraint to the region. The number of buildings in the region must be less or equal to the number of buildings that can be built in the region.
        :return:
        """
        Games.problem += lpSum(
            building.lp_variable for building in self.buildings
        ) <= self.n_buildings, f"Max_Buildings_{self.name}"


class Province:
    """
    We need to create a Province class that contains a list of regions.
    """

    def __init__(self, n_regions: int, name: str):
        self.regions = []
        self.n_regions = n_regions
        self.name = name

    def add_region(self, region: Region):
        """
        Add a region to the province.
        :param region:
        :return:
        """
        self.regions.append(region)

    def add_public_order_constraint(self):
        """
        Add public order constraint to the province.
        :return:
        """
        Games.problem += lpSum(
            building.public_order() * building.lp_variable
            for building in self.buildings()
        ) >= 0, "Public_Order_Constraint"

    def add_food_constraint(self):
        """
        Add food constraint to the province.
        :return:
        """
        Games.problem += lpSum(
            building.food() * building.lp_variable
            for building in self.buildings()
        ) >= 0, "Food_Constraint"

    def add_sanitation_constraint(self):
        """
        Add sanitation constraint to each region in the province, using the sanitation method from the building class + global effects.
        Sum of each buildings sanitation must be greater or equal to 1, per region, including global effects. We can thus substract the global effects from 1.
        :return:
        """
        for region in self.regions:
            Games.problem += lpSum(
                building.sanitation() * building.lp_variable
                for building in region.buildings
            ) >= 1 - lpSum(
                building.sanitation_scope(Scope.PROVINCE) * building.lp_variable
                for building in self.buildings()
            ), f"Sanitation_Constraint_{region.name}"

    def buildings(self) -> List[Building]:
        """
        Return all buildings in the province that are potentially built. Basically, will be all our LpVariables.
        :return:
        """
        return [building for region in self.regions for building in region.buildings]
