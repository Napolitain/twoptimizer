import abc
import enum
import pathlib
from typing import List

from engine.enums import EntryType


class Parser(abc.ABC):
    def __init__(self):
        self.buildings = {}

    @abc.abstractmethod
    def get_scope(self, scope: str) -> enum.Enum:
        """
        Classify the scope of the effect.
        :param scope: scope of the effect
        :return: enum of the scope
        """
        pass

    @abc.abstractmethod
    def parse_building_effects_junction_tables(self) -> None:
        """
        Get buildings effects from building_effects_junction_table.tsv
        :return:
        """
        pass

    @abc.abstractmethod
    def get_entry_name(self, name: str, entry_type: EntryType) -> str:
        """
        Get the building name from the full name.
        x_y_bld_z -> bld_z
        :param name: full name
        :param entry_type: type of the entry (building, region, province)
        :raise ValueError: if the entry type is not found in the name (e.g. bld, reg, prov not found in name)
        :return: name of the entry
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
