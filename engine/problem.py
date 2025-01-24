import enum
from pathlib import Path
from time import perf_counter_ns
from typing import List

from pulp import LpProblem, LpMaximize, PULP_CBC_CMD

from engine.building import Building
from engine.enums import EntryType
from engine.filters.utils import get_entry_name
from engine.games import Games
from engine.models.model import RegionType, RegionPort
from engine.models.model_attila import AttilaRegionResources
from engine.parser.parser import parse_tsv
from engine.province import Province
from engine.region import Region


def get_dictionary_regions_to_province(game_dir: Path):
    """
    Get a dictionary of regions to province from a tsv file (TW DB)
    :param game_dir: path to the game folder
    :return: dictionary of regions to province (region_name: province_name)
    """
    path_province_region_junctions = game_dir / "region_to_provinces_junctions_table.tsv"
    dictionary_regions_to_province = {}
    with open(path_province_region_junctions, 'r') as file:
        data = file.read()
        data = data.split('\n')
        data = [i.split('\t') for i in data]
    for province_name, region_name in data:
        # Filter game
        if Games.instance.get_campaign().value[1] not in province_name:
            continue
        pn = get_entry_name(province_name, EntryType.PROVINCE)
        rn = get_entry_name(region_name, EntryType.REGION)
        dictionary_regions_to_province[rn] = pn
    return dictionary_regions_to_province


class ProblemState(enum.Enum):
    INIT = 0
    PROVINCES_ADDED = 1
    BUILDINGS_ADDED = 2
    FILTERS_ADDED = 3
    CONSTRAINTS_ADDED = 4
    OBJECTIVE_ADDED = 5
    SOLVED = 6


def parse_start_pos_tsv(file_tsv: Path) -> dict[str, Province]:
    # Link region name to province name
    dictionary_regions_to_province = get_dictionary_regions_to_province(file_tsv)
    # Link province name to province object
    dictionary_provinces = {}
    for province_name in dictionary_regions_to_province.values():
        if province_name not in dictionary_provinces:
            dictionary_provinces[province_name] = Province(province_name)
    # Read file building_effects_junction_tables.tsv (tabulated)
    path_startpos_regions = file_tsv / "start_pos_region_slot_templates_table.tsv"
    data = parse_tsv(path_startpos_regions)
    dictionary_regions = {}
    for _, game, full_region_name, type_building, building in data:
        # Check if it is correct game
        if Games.instance.get_campaign().value[1] not in full_region_name or Games.instance.get_campaign().value[
            0] not in game:
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
                dictionary_regions[region_name] = Region(5, region_name)
                dictionary_regions[region_name].set_region_type(RegionType.REGION_MAJOR)
            else:
                dictionary_regions[region_name] = Region(3, region_name)
                dictionary_regions[region_name].set_region_type(RegionType.REGION_MINOR)
            # Add region to province
            dictionary_provinces[province_name].add_region(dictionary_regions[region_name])
        # Add resources type / port to region
        # 1. If type is primary, discard
        if type_building == "primary":
            continue
        # 2. If type is port, add port if it is not "spice".
        if type_building == "port":
            if "spice" not in building:
                dictionary_regions[region_name].set_has_port(RegionPort.REGION_PORT)
            else:
                dictionary_regions[region_name].set_has_ressource(AttilaRegionResources.ATTILA_REGION_SPICE)
        # 3. If type is secondary, add resource
        if type_building == "secondary":
            if "city" in building:
                dictionary_regions[region_name].set_has_ressource(
                    AttilaRegionResources.ATTILA_REGION_CHURCH_ORTHODOX)
            else:
                # Check if building is a resource building
                for resource in AttilaRegionResources:
                    if resource.value in building:
                        dictionary_regions[region_name].set_has_ressource(resource)
    return dictionary_provinces


class Problem:
    def __init__(self):
        """
        Init a linear programming problem.
        """
        self.provinces: List[Province] = []
        self.problem = LpProblem("GDP Maximization", LpMaximize)
        self.state = ProblemState.INIT
        self.global_time = 0
        Games.problem = self.problem

    def add_province(self, province: Province) -> None:
        """
        Add a province to the problem.
        :param province:
        :return:
        """
        self.provinces.append(province)
        self.state = ProblemState.PROVINCES_ADDED

    def add_provinces(self, file_tsv: Path) -> None:
        """
        Add all provinces to the problem.
        :param file_tsv: file containing the provinces schema, usually start_pos_region_slot_templates_table.tsv
        :return:
        """
        dictionary_provinces = parse_start_pos_tsv(file_tsv)
        for province in dictionary_provinces.values():
            self.add_province(province)

    def add_buildings(self) -> None:
        """
        Add all buildings to the problem.
        :return: None
        """
        if self.state != ProblemState.PROVINCES_ADDED:
            raise ValueError("Provinces must be added first.")
        for province in self.provinces:
            for region in province.regions:
                region.add_buildings()
        self.state = ProblemState.BUILDINGS_ADDED

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
        if self.state != ProblemState.CONSTRAINTS_ADDED:
            raise ValueError("Constraints must be added first.")
        self.problem += sum(
            building.gdp() * building.lp_variable
            for building in self.buildings()
        ), "Objective Function"
        self.state = ProblemState.OBJECTIVE_ADDED

    def reset_problem(self) -> None:
        self.problem = LpProblem("GDP Maximization", LpMaximize)
        self.state = ProblemState.INIT
        Games.problem = self.problem

    def solve(self, msg=False, timing=False) -> None:
        """
        Solve the problem.
        :return: None
        """
        if self.state != ProblemState.OBJECTIVE_ADDED:
            raise ValueError("Objective must be added first.")
        solver = PULP_CBC_CMD(msg=msg)
        start_time = perf_counter_ns()
        self.problem.solve(solver)
        end_time = perf_counter_ns()
        if timing:
            print(f"Solving time: {(end_time - start_time) / 1_000_000_000} seconds")
        self.state = ProblemState.SOLVED
        self.global_time += end_time - start_time

    def print_problem_xy(self) -> None:
        """
        Print the number of variables and constraints in the problem.
        :return: None
        """
        print(
            f"Number of variables: {len(self.problem.variables())}\nNumber of constraints: {len(self.problem.constraints)}\n")

    def get_problem_answers(self) -> List[tuple[str, str]]:
        """
        Return the variables equal to 1 with their respective contribution.
        :return: list of tuples (region_name, building_name)
        """
        if self.problem.status != 1:
            raise ValueError("Problem is not solved.")
        answers = []
        for v in self.problem.variables():
            name = get_entry_name(v.name, EntryType.BUILDING)
            if v.varValue == 1:
                answers.append(
                    (get_entry_name(v.name, EntryType.REGION), Games.buildings[Games.instance.get_campaign()[1]][name]))
        return answers

    def print_problem_answers(self):
        """
        Print the variables equal to 1 with their respective contribution.
        :return:
        """
        problem_answers = self.get_problem_answers()
        for region_name, building_name in problem_answers:
            print(f"{region_name}: {building_name}")
