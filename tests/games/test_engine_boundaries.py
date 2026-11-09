"""A game must not depend on another game's optimization implementation."""

import pytest

from tests.support.imports import imports
from tests.support.paths import REPO_ROOT

GAMES = ("attila", "rome2", "shogun2", "three_kingdoms")


@pytest.mark.parametrize("game", GAMES)
def test_engines_use_shared_mechanisms_without_importing_sibling_engines(game):
    forbidden = tuple(f"games.tw.{other}" for other in GAMES if other != game)
    violations = [
        (str(path.relative_to(REPO_ROOT)), module)
        for path in (REPO_ROOT / "games/tw" / game).rglob("*.py")
        for module in imports(path)
        if any(module == prefix or module.startswith(prefix + ".") for prefix in forbidden)
    ]
    assert violations == []
