"""Backend-independent failures that allow an exact formulation fallback."""


class UnsupportedFormulation(ValueError):
    """An optional formulation cannot safely represent the requested model."""
