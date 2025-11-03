"""
Optimization package for HOI4.

Provides optimization models and solvers for various HOI4 problems.
"""

from .production_optimizer import ProductionOptimizer

__all__ = [
    "ProductionOptimizer",
]
