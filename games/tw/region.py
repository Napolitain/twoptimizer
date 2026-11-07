from collections import defaultdict
from typing import cast

from games.tw.bases import RegionBase
from games.tw.building import Building
from games.tw.entity import Entity
from games.tw.enums import NameType, get_hash_name
from games.tw.games import Games
from games.tw.models.game_attila import AttilaGame
from games.tw.models.model import RegionPort, RegionType
from games.tw.models.model_attila import AttilaRegionResources, AttilaReligion


class Region(RegionBase, Entity):
    """
    A region contains buildings.
    """

    def __init__(self, name: str, print_name: str = ""):
        super().__init__()
        self.hash_name = get_hash_name("R")
        self.fertility = None  # Explicit regional fertility; None uses the scenario value.
        self.n_buildings = (
            0  # Number of buildings that can be built in the region. NOT equal to len(buildings).
        )
        self.buildings: list[
            Building
        ] = []  # List of buildings that are potentially fit for the region.
        self.effects = defaultdict(list)
        self.name = name
        if print_name == "":
            self.print_name = name
        else:
            self.print_name = print_name
        self.region_type = RegionType.REGION_MAJOR
        self.has_port = RegionPort.REGION_NO_PORT
        self.has_ressource = AttilaRegionResources.ATTILA_REGION_NO_RESSOURCE
        self.building_chain_to_hashname = {}

    def get_n_buildings(self):
        if isinstance(Games.instance, AttilaGame) and self.name not in [
            # In attila, except a few regions, we can build one more building in any case.
            "reg_bithynia_ancyra",
            "reg_cappadocia_caesarea_eusebia",
            "reg_palaestinea_nova_trajana_bostra",
        ]:
            return self.n_buildings + 1
        elif (
            self.has_port == RegionPort.REGION_PORT
        ):  # If the region has a port, then we can build one more building, in Rome 2.
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
        if Games.buildings is None:
            raise ValueError("Load a game building catalog first")
        for building in Games.buildings[Games.current().get_campaign().value[1]].values():
            if not Games.legacy_effects and any(
                marker in building.name for marker in ("_barbmigs_", "_nomad_", "_eastmig_")
            ):
                continue  # Horde structures are not province building slots.
            # Filter out buildings that are not of the campaign to reduce the number of LpVariables.
            if Games.current().get_filter().building_is_not_of_campaign(building.name):
                continue
            if (
                self.region_type == RegionType.REGION_MAJOR
                and Games.current().get_filter().building_is_minor(building.name)
            ):
                continue
            if (
                self.region_type == RegionType.REGION_MINOR
                and Games.current().get_filter().building_is_major(building.name)
            ):
                continue
            if "ruin" in building.name or (
                not Games.legacy_effects and building.name.startswith("att_abandoned_")
            ):
                continue
            if not Games.legacy_effects and not self._building_matches_culture(building):
                continue
            self._copy_building(building)
        # Filter buildings out (remove LpVariables)
        self.filter_type()
        self.filter_resource()
        self.filter_port()

    @staticmethod
    def _building_matches_culture(building):
        from games.tw.attila.catalogue import CULTURE_SLUGS

        if building.metadata is None:
            return True
        parser = Games.current().get_parser()
        subculture = parser.faction_to_culture[parser.faction.value].subculture
        culture = CULTURE_SLUGS.get(subculture)
        return culture is None or culture in building.metadata["requirements_by_culture"]

    def _copy_building(self, building):
        deep_copy = building.__copy__()
        deep_copy.region = self
        deep_copy.name = f"{self.name}_{building.name}"
        deep_copy.hash_name = f"{self.hash_name}_{building.hash_name}"
        deep_copy.print_name = f"{self.print_name} {building.print_name}"
        if Games.USE_NAME == NameType.PRINT_NAME:
            deep_copy.lp_variable = Games.problem.create_variable(deep_copy.name, "Binary")
        else:
            deep_copy.lp_variable = Games.problem.create_variable(deep_copy.get_name(), "Binary")
        self.buildings.append(deep_copy)

    def filter_technologies(self):
        researched = getattr(Games.problem, "technologies", None)
        self._exclude_missing_income_metadata()
        disabled = getattr(Games.problem, "disabled_technologies", set())
        if not Games.legacy_effects and researched is None and disabled:
            from games.tw.attila.catalogue import CULTURE_SLUGS

            parser = Games.current().get_parser()
            culture = CULTURE_SLUGS[parser.faction_to_culture[parser.faction.value].subculture]
            for i, building in reversed(list(enumerate(self.buildings))):
                if building.metadata is not None:
                    requirements = building.metadata["requirements_by_culture"].get(culture, [])
                    if any(
                        alternatives and set(alternatives) <= disabled
                        for alternatives in requirements
                    ):
                        self.buildings.pop(i)
        if not Games.legacy_effects and researched is not None:
            from games.tw.attila.catalogue import CULTURE_SLUGS, technology_available

            parser = Games.current().get_parser()
            subculture = parser.faction_to_culture[parser.faction.value].subculture
            for i, building in reversed(list(enumerate(self.buildings))):
                if not technology_available(building, CULTURE_SLUGS[subculture], researched):
                    self.buildings.pop(i)

    def _exclude_missing_income_metadata(self):
        if not Games.legacy_effects and getattr(Games.problem, "require_income_metadata", False):
            for i, building in reversed(list(enumerate(self.buildings))):
                if building.metadata is None:
                    Games.problem.catalogue_exclusions.append(
                        {
                            "building": building.name,
                            "reason": (
                                "Missing imported upkeep/availability metadata; not assumed free"
                            ),
                        }
                    )
                    self.buildings.pop(i)

    def add_constraints(self):
        """
        Add constraints to the region, after filtering out.
        :return:
        """
        self.filter_technologies()
        self.add_type_constraint()
        self.add_resource_constraint()
        self.add_port_constraint()
        self.add_chain_constraint()
        self.add_building_count_constraint()

    def filter_port(self):
        if self.has_port != RegionPort.REGION_PORT:
            # Filter out all ports that are not spice if the region has no port to reduce the
            # number of LpVariables.
            for i, building in reversed(list(enumerate(self.buildings))):
                if Games.current().get_filter().building_is_port(building.name):
                    self.buildings.pop(i)
        # Filter out port that do not contain "resource" because we have duplicates?
        for i, building in reversed(list(enumerate(self.buildings))):
            if Games.current().get_filter().building_is_duplicate(building.name):
                self.buildings.pop(i)

    def add_port_constraint(self):
        """
        If the region has a port, then we can add a constraint that the number of buildings in
        the region with "port" is between 1 and 1.
        :return:
        """
        if self.has_port == RegionPort.REGION_PORT:
            Games.problem.create_constraint(
                name=f"{self.get_name()}_Port",
                variables=[
                    building.lp_variable
                    for building in self.buildings
                    if Games.current().get_filter().building_is_port(building.name)
                ],
                constraint_fn=lambda expr: expr == 1,
            )

    def filter_resource(self):
        """
        Filter out buildings that are not of the region resource type.
        :return:
        """
        # Remove buildings that are illegal
        for i, building in reversed(list(enumerate(self.buildings))):
            if (
                (
                    self.has_ressource != AttilaRegionResources.ATTILA_REGION_CHURCH_CATHOLIC
                    and "religion_catholic_legendary" in building.name
                )
                or (
                    self.has_ressource != AttilaRegionResources.ATTILA_REGION_CHURCH_ORTHODOX
                    and "religion_orthodox_legendary" in building.name
                )
                or (
                    self.has_ressource == AttilaRegionResources.ATTILA_REGION_NO_RESSOURCE
                    and Games.current().get_filter().building_is_resource(building)
                )
            ):
                self.buildings.pop(i)
            elif self.has_ressource in AttilaRegionResources:
                resource = self.has_ressource.value
                if (
                    "resource" in building.name
                    and resource not in building.name
                    and "port" not in building.name
                ) or ("spice" in building.name and resource != "spice"):
                    self.buildings.pop(i)
            elif (
                self.has_ressource == AttilaRegionResources.ATTILA_REGION_CHURCH_ORTHODOX
                or self.has_ressource == AttilaRegionResources.ATTILA_REGION_CHURCH_CATHOLIC
            ) and (
                ("resource" in building.name and "port" not in building.name)
                or "spice" in building.name
            ):
                self.buildings.pop(i)

    def add_resource_constraint(self):
        """
        If the region has a resource, then we can add a constraint that the number of buildings
        in the region with "resource" and "spice" is between 1 and 1. That's because
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
        if hasattr(Games.instance, "religion"):
            x = cast(AttilaGame, Games.instance)
            if x.religion != AttilaReligion.CHRIST_CATHOLIC:
                resource_constraints[AttilaRegionResources.ATTILA_REGION_CHURCH_CATHOLIC] = False
            if x.religion != AttilaReligion.CHRIST_ORTHODOX:
                resource_constraints[AttilaRegionResources.ATTILA_REGION_CHURCH_ORTHODOX] = False

        # Add constraints dynamically based on the resource type
        if self.has_ressource in resource_constraints:
            chain_name = self.has_ressource.value
            chain_is_mandatory = resource_constraints[self.has_ressource]
            constraint = [
                building.lp_variable
                for building in self.buildings
                if chain_name in building.name
                and ("resource" in building.name or "religion" in chain_name)
            ]
            # If the resource is mandatory, then the constraint is == 1, otherwise <= 1, because
            # not putting it may be better.
            Games.problem.create_constraint(
                name=f"{self.get_name()}_{chain_name.capitalize()}_Resource",
                variables=constraint,
                constraint_fn=lambda expr: expr == 1 if chain_is_mandatory else expr <= 1,
            )

    def filter_type(self):
        """
        Filter out buildings that are not of the region type.
        :return:
        """
        for i, building in reversed(list(enumerate(self.buildings))):
            if (
                self.region_type == RegionType.REGION_MAJOR
                and Games.current().get_filter().building_is_minor(building.name)
            ) or (
                self.region_type == RegionType.REGION_MINOR
                and Games.current().get_filter().building_is_major(building.name)
            ):
                self.buildings.pop(i)

    def add_type_constraint(self):
        """
        If the region is major, then we can add a constraint that all buildings with "minor" are
        between 0 and 0, as well as "agriculture".
        Conversely, disable civic, major buildings in minor regions.
        :return:
        """
        if self.region_type == RegionType.REGION_MAJOR:
            Games.problem.create_constraint(
                name=f"{self.get_name()}_Major",
                variables=[
                    building.lp_variable
                    for building in self.buildings
                    if Games.current().get_filter().building_is_majorcity(building.name)
                ],
                constraint_fn=lambda expr: expr == 1,
            )
        else:
            Games.problem.create_constraint(
                name=f"{self.get_name()}_Minor",
                variables=[
                    building.lp_variable
                    for building in self.buildings
                    if Games.current().get_filter().building_is_minorcity(building.name)
                ],
                constraint_fn=lambda expr: expr == 1,
            )

    def add_chain_constraint(self):
        """
        Add chain constraint to the region. buildingX_1 and buildingX_2 are exclusive, because
        it is an upgrade.

        :return:
        """
        building_name_to_building = defaultdict(list[Building])
        for building in self.buildings:
            # name is everything until last underscore
            name = building.name.split("_")[:-1]
            building_name_to_building["_".join(name)].append(building)
        for building_chain, building_list in building_name_to_building.items():
            if building_chain not in self.building_chain_to_hashname:
                self.building_chain_to_hashname[building_chain] = get_hash_name("BC")
            Games.problem.create_constraint(
                name=f"{self.get_name()}_Chain_{self.get_building_chain_name(building_chain)}",
                variables=[building.lp_variable for building in building_list],
                constraint_fn=lambda expr: expr <= 1,
            )

    def add_building_count_constraint(self):
        """
        Add building count constraint to the region. The number of buildings in the region must
        be less or equal to the number of buildings that can be built in the region.
        :return:
        """
        Games.problem.create_constraint(
            name=f"Max_Buildings_{self.get_name()}",
            variables=[building.lp_variable for building in self.buildings],
            constraint_fn=lambda expr: expr <= self.get_n_buildings(),
        )

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
            if split_name[j].isdigit():
                if len(split_name) > 1 and float(split_name[j]) < level:
                    self.buildings.pop(i)
            else:
                # print(f"Building {building.get_name()} has no level.")
                self.buildings.pop(i)

    def filter_military(self):
        """
        Filter out all military buildings, which are not GDP buildings anyway, and will be a
        province in isolation.
        :return:
        """
        for i, building in reversed(list(enumerate(self.buildings))):
            if "military" in building.name:
                self.buildings.pop(i)

    HASH_NAME = "R1"

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

    def get_building_chain_name(self, building_chain_name: str):
        if Games.USE_NAME == NameType.HASH_NAME:
            return self.building_chain_to_hashname[building_chain_name]
        return building_chain_name
