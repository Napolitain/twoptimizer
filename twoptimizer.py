import abc
import enum
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import List

from pulp import LpVariable, LpInteger, LpProblem, LpMaximize, lpSum


class EntryType(enum.Enum):
    BUILDING = "bld"
    REGION = "reg"
    PROVINCE = "prov"


def get_entry_name(name: str, entry_type: EntryType) -> str:
    """
    Get the building name from the full name.
    x_y_bld_z -> bld_z
    :param name: full name
    :param entry_type: type of the entry (building, region, province)
    :return: name of the entry
    """
    split_name = name.split("_")
    i = 0
    while i < len(split_name) and split_name[i] != entry_type.value:
        i += 1
    if i == len(split_name):
        raise ValueError(f"Entry type {entry_type.value} not found in {name}.")
    # Return everything after the entry type unless it matches any other entry type (e.g. reg, prov)
    j = i + 1
    # Matches bld, reg, if we search prov, etc...
    entries = [entry.value for entry in EntryType if entry != entry_type]
    while j < len(split_name) and split_name[j] not in entries:
        j += 1
    if j == len(split_name):
        return "_".join(split_name[i:])
    return "_".join(split_name[i:j])


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


class RegionHasResource(enum.Enum):
    ATTILA_REGION_NO_RESSOURCE = "NONE"
    ATTILA_REGION_FURS = "furs"
    ATTILA_REGION_IRON = "iron"
    ATTILA_REGION_WINE = "wine"
    ATTILA_REGION_WOOD = "wood"
    ATTILA_REGION_GOLD = "gold"
    ATTILA_REGION_MARBLE = "marble"
    ATTILA_REGION_GEMS = "gems"
    ATTILA_REGION_SILK = "silk"
    ATTILA_REGION_SPICE = "spice"
    ATTILA_REGION_SALT = "salt"
    ATTILA_REGION_LEAD = "lead"
    ATTILA_REGION_OLIVES = "olives"
    ATTILA_REGION_CHURCH_CATHOLIC = "church_catholic"
    ATTILA_REGION_CHURCH_ORTHODOX = "church_orthodox"


