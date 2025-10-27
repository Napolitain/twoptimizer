from games.tw.filters.filter import Filter


class FilterRome2(Filter):
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
