"""Choose parallelism from the process CPU allocation, including containers."""

import os
from contextlib import suppress
from math import ceil
from pathlib import Path


def _quota_paths():
    paths = [Path("/sys/fs/cgroup/cpu.max")]
    try:
        for entry in Path("/proc/self/cgroup").read_text().splitlines():
            hierarchy, controllers, location = entry.split(":", 2)
            if hierarchy == "0" and not controllers:
                root = Path("/sys/fs/cgroup")
                parts = Path(location).parts[1:]
                if ".." not in parts:
                    paths.extend(
                        root.joinpath(*parts[:i], "cpu.max") for i in range(1, len(parts) + 1)
                    )
    except OSError, ValueError:
        pass
    return paths


def available_workers():
    counts = []
    for detected in (os.cpu_count(), getattr(os, "process_cpu_count", lambda: None)()):
        if detected:
            counts.append(detected)
    with suppress(AttributeError, OSError):
        counts.append(len(os.sched_getaffinity(0)))
    paths = _quota_paths()
    for path in paths:
        try:
            quota, period = path.read_text().split()
            if quota != "max" and int(quota) > 0 and int(period) > 0:
                counts.append(ceil(int(quota) / int(period)))
        except OSError, ValueError:
            pass
    try:
        quota = int(Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us").read_text())
        period = int(Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read_text())
        if quota > 0 and period > 0:
            counts.append(ceil(quota / period))
    except OSError, ValueError:
        pass
    return max(1, min(counts, default=1))


def resolve_workers(requested=None):
    if requested is None:
        return available_workers()
    if isinstance(requested, bool) or not isinstance(requested, int) or requested < 1:
        raise ValueError("Worker override must be a positive integer")
    return requested
