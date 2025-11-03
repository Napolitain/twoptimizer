# Hearts of Iron IV Optimization Module

This module provides data structures and functionality for optimizing Hearts of Iron IV gameplay, including factory production, infrastructure, and military production using OR-Tools.

## Overview

The HoI4 module allows you to:
- Create and manage factions (nations/countries) with multiple states
- Track industrial capacity (civilian and military factories)
- Monitor infrastructure levels
- Manage defensive structures (bunkers)
- Track naval and air bases
- Handle building slots and state categories
- Track resources (oil, steel, aluminum, etc.)
- Manage manpower and victory points
- Apply state modifiers for game mechanics
- Aggregate statistics across entire factions
- **NEW**: Simulate game time with historical dates
- **NEW**: Model military equipment production with resource costs
- **NEW**: Optimize factory allocation using OR-Tools
- **NEW**: Plan production to meet targets by specific dates
- **NEW**: Model factory efficiency growth over time

## NEW in Phase 4: Production Optimization

Phase 4 adds complete production optimization capabilities:

### Quick Start - Production Optimization

```python
from games.hoi4 import ProductionOptimizer, HISTORICAL_DATES
from games.hoi4.models.equipment import create_infantry_equipment, create_artillery
from games.hoi4.optimization.production_optimizer import ProductionGoal

# Create optimizer
optimizer = ProductionOptimizer()

# Define goals
eq1 = create_infantry_equipment()
eq2 = create_artillery()

goals = [
    ProductionGoal(eq1, target_amount=5000, target_date=HISTORICAL_DATES["war_start"], weight=2.0),
    ProductionGoal(eq2, target_amount=1000, target_date=HISTORICAL_DATES["war_start"], weight=1.0),
]

# Optimize
result = optimizer.optimize_production(
    available_military_factories=25.0,
    available_naval_factories=5.0,
    goals=goals,
    start_date=HISTORICAL_DATES["game_start"]
)

# View results
print(f"Status: {result.status}")
for eq_name, factories in result.factory_allocations.items():
    output = result.expected_output[eq_name]
    print(f"{eq_name}: {factories:.2f} factories → {output:.0f} units")
```

### Time Simulation

```python
from games.hoi4 import GameDate, GameClock, HISTORICAL_DATES

# Create a clock
clock = GameClock(start_date=HISTORICAL_DATES["game_start"])

# Advance time
clock.advance_to_date(HISTORICAL_DATES["war_start"])
print(f"Days until war: {clock.elapsed_days()}")  # 1339 days

# Historical dates available:
# - game_start (1936.01.01)
# - war_start (1939.09.01)
# - barbarossa (1941.06.22)
# - pearl_harbor (1941.12.07)
# - d_day (1944.06.06)
# - war_end_europe (1945.05.08)
```

### Equipment Production

```python
from games.hoi4.models.equipment import create_infantry_equipment, EQUIPMENT_DATABASE

# Get equipment
eq = create_infantry_equipment()
print(f"{eq.display_name}")
print(f"Cost: {eq.production_cost} IC")
print(f"Time: {eq.production_time} days")
print(f"Resources: {eq.resource_cost}")

# Available equipment types:
# - Infantry: infantry_equipment, artillery, anti_tank, anti_air
# - Armor: light_tank, medium_tank, heavy_tank, modern_tank
# - Air: fighter, cas, tactical_bomber, strategic_bomber, naval_bomber
# - Naval: destroyer, light_cruiser, heavy_cruiser, battleship, carrier, submarine
```

### Production Lines

```python
from games.hoi4 import Production, GameDate
from games.hoi4.models.equipment import create_infantry_equipment

prod = Production(military_factories=20)
eq = create_infantry_equipment()
start = GameDate(1936, 1, 1)
target = GameDate(1937, 1, 1)

# Add production line
line = prod.add_production_line(eq, 10.0, start)

# Calculate output (efficiency grows from 10% to 100% over 90 days)
total = line.calculate_output_by_date(target, start)
print(f"Total produced: {total:.0f} units")

# Resource consumption
consumption = line.get_daily_resource_consumption()
print(f"Steel per day: {consumption['steel']:.2f}")
```

For complete examples, see [PHASE4_SUMMARY.md](PHASE4_SUMMARY.md) and run the demonstration:
```bash
PYTHONPATH=/home/runner/work/twoptimizer/twoptimizer python games/hoi4/optimization_demo.py
```

## Core Components

### State

Represents a geographical area within a nation with comprehensive game mechanics:

```python
from games.hoi4 import State, StateCategory

state = State(
    name="Paris",
    civilian_factories=8,
    military_factories=4,
    infrastructure=7,
    bunkers=0,
    naval_bases=None,  # Optional
    air_bases=5,       # Optional
    state_category=StateCategory.METROPOLIS,
    manpower=5000000,
    victory_points=50,
    resources={"steel": 20.0, "aluminum": 5.0},
    provinces=[16, 17, 18]
)
```

