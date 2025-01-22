import enum

from engine.models.model import RegionType, RegionPort
from engine.models.model_attila import AttilaFactions, AttilaRegionResources, AttilaCampaign
from engine.models.model_rome2 import Rome2Factions, Rome2RegionResources, Rome2Campaign


class EntryType(enum.Enum):
    BUILDING = "bld"
    REGION = "reg"
    PROVINCE = "prov"


class AttilaGame:
    # Enum aliases
    Factions = AttilaFactions
    Resources = AttilaRegionResources
    Port = RegionPort
    Type = RegionType
    Campaign = AttilaCampaign

    # Properties
    campaign = AttilaCampaign.ATTILA
    faction = AttilaFactions.ATTILA_ROMAN_EAST


class Rome2Game:
    # Enum aliases
    Factions = Rome2Factions
    Resources = Rome2RegionResources
    Port = RegionPort
    Type = RegionType
    Campaign = Rome2Campaign

    # Properties
    campaign = Rome2Campaign.ROME
    faction = Rome2Factions.ROM_ROME


class Scope(enum.Enum):
    """
    Scope of the effect.
    """
    FACTION = 0
    PROVINCE = 1
    REGION = 2
    BUILDING = 3
