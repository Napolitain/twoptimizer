import pathlib

from engine.building import Building
from engine.enums import Scope, EntryType
from engine.models.game_attila import AttilaReligion
from engine.models.model import RegionType, RegionPort
from engine.models.model_attila import AttilaCampaign, AttilaFactions, AttilaRegionResources
from engine.parser.parser import Parser, parse_tsv, Faction


class ParserAttila(Parser):
    def __init__(self, campaign: AttilaCampaign, faction: AttilaFactions,
                 religion: AttilaReligion = AttilaReligion.CHRIST_ORTHODOX):
        super().__init__()
        self.game_dir = pathlib.Path("data/attila")
        self.campaign = campaign
        self.faction: AttilaFactions = faction
        self.religion = religion
        self.faction_to_culture = self.parse_factions_table()

    def parse_provinces(self):
        from engine.province import Province
        data = parse_tsv(self.game_dir / "provinces.tsv")
        for name, print_name in data:
            if self.campaign.value[1] not in name:
                continue
            self.provinces[name] = Province(name, print_name)

    def parse_regions(self):
        from engine.region import Region
        data = parse_tsv(self.game_dir / "regions.tsv")
        for name, print_name in data:
            if self.campaign.value[1] not in name:
                continue
            self.regions[name] = Region(name, print_name)

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
        if entry_type == EntryType.BUILDING:
            # Check if a_b_c, b_c, c is in buildings list, and return the name if it matches
            for i in range(len(split_name)):
                if "_".join(split_name[i:]) in self.buildings[self.campaign.value[1]]:
                    return "_".join(split_name[i:])
            raise ValueError(f"Entry type {entry_type.value} not found in {name}.")
        else:
            # TODO: remove that part eventually, to be replaced with full id and id to name matching, like up
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
            dictionary_regions_to_province[region_name] = province_name
        return dictionary_regions_to_province

    def parse_buildings_culture_variants_table(self) -> None:
        # TODO: Fix religion buildings
        path_buildings_culture_variants = self.game_dir / "building_culture_variants_table.tsv"
        data = parse_tsv(path_buildings_culture_variants)
        for building_id1, culture2, subculture3, faction_id4, building_name6, *rest in data:
            campaign_name = building_id1.split("_")[0]
            if campaign_name not in self.buildings:
                self.buildings[campaign_name] = {}
            # Filter for the campaign to optimize memory usage
            if self.campaign.value[1] in building_id1:
                # Filter for the faction to optimize memory usage
                if self.building_is_of_faction(culture2, faction_id4, subculture3) or self.building_is_of_religion(
                        building_id1):
                    self.buildings[campaign_name][building_id1] = Building(building_id1, building_name6)

    def building_is_of_religion(self, building_id1):
        if "religion" in building_id1:
            return self.religion == AttilaReligion.ANY or self.religion.value in building_id1
        return False

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

    def parse_start_pos_tsv(self, file_tsv: pathlib.Path):
        self.parse_provinces()
        self.parse_regions()
        # Link region name to province name
        dictionary_regions_to_province = self.get_dictionary_regions_to_province(file_tsv)
        # Link province name to province object
        for region_name, province_name in dictionary_regions_to_province.items():
            self.provinces[province_name].add_region(self.regions[region_name])
        # Read file building_effects_junction_tables.tsv (tabulated)
        path_startpos_regions = file_tsv / "start_pos_region_slot_templates_table.tsv"
        data = parse_tsv(path_startpos_regions)
        for _, game, full_region_name, type_building, building in data:
            # Province name is the regio_name mapped to the province name
            # If region not in dictionary, print
            if full_region_name not in self.regions:
                # print(f"Region {full_region_name} not found.")
                continue
            # If building contains "major", it is a major region, else minor
            if full_region_name == "att_reg_thracia_constantinopolis":
                print(game, full_region_name, type_building, building)
            if type_building == "primary":
                if "major" in building:
                    self.regions[full_region_name].set_buildings_limit(5)
                    self.regions[full_region_name].set_region_type(RegionType.REGION_MAJOR)
                else:
                    self.regions[full_region_name].set_buildings_limit(3)
                    self.regions[full_region_name].set_region_type(
                        RegionType.REGION_MINOR)  # Add resources type / port to region
                continue
            # 2. If type is port, add port if it is not "spice".
            if type_building == "port":
                if "spice" not in building:
                    self.regions[full_region_name].set_has_port(RegionPort.REGION_PORT)
                else:
                    self.regions[full_region_name].set_has_ressource(AttilaRegionResources.ATTILA_REGION_SPICE)
                continue
            # 3. If type is secondary, add resource
            if type_building == "secondary":
                if "city" in building:
                    self.regions[full_region_name].set_has_ressource(
                        AttilaRegionResources.ATTILA_REGION_CHURCH_ORTHODOX)
                else:
                    # Check if building is a resource building
                    for resource in AttilaRegionResources:
                        if resource.value in building:
                            self.regions[full_region_name].set_has_ressource(resource)
                continue

    def parse_factions_table(self) -> dict[str, Faction]:
        subculture_to_culture = self.parse_cultures_subcultures()
        path_factions = self.game_dir / "factions_table.tsv"
        data = parse_tsv(path_factions)
        faction_to_culture = {}
        for faction_id1, _, subculture3, _, faction_name5, _, _, _, _, *rest in data:
            # Associate faction to culture and subculture
            faction_to_culture[faction_id1] = Faction(faction_id1, faction_name5, subculture_to_culture[subculture3],
                                                      subculture3)
        return faction_to_culture

    def parse_cultures_subcultures(self) -> dict[str, str]:
        path_cultures = self.game_dir / "cultures_subcultures_table.tsv"
        data = parse_tsv(path_cultures)
        subculture_to_culture = {}
        for subculture1, culture2, *rest in data:
            # Associate subculture to culture
            subculture_to_culture[subculture1] = culture2
        return subculture_to_culture

    def parse_cultures_subcultures_table(self) -> None:
        pass
