import enum
import pathlib

from engine.building import Building
from engine.enums import Scope, EntryType
from engine.models.model_rome2 import Rome2Campaign, Rome2Factions
from engine.parser.parser import Parser, parse_tsv


class ParserRome2(Parser):
    def __init__(self, campaign: Rome2Campaign, faction: Rome2Factions):
        super().__init__()
        self.game_dir = pathlib.Path("data/rome2")
        self.campaign = campaign
        self.faction = faction

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

    def parse_building_effects_junction_tables(self):
        path_buildings = self.game_dir / "building_effects_junction_table.tsv"
        # Read file building_effects_junction_table.tsv (tabulated)
        data = parse_tsv(path_buildings)
        # Create a dictionary of buildings per game / DLC
        # dict{game1: set{building1, building2, ...}, game2: set{building1, building2, ...}, ...}
        for name, effect, amount, scope in data:
            game = name.split("_")[0]
            if game not in self.buildings:
                self.buildings[game] = {}
            # Filter for att and maximize only gdp for now
            if self.campaign.value[1] in name:
                # Filter only for east romans for now
                if name not in self.buildings[game]:
                    self.buildings[game][name] = Building(name)
                try:
                    scope_value = self.get_scope(scope)
                except ValueError:
                    continue
                self.buildings[game][name].add_effect(effect, scope_value, float(amount))

    def get_entry_name(self, name: str, entry_type: EntryType) -> str:
        raise NotImplementedError

    def get_dictionary_regions_to_province(self, game_dir: pathlib.Path):
        path_province_region_junctions = game_dir / "region_to_provinces_junctions_table.tsv"
        dictionary_regions_to_province = {}
        data = parse_tsv(path_province_region_junctions)
        for region_name, province_name in data:
            # Filter game
            if self.campaign.value[1] not in province_name:
                continue
            dictionary_regions_to_province[region_name] = province_name
        return dictionary_regions_to_province
