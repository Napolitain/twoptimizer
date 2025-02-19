import abc
import dataclasses
import enum
import pathlib
from typing import List

from engine.bases import RegionBase, ProvinceBase
from engine.enums import EntryType
from engine.models.model import FullEntryName, EntryName, RegionType


@dataclasses.dataclass
class Faction:
    id: str
    name: str
    culture: str
    subculture: str


class Parser(abc.ABC):
    def __init__(self):
        # store id to object
        self.game_dir = pathlib.Path(__file__).resolve().parent
        while self.game_dir != self.game_dir.root and not (self.game_dir / ".git").exists():
            self.game_dir = self.game_dir.parent
        print(self.game_dir)
        self.game_dir = self.game_dir / "data"
        self.campaign = None
        self.buildings = {}
        self.regions: dict[str, RegionBase] = {}
        self.provinces: dict[str, ProvinceBase] = {}

    @abc.abstractmethod
    def parse_building_effects_junction_tables(self) -> None:
        """
        Get buildings effects from building_effects_junction_table.tsv
        :return: None
        """
        pass

    def parse_provinces(self) -> None:
        """
        Map province names to province objects in self.provinces
        :return: None
        """
        from engine.province import Province
        data = parse_tsv(self.game_dir / "provinces.tsv")
        for name, print_name in data:
            if self.campaign.value[1] not in name:
                continue
            self.provinces[name] = Province(name, print_name)

    def parse_regions(self) -> None:
        """
        Map region names to region objects in self.regions
        :return: None
        """
        from engine.region import Region
        data = parse_tsv(self.game_dir / "regions.tsv")
        for name, print_name in data:
            if self.campaign.value[1] not in name:
                continue
            self.regions[name] = Region(name, print_name)

    def parse_start_pos_tsv(self, file_tsv: pathlib.Path):
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

    @abc.abstractmethod
    def parse_buildings_culture_variants_table(self) -> None:
        """
        Parse the buildings_culture_variants_table.tsv file.
        :return:
        """
        pass

    @abc.abstractmethod
    def parse_cultures_subcultures_table(self) -> None:
        """
        Parse the cultures_subcultures_table.tsv file.
        :return:
        """
        pass

    @abc.abstractmethod
    def parse_factions_table(self) -> dict[str, Faction]:
        """
        Parse the factions_table.tsv file.
        :return:
        """
        pass

    @abc.abstractmethod
    def get_scope(self, scope: str) -> enum.Enum:
        """
        Classify the scope of the effect.
        :param scope: scope of the effect
        :return: enum of the scope
        """
        pass

    def get_entry_name(self, full_name: FullEntryName, entry_type: EntryType) -> EntryName:
        """
        Get the entry_type name from a concatenated name.
        :param full_name: att_prov_thracia_att_reg_thracia_constantinopolis_att_bld_all_industry_major_pewter_4
        :param entry_type: EntryType.PROVINCE, EntryType.REGION, EntryType.BUILDING
        :return: att_reg_thracia_constantinopolis
        """
        if entry_type == EntryType.BUILDING:
            for building in self.buildings[self.campaign.value[1]].values():
                building_name = building.get_name()
                if f"_{building_name}" in full_name.name:
                    return EntryName(building_name)
        elif entry_type == EntryType.REGION:
            for region in self.regions.values():
                region_name = region.get_name()
                if f"{region_name}_" in full_name.name:
                    return EntryName(region_name)
        elif entry_type == EntryType.PROVINCE:
            for province in self.provinces.values():
                province_name = province.get_name()
                if f"{province_name}_" in full_name.name:
                    return EntryName(province_name)
        raise KeyError(f"No matching region found in {full_name.name}")  # Raise KeyError if no match is found

    def get_name_from_use_name(self, entry_name: EntryName, entry_type: EntryType) -> EntryName:
        """
        Get the name from the use_name.
        :param entry_name: R1
        :param entry_type: EntryType.PROVINCE, EntryType.REGION, EntryType.BUILDING
        :return: region_name such as att_reg_thracia_constantinopolis
        """
        if entry_type == EntryType.BUILDING:
            for building in self.buildings[self.campaign.value[1]].values():
                if building.get_name() == entry_name.name:
                    return EntryName(building.name)
        elif entry_type == EntryType.REGION:
            for region in self.regions.values():
                if region.get_name() == entry_name.name:
                    return EntryName(region.name)
        elif entry_type == EntryType.PROVINCE:
            for province in self.provinces.values():
                if province.get_name() == entry_name.name:
                    return EntryName(province.name)
        raise KeyError(f"No matching region found in {entry_name.name}")  # Raise KeyError if no match is found

    def get_dictionary_regions_to_province(self, game_dir: pathlib.Path, swap: bool = False):
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

    def get_print_name(self, name: EntryName, entry_type: EntryType) -> str:
        """
        Get the print name of the entry.
        :param name: name of the entry
        :param entry_type: type of the entry
        :return: print name of the entry
        """
        if entry_type == EntryType.BUILDING:
            return self.buildings[self.campaign.value[1]][name.name].get_name_output()
        elif entry_type == EntryType.REGION:
            return self.regions[name.name].get_name_output()
        elif entry_type == EntryType.PROVINCE:
            return self.provinces[name.name].get_name_output()
        raise ValueError(f"Entry type {entry_type.value} not found in {name.name}.")

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
            "secondary": self.process_secondary_region
        }

        if type_building in handlers:
            handlers[type_building](region, building)

    def filter_by_campaign(self, full_region_name, game):
        return self.campaign.value[1] not in full_region_name or self.campaign.value[0] not in game

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

    @abc.abstractmethod
    def process_port_region(self, region, building):
        """
        Handles port regions, setting port or spice resources.
        :param region: the region
        :param building: the building entry
        """
        pass

    @abc.abstractmethod
    def process_secondary_region(self, region, building):
        """
        Assigns resources to secondary regions.
        :param region: the region
        :param building: the building entry
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
