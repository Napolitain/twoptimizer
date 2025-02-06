from engine.effect import Effect
from engine.entity import Entity
from engine.enums import Scope
from engine.games import Games


class Building(Effect, Entity):
    """
    A building contains effects that can be applied to a province, region, or building.
    We need to create a Building class that contains a list of effects.
    """
    HASH_NAME = "B1"

    def __init__(self, name: str, print_name: str = None, hash_name: str = None):
        super().__init__()
        self.lp_variable = None
        self.name = name
        if hash_name is None:
            self.hash_name = self.increment_hash_name()
        else:
            self.hash_name = hash_name
        if print_name is None:
            self.print_name = name
        else:
            self.print_name = print_name
        self.effects_to_faction = {}
        self.effects_to_province = {}
        self.effects_to_region = {}
        self.effects_to_building = {}

    def __copy__(self):
        new_building = Building(self.name, self.print_name, self.hash_name)
        new_building.lp_variable = self.lp_variable
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
        return [self.print_name, self.gdp(), self.public_order(), self.sanitation(), self.food()]

    def __str__(self):
        return f"{self.print_name}, GDP: {self.gdp()}, Public Order: {self.public_order()}, Sanitation: {self.sanitation()}, Food: {self.food()}"

    def add_effect(self, effect: str, scope: Scope, amount: float):
        """
        Add an effect to the building.
        :param effect: the effect name
        :param scope: the scope of the effect
        :param amount: the amount of the effect
        :return:
        """
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

    def gdp(self):
        """
        Calculate the total GDP by summing GDP values from effects,
        adjusted for fertility where applicable.
        :return: total GDP value.
        """

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
                if Games.instance.get_filter().effect_is_gdp(effect, include_fertility)
            )
            return gdp_sum * (Games.fertility if include_fertility else 1)

        base_gdp = calculate_gdp()
        fertility_gdp = calculate_gdp(include_fertility=True)

        return base_gdp + fertility_gdp

    def public_order(self):
        """
        For every effects dictionaries, if it contains public_order, we sum the values.
        :return: sum of public_order values
        """
        etf = sum([amount for effect, amount in self.effects_to_faction.items() if "public_order" in effect])
        etp = sum([amount for effect, amount in self.effects_to_province.items() if "public_order" in effect])
        etr = sum([amount for effect, amount in self.effects_to_region.items() if "public_order" in effect])
        etb = sum([amount for effect, amount in self.effects_to_building.items() if "public_order" in effect])
        return etf + etp + etr + etb

    def sanitation(self):
        """
        For every effects dictionaries, if it contains sanitation, we sum the values.
        If it contains squalor, we subtract the values.
        :return: sum of sanitation values minus squalor values
        """
        etr = sum([amount for effect, amount in self.effects_to_region.items() if 'sanitation_buildings' in effect])
        etb = sum([amount for effect, amount in self.effects_to_building.items() if 'sanitation_buildings' in effect])
        sanitation = etr + etb
        etr = sum([amount for effect, amount in self.effects_to_region.items() if "squalor" in effect])
        etb = sum([amount for effect, amount in self.effects_to_building.items() if "squalor" in effect])
        squalor = etr + etb
        # Province scope will be handled in province class.
        return sanitation - squalor

    def sanitation_scope(self, scope: Scope) -> float:
        """
        For every effects dictionaries, if it contains sanitation, we sum the values.
        :param scope: Scope of the sanitation.
        :return: sum of sanitation values
        """
        if scope == Scope.FACTION:
            sanitation = sum(
                [amount for effect, amount in self.effects_to_faction.items() if 'sanitation_buildings' in effect])
            squalor = sum([amount for effect, amount in self.effects_to_faction.items() if "squalor" in effect])
            return sanitation - squalor
        elif scope == Scope.PROVINCE:
            sanitation = sum(
                [amount for effect, amount in self.effects_to_province.items() if 'sanitation_buildings' in effect])
            squalor = sum([amount for effect, amount in self.effects_to_province.items() if "squalor" in effect])
            return sanitation - squalor
        else:
            sanitation = sum(
                [amount for effect, amount in self.effects_to_region.items() if 'sanitation_buildings' in effect])
            squalor = sum([amount for effect, amount in self.effects_to_region.items() if "squalor" in effect])
            sanitation += sum(
                [amount for effect, amount in self.effects_to_building.items() if 'sanitation_buildings' in effect])
            squalor += sum([amount for effect, amount in self.effects_to_building.items() if "squalor" in effect])
            return sanitation - squalor

    def food(self):
        """
        Calculate the net food production by summing food production values
        (adjusted for fertility where applicable) and subtracting food consumption values.
        :return: net food production.
        """

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
                if "food" in effect and effect_type in effect and (include_fertility == ("fertility" in effect))
            )
            return food_sum * (Games.fertility if include_fertility else 1)

        food_production = calculate_food("production") + calculate_food("production", include_fertility=True)
        food_consumption = calculate_food("consumption")

        return food_production - food_consumption

    def increment_hash_name(self) -> str:
        """
        Increment the hash name of the region. Must be X1, X2... Xn.
        :return:
        """
        x = Building.HASH_NAME
        split_name = x.split("B")
        split_name[1] = str(int(split_name[1]) + 1)
        Building.HASH_NAME = "B".join(split_name)
        return x
