"""One source fingerprint shared by report creation and independent replay."""

import hashlib
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[3]

MODEL_SOURCES = (
    *(
        f"games/tw/rome2/{name}"
        for name in (
            "model.py",
            "linear.py",
            "compiler.py",
            "optimization.py",
            "joint_search.py",
            "bound_search.py",
            "native_search.py",
            "placement.py",
            "scenario.py",
            "building_constraints.py",
            "catalog.py",
            "records.py",
            "effects.py",
            "world.py",
            "provenance.py",
            "data/world.json",
            "data/world_modifiers.json",
        )
    ),
    "games/tw/immutable.py",
)


def model_fingerprint() -> str:
    """Fingerprint source provenance, separately from compiled-model proof identity."""
    core = (
        path.relative_to(PACKAGE_ROOT).as_posix()
        for path in (PACKAGE_ROOT / "games/optimization").glob("*.py")
    )
    digest = hashlib.sha256()
    for name in sorted((*MODEL_SOURCES, *core)):
        digest.update(name.encode())
        digest.update((PACKAGE_ROOT / name).read_bytes())
    return digest.hexdigest()
