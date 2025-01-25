from engine.filters.filter import Filter
from engine.models.model_attila import AttilaFactions


class FilterAttila(Filter):
    def building_is_not_of_campaign(self, building_name: str) -> bool:
        return False

    def building_is_not_of_faction(self, building_name: str) -> bool:
        """
        Check if a building is of the faction currently assigned in Games.
        :param building_name:
        :return:
        """
        split_name = building_name.split("_")
        if self.faction == AttilaFactions.ATTILA_ROMAN_EAST:
            if (
                    "roman" in building_name and "west" not in building_name) or ("orthodox" in building_name) or (
                    "all" in split_name and "camel" not in building_name and "pigs" not in building_name):
                return False
        if self.faction == AttilaFactions.ATTILA_ROMAN_WEST:
            if (
                    "roman" in building_name and "east" not in building_name) or ("catholic" in building_name) or (
                    "all" in split_name and "camel" not in building_name and "pigs" not in building_name):
                return False
        if self.faction == AttilaFactions.ATTILA_FRANKS:
            if "barbarian" in building_name or (
                    "catholic" in building_name) or (
                    "all" in split_name and "camel" not in building_name and "pigs" not in building_name):
                return False
        if self.faction == AttilaFactions.ATTILA_SASSANIDS:
            if "eastern" in building_name or (
                    "zoro" in building_name) or (
                    "all" in split_name and "cows" not in building_name and "pigs" not in building_name):
                return False
        return True

    def building_is_major(self, building_name: str) -> bool:
        """
        Check if a building is major (city or town).
        :param building_name:
        :return:
        """
        if "major" in building_name or "civic" in building_name or "military_upgrade" in building_name or "aqueducts" in building_name or "sewers" in building_name:
            return True
        return False

    def building_is_minor(self, building_name: str) -> bool:
        """
        Check if a building is minor (village).
        :param building_name:
        :return:
        """
        if "minor" in building_name or "agriculture" in building_name or "livestock" in building_name:
            return True
        return False

    def building_is_resource(self, building):
        """
        Check if a building is a resource building.
        If the building contains resource but not port, it is a resource building.
        If the building contains spice, it is a resource building.
        :param building:
        :return:
        """
        return ("resource" in building.name and "port" not in building.name) or "spice" in building.name

    def building_is_port(self, building_name: str) -> bool:
        if "port" in building_name and "spice" not in building_name:
            return True
        return False

    def building_is_duplicate(self, building_name: str) -> bool:
        """
        In attila, we have duplicate buildings such as port_fish1, port_resource_fish1.
        :param building_name:
        :return:
        """
        if "port" in building_name and "resource" not in building_name:
            return True
        return False

    def effect_is_gdp(self, effect: str, include_fertility: bool = False):
        return "gdp" in effect and "mod" not in effect and (include_fertility == ("fertility" in effect))
