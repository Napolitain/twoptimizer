# att_effect_economy_gdp_industry
# att_bld_roman_west_city_major_1

# PuLP is an linear and mixed integer programming modeler written in Python.
from pulp import *

from twoptimizer import Building, Province, Region

"""
A province contains n regions.
A capital and smaller settlements are regions part of a province.
A region contains buildings.

A province has public order, global economy, religion, and food, which is the total of all regions.
A region has sanitation, public order, economy, religion, and food.

We need to optimize using linear programming the economy of a province, here using PuLP.
"""
from collections import defaultdict

"""
('cha_effect_imperium', 'faction_to_faction_own_unseen', '10.0000'), ('att_effect_economy_gdp_trade_local', 'building_to_building_own', '200.0000'), ('att_effect_public_order_base', 'province_to_province_own', '2.0000'), ('att_effect_region_resource_wine_production', 'building_to_building_own', '10.0000'), ('att_effect_economy_gdp_trade_local', 'building_to_building_own', '300.0000'), ('att_effect_public_order_base', 'province_to_province_own', '4.0000'), ('att_effect_region_resource_wine_production', 'building_to_building_own', '15.0000'), ('att_effect_economy_gdp_trade_local', 'building_to_building_own', '400.0000'), ('att_effect_public_order_base', 'province_to_province_own', '6.0000'), ('att_effect_region_resource_wine_production', 'building_to_building_own', '20.0000'), ('att_effect_economy_gdp_trade_local', 'building_to_building_own', '200.0000'), ('att_effect_province_growth_building', 'province_to_province_own', '2.0000'), ('att_effect_economy_gdp_trade_local', 'building_to_building_own', '300.0000'), ('att_effect_province_growth_building', 'province_to_province_own', '4.0000'), ('att_effect_economy_gdp_trade_local', 'building_to_building_own', '400.0000'), ('att_effect_province_growth_building', 'province_to_province_own', '6.0000'), ('att_effect_economy_gdp_mod_industry', 'province_to_region_own', '10.0000'), ('att_effect_region_resource_wood_production', 'building_to_building_own', '10.0000'), ('att_effect_economy_gdp_mod_industry', 'province_to_region_own', '20.0000'), ('att_effect_region_resource_wood_production', 'building_to_building_own', '15.0000'), ('att_effect_economy_gdp_mod_industry', 'province_to_region_own', '30.0000'), ('att_effect_region_resource_wood_production', 'building_to_building_own', '20.0000')]})
"""


if __name__ == '__main__':
    # Read file data.tsv (tabulated)
    with open('data.tsv', 'r') as file:
        data = file.read()
        data = data.split('\n')
        data = [i.split('\t') for i in data]

    # dict{game1: set{building1, building2, ...}, game2: set{building1, building2, ...}, ...}
    games = {}
    for name, effect, scope, amount, _, _ in data:
        game = name.split("_")[0]
        if game not in games:
            games[game] = {}
        # Filter for att and maximize only gdp for now
        if "att" in name:
            # Filter only for east romans for now
            if ("roman" in name and "west" not in name) or ("orthodox" in name) or ("all" in name):
                if name not in games[game]:
                    games[game][name] = Building(name)
                games[game][name].add_effect(effect, scope, float(amount))

    # PuLP model
    # Create a gdp maximization problem
    problem = LpProblem("GDP Maximization", LpMaximize)
    # Constraint: Maximum number of buildings to select
    max_buildings = 6

    # Create decision variables and include mandatory building condition
    for building in games["att"].values():
        if "att_bld_roman_east_city_major_4" in building.name:
            # Mandatory building
            building.add_lp_variable(1, 1, LpInteger)
        else:
            # Optional building
            building.add_lp_variable(0, 1, LpInteger)

    thrace = Province(3)
    constantinople = Region(6)
    marcianopolis = Region(4)
    trimontium = Region(4)

    thrace.add_region(constantinople)
    thrace.add_region(marcianopolis)
    thrace.add_region(trimontium)


    # Objective function: Maximize GDP
    problem += lpSum(
        building.gdp() * building.lp_variable
        for building in games["att"].values()
    ), "Total_GDP"

    # Constraint: Maximum number of buildings (excluding mandatory one)
    problem += (
        lpSum(building.lp_variable for building in games["att"].values() if "att_bld_roman_east_city_major_4" not in building.name)
        <= max_buildings - 1,
        "Max_Optional_Buildings"
    )

    # Solve the problem
    problem.solve()

    # Print the variables equal to 1 with their respective contribution
    for v in problem.variables():
        if v.varValue == 1:
            print(v.name, "=", games["att"][v.name].gdp())

