"""
A province contains n regions.
A capital and smaller settlements are regions part of a province.
A region contains buildings.

A province has public order, global economy, religion, and food, which is the total of all regions.
A region has sanitation, public order, economy, religion, and food.

We need to optimize using linear programming the economy of a province, here using PuLP.
"""

# att_effect_economy_gdp_industry
# att_bld_roman_west_city_major_1
import pathlib

from games.tw.context import GameContext
from games.tw.enums import NameType, ProblemState
from games.tw.models.game_attila import AttilaGame
from games.tw.problem import Problem

# PuLP is a linear and mixed integer programming modeler written in Python.


def main():
    context = GameContext(name_type=NameType.HASH_NAME, fertility=0)
    # Create a province, with regions, and buildings constraints.
    context.instance = AttilaGame(
        context=context,
        campaign=AttilaGame.Campaign.ATTILA,
        faction=AttilaGame.Factions.ATT_FACT_EASTERN_ROMAN_EMPIRE,
        religion=AttilaGame.Religion.CHRIST_ORTHODOX,
    )
    parser = context.current().get_parser()
    context.buildings = parser.buildings
    # context.current().campaign = AttilaGame.Campaign.CHARLEMAGNE

    # Attila data folder
    path = pathlib.Path(__file__).parent.absolute() / "data"
    parser.parse_building_effects_junction_tables()
    parser.parse_start_pos_tsv(path)

    # Linear programming problem
    lp_problem = Problem(context=context)
    # lp_problem.add_provinces()

    # Options
    lp_problem.context.name_type = NameType.HASH_NAME

    for index, province in enumerate(parser.provinces.values()):
        lp_problem.reset_problem()
        lp_problem.add_province(province)
        # Filter out all buildings
        for region in province.regions:
            region.add_buildings()
            # Filter out city build below x (to force a city level)
            region.filter_city_level(4)
            region.filter_building_level(1)
            region.filter_military()
            # Necessary (for now) for Google OR-Tools to add the variables which were added lazily
            region.filter_technologies()
            lp_problem.problem.filter_added(
                {building.name: building for building in region.buildings}
            )
        lp_problem.state = ProblemState.FILTERS_ADDED

        # Set province wide fertility : impacts food and GDP
        lp_problem.context.fertility = 0

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
        # lp_problem.print_problem_xy()
        lp_problem.solve()
        print(f"{province.get_name_output()} : {lp_problem.problem.get_objective()}")

        # Print the variables equal to 1 with their respective contribution
        if province.print_name == "Thracia" and lp_problem.context.name_type == NameType.NAME:
            lp_problem.print_problem_answers()
            lp_problem.dump("attila_problem.lp")
        if index == 0 and lp_problem.context.name_type == NameType.HASH_NAME:
            lp_problem.print_problem_answers()
            # write problem to file for debugging
            lp_problem.dump("attila_problem.lp")
            break
        # lp_problem.print_problem_answers()
        province.clean()

    print(f"Total solving time: {lp_problem.global_time / 1_000_000_000} seconds")


if __name__ == "__main__":
    main()
