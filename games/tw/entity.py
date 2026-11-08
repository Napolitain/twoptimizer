from games.tw.context import GameContext
from games.tw.enums import NameType
from games.tw.models.entity_interface import EntityInterface


class Entity(EntityInterface):
    def __init__(self, *, context: GameContext):
        self.context = context
        self.hash_name = "None"
        self.name = "None"
        self.print_name = "None"

    def get_name(self, name_type: NameType | None = None):
        """
        :param name_type: the type of name to return (default use self.context.name_type)
        :return: either the print name, name, or hash name of the entity
        """
        if name_type is None:
            name_type = self.context.name_type

        if name_type == NameType.PRINT_NAME:
            return self.print_name
        elif name_type == NameType.NAME:
            return self.name
        elif name_type == NameType.HASH_NAME:
            return self.hash_name
        else:
            raise ValueError("Region name not set.")

    def get_name_output(self):
        if self.context.name_type == NameType.PRINT_NAME or self.context.name_type == NameType.NAME:
            return self.print_name
        else:
            return self.hash_name
