# Hearts of Iron IV Optimization Module

This module provides data structures and functionality for optimizing Hearts of Iron IV gameplay, including factory production, infrastructure, and military production using OR-Tools.

## Overview

The HoI4 module allows you to:
- Create and manage factions (nations/countries) with multiple regions
- Track industrial capacity (civilian and military factories)
- Monitor infrastructure levels
- Manage defensive structures (bunkers)
- Track naval and air bases
- Aggregate statistics across entire factions

This is the foundation for future optimization features using OR-Tools to determine optimal building strategies, production allocation, and resource management.

## Core Components

### Region

Represents a geographical area within a nation with various attributes:

```python
from games.hoi4 import Region

region = Region(
    name="Paris",
    civilian_factories=8,
    military_factories=4,
    infrastructure=7,
    bunkers=0,
    naval_bases=None,  # Optional
    air_bases=5        # Optional
)
```

**Attributes:**
- `name`: The name of the region
- `civilian_factories`: Number of civilian factories
- `military_factories`: Number of military factories
- `infrastructure`: Infrastructure level (affects production and supply)
- `bunkers`: Number of bunkers/fortifications
- `naval_bases`: Number of naval bases (optional)
- `air_bases`: Number of air bases (optional)

**Methods:**
- `total_factories()`: Returns the sum of civilian and military factories

### Faction

Represents a nation/country with multiple regions:

```python
from games.hoi4 import Faction, Region

faction = Faction(name="France")
faction.add_region(Region(name="Paris", civilian_factories=8))
faction.add_region(Region(name="Normandy", civilian_factories=3))
```

**Methods:**
- `add_region(region)`: Add a region to the faction
- `total_civilian_factories()`: Sum of all civilian factories
- `total_military_factories()`: Sum of all military factories
- `total_factories()`: Sum of all factories
- `average_infrastructure()`: Average infrastructure across all regions
- `total_bunkers()`: Sum of all bunkers
- `get_region(name)`: Retrieve a specific region by name

## Pre-built Factions

The module includes historically-inspired example factions:

```python
from games.hoi4 import (
    create_france_faction,
    create_germany_faction,
    create_soviet_union_faction,
)

france = create_france_faction()
germany = create_germany_faction()
soviet_union = create_soviet_union_faction()

print(f"France has {france.total_factories()} total factories")
print(f"Germany has {germany.total_factories()} total factories")
print(f"Soviet Union has {soviet_union.total_factories()} total factories")
```

### Available Pre-built Factions

1. **France** - 5 regions including Paris, Normandy, Lorraine, Provence, and Brittany
2. **Germany** - 3 regions including Berlin, Ruhr, and Bavaria
3. **Soviet Union** - 4 regions including Moscow, Leningrad, Stalingrad, and Urals

## Usage Examples

### Example 1: Creating a Custom Faction

```python
from games.hoi4 import Faction, Region

# Create a new faction
my_nation = Faction(name="My Custom Nation")

# Add regions
capital = Region(
    name="Capital City",
    civilian_factories=10,
    military_factories=5,
    infrastructure=8,
    bunkers=2
)

industrial_hub = Region(
    name="Industrial Region",
    civilian_factories=15,
    military_factories=10,
    infrastructure=7,
    bunkers=1
)

my_nation.add_region(capital)
my_nation.add_region(industrial_hub)

# View statistics
print(f"Total factories: {my_nation.total_factories()}")
print(f"Average infrastructure: {my_nation.average_infrastructure()}")
```

### Example 2: Comparing Factions

```python
from games.hoi4 import create_france_faction, create_germany_faction

france = create_france_faction()
germany = create_germany_faction()

print(f"France: {france.total_factories()} factories")
print(f"Germany: {germany.total_factories()} factories")

if germany.total_factories() > france.total_factories():
    print("Germany has industrial superiority")
else:
    print("France has industrial superiority")
```

### Example 3: Analyzing Regions

```python
from games.hoi4 import create_france_faction

france = create_france_faction()

# Iterate through all regions
for region in france.regions:
    print(f"{region.name}:")
    print(f"  Total factories: {region.total_factories()}")
    print(f"  Infrastructure: {region.infrastructure}")

# Access specific region
paris = france.get_region("Paris")
print(f"\nParis has {paris.civilian_factories} civilian factories")
```

## Running the Example

To see a comprehensive demonstration of the module's capabilities:

```bash
cd /home/runner/work/twoptimizer/twoptimizer
PYTHONPATH=/home/runner/work/twoptimizer/twoptimizer python games/hoi4/example_usage.py
```

## Running Tests

To run the unit tests:

```bash
cd /home/runner/work/twoptimizer/twoptimizer
python -m unittest tests.test_hoi4 -v
```

## Future Development

This module lays the groundwork for future optimization features:

1. **Factory Optimization**: Use OR-Tools to determine optimal allocation of civilian vs military factories
2. **Infrastructure Planning**: Optimize infrastructure construction for maximum production efficiency
3. **Production Scheduling**: Determine optimal military production schedules
4. **Resource Management**: Optimize resource allocation across regions
5. **Defense Planning**: Optimize bunker and fortification placement

## Contributing

When adding new features to this module:

1. Add comprehensive unit tests to `tests/test_hoi4.py`
2. Update this README with new functionality
3. Ensure all tests pass before committing
4. Follow the existing code style and patterns

## Data Validation

All region attributes are validated:
- Factories, infrastructure, bunkers, naval bases, and air bases cannot be negative
- Invalid values will raise a `ValueError` with a descriptive message

## License

This module is part of the twoptimizer project.
