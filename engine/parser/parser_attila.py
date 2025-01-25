import pathlib

from engine.building import Building
from engine.enums import Scope, EntryType
from engine.models.model_attila import AttilaCampaign, AttilaFactions
from engine.parser.parser import Parser, parse_tsv


class ParserAttila(Parser):
    def __init__(self, campaign: AttilaCampaign, faction: AttilaFactions):
        super().__init__()
        self.game_dir = pathlib.Path("data/attila")
        self.campaign = campaign
        self.faction = faction

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
            if self.campaign.value[1] in name:
                # building name is the name split("_") from bld to end
                try:
                    building_name = self.get_entry_name(name, EntryType.BUILDING)
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

    def get_entry_name(self, name: str, entry_type: EntryType) -> str:
        split_name = name.split("_")
        i = 0
        while i < len(split_name) and split_name[i] != entry_type.value:
            i += 1
        if i == len(split_name):
            raise ValueError(f"Entry type {entry_type.value} not found in {name}.")
        # Return everything after the entry type unless it matches any other entry type (e.g. reg, prov)
        j = i + 1
        # Matches bld, reg, if we search prov, etc...
        entries = [entry.value for entry in EntryType if entry != entry_type]
        while j < len(split_name) and split_name[j] not in entries:
            j += 1
        if j == len(split_name):
            return "_".join(split_name[i:])
        return "_".join(split_name[i:j])

    def get_dictionary_regions_to_province(self, game_dir: pathlib.Path):
        path_province_region_junctions = game_dir / "region_to_provinces_junctions_table.tsv"
        dictionary_regions_to_province = {}
        data = parse_tsv(path_province_region_junctions)
        for province_name, region_name in data:
            # Filter game
            if self.campaign.value[1] not in province_name:
                continue
            pn = self.get_entry_name(province_name, EntryType.PROVINCE)
            rn = self.get_entry_name(region_name, EntryType.REGION)
            dictionary_regions_to_province[rn] = pn
        return dictionary_regions_to_province
