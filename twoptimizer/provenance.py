"""Canonical package-relative hashes of game models, data and solve preparation.

The package root is the checkout root or the installed wheel's site-packages
folder. Historical reports retain their original source keys; only newly created
reports use this manifest, so a migration invalidates reuse without rewriting
old evidence or changing the mathematical model fingerprint.
"""

import hashlib
from pathlib import Path

from twoptimizer.registry import game_plugin

PACKAGE_ROOT = Path(__file__).resolve().parent.parent

COMMON_SOURCES = (
    "games/optimization/*.py",
    "twoptimizer/catalog.py",
    "twoptimizer/game_plugin.py",
    "twoptimizer/registry.py",
    "twoptimizer/provenance.py",
    "twoptimizer/requests.py",
    "twoptimizer/models.py",
    "twoptimizer/constraint_options.py",
    "twoptimizer/constraint_comparison.py",
    "twoptimizer/service.py",
    "twoptimizer/session.py",
    "twoptimizer/session_cache.py",
    "twoptimizer/holdings.py",
    "twoptimizer/progress.py",
    "twoptimizer/search_measurements.py",
    "twoptimizer/adapters/model_stats.py",
    "twoptimizer/adapters/search.py",
)


def _source_paths(patterns: tuple[str, ...], root: Path) -> tuple[Path, ...]:
    paths: set[Path] = set()
    for pattern in patterns:
        if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
            raise ValueError("Source manifests require package-relative paths")
        matches = tuple(path for path in root.glob(pattern) if path.is_file())
        if not matches:
            raise FileNotFoundError(f"Source manifest matched no packaged files: {pattern}")
        paths.update(matches)
    return tuple(sorted(paths))


def source_files(game: str) -> dict[str, str]:
    """Hash the registered game and shared solve sources without caching file content."""
    plugin = game_plugin(game)
    paths = _source_paths((*COMMON_SOURCES, *plugin.source_patterns), PACKAGE_ROOT)
    return {
        path.relative_to(PACKAGE_ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
    }
