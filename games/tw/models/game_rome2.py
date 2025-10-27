from games.tw.filters.filter_rome2 import FilterRome2
from games.tw.models.game import Game
from games.tw.models.model import RegionPort, RegionType
from games.tw.models.model_rome2 import Rome2Factions, Rome2RegionResources, Rome2Campaign
from games.tw.parser.parser_rome2 import ParserRome2


class Rome2Game(Game):
    # Enum aliases
    Factions = Rome2Factions
    Resources = Rome2RegionResources
    Port = RegionPort
    Type = RegionType
    Campaign = Rome2Campaign

    def __init__(self, campaign: Rome2Campaign = Rome2Campaign.ROME,
                 faction: Rome2Factions = Rome2Factions.ROM_ROME):
        super().__init__()
        self.campaign = campaign
        self.faction = faction
        self.parser = ParserRome2(campaign, faction)
        self.filter = FilterRome2(faction)
