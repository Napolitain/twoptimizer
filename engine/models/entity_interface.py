from abc import ABC, abstractmethod

from engine.enums import PrintType


class EntityInterface(ABC):
    @abstractmethod
    def get_name(self, name_type: PrintType = None):
        """
        :param name_type: the type of name to return (default use Games.USE_NAME)
        :return: either the print name, name, or hash name of the entity
        """
        pass  # Must be implemented by subclasses

    @abstractmethod
    def get_name_output(self):
        """Returns the preferred name output based on Games.USE_NAME."""
        pass  # Must be implemented by subclasses
