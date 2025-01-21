from collections import defaultdict
from typing import List

from pulp import LpVariable, lpSum

from engine.building import Building
from engine.enums import RegionType, RegionHasPort, RegionHasResource, RegionAttila
from engine.games import Games
from engine.utils import building_is_not_of_faction, building_is_minor, building_is_major, building_is_resource


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
            deep_copy.lp_variable = LpVariable(deep_copy.name, cat='Binary')
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
        # Filter out port that do not contains "resource" because we have duplicates?
        for i, building in reversed(list(enumerate(self.buildings))):
            if "port" in building.name and "resource" not in building.name:
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
        :param city_level: level of the city (between 1 and 4)
        :return:
        """
        for i, building in reversed(list(enumerate(self.buildings))):
            if "_city_" in building.name:
                split_name = building.name.split("_")
                if float(split_name[-1]) < city_level:
                    self.buildings.pop(i)

    def filter_building_level(self, level: int):
        """
        Filter out all buildings that are not at least the level.
        :param level: level of the building (between 1 and 4)
        :return:
        """
        for i, building in reversed(list(enumerate(self.buildings))):
            split_name = building.name.split("_")
            # Find level inside the split_name, which is the last element convertable to float.
            j = len(split_name) - 1
            while j >= 0:
                try:
                    float(split_name[j])
                    break
                except ValueError:
                    j -= 1
            if len(split_name) > 1 and float(split_name[j]) < level:
                self.buildings.pop(i)

    def filter_military(self):
        """
        Filter out all military buildings, which are not GDP buildings anyway, and will be a province in isolation.
        :return:
        """
        for i, building in reversed(list(enumerate(self.buildings))):
            if "military" in building.name:
                self.buildings.pop(i)