**Basic Attributes:**
- `name`: The name of the state
- `civilian_factories`: Number of civilian factories
- `military_factories`: Number of military factories
- `infrastructure`: Infrastructure level (affects production, supply, and building slots)
- `bunkers`: Number of bunkers/fortifications
- `naval_bases`: Number of naval bases (optional)
- `air_bases`: Number of air bases (optional)

**Enhanced Attributes:**
- `state_category`: Category determining building slot capacity (StateCategory enum)
- `manpower`: Available manpower in the state
- `victory_points`: Victory points value
- `resources`: Dictionary of resource_name -> amount (oil, steel, aluminum, tungsten, chromium, rubber)
- `building_slots`: Maximum building slots (auto-calculated from category if not specified)
- `state_modifiers`: Dictionary of state-level modifiers
- `provinces`: List of province IDs in this state

**Methods:**
- `total_factories()`: Returns the sum of civilian and military factories
- `get_max_building_slots()`: Get maximum available building slots (base + infrastructure bonus)
- `get_used_building_slots()`: Calculate currently used building slots
- `get_free_building_slots()`: Calculate available building slots
- `can_build(slots_required)`: Check if enough slots are available
- `get_resource(name)`: Get amount of a specific resource
- `set_resource(name, amount)`: Set resource amount
- `add_resource(name, amount)`: Add to resource amount
- `get_modifier(name)`: Get value of a state modifier
- `set_modifier(name, value)`: Set a state modifier
- `add_modifier(name, value)`: Add to a state modifier

### StateCategory

Enum defining state categories and their building slot capacities:

```python
from games.hoi4 import StateCategory

# Available categories:
StateCategory.WASTELAND        # 0 building slots
StateCategory.ENCLAVE          # 1 building slot
StateCategory.TINY_ISLAND      # 1 building slot
StateCategory.SMALL_ISLAND     # 2 building slots
StateCategory.PASTORAL         # 2 building slots
StateCategory.RURAL            # 4 building slots
StateCategory.TOWN             # 5 building slots
StateCategory.LARGE_TOWN       # 6 building slots
StateCategory.CITY             # 8 building slots
StateCategory.LARGE_CITY       # 10 building slots
StateCategory.METROPOLIS       # 11 building slots
StateCategory.MEGALOPOLIS      # 12 building slots
```

### Faction

Represents a nation/country with multiple states:

```python
from games.hoi4 import Faction, State

faction = Faction(name="France")
faction.add_state(State(name="Paris", civilian_factories=8))
faction.add_state(State(name="Normandy", civilian_factories=3))
```

**Methods:**
- `add_state(state)`: Add a state to the faction
- `total_civilian_factories()`: Sum of all civilian factories
- `total_military_factories()`: Sum of all military factories
- `total_factories()`: Sum of all factories
- `average_infrastructure()`: Average infrastructure across all states
- `total_bunkers()`: Sum of all bunkers
- `get_state(name)`: Retrieve a specific state by name

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
from games.hoi4 import Faction, State, StateCategory

# Create a new faction
my_nation = Faction(name="My Custom Nation")

# Add states with enhanced features
capital = State(
    name="Capital City",
    civilian_factories=10,
    military_factories=5,
    infrastructure=8,
    bunkers=2,
    state_category=StateCategory.METROPOLIS,
    manpower=2000000,
    victory_points=30,
    resources={"steel": 15.0, "aluminum": 5.0}
)

industrial_hub = State(
    name="Industrial Region",
    civilian_factories=15,
    military_factories=10,
    infrastructure=7,
    bunkers=1,
    state_category=StateCategory.LARGE_CITY,
    manpower=1500000,
    resources={"oil": 10.0, "steel": 20.0}
)

my_nation.add_state(capital)
my_nation.add_state(industrial_hub)

# View statistics
print(f"Total factories: {my_nation.total_factories()}")
print(f"Average infrastructure: {my_nation.average_infrastructure()}")
print(f"Capital has {capital.get_free_building_slots()} free building slots")
print(f"Capital steel production: {capital.get_resource('steel')}")
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

### Example 3: Analyzing States

```python
from games.hoi4 import create_france_faction

france = create_france_faction()

# Iterate through all states
for state in france.states:
    print(f"{state.name}:")
    print(f"  Total factories: {state.total_factories()}")
    print(f"  Infrastructure: {state.infrastructure}")

# Access specific state
paris = france.get_state("Paris")
print(f"\nParis has {paris.civilian_factories} civilian factories")
```

### Example 4: Working with Resources and Building Slots

