"""
Gods data package for Smite 1.
Contains all god definitions with their base statistics loaded from CSV.
"""

from games.smite.smite1.data.gods.gods_loader import _ALL_GODS, __all__

# Import all gods into this module's namespace
globals().update(_ALL_GODS)
