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
