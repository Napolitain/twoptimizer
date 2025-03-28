# att_effect_economy_gdp_industry
# att_bld_roman_west_city_major_1
import pathlib

from pulp import value

from engine.enums import ProblemState
from engine.games import Games
from engine.models.game_rome2 import Rome2Game
from engine.problem import Problem

# PuLP is a linear and mixed integer programming modeler written in Python.

"""
A province contains n regions.
A capital and smaller settlements are regions part of a province.
A region contains buildings.

A province has public order, global economy, religion, and food, which is the total of all regions.
A region has sanitation, public order, economy, religion, and food.

We need to optimize using linear programming the economy of a province, here using PuLP.
"""

"""
('cha_effect_imperium', 'faction_to_faction_own_unseen', '10.0000'), ('att_effect_economy_gdp_trade_local', 'building_to_building_own', '200.0000'), ('att_effect_public_order_base', 'province_to_province_own', '2.0000'), ('att_effect_region_resource_wine_production', 'building_to_building_own', '10.0000'), ('att_effect_economy_gdp_trade_local', 'building_to_building_own', '300.0000'), ('att_effect_public_order_base', 'province_to_province_own', '4.0000'), ('att_effect_region_resource_wine_production', 'building_to_building_own', '15.0000'), ('att_effect_economy_gdp_trade_local', 'building_to_building_own', '400.0000'), ('att_effect_public_order_base', 'province_to_province_own', '6.0000'), ('att_effect_region_resource_wine_production', 'building_to_building_own', '20.0000'), ('att_effect_economy_gdp_trade_local', 'building_to_building_own', '200.0000'), ('att_effect_province_growth_building', 'province_to_province_own', '2.0000'), ('att_effect_economy_gdp_trade_local', 'building_to_building_own', '300.0000'), ('att_effect_province_growth_building', 'province_to_province_own', '4.0000'), ('att_effect_economy_gdp_trade_local', 'building_to_building_own', '400.0000'), ('att_effect_province_growth_building', 'province_to_province_own', '6.0000'), ('att_effect_economy_gdp_mod_industry', 'province_to_region_own', '10.0000'), ('att_effect_region_resource_wood_production', 'building_to_building_own', '10.0000'), ('att_effect_economy_gdp_mod_industry', 'province_to_region_own', '20.0000'), ('att_effect_region_resource_wood_production', 'building_to_building_own', '15.0000'), ('att_effect_economy_gdp_mod_industry', 'province_to_region_own', '30.0000'), ('att_effect_region_resource_wood_production', 'building_to_building_own', '20.0000')]})
"""

if __name__ == '__main__':
    # Create a province, with regions, and buildings constraints.
    Games.instance = Rome2Game(campaign=Rome2Game.Campaign.ROME, faction=Rome2Game.Factions.ROM_ROME)
    Games.buildings = Games.instance.parser.buildings
    # Games.instance.campaign = AttilaGame.Campaign.CHARLEMAGNE

    # Attila data folder
    path = pathlib.Path(__file__).parent.absolute() / "data" / "rome2"
    Games.instance.parser.parse_building_effects_junction_tables()

    # Linear programming problem
    lp_problem = Problem()
    lp_problem.add_provinces(path)

    for province in lp_problem.provinces:
        lp_problem.reset_problem()
        # Filter out all buildings
        for region in province.regions:
            region.add_buildings()
            # Filter out city build below x (to force a city level)
            region.filter_city_level(4)
            region.filter_building_level(4)
            region.filter_military()
            lp_problem.state = ProblemState.FILTERS_ADDED

        # Set province wide fertility : impacts food and GDP
        Games.fertility = 5

        # Regional constraints
        for region in province.regions:
            region.add_constraints()
        # Sanitation is regional, but requires province wide view to look at province wide effects
        # province.add_sanitation_constraint()

        # Province constraints
        province.add_food_constraint()
        province.add_public_order_constraint()
        lp_problem.state = ProblemState.CONSTRAINTS_ADDED

        # GDP maximization
        lp_problem.add_objective()
        # lp_problem.print_problem_xy()
        lp_problem.solve()
        print(f"{province.name} : {value(lp_problem.problem.objective)}")

        # Print the variables equal to 1 with their respective contribution
        # lp_problem.print_problem_answers()
        province.clean()

    print(f"Total solving time: {lp_problem.global_time / 1_000_000_000} seconds")
