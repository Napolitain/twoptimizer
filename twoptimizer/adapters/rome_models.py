"""Application observers for Rome's existing compilation boundaries.

These subclasses return the engine's models untouched. In particular the
canonical proof model is distinct from the linearization used by CP-SAT.
"""

from games.optimization.cp_backend import NativeCP
from games.tw.rome2.holdings import HoldingEconomy
from games.tw.rome2.model import Economy
from twoptimizer.progress import ModelStats, PhaseTimer


def record_build(phase: PhaseTimer, economy: Economy, model, algorithm: str) -> None:
    decisions = len(economy.decisions) + len(economy.party_variables)
    if isinstance(model, NativeCP):
        stats = ModelStats(
            "Rome II canonical proof model",
            len(model.model.proto.variables),
            len(model.model.proto.constraints),
            formulation="native_products",
            decision_variables=decisions,
        )
    else:
        stats = ModelStats(
            "Rome II linearized model",
            len(model.variable),
            len(model.constraint),
            formulation="linearized_income",
            stage="solver" if algorithm == "highs" else "reference",
            decision_variables=decisions,
            nonzeros=sum(len(row.var_index) for row in model.constraint),
        )
    phase.record_model(stats)


class ObservedEconomy(Economy):
    def __init__(self, scenario, data, phase: PhaseTimer, algorithm: str):
        super().__init__(scenario, data)
        self.phase = phase
        self.algorithm = algorithm

    def build(self, native=False):
        model = super().build(native)
        record_build(self.phase, self, model, self.algorithm)
        return model


class ObservedHoldingEconomy(HoldingEconomy):
    def __init__(self, scenario, data, phase: PhaseTimer, algorithm: str):
        super().__init__(scenario, data)
        self.phase = phase
        self.algorithm = algorithm

    def build(self, native=False):
        model = super().build(native)
        record_build(self.phase, self, model, self.algorithm)
        return model
