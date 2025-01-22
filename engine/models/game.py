from engine.filters.filter import Filter
from engine.models.model import GameCampaign, GameFactions
from engine.parser.parser import Parser


class Game:
    def __init__(self):
        self.campaign: GameCampaign
        self.faction: GameFactions
        self.parser: Parser
        self.filter: Filter
