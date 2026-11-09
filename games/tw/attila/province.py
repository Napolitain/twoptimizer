from games.tw.attila.building import Building
from games.tw.attila.context import AttilaContext
from games.tw.attila.entity import Entity
from games.tw.attila.region import Region


class Province(Entity):
    """
    We need to create a Province class that contains a list of regions.
    """

    def __init__(self, name: str, print_name: str = "", *, context: AttilaContext):
        super().__init__(context=context)
        self.regions = []
        self.name = name
        self.hash_name = context.next_id("P")
        if print_name == "":
            self.print_name = name
        else:
            self.print_name = print_name

    def add_region(self, region: Region):
        """
        Add a region to the province.
        :param region:
        :return:
        """
        self.regions.append(region)

    def buildings(self) -> list[Building]:
        """
        Return all buildings in the province that are potentially built. Basically, will be all
        our LpVariables.
        :return:
        """
        return [building for region in self.regions for building in region.buildings]

    def clean(self):
        """
        Clean the province memory (buildings).
        :return:
        """
        for region in self.regions:
            region.buildings = []
