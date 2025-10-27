"""
Hearts of Iron IV models package.

This package contains data models for representing HOI4 game objects.
"""

from .building import Building
from .modifier import Modifier

__all__ = [
    "Building",
    "Modifier",
]
