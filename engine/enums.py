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
    Used for problem modeling.
    """
    USE_ID = 0  # R1, or region_building
    USE_PRINT_NAME = 1  # Region Building


class ProblemState(enum.Enum):
    INIT = 0
    PROVINCES_ADDED = 1
    BUILDINGS_ADDED = 2
    FILTERS_ADDED = 3
    CONSTRAINTS_ADDED = 4
    OBJECTIVE_ADDED = 5
    SOLVED = 6


class SolverType(enum.Enum):
    PULP = 0
    SCIP = 1
    GOOGLE = 2
