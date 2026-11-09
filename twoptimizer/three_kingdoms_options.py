"""Explicit snapshot inputs shared by Three Kingdoms CLI and terminal controls."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ThreeKingdomsOptions:
    city_level: int | None = 5
    population: int = 1_000_000
    corruption_percent: int = 0
    order_offset: int = 0
    minimum_order: int = 0
    external_food: int = 0
    capital_commandery: str | None = None
    external_resources: tuple[str, ...] = ()
    include_leader_effects: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.external_resources, (tuple, list)) or any(
            not isinstance(value, str) or not value for value in self.external_resources
        ):
            raise ValueError("External resources must be a list of resource IDs.")
        if len(set(self.external_resources)) != len(self.external_resources):
            raise ValueError("List each external resource only once.")
        object.__setattr__(self, "external_resources", tuple(self.external_resources))

    def validate(self) -> None:
        from games.tw.three_kingdoms.scenario import Commandery, Scenario

        options = self.to_dict()
        food = options.pop("external_food")
        capital = options.pop("capital_commandery")
        resources = tuple(options.pop("external_resources"))
        leader = options.pop("include_leader_effects")
        commandery = Commandery("validation", **options)
        Scenario(
            "validation",
            (commandery,),
            external_food=food,
            capital_commandery=capital,
            external_resources=resources,
            include_leader_effects=leader,
        )

    def to_dict(self) -> dict:
        return {
            **{key: getattr(self, key) for key in self.__dataclass_fields__},
            "external_resources": list(self.external_resources),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> ThreeKingdomsOptions:
        if not isinstance(payload, dict):
            raise ValueError("Three Kingdoms options must be a JSON object.")
        return cls(**payload)
