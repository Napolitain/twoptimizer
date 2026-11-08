import json
from pathlib import Path

from games.tw.building import Building
from games.tw.context import GameContext
from games.tw.enums import Scope
from games.tw.models.model import RegionPort, RegionType
from games.tw.models.model_attila import (
    AttilaCampaign,
    AttilaFactions,
    AttilaRegionResources,
    AttilaReligion,
)
from games.tw.parser.parser import Faction, Parser, parse_tsv


class ParserAttila(Parser):
    def __init__(
        self,
        campaign: AttilaCampaign,
        faction: AttilaFactions,
        religion: AttilaReligion = AttilaReligion.CHRIST_ORTHODOX,
        *,
        context: GameContext,
    ):
        super().__init__(context=context)
        # Resolve bundled data relative to the package for installed-wheel support.
        self.game_dir = Path(__file__).resolve().parents[1] / "attila" / "data"
        self.campaign = campaign
        self.faction = faction
        self.religion = religion
        self.faction_to_culture = self.parse_factions_table()
        metadata_path = self.game_dir / "online_buildings.json"
        self.online_data = (
            json.loads(metadata_path.read_text()) if metadata_path.exists() else {"buildings": {}}
        )
        self.unsupported_effects = []

    def get_scope(self, scope: str) -> Scope | None:
        if not self.context.legacy_effects:
            from games.tw.attila.effects import Reach, reach

            return {
                Reach.BUILDING: Scope.BUILDING,
                Reach.LOCAL: Scope.REGION,
                Reach.PROVINCE: Scope.PROVINCE,
                Reach.FACTION: Scope.FACTION,
            }.get(reach(scope))
        if scope.startswith("faction"):
            return Scope.FACTION
        elif scope.startswith("province"):
            return Scope.PROVINCE
        elif scope.startswith("region"):
            return Scope.REGION
        elif scope.startswith("building"):
            return Scope.BUILDING
        raise ValueError(f"Scope {scope} not found.")

    def parse_buildings_culture_variants_table(self) -> None:
        # TODO: Fix religion buildings
        path_buildings_culture_variants = self.game_dir / "building_culture_variants_table.tsv"
        data = parse_tsv(path_buildings_culture_variants)
        for (
            building_id1,
            culture2,
            subculture3,
            faction_id4,
            building_name6,
            *_rest,
        ) in data:
            if (
                not self.context.legacy_effects
                and "religion" in building_id1
                and not self.building_is_of_religion(building_id1)
            ):
                continue
            campaign_name = building_id1.split("_")[0]
            if campaign_name not in self.buildings:
                self.buildings[campaign_name] = {}
            if self.campaign.value[1] in building_id1 and (
                self.building_is_of_faction(culture2, faction_id4, subculture3)
                or self.building_is_of_religion(building_id1)
            ):
                building = Building(building_id1, building_name6, context=self.context)
                building.metadata = self.online_data["buildings"].get(building_id1)
                self.buildings[campaign_name][building_id1] = building

    def building_is_of_religion(self, building_id1):
        if "religion" not in building_id1:
            return False
        if self.religion == AttilaReligion.ANY:
            return True
        aliases = {
            "eastern": ("eastern", "east_church"),
            "tengris": ("tengri", "tengris"),
            "slavic": ("slav",),
            "semitic_paganism": ("semitic",),
        }
        return any(
            alias in building_id1
            for alias in aliases.get(self.religion.value, (self.religion.value,))
        )

    def building_is_of_faction(self, culture, faction_id, subculture) -> bool:
        """
        Check if the building is of the faction.
        Building is added if :
        - faction id == self.faction.value
        - faction subculture == self.faction_to_culture[self.faction.value].subculture and
        faction id is none
        - faction culture == self.faction.culture and faction id and subculture are none
        - all are none and not nomad, mig, religion, ruin
        :param culture: culture of the building
        :param faction_id: faction id of the building
        :param subculture: subculture of the building
        :return: True if the building is of the faction, False otherwise
        """
        return (
            faction_id == self.faction.value
            or (
                faction_id == ""
                and subculture == self.faction_to_culture[self.faction.value].subculture
            )
            or (
                faction_id == ""
                and subculture == ""
                and culture == self.faction_to_culture[self.faction.value].culture
            )
            or (
                faction_id == ""
                and subculture == ""
                and culture == ""
                and "nomad" not in culture
                and "mig" not in culture
                and "religion" not in culture
                and "ruin" not in culture
            )
        )

    def parse_building_effects_junction_tables(self):
        path_buildings = self.game_dir / "building_effects_junction_table.tsv"
        # Read file building_effects_junction_table.tsv (tabulated)
        data = parse_tsv(path_buildings)
        if len(self.buildings) == 0:
            self.parse_buildings_culture_variants_table()
        # for buil in self.buildings[self.campaign.value[1]]:
        #     print(buil)
        for building_id, effect, scope, amount in data:
            if building_id not in self.buildings[self.campaign.value[1]]:
                continue
            try:
                scope_value = self.get_scope(scope)
            except ValueError:
                print(f"Unsupported scope {scope} for building {building_id}")
                self.buildings[self.campaign.value[1]].pop(building_id)
                continue
            if scope_value is None:
                self.unsupported_effects.append((building_id, effect, scope))
            self.buildings[self.campaign.value[1]][building_id].add_effect(
                effect, scope_value, float(amount), raw_scope=scope
            )

    def parse_factions_table(self) -> dict[str, Faction]:
        subculture_to_culture = self.parse_cultures_subcultures()
        path_factions = self.game_dir / "factions_table.tsv"
        data = parse_tsv(path_factions)
        faction_to_culture = {}
        for faction_id1, _, subculture3, _, faction_name5, _, _, _, _, *_rest in data:
            # Associate faction to culture and subculture
            faction_to_culture[faction_id1] = Faction(
                faction_id1,
                faction_name5,
                subculture_to_culture[subculture3],
                subculture3,
            )
        return faction_to_culture

    def parse_cultures_subcultures(self) -> dict[str, str]:
        path_cultures = self.game_dir / "cultures_subcultures_table.tsv"
        data = parse_tsv(path_cultures)
        subculture_to_culture = {}
        for subculture1, culture2, *_rest in data:
            # Associate subculture to culture
            subculture_to_culture[subculture1] = culture2
        return subculture_to_culture

    def parse_cultures_subcultures_table(self) -> None:
        pass

    def process_primary_region(self, region, building):
        """
        Sets building limits and region type for primary regions.
        :param region: the region
        :param building: the building entry
        """
        if "major" in building:
            region.set_buildings_limit(5)
            region.set_region_type(RegionType.REGION_MAJOR)
        else:
            region.set_buildings_limit(3)
            region.set_region_type(RegionType.REGION_MINOR)

    def process_port_region(self, region, building):
        """
        Handles port regions, setting port or spice resources.
        :param region: the region
        :param building: the building entry
        """
        if "spice" not in building:
            region.set_has_port(RegionPort.REGION_PORT)
        else:
            region.set_has_ressource(AttilaRegionResources.ATTILA_REGION_SPICE)

    def process_secondary_region(self, region, building):
        """
        Assigns resources to secondary regions.
        :param region: the region
        :param building: the building entry
        """
        if "city" in building:
            region.set_has_ressource(AttilaRegionResources.ATTILA_REGION_CHURCH_ORTHODOX)
        else:
            for resource in AttilaRegionResources:
                if resource.value in building:
                    region.set_has_ressource(resource)
