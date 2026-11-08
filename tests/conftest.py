"""Explicit, isolated engine dependencies for arithmetic examples."""

import pytest

from games.tw.context import GameContext


@pytest.fixture
def context() -> GameContext:
    return GameContext(fertility=2)
