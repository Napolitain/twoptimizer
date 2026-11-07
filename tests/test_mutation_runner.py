"""Ensure the mutation gate cannot pass with stale, empty or failed results."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools import mutation


def successful_stats():
    return dict(
        killed=2,
        total=2,
        survived=0,
        no_tests=0,
        suspicious=0,
        timeout=0,
        segfault=0,
        check_was_interrupted_by_user=0,
    )


def install_runner(monkeypatch, tmp_path, stats):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["mutation.py"])
    path = Path("mutants/mutmut-cicd-stats.json")
    path.parent.mkdir()
    path.write_text(json.dumps(successful_stats()))
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        assert kwargs["check"]
        if argv[1] == "run":
            assert not path.exists(), "Stale stats must be removed before executing tests"
        if argv[1] == "export-cicd-stats" and stats is not None:
            path.write_text(json.dumps(stats))

    monkeypatch.setattr(mutation.subprocess, "run", run)
    return calls


def test_successful_mutation_gate_uses_new_results(monkeypatch, tmp_path):
    calls = install_runner(monkeypatch, tmp_path, successful_stats())
    assert mutation.main() == 0
    assert calls == [["mutmut", "run"], ["mutmut", "export-cicd-stats"]]


@pytest.mark.parametrize(
    "failure",
    [
        "survived",
        "no_tests",
        "suspicious",
        "timeout",
        "segfault",
        "check_was_interrupted_by_user",
        "empty",
    ],
)
def test_failed_or_empty_mutation_results_fail_the_gate(monkeypatch, tmp_path, failure):
    stats = successful_stats()
    stats["total" if failure == "empty" else failure] = 0 if failure == "empty" else 1
    calls = install_runner(monkeypatch, tmp_path, stats)
    assert mutation.main() == 1
    assert calls[-1] == ["mutmut", "results"]


def test_missing_new_export_cannot_reuse_old_success(monkeypatch, tmp_path):
    install_runner(monkeypatch, tmp_path, None)
    with pytest.raises(FileNotFoundError):
        mutation.main()


def test_mutation_process_failure_is_preserved(monkeypatch, tmp_path):
    install_runner(monkeypatch, tmp_path, successful_stats())

    def fail(argv, **kwargs):
        raise subprocess.CalledProcessError(2, argv)

    monkeypatch.setattr(mutation.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError) as error:
        mutation.main()
    assert error.value.returncode == 2


def test_partial_mutation_run_fails_the_gate(monkeypatch, tmp_path):
    stats = successful_stats()
    stats["total"] = 3
    install_runner(monkeypatch, tmp_path, stats)
    assert mutation.main() == 1
