from games.tw.attila.context import AttilaContext
from games.tw.attila.enums import (
    AttilaCampaign,
    AttilaFactions,
    AttilaRegionResources,
    AttilaReligion,
    RegionPort,
    RegionType,
)
from games.tw.attila.loader import AttilaLoader
from games.tw.attila.placement import PlacementRules


class AttilaGame:
    # Enum aliases
    Factions = AttilaFactions
    Resources = AttilaRegionResources
    Port = RegionPort
    Type = RegionType
    Campaign = AttilaCampaign
    Religion = AttilaReligion

    def __init__(
        self,
        campaign: AttilaCampaign = AttilaCampaign.ATTILA,
        faction: AttilaFactions = AttilaFactions.ATT_FACT_WESTERN_ROMAN_EMPIRE,
        religion: AttilaReligion = AttilaReligion.CHRIST_ORTHODOX,
        *,
        context: AttilaContext | None = None,
    ):
        context = AttilaContext() if context is None else context
        context.instance = self
        self.campaign = campaign
        self.faction = faction
        self.parser = AttilaLoader(campaign, faction, religion, context=context)
        context.buildings = self.parser.buildings
        self.filter = PlacementRules()
        self.religion = religion
