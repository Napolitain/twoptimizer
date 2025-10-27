# Hearts of Iron IV Optimizer - Massive Overhaul TODO

## 🎯 Project Overview
Transform the current basic HOI4 optimizer into a comprehensive, data-driven optimization system that leverages the extensive game data files and integrates with the main twoptimizer engine.

## 📋 Implementation Phases

### Phase 1: Foundation (Sprint 1 - Week 1-2)
#### CRITICAL FIXES
- [ ] **Fix region vs state naming bugs** - Current faction.py uses inconsistent variable names
- [ ] **Create data parser framework** - Base classes for parsing game data files
- [ ] **Parse building definitions** - Extract building data from `data/buildings/*.txt`
- [ ] **Enhanced State class** - Replace basic state with comprehensive HoI4 mechanics

#### FOUNDATION ARCHITECTURE
- [ ] Create `parsers/` directory structure
- [ ] Implement `BaseParser` class for common parsing logic
- [ ] Build `BuildingParser` for building definitions
- [ ] Redesign `State` class with:
  - Building slots management
  - Resource production/consumption
  - State modifiers
  - Province-level details
  - Victory point system

### Phase 2: Core Game Mechanics (Sprint 2 - Week 3-4)
#### COUNTRY SYSTEM
- [ ] **Replace Faction with Country class** - Full country representation
- [ ] **Parse national ideas** - Extract from `data/ideas/*.txt` (150+ countries)
- [ ] **Implement dynamic modifiers** - National ideas affecting game mechanics
- [ ] **Country-specific bonuses** - Historical accuracy for different nations

#### RESOURCE MANAGEMENT
- [ ] **Resource system** - Oil, steel, aluminum, tungsten, chromium, rubber
- [ ] **Trade mechanics** - Import/export optimization
- [ ] **Resource shortage modeling** - Impact on production and military
- [ ] **Strategic resource allocation** - Optimize resource distribution

### Phase 3: Advanced Mechanics (Sprint 3 - Week 5-6)
#### FOCUS TREES & TECHNOLOGY
- [ ] **National focus parser** - Parse `data/national_focus/` trees
- [ ] **Focus tree optimization** - Optimal progression paths
- [ ] **Technology system** - Research priorities and prerequisites
- [ ] **Research time optimization** - Balance multiple research paths

#### PRODUCTION SYSTEMS
- [ ] **Production chains** - From resources to equipment
- [ ] **Factory efficiency** - Modifiers affecting production
- [ ] **Equipment variants** - Different designs and their trade-offs
- [ ] **Supply system** - Logistics and supply line optimization

### Phase 4: Optimization Integration (Sprint 4 - Week 7-8)
#### SOLVER INTEGRATION
- [ ] **Connect to main engine** - Use existing solver framework
- [ ] **Multi-objective optimization** - Industry vs Military vs Research
- [ ] **Time-series problems** - Multi-year planning optimization
- [ ] **Constraint modeling** - Building slots, resources, time, technology

#### SCENARIOS & ANALYSIS
- [ ] **Historical scenarios** - 1936 start, 1939 war start, custom dates
- [ ] **What-if analysis** - Alternative history scenarios
- [ ] **Comparative analysis** - Compare different strategies
- [ ] **Bottleneck identification** - Find limiting factors

## 🏗️ Directory Structure (Target)

