import importlib
from pathlib import Path
from typing import List

from games.smite.item import Item

items_list: List[Item] = []

# Get the current directory
current_dir = Path(__file__).parent

# Find all `items_entry_*.py` files in the items directory
items_dir = current_dir.parent / 'items'
for file in items_dir.glob('item_*.py'):
    module_name = file.stem

    # Dynamically import the module
    module = importlib.import_module(module_name)

    # If the module defines a variable `item`, clone it and add it to the list
    if hasattr(module, 'item'):
        item = getattr(module, 'item')
        items_list.append(item)
