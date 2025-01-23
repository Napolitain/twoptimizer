from engine.filters.filter import Filter
from engine.models.model import GameCampaign, GameFactions
from engine.parser.parser import Parser


class Game:
    def __init__(self):
        self.campaign: GameCampaign
        self.faction: GameFactions
        self.parser: Parser
        self.filter: Filter

    def get_campaign(self) -> GameCampaign:
        return self.campaign

    def get_faction(self) -> GameFactions:
        return self.faction

    def get_parser(self) -> Parser:
        return self.parser

    def get_filter(self) -> Filter:
        return self.filter
