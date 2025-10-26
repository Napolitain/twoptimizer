# Smite 1 God Builder

This module provides optimization tools for building gods in Smite 1 to maximize DPS (Damage Per Second).

## Features

- **GodBuilder**: Optimizes god item builds using OR-TOOLS linear programming
- **Constraints**:
  - Exactly 6 items per build
  - Maximum 1 starter item (included in the 6 total)
- **Optimization**: Maximizes DPS based on:
  - Physical/Magical Power from items
  - Attack Speed from items
  - God base stats and scaling

## Usage

### Basic Example

```python
from games.smite.smite1.data.gods.gods_loader import _ALL_GODS
from games.smite.smite1.data.items.items_loader import ALL_ITEMS
from games.smite.smite1.god_builder import GodBuilder
from games.smite.smite1.enums import PowerType

# Load a god
god = _ALL_GODS['ah_muzen_cab']

# Filter items for physical gods
relevant_items = [
    item for item in ALL_ITEMS 
    if item.stats and (
        item.stats.power_physical > 0 or 
        (item.stats.basic_attack_speed > 0 and item.stats.power_magical == 0)
    )
]

# Create builder and optimize
builder = GodBuilder(god, relevant_items)
result = builder.optimize_build()

if result:
    build, dps = result
    print(f"Optimized DPS: {dps:.2f}")
    print(f"Items: {build.item1.name}, {build.item2.name}, ...")
```

### Running Examples

Run the main script to see optimization for multiple gods:

```bash
python -m games.smite.smite1.main
```

Or run the detailed example:

```bash
python -m games.smite.smite1.example_god_builder
```

### Running Tests

```bash
python -m unittest tests.test_god_builder
```

## Classes

### GodBuilder

Main class for optimizing god builds.

**Methods:**
- `__init__(god, available_items)`: Initialize builder with a god and available items
- `optimize_build()`: Returns `(Build, DPS)` tuple with optimized build
- `calculate_dps(items)`: Calculate DPS for a specific set of items

### God

Represents a god with stats and abilities.

**Key Methods:**
- `get_dps_basic_attack()`: Calculate DPS with current build
- `get_basic_attack_damage()`: Calculate basic attack damage
- `get_hp()`: Get total HP including items and buffs

### Build

Dataclass representing an item build with 6 item slots.

**Fields:**
- `item1` through `item6`: Item slots (item1 can be a Starter)

## Implementation Details

### Optimization Approach

The optimizer uses OR-TOOLS with a linear programming approach. Since DPS = damage × attack_speed is non-linear (product of two variables), we use a weighted linear combination that approximates DPS maximization:

```
Maximize: (scaling × base_AS) × power + base_damage × attack_speed
```

This linear approximation favors balanced builds and produces optimal results.

### DPS Calculation

DPS is calculated as:

```python
final_damage = base_damage + (scaling / 100) × total_power
final_attack_speed = base_AS + (item_AS / 100)
DPS = min(final_damage, damage_limit) × min(final_attack_speed, AS_limit)
```

## Data Loading

- **Gods**: Loaded from `data/gods/gods_data.csv`
- **Items**: Dynamically loaded from `data/items/item_*.py` files

Currently, only regular items are loaded. Starter items are incomplete in the data files.
