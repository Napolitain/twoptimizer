from pathlib import Path
from typing import List

from pulp import LpProblem, LpMaximize

from engines.building import Building
from engines.enums import EntryType, RegionType, RegionHasPort, RegionHasResource
from engines.games import Games
from engines.province import Province
from engines.region import Region
from engines.utils import get_entry_name


def get_dictionary_regions_to_province(file_tsv: Path):
    """
    Get a dictionary of regions to province from a tsv file (TW DB)
    :param file_tsv: path to the game folder
    :return: dictionary of regions to province (region_name: province_name)
    """
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
    return dictionary_regions_to_province


class Problem:
    def __init__(self):
        """
        Init a linear programming problem.
        """
        self.provinces: List[Province] = []
        self.problem = LpProblem("GDP Maximization", LpMaximize)
        Games.problem = self.problem

    def add_province(self, province: Province) -> None:
        """
        Add a province to the problem.
        :param province:
        :return:
        """
        self.provinces.append(province)

    def add_provinces(self, file_tsv: Path) -> None:
        """
        Add all provinces to the problem.
        :param file_tsv: file containing the provinces schema, usually start_pos_region_slot_templates_table.tsv
        :return:
        """
        # Link region name to province name
        dictionary_regions_to_province = get_dictionary_regions_to_province(file_tsv)
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

    def add_buildings(self) -> None:
        for province in self.provinces:
            for region in province.regions:
                region.add_buildings()

    def buildings(self) -> List[Building]:
        """
        Return all buildings in the problem that are potentially built. Basically, will be all our LpVariables.
        :return:
        """
        return [building for province in self.provinces for region in province.regions for building in region.buildings]

    def add_objective(self) -> None:
        """
        Add the objective function to the problem.
        Objective function: Maximize GDP on LpVariables (buildings) that are remaining.
        After this, we CANNOT change the buildings anymore, because LpVariables are already factored in the objective function.
        :return: None
        """
        self.problem += sum(
            building.gdp() * building.lp_variable
            for building in self.buildings()
        ), "Objective Function"

    def reset_problem(self) -> None:
        self.problem = LpProblem("GDP Maximization", LpMaximize)
        Games.problem = self.problem

    def solve(self):
        self.problem.solve()
        return self.problem
