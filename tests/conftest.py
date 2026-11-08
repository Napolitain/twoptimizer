"""Explicit, isolated engine dependencies for arithmetic examples."""

import pytest

from games.tw.context import GameContext
from tests.support.rome2 import tiny_catalog


@pytest.fixture
def context() -> GameContext:
    return GameContext(fertility=2)


@pytest.fixture
def tiny():
    return tiny_catalog()
