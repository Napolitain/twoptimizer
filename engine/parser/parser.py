import abc
import enum
import pathlib
from typing import List


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
