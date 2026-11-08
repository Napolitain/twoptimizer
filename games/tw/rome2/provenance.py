"""One source fingerprint shared by report creation and independent replay."""

import hashlib
from pathlib import Path

MODEL_SOURCES = (
    "model.py",
    "linear.py",
    "compiler.py",
    "optimization.py",
    "backends.py",
    "placement.py",
    "scenario.py",
    "building_constraints.py",
    "catalog.py",
    "records.py",
    "effects.py",
    "world.py",
    "provenance.py",
    "../immutable.py",
    "data/world.json",
    "data/world_modifiers.json",
)


def model_fingerprint() -> str:
    root = Path(__file__).parent
    digest = hashlib.sha256()
    for name in MODEL_SOURCES:
        digest.update(name.encode())
        digest.update((root / name).read_bytes())
    return digest.hexdigest()