```python
from games.hoi4 import State, StateCategory

# Create a resource-rich state
state = State(
    name="Oil Region",
    state_category=StateCategory.RURAL,
    infrastructure=4,
    civilian_factories=2
)

# Add resources
state.set_resource("oil", 50.0)
state.set_resource("steel", 10.0)

# Check building capacity
print(f"Max building slots: {state.get_max_building_slots()}")  # Rural (4) + infrastructure (2) = 6
print(f"Used slots: {state.get_used_building_slots()}")  # 2 factories
print(f"Free slots: {state.get_free_building_slots()}")  # 4 remaining

# Check if we can build
if state.can_build(3):
    print("Can build 3 more factories")
    
# Extract resources
oil_amount = state.get_resource("oil")
print(f"Oil production: {oil_amount}")
```

### Example 5: State Modifiers

```python
from games.hoi4 import State

state = State(name="Industrial State")

# Apply state modifiers
state.set_modifier("production_speed_buildings_factor", 0.15)
state.set_modifier("local_building_slots", 2.0)

# Stack modifiers
state.add_modifier("production_speed_buildings_factor", 0.05)

print(f"Production speed bonus: {state.get_modifier('production_speed_buildings_factor')}")
print(f"Extra building slots: {state.get_modifier('local_building_slots')}")
```
```

## Running the Examples

To see comprehensive demonstrations of the module's capabilities:

**Original examples:**
```bash
cd /home/runner/work/twoptimizer/twoptimizer
PYTHONPATH=/home/runner/work/twoptimizer/twoptimizer python games/hoi4/example_usage.py
```

**NEW - Optimization demo:**
```bash
cd /home/runner/work/twoptimizer/twoptimizer
PYTHONPATH=/home/runner/work/twoptimizer/twoptimizer python games/hoi4/optimization_demo.py
```

## Running Tests

To run the unit tests:

```bash
cd /home/runner/work/twoptimizer/twoptimizer
# All tests
python -m unittest tests.test_hoi4 tests.test_hoi4_phase2 tests.test_hoi4_phase3 tests.test_hoi4_phase4 -v

# Individual phases
python -m unittest tests.test_hoi4 -v          # Phase 1: 40 tests
python -m unittest tests.test_hoi4_phase2 -v   # Phase 2: 20 tests
python -m unittest tests.test_hoi4_phase3 -v   # Phase 3: 20 tests
python -m unittest tests.test_hoi4_phase4 -v   # Phase 4: 31 tests
```

Total: **111 tests, all passing**

## Implemented Features

### Phase 1: Foundation ✅
- States with buildings, resources, manpower
- Building slots and state categories
- Data parsers for game files

### Phase 2: Core Mechanics ✅
- Countries with national ideas and laws
- Resource management
- Modifiers system

### Phase 3: Advanced Mechanics ✅
- Focus trees with prerequisites
- Focus availability checking
- Cost calculations

### Phase 4: Optimization ✅ NEW
- **Time simulation** with historical dates
- **Equipment models** for all unit types
- **Production system** with efficiency modeling
- **OR-Tools integration** for optimization
- **Multi-objective** factory allocation
- **Resource-constrained** optimization

## Future Development

### Completed
1. ✅ **Factory Optimization**: OR-Tools determines optimal allocation
2. ✅ **Production Scheduling**: Optimal military production by target date
3. ✅ **Resource Management**: Resource-constrained optimization
4. ✅ **Multi-objective Optimization**: Weighted production goals

### Planned
5. **Infrastructure Planning**: Optimize infrastructure construction for maximum production
6. **Defense Planning**: Optimize bunker and fortification placement
7. **Building Slot Optimization**: Determine optimal building construction
8. **Technology Trees**: Optimize research progression
9. **Equipment Variants**: Model upgraded equipment versions
10. **Division Templates**: Optimize army compositions

## Data Integration

The module includes parsers for HOI4 game data files:

- **BuildingParser**: Parses building definitions from `data/buildings/*.txt`
- **BaseParser**: Common functionality for parsing HOI4 data format

Example usage:

```python
from pathlib import Path
from games.hoi4.parsers import BuildingParser

parser = BuildingParser()
data_dir = Path("games/hoi4/data/buildings")
buildings = parser.parse_directory(data_dir)

# Get all factory buildings
factories = parser.get_factory_buildings()
for name, building in factories.items():
    print(f"{name}: Cost {building['base_cost']}")
```

## Contributing

When adding new features to this module:

1. Add comprehensive unit tests to `tests/test_hoi4.py`
2. Update this README with new functionality
3. Ensure all tests pass before committing
4. Follow the existing code style and patterns

## Data Validation

All state attributes are validated:
- Factories, infrastructure, bunkers, naval bases, and air bases cannot be negative
- Resources cannot be negative
- Manpower and victory points cannot be negative
- Invalid values will raise a `ValueError` with a descriptive message

## License

This module is part of the twoptimizer project.
