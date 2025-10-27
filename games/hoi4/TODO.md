# Hearts of Iron IV Optimizer - Massive Overhaul TODO

## 🎯 Project Overview
Transform the current basic HOI4 optimizer into a comprehensive, data-driven optimization system that leverages the extensive game data files and integrates with the main twoptimizer engine.

## 📋 Implementation Phases

### Phase 1: Foundation (Sprint 1 - Week 1-2) ✅ COMPLETED
#### CRITICAL FIXES
- [x] **Fix region vs state naming bugs** - Current faction.py uses inconsistent variable names ✅
- [x] **Create data parser framework** - Base classes for parsing game data files ✅
- [x] **Parse building definitions** - Extract building data from `data/buildings/*.txt` ✅
- [x] **Enhanced State class** - Replace basic state with comprehensive HoI4 mechanics ✅

#### FOUNDATION ARCHITECTURE
- [x] Create `parsers/` directory structure ✅
- [x] Implement `BaseParser` class for common parsing logic ✅
- [x] Build `BuildingParser` for building definitions ✅
- [x] Redesign `State` class with: ✅
  - [x] Building slots management ✅
  - [x] Resource production/consumption ✅
  - [x] State modifiers ✅
  - [x] Province-level details ✅
  - [x] Victory point system ✅

**Phase 1 Completion Date**: October 27, 2025
**Status**: All objectives completed successfully. See PHASE1_SUMMARY.md for details.
**Test Coverage**: 40 tests passing (25 original + 15 new)
**Documentation**: Complete with README updates and demo script

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

### ✅ Sprint 1 - COMPLETED (October 27, 2025)
1. ✅ **Fix current bugs** - region/state naming consistency
2. ✅ **Create parser framework** - Foundation for all data parsing
3. ✅ **Building parser** - First concrete data integration (28 building types)
4. ✅ **Enhanced State class** - Core game representation with full mechanics

### Next Sprint (Sprint 2)
5. **Country class** - Replace/extend faction with full country model
6. **National ideas** - Parse and integrate country-specific modifiers
7. **Resource system** - Basic resource management and trade
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

### Phase 1 Achievements ✅
- ✅ **Data coverage** - BuildingParser operational with 28 building types from 2 data files
- ✅ **Code quality** - 40 comprehensive tests with 100% pass rate
- ✅ **Documentation** - Complete README, inline docs, and demo script
- ✅ **Backward compatibility** - Zero breaking changes
- ✅ **Extensibility** - Clean architecture for Phase 2 additions

### Overall Project Goals
- **Data coverage** - Parse 90%+ of game data files
- **Historical accuracy** - Match known historical outcomes
- **Performance** - Solve complex problems in reasonable time
- **Extensibility** - Easy addition of new mechanics
- **User adoption** - Clear documentation and examples

---

**Status**: Phase 1 Complete - Ready for Phase 2 Implementation
**Last Updated**: October 27, 2025
**Next Review**: After Phase 2 completion
