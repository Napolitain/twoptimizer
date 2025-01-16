# att_effect_economy_gdp_industry
# att_bld_roman_west_city_major_1

# PuLP is an linear and mixed integer programming modeler written in Python.
from pulp import *

from twoptimizer import Building, Province, Region, RegionAttila, RegionHasPort, RegionHasRessource, RegionType, Games, \
    AttilaFactions, Problem

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
    # Read file data.tsv (tabulated)
    with open('data.tsv', 'r') as file:
        data = file.read()
        data = data.split('\n')
        data = [i.split('\t') for i in data]

    # Create a dictionary of buildings per game / DLC
    # dict{game1: set{building1, building2, ...}, game2: set{building1, building2, ...}, ...}
    for name, effect, scope, amount, _, _ in data:
        game = name.split("_")[0]
        if game not in Games.buildings:
            Games.buildings[game] = {}
        # Filter for att and maximize only gdp for now
        if "att" in name:
            # Filter only for east romans for now
            if name not in Games.buildings[game]:
                Games.buildings[game][name] = Building(name)
            Games.buildings[game][name].add_effect(effect, scope, float(amount))

    # Create a province, with regions, and buildings constraints.
    Games.faction = AttilaFactions.ATTILA_ROMAN_EAST

    thrace = Province(3, "Thrace")
    constantinople = Region(6, "Constantinople")
    marcianopolis = Region(4, "Marcianopolis")
    trimontium = Region(4, "Trimontium")

    thrace.add_region(constantinople)
    thrace.add_region(marcianopolis)
    thrace.add_region(trimontium)

    macedonia = Province(3, "Macedonia")
    thessalonica = Region(6, "Thessalonica")
    corinthus = Region(4, "Corinthus")
    dyrrachium = Region(4, "Dyrrachium")
    macedonia.add_region(thessalonica)
    macedonia.add_region(corinthus)
    macedonia.add_region(dyrrachium)

    # Linear programming problem
    # Create a gdp maximization problem
    lp_problem = Problem()
    # lp_problem.add_province(thrace)
    # constantinople.add_buildings(RegionAttila(RegionType.ATTILA_REGION_MAJOR, RegionHasPort.ATTILA_REGION_PORT,
    #                                           RegionHasRessource.ATTILA_REGION_CHURCH_ORTHODOX))
    # marcianopolis.add_buildings(RegionAttila(RegionType.ATTILA_REGION_MINOR, RegionHasPort.ATTILA_REGION_NO_PORT,
    #                                          RegionHasRessource.ATTILA_REGION_NO_RESSOURCE))
    # trimontium.add_buildings(RegionAttila(RegionType.ATTILA_REGION_MINOR, RegionHasPort.ATTILA_REGION_NO_PORT,
    #                                       RegionHasRessource.ATTILA_REGION_GOLD))
    lp_problem.add_province(macedonia)
    thessalonica.add_buildings(RegionAttila(RegionType.ATTILA_REGION_MAJOR, RegionHasPort.ATTILA_REGION_PORT,
                                            RegionHasRessource.ATTILA_REGION_NO_RESSOURCE))
    corinthus.add_buildings(RegionAttila(RegionType.ATTILA_REGION_MINOR, RegionHasPort.ATTILA_REGION_PORT,
                                         RegionHasRessource.ATTILA_REGION_NO_RESSOURCE))
    dyrrachium.add_buildings(RegionAttila(RegionType.ATTILA_REGION_MINOR, RegionHasPort.ATTILA_REGION_PORT,
                                          RegionHasRessource.ATTILA_REGION_OLIVES))

    for province in lp_problem.provinces:
        # Filter out all buildings
        for region in province.regions:
            # Filter out city build below x (to force a city level)
            region.filter_city_level(4)

        # Set province wide fertility : impacts food and GDP
        province.set_fertility(1)

        # Regional constraints
        for region in province.regions:
            region.add_constraints()
        # Sanitation is regional, but requires province wide view to look at province wide effects
        province.add_sanitation_constraint()

        # Province constraints
        province.add_food_constraint()
        province.add_public_order_constraint()

    # Objective function: Maximize GDP on LpVariables (buildings) that are remaining
    # After this, we CANNOT change the buildings anymore, because LpVariables are already factored in the objective function.
    Games.problem += lpSum(
        building.gdp() * building.lp_variable
        for building in lp_problem.buildings()
    ), "Total_GDP"

    # Solve the problem
    status = Games.problem.solve()

    # Print number of variables, constraints, and status of the solution
    print(
        f"Number of variables: {len(Games.problem.variables())}\nNumber of constraints: {len(Games.problem.constraints)}\n")

    # Print the variables equal to 1 with their respective contribution
    for v in Games.problem.variables():
        # name key is the building name split("_") from 1 to end joined by _
        name = "_".join(v.name.split("_")[1:])
        if v.varValue == 1:
            print(v.name, "=", Games.buildings["att"][name])
