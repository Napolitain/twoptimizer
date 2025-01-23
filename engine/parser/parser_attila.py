import pathlib

from engine.building import Building
from engine.enums import Scope, EntryType
from engine.filters.utils import get_entry_name
from engine.parser.parser import Parser, parse_tsv


class ParserAttila(Parser):
    def __init__(self):
        super().__init__()
        self.game_dir = pathlib.Path("data/attila")
        self.game_name = "att"
        self.faction = "romans"

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

    def parse_building_effects_junction_tables(self):
        path_buildings = self.game_dir / "building_effects_junction_table.tsv"
        # Read file building_effects_junction_table.tsv (tabulated)
        data = parse_tsv(path_buildings)
        # Create a dictionary of buildings per game / DLC
        # dict{game1: set{building1, building2, ...}, game2: set{building1, building2, ...}, ...}
        for name, effect, scope, amount in data:
            game = name.split("_")[0]
            if game not in self.buildings:
                self.buildings[game] = {}
            # Filter for att and maximize only gdp for now
            if self.game_name in name:
                # building name is the name split("_") from bld to end
                try:
                    building_name = get_entry_name(name, EntryType.BUILDING)
                except ValueError:
                    continue
                # Filter only for east romans for now
                if building_name not in self.buildings[game]:
                    self.buildings[game][building_name] = Building(building_name)
                try:
                    scope_value = self.get_scope(scope)
                except ValueError:
                    continue
                self.buildings[game][building_name].add_effect(effect, scope_value, float(amount))
