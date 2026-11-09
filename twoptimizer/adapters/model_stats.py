"""Read compiled model sizes without changing or compiling the models again."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from games.optimization.sparse import SparseConstraints
from twoptimizer.progress import ModelStats, PhaseTimer

if TYPE_CHECKING:
    from games.optimization.competition import BinaryModel


def record_binary(
    phase: PhaseTimer, model: BinaryModel, label: str, decisions: int, algorithm: str
) -> None:
    matrix = model.matrix
    nonzeros = (
        len(matrix.values)
        if isinstance(matrix, SparseConstraints)
        else int(np.count_nonzero(matrix))
    )
    phase.record_model(
        ModelStats(
            label,
            len(model.names),
            matrix.shape[0],
            formulation="expanded_boolean",
            stage="solver" if algorithm == "highs" else "reference",
            decision_variables=decisions,
            nonzeros=nonzeros,
            storage_bytes=matrix.nbytes,
        )
    )


def record_cp_result(phase: PhaseTimer, solver: dict, decisions: int) -> None:
    """Record actual native inputs before/after search; omit reused proof counts."""
    if solver.get("algorithm") != "cp-sat" or "proof_reused_from" in solver:
        return
    for stage in solver.get("stages", [solver]):
        stats = stage.get("model_stats") or stage
        if stats.get("formulation") not in {
            "factored_income",
            "expanded_boolean",
            "linearized_income",
        }:
            continue
        phase.record_model(
            ModelStats(
                "CP-SAT solver input",
                stats["variables"],
                stats["constraints"],
                formulation=stats["formulation"],
                stage="solver",
                # The compact Attila builder can eliminate fixed decisions.
                # Its native decision/auxiliary split is not exposed.
                decision_variables=None if stats["formulation"] == "factored_income" else decisions,
            )
        )
