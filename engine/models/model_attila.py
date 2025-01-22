import enum

from engine.models.model import GameFactions, GameCampaign


class AttilaFactions(GameFactions):
    """
    Enum containing a list of factions in Attila.
    """
    ATTILA_NONE = 0
    ATTILA_ROMAN_EAST = "roman_east"
    ATTILA_ROMAN_WEST = "roman_west"
    ATTILA_FRANKS = "franks"
    ATTILA_VANDALS = "vandals"
    ATTILA_VISIGOTHS = "visigoths"
    ATTILA_ALAMANS = "alamans"
    ATTILA_SAXONS = "saxons"
    ATTILA_GEPIDS = "gepids"
    ATTILA_LANGOBARDS = "langobards"
    ATTILA_BURGUNDIANS = "burgundians"
    ATTILA_OSTROGOTHS = "ostrogoths"
    ATTILA_SUEBI = "suebi"
    ATTILA_HUNS = "huns"
    ATTILA_ALANS = "alans"
    ATTILA_SASSANIDS = "eastern"


class AttilaRegionResources(enum.Enum):
    ATTILA_REGION_NO_RESSOURCE = "NONE"
    ATTILA_REGION_FURS = "furs"
    ATTILA_REGION_IRON = "iron"
    ATTILA_REGION_WINE = "wine"
    ATTILA_REGION_WOOD = "wood"
    ATTILA_REGION_GOLD = "gold"
    ATTILA_REGION_MARBLE = "marble"
    ATTILA_REGION_GEMS = "gems"
    ATTILA_REGION_SILK = "silk"
    ATTILA_REGION_SPICE = "spice"
    ATTILA_REGION_SALT = "salt"
    ATTILA_REGION_LEAD = "lead"
    ATTILA_REGION_OLIVES = "olives"
    ATTILA_REGION_CHURCH_CATHOLIC = "religion_catholic_legendary"
    ATTILA_REGION_CHURCH_ORTHODOX = "religion_orthodox_legendary"


class AttilaCampaign(GameCampaign):
    ATTILA = ("main_attila", "att")
    LAST_ROMAN = ("bel_attila", "bel")
    CHARLEMAGNE = ("cha_attila", "cha")
