import abc
import enum
import pathlib
from typing import List

from engine.building import Building
from engine.enums import EntryType, Scope
from engine.games import Games
from engine.utils import get_entry_name


class Parser(abc.ABC):
    @abc.abstractmethod
    def get_scope(self, scope: str) -> enum.Enum:
        """
        Classify the scope of the effect.
        :param scope: scope of the effect
        :return: enum of the scope
        """
        pass

    @abc.abstractmethod
    def get_building_effects_junction_tables(self) -> None:
        """
        Get buildings effects from building_effects_junction_tables.tsv
        :return:
        """
        pass


def parse_tsv(path_buildings: pathlib.Path) -> List[List[str]]:
    """
    Parse a tsv file.
    :param path_buildings: path to the file
    :return: data as a list of lists
    """
    with open(path_buildings, 'r') as file:
        data = file.read()
        data = data.split('\n')
        data = [i.split('\t') for i in data]
    return data


class AttilaGame(enum.Enum):
    ATTILA = "att"
    LAST_ROMAN = "bel"
    CHARLEMAGNE = "cha"


class ParserAttila(Parser):
    def __init__(self):
        self.game_dir = pathlib.Path("data/attila")
        self.game_name = "att"
        self.faction = "romans"

    def set_game(self, game: AttilaGame):
        self.game_name = game.value

    def get_scope(self, scope: str) -> Scope:
        if scope.startswith('faction'):
            return Scope.FACTION
        elif scope.startswith('province'):
            return Scope.PROVINCE
        elif scope.startswith('region'):
            return Scope.REGION
        elif scope.startswith('building'):
            return Scope.BUILDING
        raise ValueError(f"Scope {scope} not found.")

    def get_building_effects_junction_tables(self):
        path_buildings = self.game_dir / "building_effects_junction_tables.tsv"
        # Read file building_effects_junction_tables.tsv (tabulated)
        data = parse_tsv(path_buildings)
        # Create a dictionary of buildings per game / DLC
        # dict{game1: set{building1, building2, ...}, game2: set{building1, building2, ...}, ...}
        for name, effect, scope, amount in data:
            game = name.split("_")[0]
            if game not in Games.buildings:
                Games.buildings[game] = {}
            # Filter for att and maximize only gdp for now
            if self.game_name in name:
                # building name is the name split("_") from bld to end
                try:
                    building_name = get_entry_name(name, EntryType.BUILDING)
                except ValueError:
                    continue
                # Filter only for east romans for now
                if building_name not in Games.buildings[game]:
                    Games.buildings[game][building_name] = Building(building_name)
                try:
                    scope_value = self.get_scope(scope)
                except ValueError:
                    continue
                Games.buildings[game][building_name].add_effect(effect, scope_value, float(amount))


class ParserRome2(Parser):
    def __init__(self):
        self.game_dir = pathlib.Path("data/rome2")
        self.game_name = "rom"

    def get_scope(self, scope: str) -> enum.Enum:
        if "faction" in scope:
            return Scope.FACTION
        elif "province" in scope:
            return Scope.PROVINCE
        elif "region" in scope:
            return Scope.REGION
        elif "building" in scope:
            return Scope.BUILDING
        raise ValueError(f"Scope {scope} not found.")

    def get_building_effects_junction_tables(self):
        path_buildings = self.game_dir / "building_effects_junction_tables.tsv"
        # Read file building_effects_junction_tables.tsv (tabulated)
        data = parse_tsv(path_buildings)
        # Create a dictionary of buildings per game / DLC
        # dict{game1: set{building1, building2, ...}, game2: set{building1, building2, ...}, ...}
        for name, effect, amount, scope in data:
            game = name.split("_")[0]
            if game not in Games.buildings:
                Games.buildings[game] = {}
            # Filter for att and maximize only gdp for now
            if "att" in name:
                # building name is the name split("_") from bld to end
                try:
                    building_name = get_entry_name(name, EntryType.BUILDING)
                except ValueError:
                    continue
                # Filter only for east romans for now
                if building_name not in Games.buildings[game]:
                    Games.buildings[game][building_name] = Building(building_name)
                try:
                    scope_value = self.get_scope(scope)
                except ValueError:
                    continue
                Games.buildings[game][building_name].add_effect(effect, scope_value, float(amount))
