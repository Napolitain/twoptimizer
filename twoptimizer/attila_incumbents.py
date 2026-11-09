"""Validate and retain Attila candidates independently of a native search result."""

import json
from copy import deepcopy
from hashlib import sha256
from math import isfinite

from games.tw.competition import BinaryModel, Result
from games.tw.sparse import SparseConstraints


def model_identity(model: BinaryModel) -> str:
    """Hash sparse coefficients in storage order without visiting implied zeros.

    Historical report fingerprints remain available through ``signature``. New
    in-memory caches require exact identity, not the historical dense encoding.
    """
    if not isinstance(model.matrix, SparseConstraints):
        return model.fingerprint()
    matrix = model.matrix
    digest = sha256(b"attila-sparse-cache-v1")
    digest.update(json.dumps([model.names, matrix.shape, str(model.offset)]).encode())
    for array in (
        model.profit,
        matrix.indices,
        matrix.values,
        matrix.pointers,
        matrix.row_ids,
        model.lower,
        model.upper,
    ):
        digest.update(json.dumps([array.shape, array.dtype.str]).encode())
        digest.update(array.tobytes())
    return digest.hexdigest()


def checked(model: BinaryModel, result: Result | None) -> Result | None:
    if result is None:
        return None
    if result.status not in {"OPTIMAL", "FEASIBLE"} or result.relaxation:
        raise ValueError("An Attila incumbent must be an integral feasible layout")
    if result.values is None or not model.feasible(result.values):
        raise ValueError("Cached Attila layout violates the original model")
    income = float(model.profit @ result.values) + model.offset
    if result.objective is None or not isfinite(result.objective):
        raise ValueError("An Attila incumbent must have finite income")
    if abs(result.objective - income) > 1e-5:
        raise ValueError("Cached Attila income differs from its original model")
    if result.bound is not None and (not isfinite(result.bound) or result.bound < income - 1e-5):
        raise ValueError("Cached Attila upper bound is below its feasible income")
    return deepcopy(result)


def retain(model: BinaryModel, result: Result, previous: Result | None) -> Result:
    """Matching model identity is the caller's prerequisite for reusing a bound."""
    if previous is None:
        return result
    assert previous.objective is not None
    if result.status == "INFEASIBLE" or (
        result.status == "OPTIMAL"
        and (result.objective is None or result.objective < previous.objective - 1e-5)
    ):
        raise RuntimeError("Native proof contradicts the validated previous Attila layout")
    if result.status not in {"UNKNOWN", "FEASIBLE", "OPTIMAL"}:
        return result
    result = deepcopy(result)
    retained = result.objective is None or previous.objective > result.objective
    native_status = result.status
    if retained:
        result.values = list(previous.values or ())
        result.objective = previous.objective
        result.status = "FEASIBLE"
    result.bound = min(
        (bound for bound in (previous.bound, result.bound) if bound is not None), default=None
    )
    checked(model, result)
    result.model_stats["warm_start"] = {"validated": True, "retained": retained}
    if result.status != native_status:
        result.model_stats["native_status"] = native_status
    return result
