"""
Test script for Phase 2 Country and Idea functionality.

Tests the new Country class, Idea parsing, and national ideas system.
"""

import sys
from pathlib import Path

# Add the project root to the path
sys.path.append(str(Path(__file__).parent.parent.parent))

from games.hoi4.core.country import Country
from games.hoi4.models.idea import Idea, IdeaCategory
from games.hoi4.parsers.idea_parser import IdeaParser
from games.hoi4.state import State, StateCategory


def test_idea_model():
    """Test the Idea model."""
    print("=" * 80)
    print("Test 1: Idea Model")
    print("=" * 80)
    
    # Create a test idea
    economy_idea = Idea(
        name="civilian_economy",
        category=IdeaCategory.ECONOMY,
        cost=150,
        modifier={
            "consumer_goods_factor": 0.30,
            "production_speed_buildings_factor": -0.10
        }
    )
    
    print(f"Created idea: {economy_idea.name}")
    print(f"  Category: {economy_idea.category.value}")
    print(f"  Cost: {economy_idea.cost} PP")
    print(f"  Is law: {economy_idea.is_law()}")
    print(f"  Modifiers:")
    for mod_name, value in economy_idea.modifier.items():
        print(f"    {mod_name}: {value:+.2f}")
    print()


def test_country_creation():
    """Test creating a Country."""
    print("=" * 80)
    print("Test 2: Country Creation")
    print("=" * 80)
    
    # Create a country
    germany = Country(
        name="Germany",
        tag="GER",
        political_power=100.0,
        stability=0.7,
        war_support=0.6
    )
    
    # Add some states
    berlin = State(
        name="Berlin",
        state_category=StateCategory.METROPOLIS,
        civilian_factories=12,
        military_factories=8,
        manpower=3000000,
        victory_points=30
    )
    
    ruhr = State(
        name="Ruhr",
        state_category=StateCategory.LARGE_CITY,
        civilian_factories=10,
        military_factories=6,
        manpower=2500000
    )
    
    ruhr.set_resource("steel", 35.0)
    ruhr.set_resource("coal", 50.0)
    
    germany.add_state(berlin)
    germany.add_state(ruhr)
    
    print(f"Country: {germany.name} ({germany.tag})")
    print(f"  Political Power: {germany.political_power}")
    print(f"  Stability: {germany.stability:.1%}")
    print(f"  War Support: {germany.war_support:.1%}")
    print(f"  States: {len(germany.states)}")
    print(f"  Total Factories: {germany.total_factories()}")
    print(f"  Total Manpower: {germany.total_manpower():,}")
    print(f"  Total Victory Points: {germany.total_victory_points()}")
    print(f"  Total Steel: {germany.get_resource('steel')}")
    print()
    
    return germany


def test_national_spirits(country: Country):
    """Test adding national spirits to a country."""
    print("=" * 80)
    print("Test 3: National Spirits")
    print("=" * 80)
    
    # Create a national spirit
    militarism = Idea(
        name="militarism",
        category=IdeaCategory.COUNTRY,
        modifier={
            "army_org_factor": 0.05,
            "land_reinforce_rate": 0.02,
            "training_time_factor": -0.10
        }
    )
    
    country.add_national_spirit(militarism)
    
    print(f"Added national spirit: {militarism.name}")
    print(f"  Active spirits: {len(country.national_spirits)}")
    print(f"  Spirit modifiers:")
    for mod_name, value in militarism.modifier.items():
        print(f"    {mod_name}: {value:+.2%}")
    print()


def test_laws(country: Country):
    """Test setting economic laws."""
    print("=" * 80)
    print("Test 4: Economic Laws")
    print("=" * 80)
    
    # Create an economic law
    early_mobilization = Idea(
        name="early_mobilization",
        category=IdeaCategory.ECONOMY,
        cost=150,
        modifier={
            "consumer_goods_factor": 0.25,
            "production_speed_industrial_complex_factor": -0.10,
            "conversion_cost_civ_to_mil_factor": -0.10
        }
    )
    
    print(f"Setting economic law: {early_mobilization.name}")
    print(f"  Cost: {early_mobilization.cost} PP")
    print(f"  Current PP: {country.political_power}")
    
    success = country.set_law(early_mobilization)
    
    if success:
        print(f"  Law set successfully!")
        print(f"  Remaining PP: {country.political_power}")
        print(f"  Law modifiers:")
        for mod_name, value in early_mobilization.modifier.items():
            print(f"    {mod_name}: {value:+.2%}")
    else:
        print(f"  Failed to set law (insufficient PP)")
    print()


def test_idea_parser():
    """Test parsing idea files."""
    print("=" * 80)
    print("Test 5: Idea Parser")
    print("=" * 80)
    
    parser = IdeaParser()
    
    # Parse economic ideas
    data_dir = Path("games/hoi4/data/ideas")
    economic_file = data_dir / "_economic.txt"
    
    if economic_file.exists():
        print(f"Parsing {economic_file.name}...")
        ideas = parser.parse_file(economic_file)
        
        print(f"  Parsed {len(ideas)} ideas")
        
        # Show some economy laws
        economy_laws = parser.get_ideas_by_category(IdeaCategory.ECONOMY)
        print(f"  Found {len(economy_laws)} economy laws:")
        
        for i, (name, idea) in enumerate(economy_laws.items()):
            if i >= 3:  # Show first 3
                break
            print(f"    {name}:")
            print(f"      Cost: {idea.cost} PP")
            if idea.modifier:
                print(f"      Key modifiers: {list(idea.modifier.keys())[:3]}")
    else:
        print(f"  Economic ideas file not found: {economic_file}")
    print()


def main():
    """Run all tests."""
    print("\n")
    print("=" * 80)
    print("PHASE 2: Country and National Ideas System Tests")
    print("=" * 80)
    print()
    
    test_idea_model()
    country = test_country_creation()
    test_national_spirits(country)
    test_laws(country)
    test_idea_parser()
    
    print("=" * 80)
    print("All Phase 2 tests completed successfully!")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
