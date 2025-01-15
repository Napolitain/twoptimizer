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
    ATTILA_SASSANIDS = 15


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
        # if "fertility" in effect:
        #     amount *= Province.fertility
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
        Calculate the total GDP by summing GDP values from effects,
        adjusted for fertility where applicable.
        :return: total GDP value.
        """

        def calculate_gdp(include_fertility=False):
            sources = [
                self.effects_to_faction,
                self.effects_to_province,
                self.effects_to_region,
                self.effects_to_building,
            ]
            gdp_sum = sum(
                amount
                for source in sources
                for effect, amount in source.items()
                if "gdp" in effect and "mod" not in effect and (include_fertility == ("fertility" in effect))
            )
            return gdp_sum * (Province.fertility if include_fertility else 1)

        base_gdp = calculate_gdp()
        fertility_gdp = calculate_gdp(include_fertility=True)

        return base_gdp + fertility_gdp

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
        Calculate the net food production by summing food production values
        (adjusted for fertility where applicable) and subtracting food consumption values.
        :return: net food production.
        """

        def calculate_food(effect_type, include_fertility=False):
            sources = [
                self.effects_to_faction,
                self.effects_to_province,
                self.effects_to_region,
                self.effects_to_building,
            ]
            food_sum = sum(
                amount
                for source in sources
                for effect, amount in source.items()
                if "food" in effect and effect_type in effect and (include_fertility == ("fertility" in effect))
            )
            return food_sum * (Province.fertility if include_fertility else 1)

        food_production = calculate_food("production") + calculate_food("production", include_fertility=True)
        food_consumption = calculate_food("consumption")

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
    ATTILA_REGION_CHURCH_CATHOLIC = 14
    ATTILA_REGION_CHURCH_ORTHODOX = 15


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
    split_name = building_name.split("_")
    if Games.faction == AttilaFactions.ATTILA_ROMAN_EAST:
        if (
                "roman" in building_name and "west" not in building_name) or ("orthodox" in building_name) or (
                "all" in split_name and "camel" not in building_name and "pigs" not in building_name):
            return False
    if Games.faction == AttilaFactions.ATTILA_ROMAN_WEST:
        if (
                "roman" in building_name and "east" not in building_name) or ("catholic" in building_name) or (
                "all" in split_name and "camel" not in building_name and "pigs" not in building_name):
            return False
    if Games.faction == AttilaFactions.ATTILA_FRANKS:
        if "barbarian" in building_name or (
                "catholic" in building_name) or (
                "all" in split_name and "camel" not in building_name and "pigs" not in building_name):
            return False
    if Games.faction == AttilaFactions.ATTILA_SASSANIDS:
        if "eastern" in building_name or (
                "zoro" in building_name) or (
                "all" in split_name and "cows" not in building_name and "pigs" not in building_name):
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
        self.region_type = None

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
        self.region_type = region
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
        # Filter buildings out (remove LpVariables)
        self.filter_type()
        self.filter_resource()
        self.filter_port()

    def add_constraints(self):
        """
        Add constraints to the region, after filtering out.
        :return:
        """
        self.add_type_constraint(self.region_type)
        self.add_resource_constraint(self.region_type)
        self.add_port_constraint(self.region_type)
        self.add_chain_constraint()
        self.add_building_count_constraint()

    def filter_port(self):
        if self.region_type.has_port != RegionHasPort.ATTILA_REGION_PORT:
            # Filter out all ports that are not spice if the region has no port to reduce the number of LpVariables.
            for i, building in reversed(list(enumerate(self.buildings))):
                if "port" in building.name and "spice" not in building.name:
                    self.buildings.pop(i)

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

    def filter_resource(self):
        """
        Filter out buildings that are not of the region resource type.
        :return:
        """
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
            RegionHasRessource.ATTILA_REGION_CHURCH_CATHOLIC: ("religion_catholic_legendary", True),
            RegionHasRessource.ATTILA_REGION_CHURCH_ORTHODOX: ("religion_orthodox_legendary", True),
        }
        resources = {k: v[0] for k, v in resource_constraints.items()}

        # Remove buildings that are illegal
        for i, building in reversed(list(enumerate(self.buildings))):
            if self.region_type.has_ressource != RegionHasRessource.ATTILA_REGION_CHURCH_CATHOLIC and "religion_catholic_legendary" in building.name:
                self.buildings.pop(i)
            elif self.region_type.has_ressource != RegionHasRessource.ATTILA_REGION_CHURCH_ORTHODOX and "religion_orthodox_legendary" in building.name:
                self.buildings.pop(i)
            elif self.region_type.has_ressource == RegionHasRessource.ATTILA_REGION_NO_RESSOURCE and building_is_resource(
                    building):
                self.buildings.pop(i)
            elif self.region_type.has_ressource in resources:
                resource = resources[self.region_type.has_ressource]
                if (
                        "resource" in building.name
                        and resource not in building.name
                        and "port" not in building.name
                ) or "spice" in building.name:
                    self.buildings.pop(i)
            elif self.region_type.has_ressource == RegionHasRessource.ATTILA_REGION_CHURCH_ORTHODOX or self.region_type.has_ressource == RegionHasRessource.ATTILA_REGION_CHURCH_CATHOLIC:
                if ("resource" in building.name and "port" not in building.name) or "spice" in building.name:
                    self.buildings.pop(i)

    def add_resource_constraint(self, region: RegionAttila):
        """
        If the region has a resource, then we can add a constraint that the number of buildings in the region with "resource" and "spice" is between 1 and 1. That's because
        spice resource is mandatory (is a port). Any other resource is optional.
        :param region:
        :return:
        """
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
            RegionHasRessource.ATTILA_REGION_CHURCH_CATHOLIC: ("religion_catholic_legendary", True),
            RegionHasRessource.ATTILA_REGION_CHURCH_ORTHODOX: ("religion_orthodox_legendary", True),
        }

        # Add constraints dynamically based on the resource type
        if region.has_ressource in resource_constraints:
            chain_name, chain_is_mandatory = resource_constraints[region.has_ressource]
            constraint = (
                lpSum(
                    building.lp_variable
                    for building in self.buildings
                    if chain_name in building.name and (
                            "resource" in building.name or "religion" in chain_name
                    )
                )
            )
            if chain_is_mandatory:
                Games.problem += constraint == 1, f"{self.name}_{chain_name.capitalize()}_Resource_Constraint"
            else:
                Games.problem += constraint <= 1, f"{self.name}_{chain_name.capitalize()}_Resource_Constraint"

    def filter_type(self):
        """
        Filter out buildings that are not of the region type.
        :return:
        """
        for i, building in reversed(list(enumerate(self.buildings))):
            if self.region_type == RegionType.ATTILA_REGION_MAJOR and building_is_minor(building.name):
                self.buildings.pop(i)
            elif self.region_type == RegionType.ATTILA_REGION_MINOR and building_is_major(building.name):
                self.buildings.pop(i)

    def add_type_constraint(self, region: RegionAttila):
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

    def filter_city_level(self, city_level: int):
        """
        Filter out buildings that are not at least the city level.
        :param city_level:
        :return:
        """
        for i, building in reversed(list(enumerate(self.buildings))):
            if "_city_" in building.name:
                split_name = building.name.split("_")
                if float(split_name[-1]) < city_level:
                    self.buildings.pop(i)


class Province:
    """
    We need to create a Province class that contains a list of regions.
    """
    fertility = 3

    def __init__(self, n_regions: int, name: str):
        self.regions = []
        self.n_regions = n_regions
        self.name = name

    def set_fertility(self, fertility: int):
        """
        Set the fertility of the province.
        :param fertility:
        :return:
        """
        Province.fertility = fertility

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
