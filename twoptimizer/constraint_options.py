"""Optional user requirements, separate from the games' always-enforced rules."""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class ConstraintOptions:
    required_buildings: tuple[str, ...] = ()
    forbidden_buildings: tuple[str, ...] = ()
    minimum_religious_influence: float | None = None
    shogun_religion: str | None = None
    nanban_contact: bool = False

    def __post_init__(self) -> None:
        for field in ("required_buildings", "forbidden_buildings"):
            value = getattr(self, field)
            if not isinstance(value, (tuple, list)) or any(
                not isinstance(key, str) or not key.strip() for key in value
            ):
                raise ValueError("Building requirements must be lists of exact building IDs.")
            if len(set(value)) != len(value):
                raise ValueError("List each required or forbidden building only once.")
            object.__setattr__(self, field, tuple(value))
        if set(self.required_buildings) & set(self.forbidden_buildings):
            raise ValueError("A building cannot be both required and forbidden.")
        self._validate_religion()

    def _validate_religion(self) -> None:
        value = self.minimum_religious_influence
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(value)
            or value < 0
        ):
            raise ValueError("Minimum religious influence must be finite and nonnegative.")
        if self.shogun_religion not in (None, "buddhist", "christian", "ikko"):
            raise ValueError("Choose a supported Shogun religion.")
        if not isinstance(self.nanban_contact, bool):
            raise ValueError("Nanban contact must be a boolean.")

    def to_dict(self) -> dict:
        result = {}
        for field in ("required_buildings", "forbidden_buildings"):
            if value := getattr(self, field):
                result[field] = list(value)
        for field in ("minimum_religious_influence", "shogun_religion"):
            if (value := getattr(self, field)) is not None:
                result[field] = value
        if self.nanban_contact:
            result["nanban_contact"] = True
        return result

    @classmethod
    def from_dict(cls, payload: dict) -> ConstraintOptions:
        if not isinstance(payload, dict):
            raise ValueError("Optional constraints must be a JSON object.")
        if unknown := set(payload) - cls.__dataclass_fields__.keys():
            raise ValueError(f"Unknown optional constraints: {sorted(unknown)}")
        return cls(**payload)

    def validate_game(self, game: str) -> None:
        if self.minimum_religious_influence is not None and game != "attila":
            raise ValueError("Minimum religious influence is currently supported for Attila.")
        if (self.shogun_religion is not None or self.nanban_contact) and game != "shogun2":
            raise ValueError("Shogun religion and Nanban contact require Shogun 2.")
