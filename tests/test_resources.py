"""Automatic parallelism respects affinity, container quotas and backend support."""

from pathlib import Path

import numpy as np
import pytest

from games.tw import resources
from games.tw.competition import BinaryModel, solve


@pytest.mark.parametrize(
    "root_limit,nested_limit,affinity,expected",
    [
        ("max 100000", None, 8, 8),
        ("400000 100000", None, 8, 4),
        ("max 100000", "150000 100000", 8, 2),
        ("max 100000", "400000 100000", 2, 2),
    ],
)
def test_cpu_allocation(root_limit, nested_limit, affinity, expected, monkeypatch):
    monkeypatch.setattr(resources.os, "cpu_count", lambda: 16)
    monkeypatch.setattr(resources.os, "process_cpu_count", lambda: None, raising=False)
    monkeypatch.setattr(
        resources.os, "sched_getaffinity", lambda _: set(range(affinity)), raising=False
    )
    files = {"/sys/fs/cgroup/cpu.max": root_limit, "/proc/self/cgroup": "0::/job\n"}
    if nested_limit is not None:
        files["/sys/fs/cgroup/job/cpu.max"] = nested_limit

    def read(path):
        if str(path) not in files:
            raise FileNotFoundError(str(path))
        return files[str(path)]

    monkeypatch.setattr(Path, "read_text", read)
    assert resources.available_workers() == expected


def test_auto_workers_and_advanced_override(monkeypatch):
    monkeypatch.setattr(resources, "available_workers", lambda: 3)
    assert resources.resolve_workers() == 3
    assert resources.resolve_workers(2) == 2
    for invalid in (0, -1, True, 2.5):
        with pytest.raises(ValueError):
            resources.resolve_workers(invalid)
    model = BinaryModel(
        ("x",), np.array([1.0]), np.array([[1.0]]), np.array([0.0]), np.array([1.0])
    )
    for algorithm in ("cp-sat", "highs"):
        automatic = solve(model, algorithm)
        explicit = solve(model, algorithm, workers=1)
        assert automatic.workers == 3 and explicit.workers == 1
        assert automatic.status == explicit.status == "OPTIMAL"
        assert automatic.objective == explicit.objective == 1
