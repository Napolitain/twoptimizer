from engine.filters.filter_attila import FilterAttila
from engine.models.game import Game
from engine.models.model import RegionPort, RegionType
from engine.models.model_attila import AttilaFactions, AttilaRegionResources, AttilaCampaign, AttilaReligion
from engine.parser.parser_attila import ParserAttila


class AttilaGame(Game):
    # Enum aliases
    Factions = AttilaFactions
    Resources = AttilaRegionResources
    Port = RegionPort
    Type = RegionType
    Campaign = AttilaCampaign
    Religion = AttilaReligion

    def __init__(self, campaign: AttilaCampaign = AttilaCampaign.ATTILA,
                 faction: AttilaFactions = AttilaFactions.ATT_FACT_WESTERN_ROMAN_EMPIRE,
                 religion: AttilaReligion = AttilaReligion.CHRIST_ORTHODOX):
        super().__init__()
        self.campaign = campaign
        self.faction = faction
        self.parser = ParserAttila(campaign, faction, religion)
        self.filter = FilterAttila(faction)
        self.religion = religion
