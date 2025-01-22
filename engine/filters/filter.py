import abc
from abc import abstractmethod

from engine.models.model import GameFactions


class Filter(abc.ABC):
    def __init__(self, faction: GameFactions):
        self.faction = faction

    @abstractmethod
    def building_is_major(self, building_name: str) -> bool:
        pass

    @abstractmethod
    def building_is_minor(self, building_name: str) -> bool:
        pass

    @abc.abstractmethod
    def building_is_resource(self, building) -> bool:
        pass

    @abstractmethod
    def building_is_not_of_faction(self, building_name: str) -> bool:
        pass