```
games/hoi4/
├── README.md
├── TODO.md                    # This file
├── __init__.py
├── core/                      # Core game mechanics
│   ├── __init__.py
│   ├── state.py              # Enhanced state with full mechanics
│   ├── country.py            # Replaces faction.py
│   ├── province.py           # Province-level details
│   ├── world.py              # Global game state
│   └── game_date.py          # Time progression system
├── models/                    # Game object models
│   ├── __init__.py
│   ├── building.py           # Building types and effects
│   ├── idea.py               # National ideas system
│   ├── focus.py              # National focus mechanics
│   ├── technology.py         # Technology trees
│   ├── resource.py           # Resource types and management
│   ├── modifier.py           # Game modifier system
│   ├── equipment.py          # Military equipment
│   └── production.py         # Production chains
├── parsers/                   # Data file parsers
│   ├── __init__.py
│   ├── base_parser.py        # Common parsing functionality
│   ├── building_parser.py    # Parse building definitions
│   ├── idea_parser.py        # Parse national ideas
│   ├── focus_parser.py       # Parse focus trees
│   ├── state_parser.py       # Parse state definitions
│   ├── technology_parser.py  # Parse tech trees
│   └── modifier_parser.py    # Parse game modifiers
├── optimization/              # Optimization problems
│   ├── __init__.py
│   ├── objectives/           # Optimization objectives
│   │   ├── __init__.py
│   │   ├── industrial_capacity.py
│   │   ├── military_strength.py
│   │   ├── resource_efficiency.py
│   │   └── research_speed.py
│   ├── constraints/          # Optimization constraints
│   │   ├── __init__.py
│   │   ├── building_slots.py
│   │   ├── resource_limits.py
│   │   ├── technology_prereqs.py
│   │   └── time_constraints.py
│   └── problems/             # Specific optimization problems
│       ├── __init__.py
│       ├── industrial_buildup.py
│       ├── military_production.py
│       └── research_planning.py
├── scenarios/                 # Historical and custom scenarios
│   ├── __init__.py
│   ├── historical_1936.py    # 1936 start scenario
│   ├── historical_1939.py    # 1939 war start
│   ├── barbarossa.py         # Operation Barbarossa
│   ├── sealion.py            # Operation Sea Lion
│   └── custom_scenario.py    # User-defined scenarios
├── analysis/                  # Analysis and reporting
│   ├── __init__.py
│   ├── comparative_analysis.py
│   ├── sensitivity_analysis.py
│   ├── bottleneck_analysis.py
│   └── report_generator.py
└── data/                      # Game data files (already exists)
    ├── buildings/
    ├── ideas/
    ├── national_focus/
    └── state_category/
```

## ⚡ Priority Implementation Order

### Immediate (This Sprint)
1. **Fix current bugs** - region/state naming consistency
2. **Create parser framework** - Foundation for all data parsing
3. **Building parser** - First concrete data integration
4. **Enhanced State class** - Core game representation

### Next Sprint
5. **Country class** - Replace faction with full country model
6. **National ideas** - Parse and integrate country-specific modifiers
7. **Resource system** - Basic resource management
8. **Optimization integration** - Connect to main solver

### Future Sprints
9. **Focus trees** - National focus system
10. **Technology** - Research and tech trees
11. **Production chains** - Complex manufacturing
12. **Scenarios** - Historical and what-if analysis

## 🔧 Technical Considerations

### Data Parsing Strategy
- **Robust parsing** - Handle variations in game data format
- **Validation** - Ensure data integrity after parsing
- **Caching** - Cache parsed data for performance
- **Version compatibility** - Handle different game versions

### Performance Requirements
- **Large datasets** - 150+ countries, 1000+ states
- **Complex calculations** - Multi-objective optimization
- **Memory efficiency** - Handle large game states
- **Scalable algorithms** - Support various problem sizes

### Integration Points
- **Main engine compatibility** - Use existing solver infrastructure
- **Extensibility** - Easy to add new game mechanics
- **Modularity** - Components can be used independently
- **Testing** - Comprehensive test coverage

## 🎮 Key Optimization Problems

### Industrial Optimization
- **Factory construction** - Optimal building order and timing
- **Infrastructure investment** - Transport and supply optimization
- **Resource allocation** - Maximize production efficiency

### Military Planning
- **Production balance** - Civilian vs military factories
- **Equipment priorities** - What to produce and when
- **Doctrine selection** - Military doctrine optimization

### Research Strategy
- **Technology priorities** - Research tree optimization
- **Research timing** - When to research different technologies
- **Focus tree paths** - Optimal national focus progression

### Strategic Analysis
- **Comparative strategies** - Compare different approaches
- **Sensitivity analysis** - Impact of parameter changes
- **Bottleneck identification** - Find limiting factors
- **What-if scenarios** - Alternative history analysis

## 📊 Success Metrics

- **Data coverage** - Parse 90%+ of game data files
- **Historical accuracy** - Match known historical outcomes
- **Performance** - Solve complex problems in reasonable time
- **Extensibility** - Easy addition of new mechanics
- **User adoption** - Clear documentation and examples

---

**Status**: Planning Complete - Ready for Implementation
**Last Updated**: October 26, 2025
**Next Review**: After Phase 1 completion
