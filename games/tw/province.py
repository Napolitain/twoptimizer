from typing import List

from games.tw.bases import ProvinceBase
from games.tw.building import Building
from games.tw.entity import Entity
from games.tw.enums import Scope, get_hash_name
from games.tw.games import Games
from games.tw.region import Region


class Province(ProvinceBase, Entity):
    """
    We need to create a Province class that contains a list of regions.
    """
    HASH_NAME = "P1"

    def __init__(self, name: str, print_name: str = ""):
        super().__init__()
        self.regions = []
        self.name = name
        self.hash_name = get_hash_name("P")
        if print_name == "":
            self.print_name = name
        else:
            self.print_name = print_name

    def add_region(self, region: Region):
        """
        Add a region to the province.
        :param region:
        :return:
        """
        self.regions.append(region)

    def add_public_order_constraint(self):
        """
        Add public order constraint to the province.
        :return:
        """
        Games.problem.create_constraint(
            name=f"{self.get_name()}_Public_Order",
            variables=[
                building.public_order() * building.lp_variable
                for building in self.buildings()
            ],
            constraint_fn=lambda expr: expr >= 0
        )

    def add_food_constraint(self):
        """
        Add food constraint to the province.
        :return:
        """
        Games.problem.create_constraint(
            name=f"{self.get_name()}_Food",
            variables=[
                building.food() * building.lp_variable
                for building in self.buildings()
            ],
            constraint_fn=lambda expr: expr >= 0
        )

    def add_sanitation_constraint(self):
        """
        Add sanitation constraint to each region in the province, using the sanitation method from the building class + global effects.
        Sum of each buildings sanitation must be greater or equal to 1, per region, including global effects. We can thus substract the global effects from 1.
        :return:
        """
        for region in self.regions:
            Games.problem.create_constraint(
                name=f"{self.get_name()}_Sanitation_Constraint_{region.name}",
                variables=[
                    building.sanitation() * building.lp_variable
                    for building in region.buildings
                ],
                variables2=[
                    building.sanitation_scope(Scope.PROVINCE) * building.lp_variable
                    for building in self.buildings()
                ],
                constraint_fn=lambda expr1, expr2: expr1 >= 1 - expr2
            )

    def buildings(self) -> List[Building]:
        """
        Return all buildings in the province that are potentially built. Basically, will be all our LpVariables.
        :return:
        """
        return [building for region in self.regions for building in region.buildings]

    def clean(self):
        """
        Clean the province memory (buildings).
        :return:
        """
        for region in self.regions:
            region.buildings = []

    def increment_hash_name(self) -> str:
        """
        Increment the hash name of the region. Must be X1, X2... Xn.
        :return:
        """
        x = Province.HASH_NAME
        split_name = x.split("P")
        split_name[1] = str(int(split_name[1]) + 1)
        Province.HASH_NAME = "P".join(split_name)
        return x
