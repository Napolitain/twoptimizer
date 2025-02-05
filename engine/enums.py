import enum


class EntryType(enum.Enum):
    BUILDING = "bld"
    REGION = "reg"
    PROVINCE = "prov"


class Scope(enum.Enum):
    """
    Scope of the effect.
    """
    FACTION = 0
    PROVINCE = 1
    REGION = 2
    BUILDING = 3


class NameType(enum.Enum):
    PRINT_NAME = 0  # Region name
    NAME = 1  # region_building
    HASH_NAME = 2  # X1, X2, X3...
