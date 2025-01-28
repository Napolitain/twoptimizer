import pathlib

from engine.bases import ProvinceBase
from engine.building import Building
from engine.enums import Scope, EntryType
from engine.models.model import RegionType, RegionPort
from engine.models.model_attila import AttilaCampaign, AttilaFactions, AttilaRegionResources
from engine.parser.parser import Parser, parse_tsv, Faction


class ParserAttila(Parser):
    def __init__(self, campaign: AttilaCampaign, faction: AttilaFactions):
        super().__init__()
        self.game_dir = pathlib.Path("data/attila")
        self.campaign = campaign
        self.faction: AttilaFactions = faction
        self.faction_to_culture = self.parse_factions_table()

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

    def parse_buildings_culture_variants_table(self) -> None:
        path_buildings_culture_variants = self.game_dir / "building_culture_variants_table.tsv"
        data = parse_tsv(path_buildings_culture_variants)
        for building_id1, culture2, subculture3, faction_id4, building_name6, *rest in data:
            campaign_name = building_id1.split("_")[0]
            if campaign_name not in self.buildings:
                self.buildings[campaign_name] = {}
            # Filter for the campaign to optimize memory usage
            if self.campaign.value[1] in building_id1:
                # Filter for the faction to optimize memory usage
                if self.building_is_of_faction(culture2, faction_id4, subculture3):
                    self.buildings[campaign_name][building_id1] = Building(self.faction.value, building_name6)

    def building_is_of_faction(self, culture, faction_id, subculture) -> bool:
        """
        Check if the building is of the faction.
        Building is added if :
        - faction id == self.faction.value
        - faction subculture == self.faction_to_culture[self.faction.value].subculture and faction id is none
        - faction culture == self.faction.culture and faction id and subculture are none
        :param culture: culture of the building
        :param faction_id: faction id of the building
        :param subculture: subculture of the building
        :return: True if the building is of the faction, False otherwise
        """
        return faction_id == self.faction.value or (
                faction_id == "" and subculture == self.faction_to_culture[
            self.faction.value].subculture) or (
                faction_id == "" and subculture == "" and culture == self.faction_to_culture[
            self.faction.value].culture)

    def parse_building_effects_junction_tables(self):
        path_buildings = self.game_dir / "building_effects_junction_table.tsv"
        # Read file building_effects_junction_table.tsv (tabulated)
        data = parse_tsv(path_buildings)
        if len(self.buildings) == 0:
            self.parse_buildings_culture_variants_table()
        for buil in self.buildings[self.campaign.value[1]]:
            print(buil)
        for building_id, effect, scope, amount in data:
            if building_id not in self.buildings[self.campaign.value[1]]:
                continue
            scope_value = self.get_scope(scope)
            self.buildings[self.campaign.value[1]][building_id].add_effect(effect, scope_value, float(amount))

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
            region_name = self.get_entry_name(full_region_name, EntryType.REGION)
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

    def parse_factions_table(self) -> dict[str, Faction]:
        path_factions = self.game_dir / "factions_table.tsv"
        data = parse_tsv(path_factions)
        faction_to_culture = {}
        for faction_id1, _, subculture3, _, faction_name5, _, _, _, culture9, *rest in data:
            # Associate faction to culture and subculture
            faction_to_culture[faction_id1] = Faction(faction_id1, faction_name5, culture9, subculture3)
        return faction_to_culture

    def parse_cultures_subcultures_table(self) -> None:
        pass
