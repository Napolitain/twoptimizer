"""Built-in integrations preserve public entry points and truthful capabilities."""

import subprocess
import sys
from types import SimpleNamespace

import pytest

from twoptimizer import __main__ as entry
from twoptimizer.registry import choices, game_plugin, game_plugins, solve_adapter
from twoptimizer.requests import default_config, make_jobs


@pytest.mark.parametrize(
    ("command", "module"),
    [
        ("rome2", "games.tw.rome2.benchmark"),
        ("attila", "games.tw.attila.benchmark"),
        ("attila-factions", "games.tw.attila.faction_comparison"),
        ("shogun2", "games.tw.shogun2.benchmark"),
        ("three-kingdoms", "twoptimizer.three_kingdoms_cli"),
        ("three_kingdoms", "twoptimizer.three_kingdoms_cli"),
        ("hoi4", "games.hoi4.cli"),
    ],
)
def test_cli_dispatch_preserves_commands_aliases_and_arguments(monkeypatch, command, module):
    loaded, arguments = [], []

    def load(name):
        loaded.append(name)
        return SimpleNamespace(main=arguments.append)

    monkeypatch.setattr(entry.importlib, "import_module", load)
    assert entry.main([command, "--help"]) == 0
    assert loaded == [module]
    assert arguments == [["--help"]]


@pytest.mark.parametrize(
    "game", [plugin.identifier for plugin in game_plugins() if plugin.optimizable]
)
def test_registered_optimizers_expand_their_typed_defaults(game):
    plugin, options = game_plugin(game), choices(game)
    config = default_config(game)
    jobs, skipped = make_jobs(config)
    assert jobs == [config] and skipped == []
    assert config.faction == options.default_faction
    assert config.province == options.default_province
    assert config.research == options.default_research
    assert config.algorithm in plugin.algorithms
    assert plugin.capabilities.joint_holdings
    assert plugin.session_cache is not None


def test_hoi4_keeps_inspection_and_planning_commands_without_claiming_a_static_optimizer(capsys):
    plugin = game_plugin("hoi4")
    assert plugin.capabilities.reference_inspector
    assert not plugin.optimizable and plugin.algorithms == ()
    assert plugin.session_cache is None
    assert choices("hoi4").factions == ()
    with pytest.raises(ValueError, match="complete optimizer"):
        solve_adapter("hoi4")
    with pytest.raises(ValueError, match="complete optimizer"):
        default_config("hoi4")
    assert entry.main(["--help"]) == 0
    text = capsys.readouterr().out
    assert "hoi4 data" in text and "hoi4 plan-check" in text


def test_registry_rejects_unknown_games():
    with pytest.raises(ValueError, match="Unknown game"):
        game_plugin("missing")


def test_metadata_import_does_not_load_native_solvers_or_game_models():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from twoptimizer.registry import command_help; "
            "assert command_help(); "
            "assert not any(name.startswith(('ortools', 'twoptimizer.adapters')) "
            "for name in sys.modules); "
            "assert 'games.tw.attila.model' not in sys.modules",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == result.stderr == ""
