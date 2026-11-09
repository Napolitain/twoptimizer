"""Source manifests survive wheel installation and never rewrite historical evidence."""

import hashlib
from dataclasses import replace
from pathlib import Path
from shutil import copyfile

import pytest

from games.tw.rome2 import provenance as rome_provenance
from tests.support.ui import result
from twoptimizer import provenance
from twoptimizer.models import CaseResult
from twoptimizer.registry import game_plugin, game_plugins


@pytest.mark.parametrize("game", [plugin.identifier for plugin in game_plugins()])
def test_registered_manifest_has_canonical_existing_source_keys(game):
    sources = provenance.source_files(game)
    assert sources
    assert list(sources) == sorted(sources)
    assert "games/optimization/resources.py" in sources
    assert "twoptimizer/registry.py" in sources
    assert "twoptimizer/game_plugin.py" in sources
    assert "twoptimizer/session_cache.py" in sources
    for name, digest in sources.items():
        assert name.startswith(("games/", "twoptimizer/"))
        assert not Path(name).is_absolute() and ".." not in Path(name).parts
        assert digest == hashlib.sha256((provenance.PACKAGE_ROOT / name).read_bytes()).hexdigest()


@pytest.mark.parametrize(
    ("game", "files"),
    [
        ("attila", ("builder.py", "construction.py", "loader.py", "context.py")),
        ("rome2", ("model.py", "holding_compiler.py", "records.py")),
        ("shogun2", ("model.py", "records.py")),
        ("three_kingdoms", ("model.py", "records.py", "parsing.py")),
    ],
)
def test_registered_manifest_tracks_game_owned_compilers_and_typed_catalogs(game, files):
    sources = provenance.source_files(game)
    assert {f"games/tw/{game}/{name}" for name in files} <= sources.keys()
    assert not sources.keys() & {
        "games/tw/problem.py",
        "games/tw/context.py",
        "games/tw/rome2/backends.py",
        "games/tw/rome2/decomposition.py",
        "games/tw/attila/native_parts.py",
        "twoptimizer/engines.py",
    }


def test_manifest_is_independent_of_install_location(tmp_path, monkeypatch):
    expected = provenance.source_files("three_kingdoms")
    site_packages = tmp_path / "lib/python3.14/site-packages"
    for name in expected:
        target = site_packages / name
        target.parent.mkdir(parents=True, exist_ok=True)
        copyfile(provenance.PACKAGE_ROOT / name, target)
    monkeypatch.setattr(provenance, "PACKAGE_ROOT", site_packages)
    assert provenance.source_files("three_kingdoms") == expected
    changed = "games/optimization/exact.py"
    (site_packages / changed).write_text("# changed source\n")
    current = provenance.source_files("three_kingdoms")
    assert current[changed] != expected[changed]
    assert {name for name in current if current[name] != expected[name]} == {changed}


def test_rome_replay_fingerprint_tracks_shared_core_at_any_install_location(tmp_path, monkeypatch):
    expected = rome_provenance.model_fingerprint()
    for name in provenance.source_files("rome2"):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        copyfile(provenance.PACKAGE_ROOT / name, target)
    monkeypatch.setattr(rome_provenance, "PACKAGE_ROOT", tmp_path)
    assert rome_provenance.model_fingerprint() == expected
    (tmp_path / "games/optimization/cp_backend.py").write_text("# changed compilation\n")
    assert rome_provenance.model_fingerprint() != expected


def test_missing_manifest_entry_fails_instead_of_silently_reusing_old_proofs(monkeypatch):
    plugin = replace(game_plugin("rome2"), source_patterns=("games/tw/retired.py",))
    monkeypatch.setattr(provenance, "game_plugin", lambda game: plugin)
    with pytest.raises(FileNotFoundError, match=r"retired\.py"):
        provenance.source_files("rome2")


@pytest.mark.parametrize("pattern", ["/outside.py", "../outside.py"])
def test_source_patterns_must_be_relative_to_the_distribution(tmp_path, pattern):
    with pytest.raises(ValueError, match="package-relative"):
        provenance._source_paths((pattern,), tmp_path)


def test_unknown_game_does_not_fall_back_to_attila():
    with pytest.raises(ValueError, match="Unknown game"):
        provenance.source_files("unknown")


def test_old_report_source_names_remain_readable_and_unmodified():
    historical = {
        "rome2/model.py": "a" * 64,
        "resources.py": "b" * 64,
        "twoptimizer/service.py": "c" * 64,
    }
    payload = {**result(), "timings": {}, "source_files": historical}
    restored = CaseResult.from_dict(payload)
    assert restored.to_dict()["source_files"] == historical
    assert payload["source_files"] == historical
