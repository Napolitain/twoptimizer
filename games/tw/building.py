from ortools.linear_solver import pywraplp
from pulp import LpVariable

from games.tw.context import GameContext
from games.tw.effect import Effect
from games.tw.entity import Entity
from games.tw.enums import Scope
from games.tw.models.model_attila import AttilaCampaign


class Building(Effect, Entity):
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
        context: GameContext,
    ):
        super().__init__(context=context)
        self.lp_variable: pywraplp.Variable | LpVariable | None = None
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

    def _use_scoped_effects(self):
        context = self.context
        campaign = getattr(context.instance, "campaign", None)
        return not context.legacy_effects and (
            campaign is None or isinstance(campaign, AttilaCampaign)
        )

    def gdp(self):
        if self._use_scoped_effects():
            from games.tw.attila.effects import base_wealth

            return base_wealth(self, self.fertility())
        return self._legacy_gdp()

    def fertility(self):
        context = self.context
        if self.region is not None and self.region.fertility is not None:
            return self.region.fertility
        return context.fertility

    def _legacy_gdp(self):
        """
        Calculate the total GDP by summing GDP values from effects,
        adjusted for fertility where applicable.
        :return: total GDP value.
        """
        context = self.context
        game_filter = context.current().get_filter()

        def calculate_gdp(include_fertility=False):
            sources = [
                self.effects_to_faction,
                self.effects_to_province,
                self.effects_to_region,
                self.effects_to_building,
            ]
            gdp_sum = sum(
                amount
                for source in sources
                for effect, amount in source.items()
                if game_filter.effect_is_gdp(effect, include_fertility)
            )
            return gdp_sum * (context.fertility if include_fertility else 1)

        base_gdp = calculate_gdp()
        fertility_gdp = calculate_gdp(include_fertility=True)

        return base_gdp + fertility_gdp

    def public_order(self):
        if self._use_scoped_effects():
            from games.tw.attila.effects import amount

            return amount(self, "public_order")
        return self._legacy_public_order()

    def _legacy_public_order(self):
        """
        For every effects dictionaries, if it contains public_order, we sum the values.
        :return: sum of public_order values
        """
        etf = sum(
            [
                amount
                for effect, amount in self.effects_to_faction.items()
                if "public_order" in effect
            ]
        )
        etp = sum(
            [
                amount
                for effect, amount in self.effects_to_province.items()
                if "public_order" in effect
            ]
        )
        etr = sum(
            [
                amount
                for effect, amount in self.effects_to_region.items()
                if "public_order" in effect
            ]
        )
        etb = sum(
            [
                amount
                for effect, amount in self.effects_to_building.items()
                if "public_order" in effect
            ]
        )
        return etf + etp + etr + etb

    def sanitation(self):
        if self._use_scoped_effects():
            from games.tw.attila.effects import Reach, amount

            return amount(self, "sanitation", (Reach.BUILDING, Reach.LOCAL)) - amount(
                self, "squalor", (Reach.BUILDING, Reach.LOCAL)
            )
        return self._legacy_sanitation()

    def _legacy_sanitation(self):
        """
        For every effects dictionaries, if it contains sanitation, we sum the values.
        If it contains squalor, we subtract the values.
        :return: sum of sanitation values minus squalor values
        """
        etr = sum(
            [
                amount
                for effect, amount in self.effects_to_region.items()
                if "sanitation_buildings" in effect
            ]
        )
        etb = sum(
            [
                amount
                for effect, amount in self.effects_to_building.items()
                if "sanitation_buildings" in effect
            ]
        )
        sanitation = etr + etb
        etr = sum(
            [amount for effect, amount in self.effects_to_region.items() if "squalor" in effect]
        )
        etb = sum(
            [amount for effect, amount in self.effects_to_building.items() if "squalor" in effect]
        )
        squalor = etr + etb
        # Province scope will be handled in province class.
        return sanitation - squalor

    def sanitation_scope(self, scope: Scope) -> float:
        if self._use_scoped_effects():
            from games.tw.attila.effects import Reach, amount

            reaches = (
                (Reach.PROVINCE,)
                if scope == Scope.PROVINCE
                else (Reach.FACTION,)
                if scope == Scope.FACTION
                else (Reach.BUILDING, Reach.LOCAL)
            )
            return amount(self, "sanitation", reaches) - amount(self, "squalor", reaches)
        return self._legacy_sanitation_scope(scope)

    def _legacy_sanitation_scope(self, scope: Scope) -> float:
        """
        For every effects dictionaries, if it contains sanitation, we sum the values.
        :param scope: Scope of the sanitation.
        :return: sum of sanitation values
        """
        if scope == Scope.FACTION:
            sanitation = sum(
                [
                    amount
                    for effect, amount in self.effects_to_faction.items()
                    if "sanitation_buildings" in effect
                ]
            )
            squalor = sum(
                [
                    amount
                    for effect, amount in self.effects_to_faction.items()
                    if "squalor" in effect
                ]
            )
            return sanitation - squalor
        elif scope == Scope.PROVINCE:
            sanitation = sum(
                [
                    amount
                    for effect, amount in self.effects_to_province.items()
                    if "sanitation_buildings" in effect
                ]
            )
            squalor = sum(
                [
                    amount
                    for effect, amount in self.effects_to_province.items()
                    if "squalor" in effect
                ]
            )
            return sanitation - squalor
        else:
            sanitation = sum(
                [
                    amount
                    for effect, amount in self.effects_to_region.items()
                    if "sanitation_buildings" in effect
                ]
            )
            squalor = sum(
                [amount for effect, amount in self.effects_to_region.items() if "squalor" in effect]
            )
            sanitation += sum(
                [
                    amount
                    for effect, amount in self.effects_to_building.items()
                    if "sanitation_buildings" in effect
                ]
            )
            squalor += sum(
                [
                    amount
                    for effect, amount in self.effects_to_building.items()
                    if "squalor" in effect
                ]
            )
            return sanitation - squalor

    def food(self):
        if self._use_scoped_effects():
            from games.tw.attila.effects import base_food

            return base_food(self, self.fertility())
        return self._legacy_food()

    def _legacy_food(self):
        """
        Calculate the net food production by summing food production values
        (adjusted for fertility where applicable) and subtracting food consumption values.
        :return: net food production.
        """
        context = self.context

        def calculate_food(effect_type, include_fertility=False):
            sources = [
                self.effects_to_faction,
                self.effects_to_province,
                self.effects_to_region,
                self.effects_to_building,
            ]
            food_sum = sum(
                amount
                for source in sources
                for effect, amount in source.items()
                if "food" in effect
                and effect_type in effect
                and (include_fertility == ("fertility" in effect))
            )
            return food_sum * (context.fertility if include_fertility else 1)

        food_production = calculate_food("production") + calculate_food(
            "production", include_fertility=True
        )
        food_consumption = calculate_food("consumption")

        return food_production - food_consumption
