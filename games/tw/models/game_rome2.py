from games.tw.context import GameContext
from games.tw.filters.filter_rome2 import FilterRome2
from games.tw.models.game import Game
from games.tw.models.model import RegionPort, RegionType
from games.tw.models.model_rome2 import Rome2Campaign, Rome2Factions, Rome2RegionResources
from games.tw.parser.parser_rome2 import ParserRome2


class Rome2Game(Game):
    # Enum aliases
    Factions = Rome2Factions
    Resources = Rome2RegionResources
    Port = RegionPort
    Type = RegionType
    Campaign = Rome2Campaign

    def __init__(
        self,
        campaign: Rome2Campaign = Rome2Campaign.ROME,
        faction: Rome2Factions = Rome2Factions.ROM_ROME,
        *,
        context: GameContext | None = None,
    ):
        super().__init__()
        context = GameContext() if context is None else context
        context.instance = self
        self.campaign = campaign
        self.faction = faction
        self.parser = ParserRome2(campaign, faction, context=context)
        context.buildings = self.parser.buildings
        self.filter = FilterRome2(faction)
