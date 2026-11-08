from games.tw.bases import ProvinceBase
from games.tw.building import Building
from games.tw.context import GameContext
from games.tw.entity import Entity
from games.tw.enums import Scope, get_hash_name
from games.tw.region import Region


class Province(ProvinceBase, Entity):
    """
    We need to create a Province class that contains a list of regions.
    """

    HASH_NAME = "P1"

    def __init__(self, name: str, print_name: str = "", *, context: GameContext | None = None):
        super().__init__()
        self._context = context
        self.regions = []
        self.name = name
        self.hash_name = context.next_id("P") if context is not None else get_hash_name("P")
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
        context = self.context
        if not context.legacy_effects:
            return  # Scoped constraints are installed together by Problem.
        """
        Add public order constraint to the province.
        :return:
        """
        context.solver.create_constraint(
            name=f"{self.get_name()}_Public_Order",
            variables=[
                building.public_order() * building.lp_variable for building in self.buildings()
            ],
            constraint_fn=lambda expr: expr >= 0,
        )

    def add_food_constraint(self):
        context = self.context
        if not context.legacy_effects:
            return
        """
        Add food constraint to the province.
        :return:
        """
        context.solver.create_constraint(
            name=f"{self.get_name()}_Food",
            variables=[building.food() * building.lp_variable for building in self.buildings()],
            constraint_fn=lambda expr: expr >= 0,
        )

    def add_sanitation_constraint(self):
        context = self.context
        if not context.legacy_effects:
            return
        """
        Add regional sanitation constraints using building and global effects.
        Each region needs at least one sanitation point, including province effects.
        :return:
        """
        for region in self.regions:
            if any(b.lp_variable is None for b in region.buildings):
                raise ValueError("Assign building variables before sanitation constraints")
            context.solver.create_constraint(
                name=f"{self.get_name()}_Sanitation_Constraint_{region.name}",
                variables=[
                    building.sanitation() * building.variable for building in region.buildings
                ],
                variables2=[
                    building.sanitation_scope(Scope.PROVINCE) * building.variable
                    for building in self.buildings()
                ],
                constraint_fn=lambda expr1, expr2: expr1 >= 1 - expr2,
            )

    def buildings(self) -> list[Building]:
        """
        Return all buildings in the province that are potentially built. Basically, will be all
        our LpVariables.
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
