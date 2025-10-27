import abc


class ProvinceBase(abc.ABC):
    @abc.abstractmethod
    def add_region(self, region):
        pass

    @abc.abstractmethod
    def add_public_order_constraint(self):
        pass

    @abc.abstractmethod
    def add_food_constraint(self):
        pass

    @abc.abstractmethod
    def add_sanitation_constraint(self):
        pass


class RegionBase(abc.ABC):
    """
    A region contains buildings.
    """

    @abc.abstractmethod
    def get_n_buildings(self) -> int:
        pass

    @abc.abstractmethod
    def filter_city_level(self, city_level: int):
        pass

    @abc.abstractmethod
    def filter_building_level(self, level: int):
        pass

    @abc.abstractmethod
    def filter_military(self):
        pass
