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
    """
    Name type, used for problem modeling.
    """
    NAME = 0  # region_building
    HASH_NAME = 1  # X1, X2, X3...
    PRINT_NAME = 2  # Region Building


class PrintType(enum.Enum):
    """
    Print type, used for problem modeling output.
    """
    PRINT_NAME = 0
    HASH_NAME = 1
