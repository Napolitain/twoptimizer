from pathlib import Path

from games.tw.building import Building
from games.tw.context import GameContext
from games.tw.enums import EntryType, Scope
from games.tw.models.model import EntryName, FullEntryName
from games.tw.models.model_rome2 import Rome2Campaign, Rome2Factions
from games.tw.parser.parser import Faction, Parser, parse_tsv


class ParserRome2(Parser):
    def __init__(self, campaign: Rome2Campaign, faction: Rome2Factions, *, context: GameContext):
        super().__init__(context=context)
        # Resolve bundled data relative to the package for installed-wheel support.
        self.game_dir = Path(__file__).resolve().parents[1] / "rome2" / "data"
        self.campaign = campaign
        self.faction = faction
        self.faction_to_culture = self.parse_factions_table()

    def get_scope(self, scope: str) -> Scope:
        if "faction" in scope:
            return Scope.FACTION
        elif "province" in scope:
            return Scope.PROVINCE
        elif "region" in scope:
            return Scope.REGION
        elif "building" in scope:
            return Scope.BUILDING
        raise ValueError(f"Scope {scope} not found.")

    def parse_buildings_culture_variants_table(self) -> None:
        pass

    def parse_cultures_subcultures_table(self) -> None:
        pass

    def parse_factions_table(self) -> dict[str, Faction]:
        return {}

    def process_port_region(self, region, building):
        pass

    def process_secondary_region(self, region, building):
        pass

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
                building_name = name.lower()
                if building_name not in self.buildings[game]:
                    self.buildings[game][building_name] = Building(
                        building_name, context=self.context
                    )
                try:
                    scope_value = self.get_scope(scope)
                except ValueError:
                    continue
                self.buildings[game][building_name].add_effect(effect, scope_value, float(amount))

    def get_entry_name(self, full_name: FullEntryName, entry_type: EntryType) -> EntryName:
        raise NotImplementedError
