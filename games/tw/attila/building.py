from ortools.linear_solver import pywraplp

from games.tw.attila.context import AttilaContext
from games.tw.attila.entity import Entity
from games.tw.attila.enums import Scope


class Building(Entity):
    """
    A building contains effects that can be applied to a province, region, or building.
    We need to create a Building class that contains a list of effects.
    """

    def __init__(
        self,
        name: str,
        print_name: str | None = None,
        hash_name: str | None = None,
        *,
        context: AttilaContext,
    ):
        super().__init__(context=context)
        self.lp_variable: pywraplp.Variable | None = None
        self.name = name
        if hash_name is None:
            self.hash_name = context.next_id("B")
        else:
            self.hash_name = hash_name
        if print_name is None:
            self.print_name = name
        else:
            self.print_name = print_name
        self.raw_effects = {}
        self.region = None
        self.metadata = None
        self.effects_to_faction = {}
        self.effects_to_province = {}
        self.effects_to_region = {}
        self.effects_to_building = {}

    @property
    def variable(self):
        if self.lp_variable is None:
            raise ValueError("Assign a solver variable before compiling constraints")
        return self.lp_variable

    def __copy__(self):
        new_building = Building(self.name, self.print_name, self.hash_name, context=self.context)
        new_building.lp_variable = self.lp_variable
        new_building.raw_effects = self.raw_effects.copy()
        new_building.metadata = self.metadata
        new_building.effects_to_faction = self.effects_to_faction.copy()
        new_building.effects_to_province = self.effects_to_province.copy()
        new_building.effects_to_region = self.effects_to_region.copy()
        new_building.effects_to_building = self.effects_to_building.copy()
        return new_building

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return self.name == other.name

    def __repr__(self):
        return str(self)

    def __str__(self):
        return (
            f"{self.print_name}"
            ", GDP: "
            f"{self.gdp()}"
            ", Public Order: "
            f"{self.public_order()}"
            ", Sanitation: "
            f"{self.sanitation()}"
            ", Food: "
            f"{self.food()}"
        )

    def add_effect(
        self,
        effect: str,
        scope: Scope | None,
        amount: float,
        raw_scope: str | None = None,
    ):
        """
        Add an effect to the building.
        :param effect: the effect name
        :param scope: the scope of the effect
        :param amount: the amount of the effect
        :return:
        """
        if raw_scope is not None:
            self.raw_effects[(effect, raw_scope)] = amount
        if scope is None:
            return
        if scope == Scope.FACTION:
            self.effects_to_faction[effect] = amount
        elif scope == Scope.PROVINCE:
            self.effects_to_province[effect] = amount
        elif scope == Scope.REGION:
            self.effects_to_region[effect] = amount
        elif scope == Scope.BUILDING:
            self.effects_to_building[effect] = amount
        else:
            raise ValueError(f"Unknown scope: {scope}")

    def fertility(self):
        context = self.context
        if self.region is not None and self.region.fertility is not None:
            return self.region.fertility
        return context.fertility

    def gdp(self):
        from games.tw.attila.effects import base_wealth

        return base_wealth(self, self.fertility())

    def public_order(self):
        from games.tw.attila.effects import amount

        return amount(self, "public_order")

    def sanitation(self):
        from games.tw.attila.effects import Reach, amount

        return amount(self, "sanitation", (Reach.BUILDING, Reach.LOCAL)) - amount(
            self, "squalor", (Reach.BUILDING, Reach.LOCAL)
        )

    def sanitation_scope(self, scope: Scope) -> float:
        from games.tw.attila.effects import Reach, amount

        reaches = (
            (Reach.PROVINCE,)
            if scope == Scope.PROVINCE
            else (Reach.FACTION,)
            if scope == Scope.FACTION
            else (Reach.BUILDING, Reach.LOCAL)
        )
        return amount(self, "sanitation", reaches) - amount(self, "squalor", reaches)

    def food(self):
        from games.tw.attila.effects import base_food

        return base_food(self, self.fertility())
