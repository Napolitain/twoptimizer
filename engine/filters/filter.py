import abc

from engine.models.model import GameFactions


class Filter(abc.ABC):
    """
    All the filters here are pass by default because they are optional.
    Each games will have its own filter implementation.
    """

    def __init__(self, faction: GameFactions):
        self.faction = faction

    def building_is_majorcity(self, building_name: str) -> bool:
        return "city_major" in building_name

    def building_is_minorcity(self, building_name: str) -> bool:
        return "city_minor" in building_name

    def building_is_major(self, building_name: str) -> bool:
        pass

    def building_is_minor(self, building_name: str) -> bool:
        pass

    def building_is_resource(self, building) -> bool:
        """
        Check if a building is a resource building.
        :param building:
        :return:
        """
        pass

    def building_is_not_of_faction(self, building_name: str) -> bool:
        """
        Check if a building is of the faction currently assigned in Games.
        If it is not of the faction, return True.
        :param building_name:
        :return:
        """
        pass

    def building_is_port(self, building_name: str) -> bool:
        """
        Check if a building is a port.
        Games affected: Rome 2, Attila
        :param building_name:
        :return:
        """
        pass

    def building_is_duplicate(self, building_name: str) -> bool:
        """
        Check if a building is a duplicate. For example, if we have port_fish1, port_resource_fish1, they are duplicates.
        :param building_name:
        :return:
        """
        pass

    def effect_is_gdp(self, effect: str, include_fertility: bool = False) -> bool:
        pass
