import abc
import dataclasses
import enum
import pathlib
from typing import List

from engine.enums import EntryType


@dataclasses.dataclass
class Faction:
    id: str
    name: str
    culture: str
    subculture: str


class Parser(abc.ABC):
    def __init__(self):
        # store id to object
        self.buildings = {}
        self.regions = {}
        self.provinces = {}

    @abc.abstractmethod
    def parse_building_effects_junction_tables(self) -> None:
        """
        Get buildings effects from building_effects_junction_table.tsv
        :return:
        """
        pass

    @abc.abstractmethod
    def parse_provinces(self):
        pass

    @abc.abstractmethod
    def parse_regions(self):
        pass

    @abc.abstractmethod
    def parse_start_pos_tsv(self, file_tsv: pathlib.Path):
        """
        Parse the start_pos_region_slot_templates_table.tsv file.
        :param file_tsv: path to the file
        :return: dictionary of provinces
        """
        pass

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

    @abc.abstractmethod
    def get_entry_name(self, full_name: str, entry_type: EntryType) -> str:
        """
        Get the entry_type name from a concatenated name.
        :param full_name: att_prov_thracia_att_reg_thracia_constantinopolis_att_bld_all_industry_major_pewter_4
        :param entry_type: EntryType.PROVINCE, EntryType.REGION, EntryType.BUILDING
        :return: att_reg_thracia_constantinopolis
        """
        pass

    @abc.abstractmethod
    def get_name_from_use_name(self, entry_name: str, entry_type: EntryType) -> str:
        """
        Get the name from the use_name.
        :param entry_name: R1
        :param entry_type: EntryType.PROVINCE, EntryType.REGION, EntryType.BUILDING
        :return: region_name such as att_reg_thracia_constantinopolis
        """
        pass

    @abc.abstractmethod
    def get_dictionary_regions_to_province(self, game_dir: pathlib.Path):
        """
        Get a dictionary of regions to province from a tsv file (TW DB)
        :param game_dir: path to the game folder
        :return: dictionary of regions to province (region_name: province_name)
        """
        pass

    @abc.abstractmethod
    def get_print_name(self, name: str, entry_type: EntryType) -> str:
        """
        Get the print name of the entry.
        :param name: name of the entry
        :param entry_type: type of the entry
        :return: print name of the entry
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
