"""Typed application contracts; individual engines retain their own scenarios."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from twoptimizer.models import EngineResult, RunConfig
    from twoptimizer.progress import PhaseTimer
    from twoptimizer.session import RunSession

type Choice = tuple[str, str]


@dataclass(frozen=True, slots=True)
class GameChoices:
    factions: tuple[Choice, ...] = ()
    provinces: tuple[Choice, ...] = ()
    research: tuple[Choice, ...] = ()
    default_faction: str = ""
    default_province: str = ""
    default_research: str = ""


@dataclass(frozen=True, slots=True)
class GameCommand:
    name: str
    module: str
    description: str
    aliases: tuple[str, ...] = ()
    examples: tuple[Choice, ...] = ()


@dataclass(frozen=True, slots=True)
class GameCapabilities:
    joint_holdings: bool = False
    borders: bool = False
    reference_inspector: bool = False


class SolveAdapter(Protocol):
    def __call__(
        self, config: RunConfig, phase: PhaseTimer, session: RunSession | None
    ) -> EngineResult: ...


class SessionCache(Protocol):
    def clear(self) -> None: ...

    def trim(self, limit: int) -> None: ...


@dataclass(frozen=True, slots=True)
class GamePlugin:
    """Built-in app integration, without prescribing a universal game model."""

    identifier: str
    label: str
    notes: str
    commands: tuple[GameCommand, ...]
    load_choices: Callable[[], GameChoices]
    source_patterns: tuple[str, ...]
    capabilities: GameCapabilities = GameCapabilities()
    algorithms: tuple[str, ...] = ()
    load_adapter: Callable[[], SolveAdapter] | None = None
    session_cache: Callable[[RunSession], SessionCache] | None = None

    @property
    def optimizable(self) -> bool:
        return self.load_adapter is not None
