# att_effect_economy_gdp_industry
# att_bld_roman_west_city_major_1
from unittest import TestCase

from engine.enums import NameType, ProblemState, SolverType
from engine.games import Games
from engine.models.game_attila import AttilaGame
from engine.problem import Problem


# PuLP is a linear and mixed integer programming modeler written in Python.


class TestRegion(TestCase):
    def test_attila_regions_f5(self):
        result = {}
        with open("result_fertility_5_ere.txt", "r") as f:
            for line in f:
                x = line.split(":")
                result[x[0].strip()] = float(x[1].strip())

        # Create a province, with regions, and buildings constraints.
        Games.instance = AttilaGame(campaign=AttilaGame.Campaign.ATTILA,
                                    faction=AttilaGame.Factions.ATT_FACT_EASTERN_ROMAN_EMPIRE,
                                    religion=AttilaGame.Religion.CHRIST_ORTHODOX)
        parser = Games.instance.get_parser()
        Games.buildings = parser.buildings
        # Games.instance.campaign = AttilaGame.Campaign.CHARLEMAGNE

        # Attila data folder
        path = parser.game_dir
        parser.parse_building_effects_junction_tables()
        parser.parse_start_pos_tsv(path)

        # Linear programming problem
        lp_problem = Problem(solver=SolverType.GOOGLE)

        # Options
        Games.USE_NAME = NameType.NAME

        for province in parser.provinces.values():
            lp_problem.reset_problem()
            lp_problem.add_province(province)
            # Filter out all buildings
            for region in province.regions:
                region.add_buildings()
                # Filter out city build below x (to force a city level)
                region.filter_city_level(4)
                region.filter_building_level(4)
                region.filter_military()
                # Necessary (for now) for Google OR-Tools to add the variables which were added lazily
                lp_problem.problem.filter_added({building.name: building for building in region.buildings})
            lp_problem.state = ProblemState.FILTERS_ADDED

            # Set province wide fertility : impacts food and GDP
            Games.fertility = 5

            # Regional constraints
            for region in province.regions:
                region.add_constraints()
            # Sanitation is regional, but requires province wide view to look at province wide effects
            province.add_sanitation_constraint()

            # Province constraints
            province.add_food_constraint()
            province.add_public_order_constraint()
            lp_problem.state = ProblemState.CONSTRAINTS_ADDED

            # GDP maximization
            lp_problem.add_objective()
            lp_problem.solve()
            self.assertEqual(result[province.get_name_output()], lp_problem.problem.get_objective())

            # Print the variables equal to 1 with their respective contribution
            # if province.print_name == "Thracia":
            #     lp_problem.print_problem_answers()
            # lp_problem.print_problem_answers()
            province.clean()
