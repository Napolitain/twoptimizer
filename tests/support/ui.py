"""Deterministic worker results and cancellable UI test doubles."""

import asyncio

from twoptimizer.models import RunConfig


def result(config=None):
    config = config or RunConfig()
    return {
        "request": config.to_dict(),
        "faction": "Rome",
        "province": "Coastal reference",
        "solver": {
            "algorithm": config.algorithm,
            "status": "OPTIMAL",
            "seconds": 0.1,
            "objective": 4182.7,
            "bound": 4182.7,
        },
        "income": 4182.7,
        "gap_percent": 0,
        "metrics": {"food_surplus": 2, "public_order": 1},
        "buildings": [{"region": "Capital", "building": "Test Market", "id": "market_4"}],
        "assumptions": "Explicit test scenario",
        "source_files": {},
        "raw": {},
    }


class QuickRunner:
    def __init__(self):
        self.cancelled = False

    async def run(self, config, on_log, on_progress=None):
        await asyncio.sleep(0.02)
        if on_progress:
            on_progress("Solving and validating")
        on_log("Validated test layout")
        return result(config)

    async def stop(self):
        self.cancelled = True
