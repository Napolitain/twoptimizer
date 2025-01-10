import abc
from collections import defaultdict
from typing import List

from pulp import LpVariable, LpInteger


class Games:
    def __init__(self):
        self.games = {}
        self.current = None


class Effect(abc.ABC):
    @abc.abstractmethod
    def gdp(self) -> float:
        pass

    @abc.abstractmethod
    def public_order(self) -> float:
        pass

    @abc.abstractmethod
    def sanitation(self) -> float:
        pass

    @abc.abstractmethod
    def food(self) -> float:
        pass


"""
A building contains effects that can be applied to a province, region, or building.
We need to create a Building class that contains a list of effects.
"""
class Building(Effect):
    def __init__(self, name: str):
        self.lp_variable = None
        self.name = name
        self.effects_to_faction = {}
        self.effects_to_province = {}
        self.effects_to_region = {}
        self.effects_to_building = {}

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return self.name == other.name

    def __repr__(self):
        return self.name

    def add_effect(self, effect: str, scope: str, amount: float):
        if scope.startswith('faction'):
            self.effects_to_faction[effect] = amount
        elif scope.startswith('province'):
            self.effects_to_province[effect] = amount
        elif scope.startswith('region'):
            self.effects_to_region[effect] = amount
        elif scope.startswith('building'):
            self.effects_to_building[effect] = amount

    def add_lp_variable(self, low: int = 0, high: int = 1, type = LpInteger):
        self.lp_variable = LpVariable(self.name, low, high, type)

    def gdp(self):
        """
        For every effects dictionaries, if it contains gdp, and it doesn't contain mod, we sum the values.
        :return: sum of gdp values
        """
        etf = sum([amount for effect, amount in self.effects_to_faction.items() if "gdp" in effect and 'mod' not in effect])
        etp = sum([amount for effect, amount in self.effects_to_province.items() if "gdp" in effect and 'mod' not in effect])
        etr = sum([amount for effect, amount in self.effects_to_region.items() if "gdp" in effect and 'mod' not in effect])
        etb = sum([amount for effect, amount in self.effects_to_building.items() if "gdp" in effect and 'mod' not in effect])
        return etf + etp + etr + etb

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
        etf = sum([amount for effect, amount in self.effects_to_faction.items() if 'sanitation' in effect])
        etp = sum([amount for effect, amount in self.effects_to_province.items() if 'sanitation' in effect])
        etr = sum([amount for effect, amount in self.effects_to_region.items() if 'sanitation' in effect])
        etb = sum([amount for effect, amount in self.effects_to_building.items() if 'sanitation' in effect])
        sanitation = etf + etp + etr + etb
        etf = sum([amount for effect, amount in self.effects_to_faction.items() if "squalor" in effect])
        etp = sum([amount for effect, amount in self.effects_to_province.items() if "squalor" in effect])
        etr = sum([amount for effect, amount in self.effects_to_region.items() if "squalor" in effect])
        etb = sum([amount for effect, amount in self.effects_to_building.items() if "squalor" in effect])
        squalor = etf + etp + etr + etb
        return sanitation - squalor

    def food(self):
        """
        For every effects dictionaries, if it contains food and production, we sum the values. If it contains food and consumption, we subtract the values.
        :return: sum of food production values minus food consumption values.
        """
        etf = sum([amount for effect, amount in self.effects_to_faction.items() if "food" in effect and 'production' in effect])
        etp = sum([amount for effect, amount in self.effects_to_province.items() if "food" in effect and 'production' in effect])
        etr = sum([amount for effect, amount in self.effects_to_region.items() if "food" in effect and 'production' in effect])
        etb = sum([amount for effect, amount in self.effects_to_building.items() if "food" in effect and 'production' in effect])
        food_production = etf + etp + etr + etb
        etf = sum([amount for effect, amount in self.effects_to_faction.items() if "food" in effect and 'consumption' in effect])
        etp = sum([amount for effect, amount in self.effects_to_province.items() if "food" in effect and 'consumption' in effect])
        etr = sum([amount for effect, amount in self.effects_to_region.items() if "food" in effect and 'consumption' in effect])
        etb = sum([amount for effect, amount in self.effects_to_building.items() if "food" in effect and 'consumption' in effect])
        food_consumption = etf + etp + etr + etb
        return food_production - food_consumption


"""
A region contains buildings.
"""
class Region(Effect):
    def __init__(self, n_buildings: int):
        self.buildings: List[Building] = []
        self.effects = defaultdict(list)

    def add_building(self, building: Building):
        self.buildings.append(building)

    def gdp(self):
        """
        For a region, we can just sum the gdp of all buildings, for now.
        :return: sum of gdp of all buildings
        """
        return sum([building.gdp() for building in self.buildings])

    def food(self):
        """
        For a region, we can just sum the food of all buildings, for now.
        :return: sum of food of all buildings
        """
        return sum([building.food() for building in self.buildings])

    def sanitation(self):
        """
        For a region, we need to make sure sanitation >= squalor in each building.
        :return: sum of sanitation of all buildings minus squalor of all buildings
        """
        return sum([building.sanitation() for building in self.buildings])

    def public_order(self):
        """
        For a region, we can just sum the public order of all buildings, for now.
        :return: sum of public order of all buildings
        """
        return sum([building.public_order() for building in self.buildings])

"""
We need to create a Province class that contains a list of regions.
"""
class Province(Effect):
    def __init__(self, n_regions: int):
        self.regions = []
        self.n_regions = n_regions

    def add_region(self, region: Region):
        self.regions.append(region)

    def gdp(self):
        """
        We want to maximize the gdp of the province.
        :return: sum of gdp of all regions
        """
        return sum([region.gdp() for region in self.regions])

    def public_order(self):
        """
        We want to satisfy the public order of the province >== x.
        With tax levels, we need to experiment different x values.
        :return: sum of public order of all regions
        """
        return sum([region.public_order() for region in self.regions])

    def food(self):
        """
        We need to satisfy the food of the province >== 0.
        :return:
        """
        return sum([region.food() for region in self.regions])

    def sanitation(self):
        """
        We need to make sure sanitation >= squalor in each region, independently.
        This method is not needed for now.
        :return:
        """
        return
