import enum
import pathlib

from engine.bases import ProvinceBase
from engine.building import Building
from engine.enums import Scope, EntryType
from engine.models.model import RegionType, RegionPort
from engine.models.model_attila import AttilaRegionResources
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
                building_name = name.lower()
                if building_name not in self.buildings[game]:
                    self.buildings[game][building_name] = Building(building_name)
                try:
                    scope_value = self.get_scope(scope)
                except ValueError:
                    continue
                self.buildings[game][building_name].add_effect(effect, scope_value, float(amount))

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

    def parse_start_pos_tsv(self, file_tsv: pathlib.Path) -> dict[str, ProvinceBase]:
        from engine.region import Region
        from engine.province import Province
        # Link region name to province name
        dictionary_regions_to_province = self.get_dictionary_regions_to_province(file_tsv)
        # Link province name to province object
        dictionary_provinces = {}
        for province_name in dictionary_regions_to_province.values():
            if province_name not in dictionary_provinces:
                dictionary_provinces[province_name] = Province(province_name)
        # Read file building_effects_junction_tables.tsv (tabulated)
        path_startpos_regions = file_tsv / "start_pos_region_slot_templates_table.tsv"
        data = parse_tsv(path_startpos_regions)
        dictionary_regions = {}
        for _, game, full_region_name, type_building, building in data:
            # Check if it is correct game
            if self.campaign.value[1] not in full_region_name or self.campaign.value[
                0] not in game:
                continue
            region_name = full_region_name
            # Province name is the regio_name mapped to the province name
            try:
                province_name = dictionary_regions_to_province[region_name]
            except KeyError:
                print(f"Region {region_name} does not have a province.")
                continue
            # If region not in dictionary, add it
            if region_name not in dictionary_regions:
                # If building contains "major", it is a major region, else minor
                if "major" in building:
                    dictionary_regions[region_name] = Region(5, region_name)
                    dictionary_regions[region_name].set_region_type(RegionType.REGION_MAJOR)
                else:
                    dictionary_regions[region_name] = Region(3, region_name)
                    dictionary_regions[region_name].set_region_type(RegionType.REGION_MINOR)
                # Add region to province
                dictionary_provinces[province_name].add_region(dictionary_regions[region_name])
            # Add resources type / port to region
            # 1. If type is primary, discard
            if type_building == "primary":
                continue
            # 2. If type is port, add port if it is not "spice".
            if type_building == "port":
                if "spice" not in building:
                    dictionary_regions[region_name].set_has_port(RegionPort.REGION_PORT)
                else:
                    dictionary_regions[region_name].set_has_ressource(AttilaRegionResources.ATTILA_REGION_SPICE)
            # 3. If type is secondary, add resource
            if type_building == "secondary":
                if "city" in building:
                    dictionary_regions[region_name].set_has_ressource(
                        AttilaRegionResources.ATTILA_REGION_CHURCH_ORTHODOX)
                else:
                    # Check if building is a resource building
                    for resource in AttilaRegionResources:
                        if resource.value in building:
                            dictionary_regions[region_name].set_has_ressource(resource)
        return dictionary_provinces
