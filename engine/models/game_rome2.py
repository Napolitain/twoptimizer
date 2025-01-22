from engine.models.model import RegionPort, RegionType
from engine.models.model_rome2 import Rome2Factions, Rome2RegionResources, Rome2Campaign
from engine.parser.parser import ParserRome2


class Rome2Game(Game):
    # Enum aliases
    Factions = Rome2Factions
    Resources = Rome2RegionResources
    Port = RegionPort
    Type = RegionType
    Campaign = Rome2Campaign

    def __init__(self):
        self.campaign = Rome2Game.Campaign.ROME
        self.faction = Rome2Game.Factions.ROM_ROME
        self.parser = ParserRome2()
