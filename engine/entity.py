from engine.enums import NameType
from engine.games import Games


class Entity:
    def __init__(self):
        self.hash_name = "None"
        self.name = "None"
        self.print_name = "None"

    def get_name(self, name_type: NameType = None):
        """
        :param name_type: the type of name to return (default use Games.USE_NAME)
        :return: either the print name, name, or hash name of the entity
        """
        if name_type is None:
            name_type = Games.USE_NAME

        if name_type == NameType.PRINT_NAME:
            return self.print_name
        elif name_type == NameType.NAME:
            return self.name
        elif name_type == NameType.HASH_NAME:
            return self.hash_name
        else:
            raise ValueError("Region name not set.")
