from abc import ABC, abstractmethod

from games.tw.enums import NameType


class EntityInterface(ABC):
    @abstractmethod
    def get_name(self, name_type: NameType | None = None):
        """
        :param name_type: the type of name to return (default use the entity context name type)
        :return: either the print name, name, or hash name of the entity
        """
        pass  # Must be implemented by subclasses

    @abstractmethod
    def get_name_output(self):
        """Returns the preferred name output based on the entity context."""
        pass  # Must be implemented by subclasses