@dataclass
class RegionAttila:
    region_type: RegionType
    has_port: RegionHasPort
    has_ressource: RegionHasResource


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
        self.region_type = RegionType.ATTILA_REGION_MAJOR
        self.has_port = RegionHasPort.ATTILA_REGION_NO_PORT
        self.has_ressource = RegionHasResource.ATTILA_REGION_NO_RESSOURCE

    def set_region_type(self, region_type: RegionType):
        self.region_type = region_type

    def set_has_port(self, has_port: RegionHasPort):
        self.has_port = has_port

    def set_has_ressource(self, has_ressource: RegionHasResource):
        self.has_ressource = has_ressource

    def add_buildings(self, region: RegionAttila = None):
        """
        Add buildings to the region.
        It should filter buildings based on the region type, port, and resource.
        Adapt constraints accordingly.
        For example, number of free buildings decrease if the region has a port.
        Building must be named region_building.
        :param region:
        :return:
        """
        if region is not None:
            self.region_type = region.region_type
            self.has_port = region.has_port
            self.has_ressource = region.has_ressource
        elif self.region_type is None or self.has_port is None or self.has_ressource is None:
            raise ValueError("Region type must be set before adding buildings.")
        # Add buildings Lp variables to the region.
        for building in Games.buildings[Games.current_game].values():
            # Filter out buildings that are not of the faction to reduce the number of LpVariables.
            if building_is_not_of_faction(building.name):
                continue
            if self.region_type == RegionType.ATTILA_REGION_MAJOR and building_is_minor(building.name):
                continue
            if self.region_type == RegionType.ATTILA_REGION_MINOR and building_is_major(building.name):
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
        self.add_type_constraint()
        self.add_resource_constraint()
        self.add_port_constraint()
        self.add_chain_constraint()
        self.add_building_count_constraint()

    def filter_port(self):
        if self.has_port != RegionHasPort.ATTILA_REGION_PORT:
            # Filter out all ports that are not spice if the region has no port to reduce the number of LpVariables.
            for i, building in reversed(list(enumerate(self.buildings))):
                if "port" in building.name and "spice" not in building.name:
                    self.buildings.pop(i)

    def add_port_constraint(self):
        """
        If the region has a port, then we can add a constraint that the number of buildings in the region with "port" is between 1 and 1.
        :return:
        """
        if self.has_port == RegionHasPort.ATTILA_REGION_PORT:
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
            RegionHasResource.ATTILA_REGION_SPICE: ("spice", True),
            RegionHasResource.ATTILA_REGION_FURS: ("furs", False),
            RegionHasResource.ATTILA_REGION_IRON: ("iron", False),
            RegionHasResource.ATTILA_REGION_WINE: ("wine", False),
            RegionHasResource.ATTILA_REGION_WOOD: ("wood", False),
            RegionHasResource.ATTILA_REGION_GOLD: ("gold", False),
            RegionHasResource.ATTILA_REGION_MARBLE: ("marble", False),
            RegionHasResource.ATTILA_REGION_GEMS: ("gems", False),
            RegionHasResource.ATTILA_REGION_SILK: ("silk", False),
            RegionHasResource.ATTILA_REGION_SALT: ("salt", False),
            RegionHasResource.ATTILA_REGION_LEAD: ("lead", False),
            RegionHasResource.ATTILA_REGION_OLIVES: ("olives", False),
            RegionHasResource.ATTILA_REGION_CHURCH_CATHOLIC: ("religion_catholic_legendary", True),
            RegionHasResource.ATTILA_REGION_CHURCH_ORTHODOX: ("religion_orthodox_legendary", True),
        }
        resources = {k: v[0] for k, v in resource_constraints.items()}

        # Remove buildings that are illegal
        for i, building in reversed(list(enumerate(self.buildings))):
            if self.has_ressource != RegionHasResource.ATTILA_REGION_CHURCH_CATHOLIC and "religion_catholic_legendary" in building.name:
                self.buildings.pop(i)
            elif self.has_ressource != RegionHasResource.ATTILA_REGION_CHURCH_ORTHODOX and "religion_orthodox_legendary" in building.name:
                self.buildings.pop(i)
            elif self.has_ressource == RegionHasResource.ATTILA_REGION_NO_RESSOURCE and building_is_resource(
                    building):
                self.buildings.pop(i)
            elif self.has_ressource in resources:
                resource = resources[self.has_ressource]
                if (
                        "resource" in building.name
                        and resource not in building.name
                        and "port" not in building.name
                ) or ("spice" in building.name and resource != "spice"):
                    self.buildings.pop(i)
            elif self.has_ressource == RegionHasResource.ATTILA_REGION_CHURCH_ORTHODOX or self.has_ressource == RegionHasResource.ATTILA_REGION_CHURCH_CATHOLIC:
                if ("resource" in building.name and "port" not in building.name) or "spice" in building.name:
                    self.buildings.pop(i)

    def add_resource_constraint(self):
        """
        If the region has a resource, then we can add a constraint that the number of buildings in the region with "resource" and "spice" is between 1 and 1. That's because
        spice resource is mandatory (is a port). Any other resource is optional.
        :param region:
        :return:
        """
        resource_constraints = {
            RegionHasResource.ATTILA_REGION_SPICE: ("spice", True),
            RegionHasResource.ATTILA_REGION_FURS: ("furs", False),
            RegionHasResource.ATTILA_REGION_IRON: ("iron", False),
            RegionHasResource.ATTILA_REGION_WINE: ("wine", False),
            RegionHasResource.ATTILA_REGION_WOOD: ("wood", False),
            RegionHasResource.ATTILA_REGION_GOLD: ("gold", False),
            RegionHasResource.ATTILA_REGION_MARBLE: ("marble", False),
            RegionHasResource.ATTILA_REGION_GEMS: ("gems", False),
            RegionHasResource.ATTILA_REGION_SILK: ("silk", False),
            RegionHasResource.ATTILA_REGION_SALT: ("salt", False),
            RegionHasResource.ATTILA_REGION_LEAD: ("lead", False),
            RegionHasResource.ATTILA_REGION_OLIVES: ("olives", False),
            RegionHasResource.ATTILA_REGION_CHURCH_CATHOLIC: ("religion_catholic_legendary", True),
            RegionHasResource.ATTILA_REGION_CHURCH_ORTHODOX: ("religion_orthodox_legendary", True),
        }

        # Add constraints dynamically based on the resource type
        if self.has_ressource in resource_constraints:
            chain_name, chain_is_mandatory = resource_constraints[self.has_ressource]
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

    def add_type_constraint(self):
        """
        If the region is major, then we can add a constraint that all buildings with "minor" are between 0 and 0, as well as "agriculture".
        Conversely, disable civic, major buildings in minor regions.
        :return:
        """
        if self.region_type == RegionType.ATTILA_REGION_MAJOR:
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
        ) >= 0, f"{self.name}_Public_Order_Constraint"

    def add_food_constraint(self):
        """
        Add food constraint to the province.
        :return:
        """
        Games.problem += lpSum(
            building.food() * building.lp_variable
            for building in self.buildings()
        ) >= 0, f"{self.name}_Food_Constraint"

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
            ), f"{self.name}_Sanitation_Constraint_{region.name}"

    def buildings(self) -> List[Building]:
        """
        Return all buildings in the province that are potentially built. Basically, will be all our LpVariables.
        :return:
        """
        return [building for region in self.regions for building in region.buildings]


