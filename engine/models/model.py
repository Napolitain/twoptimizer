import enum


class GameFactions(enum.Enum):
    pass


class GameCampaign(enum.Enum):
    pass


class RegionType(enum.Enum):
    REGION_MAJOR = 1
    REGION_MINOR = 2


class RegionPort(enum.Enum):
    REGION_NO_PORT = 1
    REGION_PORT = 2
