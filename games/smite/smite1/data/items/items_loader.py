"""
Items data loader for Smite 1.
Dynamically loads all items from the items directory.
"""

import importlib.util
from pathlib import Path
from typing import List

from games.smite.smite1.item import Item


def load_all_items() -> List[Item]:
    """
    Load all items from the items directory.
    
    Returns:
        List of Item instances
    """
    items = []
    items_dir = Path(__file__).parent
    
    # Load all item_*.py files (excluding starter items for now as they're incomplete)
    for file in sorted(items_dir.glob('item_*.py')):
        # Skip starter items as they're not fully implemented
        if 'starter' in file.name:
            continue
            
        try:
            # Dynamically import the module
            spec = importlib.util.spec_from_file_location(file.stem, file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # If the module defines a variable 'item', add it to the list
            if hasattr(module, 'item'):
                item = getattr(module, 'item')
                items.append(item)
        except Exception as e:
            # Skip items that can't be loaded
            pass
    
    return items


# Load all items on module import
ALL_ITEMS = load_all_items()

__all__ = ['ALL_ITEMS', 'load_all_items']