class Problem:
    def __init__(self):
        """
        Init a linear programming problem.
        """
        self.provinces: List[Province] = []
        self.problem = LpProblem("GDP Maximization", LpMaximize)
        Games.problem = self.problem

    def add_province(self, province: Province):
        """
        Add a province to the problem.
        :param province:
        :return:
        """
        self.provinces.append(province)

    def add_provinces(self, file_tsv: Path):
        """
        Add all provinces to the problem.
        :param file_tsv: file containing the provinces schema, usually start_pos_region_slot_templates_table.tsv
        :return:
        """
        # Link region name to province name
        path_province_region_junctions = file_tsv / "region_to_provinces_junctions_table.tsv"
        dictionary_regions_to_province = {}
        with open(path_province_region_junctions, 'r') as file:
            data = file.read()
            data = data.split('\n')
            data = [i.split('\t') for i in data]
        for province_name, region_name in data:
            # Filter game
            if Games.current_game not in province_name:
                continue
            pn = get_entry_name(province_name, EntryType.PROVINCE)
            rn = get_entry_name(region_name, EntryType.REGION)
            dictionary_regions_to_province[rn] = pn
        # Link province name to province object
        dictionary_provinces = {}
        for province_name in dictionary_regions_to_province.values():
            if province_name not in dictionary_provinces:
                dictionary_provinces[province_name] = Province(3, province_name)
        # Read file building_effects_junction_tables.tsv (tabulated)
        path_startpos_regions = file_tsv / "start_pos_region_slot_templates_tables.tsv"
        with open(path_startpos_regions, 'r') as file:
            data = file.read()
            data = data.split('\n')
            data = [i.split('\t') for i in data]
        dictionary_regions = {}
        for _, game, full_region_name, type_building, building in data:
            # Check if it is correct game
            if Games.current_game not in full_region_name or "main_attila" not in game:
                continue
            region_name = get_entry_name(full_region_name, EntryType.REGION)
            # Province name is the regio_name mapped to the province name
            try:
                province_name = dictionary_regions_to_province[region_name]
            except KeyError:
                print(f"Region {region_name} does not have a province.")
                continue
            # If region not in dictionary, add it
            if region_name not in dictionary_regions:
                # If building contains "major", it is a major region, else minor
                if "major" in building:
                    dictionary_regions[region_name] = Region(6, region_name)
                    dictionary_regions[region_name].set_region_type(RegionType.ATTILA_REGION_MAJOR)
                else:
                    dictionary_regions[region_name] = Region(4, region_name)
                    dictionary_regions[region_name].set_region_type(RegionType.ATTILA_REGION_MINOR)
                # Add region to province
                dictionary_provinces[province_name].add_region(dictionary_regions[region_name])
            # Add resources type / port to region
            # 1. If type is primary, discard
            if type_building == "primary":
                continue
            # 2. If type is port, add port if it is not "spice".
            if type_building == "port":
                if "spice" not in building:
                    dictionary_regions[region_name].set_has_port(RegionHasPort.ATTILA_REGION_PORT)
                else:
                    dictionary_regions[region_name].set_has_ressource(RegionHasResource.ATTILA_REGION_SPICE)
            # 3. If type is secondary, add resource
            if type_building == "secondary":
                if "city" in building:
                    dictionary_regions[region_name].set_has_ressource(
                        RegionHasResource.ATTILA_REGION_CHURCH_ORTHODOX)
                else:
                    # Check if building is a resource building
                    for resource in RegionHasResource:
                        if resource.value in building:
                            dictionary_regions[region_name].set_has_ressource(resource)
        for province in dictionary_provinces.values():
            self.add_province(province)
        self.add_buildings()

    def add_buildings(self):
        for province in self.provinces:
            for region in province.regions:
                region.add_buildings()

    def buildings(self) -> List[Building]:
        """
        Return all buildings in the problem that are potentially built. Basically, will be all our LpVariables.
        :return:
        """
        return [building for province in self.provinces for region in province.regions for building in region.buildings]
