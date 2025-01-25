from typing import List

from pulp import lpSum

from engine.bases import ProvinceBase
from engine.building import Building
from engine.enums import Scope
from engine.games import Games
from engine.region import Region


class Province(ProvinceBase):
    """
    We need to create a Province class that contains a list of regions.
    """

    def __init__(self, name: str):
        self.regions = []
        self.name = name

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
        Games.problem += lpSum(
            building.public_order() * building.lp_variable
            for building in self.buildings()
        ) >= 0, f"{self.name}_Public_Order_Constraint"

    def add_food_constraint(self):
        """
        Add food constraint to the province.
        :return:
        """
        Games.problem += lpSum(
            building.food() * building.lp_variable
            for building in self.buildings()
        ) >= 0, f"{self.name}_Food_Constraint"

    def add_sanitation_constraint(self):
        """
        Add sanitation constraint to each region in the province, using the sanitation method from the building class + global effects.
        Sum of each buildings sanitation must be greater or equal to 1, per region, including global effects. We can thus substract the global effects from 1.
        :return:
        """
        for region in self.regions:
            Games.problem += lpSum(
                building.sanitation() * building.lp_variable
                for building in region.buildings
            ) >= 1 - lpSum(
                building.sanitation_scope(Scope.PROVINCE) * building.lp_variable
                for building in self.buildings()
            ), f"{self.name}_Sanitation_Constraint_{region.name}"

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
