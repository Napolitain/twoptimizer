from collections import defaultdict
from typing import List, cast

from pulp import LpVariable, lpSum

from engine.bases import RegionBase
from engine.building import Building
from engine.entity import Entity
from engine.enums import NameType
from engine.games import Games
from engine.models.game_attila import AttilaGame
from engine.models.model import RegionType, RegionPort
from engine.models.model_attila import AttilaRegionResources, AttilaReligion


class Region(RegionBase, Entity):
    """
    A region contains buildings.
    """
    HASH_NAME = "R1"

    def __init__(self, name: str, print_name: str = ""):
        super().__init__()
        self.hash_name = self.increment_hash_name()
        self.n_buildings = 0  # Number of buildings that can be built in the region. NOT equal to len(buildings).
        self.buildings: List[Building] = []  # List of buildings that are potentially fit for the region.
        self.effects = defaultdict(list)
        self.name = name
        if print_name == "":
            self.print_name = name
        else:
            self.print_name = print_name
        self.region_type = RegionType.REGION_MAJOR
        self.has_port = RegionPort.REGION_NO_PORT
        self.has_ressource = AttilaRegionResources.ATTILA_REGION_NO_RESSOURCE

    def get_n_buildings(self):
        if type(Games.instance) == AttilaGame and self.get_name() not in [
            # In attila, except a few regions, we can build one more building in any case.
            "reg_bithynia_ancyra",
            "reg_cappadocia_caesarea_eusebia",
            "reg_palaestinea_nova_trajana_bostra"]:  # Argentorum(town which only has 3 slots), Ancyra, Caesarea Eusebia and Nova Trajana Bostra
            return self.n_buildings + 1
        elif self.has_port == RegionPort.REGION_PORT:  # If the region has a port, then we can build one more building, in Rome 2.
            return self.n_buildings + 1
        return self.n_buildings

    def set_region_type(self, region_type: RegionType):
        self.region_type = region_type

    def set_has_port(self, has_port: RegionPort):
        self.has_port = has_port

    def set_has_ressource(self, has_ressource: AttilaRegionResources):
        self.has_ressource = has_ressource

    def add_buildings(self):
        """
        Add buildings to the region.
        It should filter buildings based on the region type, port, and resource.
        Adapt constraints accordingly.
        For example, number of free buildings decrease if the region has a port.
        Building must be named region_building.
        :return:
        """
        if self.region_type is None or self.has_port is None or self.has_ressource is None:
            raise ValueError("Region type must be set before adding buildings.")
        # Add buildings Lp variables to the region.
        for building in Games.buildings[Games.instance.get_campaign().value[1]].values():
            # Filter out buildings that are not of the campaign to reduce the number of LpVariables.
            if Games.instance.get_filter().building_is_not_of_campaign(building.get_name()):
                continue
            if self.region_type == RegionType.REGION_MAJOR and Games.instance.get_filter().building_is_minor(
                    building.get_name()):
                continue
            if self.region_type == RegionType.REGION_MINOR and Games.instance.get_filter().building_is_major(
                    building.get_name()):
                continue
            if "ruin" in building.get_name():
                continue
            deep_copy = building.__copy__()
            deep_copy.name = f"{self.name}_{building.name}"
            deep_copy.hash_name = f"{self.hash_name}_{building.hash_name}"
            deep_copy.print_name = f"{self.print_name} {building.print_name}"
            if Games.USE_NAME == NameType.PRINT_NAME:
                deep_copy.lp_variable = LpVariable(deep_copy.name, cat='Binary')
            else:
                deep_copy.lp_variable = LpVariable(deep_copy.get_name(), cat='Binary')
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
        if self.has_port != RegionPort.REGION_PORT:
            # Filter out all ports that are not spice if the region has no port to reduce the number of LpVariables.
            for i, building in reversed(list(enumerate(self.buildings))):
                if Games.instance.get_filter().building_is_port(building.name):
                    self.buildings.pop(i)
        # Filter out port that do not contain "resource" because we have duplicates?
        for i, building in reversed(list(enumerate(self.buildings))):
            if Games.instance.get_filter().building_is_duplicate(building.name):
                self.buildings.pop(i)

    def add_port_constraint(self):
        """
        If the region has a port, then we can add a constraint that the number of buildings in the region with "port" is between 1 and 1.
        :return:
        """
        if self.has_port == RegionPort.REGION_PORT:
            Games.problem += lpSum(
                building.lp_variable
                for building in self.buildings
                if Games.instance.get_filter().building_is_port(building.name)
            ) == 1, f"{self.get_name()}_Port_Constraint"

    def filter_resource(self):
        """
        Filter out buildings that are not of the region resource type.
        :return:
        """
        # Remove buildings that are illegal
        for i, building in reversed(list(enumerate(self.buildings))):
            if self.has_ressource != AttilaRegionResources.ATTILA_REGION_CHURCH_CATHOLIC and "religion_catholic_legendary" in building.name:
                self.buildings.pop(i)
            elif self.has_ressource != AttilaRegionResources.ATTILA_REGION_CHURCH_ORTHODOX and "religion_orthodox_legendary" in building.name:
                self.buildings.pop(i)
            elif self.has_ressource == AttilaRegionResources.ATTILA_REGION_NO_RESSOURCE and Games.instance.get_filter().building_is_resource(
                    building):
                self.buildings.pop(i)
            elif self.has_ressource in AttilaRegionResources:
                resource = self.has_ressource.value
                if (
                        "resource" in building.name
                        and resource not in building.name
                        and "port" not in building.name
                ) or ("spice" in building.name and resource != "spice"):
                    self.buildings.pop(i)
            elif self.has_ressource == AttilaRegionResources.ATTILA_REGION_CHURCH_ORTHODOX or self.has_ressource == AttilaRegionResources.ATTILA_REGION_CHURCH_CATHOLIC:
                if (
                        "resource" in building.name and "port" not in building.name) or "spice" in building.name:
                    self.buildings.pop(i)

    def add_resource_constraint(self):
        """
        If the region has a resource, then we can add a constraint that the number of buildings in the region with "resource" and "spice" is between 1 and 1. That's because
        spice resource is mandatory (is a port). Any other resource is optional.
        :param region:
        :return:
        """
        resource_constraints = {x: False for x in AttilaRegionResources}
        resource_constraints[AttilaRegionResources.ATTILA_REGION_SPICE] = True
        resource_constraints[AttilaRegionResources.ATTILA_REGION_CHURCH_CATHOLIC] = True
        resource_constraints[AttilaRegionResources.ATTILA_REGION_CHURCH_ORTHODOX] = True
        del resource_constraints[AttilaRegionResources.ATTILA_REGION_NO_RESSOURCE]
        # TODO: ugly fix, should be replaced without usage of cast with dynamic check.
        if hasattr(Games.instance, 'religion'):
            x = cast(AttilaGame, Games.instance)
            if x.religion != AttilaReligion.CHRIST_CATHOLIC:
                resource_constraints[AttilaRegionResources.ATTILA_REGION_CHURCH_CATHOLIC] = False
            if x.religion != AttilaReligion.CHRIST_ORTHODOX:
                resource_constraints[AttilaRegionResources.ATTILA_REGION_CHURCH_ORTHODOX] = False

        # Add constraints dynamically based on the resource type
        if self.has_ressource in resource_constraints:
            chain_name = self.has_ressource.value
            chain_is_mandatory = resource_constraints[self.has_ressource]
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
                Games.problem += constraint == 1, f"{self.get_name()}_{chain_name.capitalize()}_Resource_Constraint"
            else:
                Games.problem += constraint <= 1, f"{self.get_name()}_{chain_name.capitalize()}_Resource_Constraint"

    def filter_type(self):
        """
        Filter out buildings that are not of the region type.
        :return:
        """
        for i, building in reversed(list(enumerate(self.buildings))):
            if self.region_type == RegionType.REGION_MAJOR and Games.instance.get_filter().building_is_minor(
                    building.name):
                self.buildings.pop(i)
            elif self.region_type == RegionType.REGION_MINOR and Games.instance.get_filter().building_is_major(
                    building.name):
                self.buildings.pop(i)

    def add_type_constraint(self):
        """
        If the region is major, then we can add a constraint that all buildings with "minor" are between 0 and 0, as well as "agriculture".
        Conversely, disable civic, major buildings in minor regions.
        :return:
        """
        if self.region_type == RegionType.REGION_MAJOR:
            Games.problem += lpSum(
                building.lp_variable
                for building in self.buildings
                if Games.instance.get_filter().building_is_majorcity(building.name)
            ) == 1, f"{self.get_name()}_Major_Constraint"
        else:
            Games.problem += lpSum(
                building.lp_variable
                for building in self.buildings
                if Games.instance.get_filter().building_is_minorcity(building.name)
            ) == 1, f"{self.get_name()}_Minor_Constraint"

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
            ) <= 1, f"{self.get_name()}_Chain_Constraint_{building_chain}"

    def add_building_count_constraint(self):
        """
        Add building count constraint to the region. The number of buildings in the region must be less or equal to the number of buildings that can be built in the region.
        :return:
        """
        Games.problem += lpSum(
            building.lp_variable for building in self.buildings
        ) <= self.get_n_buildings(), f"Max_Buildings_{self.get_name()}"

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
            try:
                float(split_name[j])
            except ValueError:
                print(f"Building {building.get_name()} has no level.")
                continue
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

    def increment_hash_name(self) -> str:
        """
        Increment the hash name of the region. Must be X1, X2... Xn.
        :return:
        """
        x = Region.HASH_NAME
        split_name = x.split("R")
        split_name[1] = str(int(split_name[1]) + 1)
        Region.HASH_NAME = "R".join(split_name)
        return x

    def set_buildings_limit(self, limit: int) -> None:
        """
        Change number of buildings that can be built in the region.
        :param limit: number of buildings that can be built in the region
        :return:
        """
        self.n_buildings = limit
