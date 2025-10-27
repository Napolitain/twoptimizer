"""
Hearts of Iron IV parsers package.

This package contains parsers for extracting data from HOI4 game files.
"""

from .base_parser import BaseParser
from .building_parser import BuildingParser

__all__ = [
    "BaseParser",
    "BuildingParser",
]
