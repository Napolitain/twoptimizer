from dataclasses import dataclass
from pathlib import Path

from games.tw.attila.building import Building
from games.tw.attila.context import AttilaContext
from games.tw.attila.enums import (
    AttilaCampaign,
    AttilaFactions,
    AttilaRegionResources,
    AttilaReligion,
    RegionPort,
    RegionType,
    Scope,
)
from games.tw.attila.templates import BuildingTemplate
from games.tw.immutable import freeze, read_catalog


@dataclass(frozen=True, slots=True)
class Faction:
    id: str
    name: str
    culture: str
    subculture: str


class AttilaLoader:
    def __init__(
        self,
        campaign: AttilaCampaign,
        faction: AttilaFactions,
        religion: AttilaReligion = AttilaReligion.CHRIST_ORTHODOX,
        *,
        context: AttilaContext,
    ):
        self.context = context
        self.buildings = {}
        self.regions = {}
        self.provinces = {}
        # Resolve bundled data relative to the package for installed-wheel support.
        self.game_dir = Path(__file__).resolve().parent / "data"
        self.campaign = campaign
        self.faction = faction
        self.religion = religion
        self.faction_to_culture = self.parse_factions_table()
        metadata_path = self.game_dir / "online_buildings.json"
        self.online_data = (
            read_catalog(metadata_path) if metadata_path.exists() else {"buildings": {}}
        )
        self.unsupported_effects = []

    def parse_buildings_culture_variants_table(self) -> None:
        path_buildings_culture_variants = self.game_dir / "building_culture_variants_table.tsv"
        data = parse_tsv(path_buildings_culture_variants)
        for (
            building_id1,
            culture2,
            subculture3,
            faction_id4,
            building_name6,
            *_rest,
        ) in data:
            if "religion" in building_id1 and not self.building_is_of_religion(building_id1):
                continue
            campaign_name = building_id1.split("_")[0]
            if campaign_name not in self.buildings:
                self.buildings[campaign_name] = {}
            if self.campaign.value[1] in building_id1 and (
                self.building_is_of_faction(culture2, faction_id4, subculture3)
                or self.building_is_of_religion(building_id1)
            ):
                building = Building(building_id1, building_name6, context=self.context)
                building.metadata = self.online_data["buildings"].get(building_id1)
                self.buildings[campaign_name][building_id1] = building

    def building_is_of_religion(self, building_id1):
        if "religion" not in building_id1:
            return False
        if self.religion == AttilaReligion.ANY:
            return True
        aliases = {
            "eastern": ("eastern", "east_church"),
            "tengris": ("tengri", "tengris"),
            "slavic": ("slav",),
            "semitic_paganism": ("semitic",),
        }
        return any(
            alias in building_id1
            for alias in aliases.get(self.religion.value, (self.religion.value,))
        )

    def building_is_of_faction(self, culture, faction_id, subculture) -> bool:
        """
        Check if the building is of the faction.
        Building is added if :
        - faction id == self.faction.value
        - faction subculture == self.faction_to_culture[self.faction.value].subculture and
        faction id is none
        - faction culture == self.faction.culture and faction id and subculture are none
        - all are none and not nomad, mig, religion, ruin
        :param culture: culture of the building
        :param faction_id: faction id of the building
        :param subculture: subculture of the building
        :return: True if the building is of the faction, False otherwise
        """
        return (
            faction_id == self.faction.value
            or (
                faction_id == ""
                and subculture == self.faction_to_culture[self.faction.value].subculture
            )
            or (
                faction_id == ""
                and subculture == ""
                and culture == self.faction_to_culture[self.faction.value].culture
            )
            or (
                faction_id == ""
                and subculture == ""
                and culture == ""
                and "nomad" not in culture
                and "mig" not in culture
                and "religion" not in culture
                and "ruin" not in culture
            )
        )

    def parse_building_effects_junction_tables(self):
        self.buildings = {}
        path_buildings = self.game_dir / "building_effects_junction_table.tsv"
        # Read file building_effects_junction_table.tsv (tabulated)
        data = parse_tsv(path_buildings)
        if len(self.buildings) == 0:
            self.parse_buildings_culture_variants_table()
        for building_id, effect, scope, amount in data:
            if building_id not in self.buildings[self.campaign.value[1]]:
                continue
            scope_value = self.get_scope(scope)
            if scope_value is None:
                self.unsupported_effects.append((building_id, effect, scope))
            self.buildings[self.campaign.value[1]][building_id].add_effect(
                effect, scope_value, float(amount), raw_scope=scope
            )

        self.freeze_catalog()

    def freeze_catalog(self) -> None:
        self.buildings = freeze(
            {
                campaign: {
                    key: BuildingTemplate.from_building(building)
                    for key, building in entries.items()
                }
                for campaign, entries in self.buildings.items()
            }
        )
        self.context.buildings = self.buildings

    def parse_factions_table(self) -> dict[str, Faction]:
        subculture_to_culture = self.parse_cultures_subcultures()
        path_factions = self.game_dir / "factions_table.tsv"
        data = parse_tsv(path_factions)
        faction_to_culture = {}
        for faction_id1, _, subculture3, _, faction_name5, _, _, _, _, *_rest in data:
            # Associate faction to culture and subculture
            faction_to_culture[faction_id1] = Faction(
                faction_id1,
                faction_name5,
                subculture_to_culture[subculture3],
                subculture3,
            )
        return faction_to_culture

    def parse_cultures_subcultures(self) -> dict[str, str]:
        path_cultures = self.game_dir / "cultures_subcultures_table.tsv"
        data = parse_tsv(path_cultures)
        subculture_to_culture = {}
        for subculture1, culture2, *_rest in data:
            # Associate subculture to culture
            subculture_to_culture[subculture1] = culture2
        return subculture_to_culture

    def process_primary_region(self, region, building):
        """
        Sets building limits and region type for primary regions.
        :param region: the region
        :param building: the building entry
        """
        if "major" in building:
            region.set_buildings_limit(5)
            region.set_region_type(RegionType.REGION_MAJOR)
        else:
            region.set_buildings_limit(3)
            region.set_region_type(RegionType.REGION_MINOR)

    def process_port_region(self, region, building):
        """
        Handles port regions, setting port or spice resources.
        :param region: the region
        :param building: the building entry
        """
        if "spice" not in building:
            region.set_has_port(RegionPort.REGION_PORT)
        else:
            region.set_has_ressource(AttilaRegionResources.ATTILA_REGION_SPICE)

    def process_secondary_region(self, region, building):
        """
        Assigns resources to secondary regions.
        :param region: the region
        :param building: the building entry
        """
        if "city" in building:
            from games.tw.attila.special_slots import church_resource

            region.set_has_ressource(church_resource(building, self.religion))
        else:
            for resource in AttilaRegionResources:
                if resource.value in building:
                    region.set_has_ressource(resource)

    @staticmethod
    def get_scope(scope: str) -> Scope | None:
        from games.tw.attila.effects import Reach, reach

        return {
            Reach.BUILDING: Scope.BUILDING,
            Reach.LOCAL: Scope.REGION,
            Reach.PROVINCE: Scope.PROVINCE,
            Reach.FACTION: Scope.FACTION,
        }.get(reach(scope))

    def parse_provinces(self) -> None:
        """
        Map province names to province objects in self.provinces
        :return: None
        """
        from games.tw.attila.province import Province

        data = parse_tsv(self.game_dir / "provinces.tsv")
        for name, print_name in data:
            if self.campaign.value[1] not in name:
                continue
            self.provinces[name] = Province(name, print_name, context=self.context)

    def parse_regions(self) -> None:
        """
        Map region names to region objects in self.regions
        :return: None
        """
        from games.tw.attila.region import Region

        data = parse_tsv(self.game_dir / "regions.tsv")
        for name, print_name in data:
            if self.campaign.value[1] not in name:
                continue
            self.regions[name] = Region(name, print_name, context=self.context)

    def parse_start_pos_tsv(self, file_tsv: Path):
        """
        Parse the start_pos_region_slot_templates_table.tsv file.
        :param file_tsv: path to the file
        :return: dictionary of provinces
        """
        self.parse_provinces()
        self.parse_regions()
        # Link region name to province name
        dictionary_regions_to_province = self.get_dictionary_regions_to_province(file_tsv, True)
        # Link province name to province object
        for region_name, province_name in dictionary_regions_to_province.items():
            self.provinces[province_name].add_region(self.regions[region_name])
        # Read file building_effects_junction_tables.tsv (tabulated)
        path_startpos_regions = file_tsv / "start_pos_region_slot_templates_table.tsv"
        data = parse_tsv(path_startpos_regions)
        for _, game, full_region_name, type_building, building in data:
            if not self.filter_by_campaign(full_region_name, game):
                self.process_building(full_region_name, type_building, building)

    def get_dictionary_regions_to_province(self, game_dir: Path, swap: bool = False):
        """
        Get a dictionary of regions to province from a tsv file (TW DB)
        :param game_dir: path to the game folder
        :param swap: swap the region and province
        :return: dictionary of regions to province (region_name: province_name)
        """
        path_province_region_junctions = game_dir / "region_to_provinces_junctions_table.tsv"
        dictionary_regions_to_province = {}
        data = parse_tsv(path_province_region_junctions)

        for region, province in data:
            if swap:
                region, province = province, region  # Swap if needed

            # Filter game
            if self.campaign.value[1] not in province:
                continue

            dictionary_regions_to_province[region] = province

        return dictionary_regions_to_province

    def process_building(self, full_region_name: str, type_building: str, building: str):
        """
        Processes a building entry and assigns attributes to the region.
        :param full_region_name: the full region name
        :param type_building: the type of building
        :param building: the building entry
        """
        region = self.regions.get(full_region_name)
        if not region:
            return  # Skip if the region does not exist

        handlers = {
            "primary": self.process_primary_region,
            "port": self.process_port_region,
            "secondary": self.process_secondary_region,
        }

        if type_building in handlers:
            handlers[type_building](region, building)

    def filter_by_campaign(self, full_region_name, game):
        return self.campaign.value[1] not in full_region_name or self.campaign.value[0] not in game


def parse_tsv(path: Path) -> list[list[str]]:
    """Read bundled exported table rows without changing their source ordering."""
    return [line.split("\t") for line in path.read_text().split("\n")]
