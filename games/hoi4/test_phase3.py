"""
Test script for Phase 3 National Focus Trees functionality.

Tests the Focus, FocusTree, and FocusParser functionality.
"""

import sys
from pathlib import Path

# Add the project root to the path
sys.path.append(str(Path(__file__).parent.parent.parent))

from games.hoi4.models.focus import Focus, FocusTree, FocusFilterCategory
from games.hoi4.parsers.focus_parser import FocusParser


def test_focus_model():
    """Test the Focus model."""
    print("=" * 80)
    print("Test 1: Focus Model")
    print("=" * 80)
    
    # Create a test focus
    focus = Focus(
        id="test_focus",
        icon="GFX_test",
        x=5,
        y=2,
        cost=10,
        prerequisites=["prereq_focus_1", "prereq_focus_2"],
        mutually_exclusive=["mutex_focus"],
        search_filters=[FocusFilterCategory.POLITICAL, FocusFilterCategory.INDUSTRY]
    )
    
    print(f"Created focus: {focus.id}")
    print(f"  Position: ({focus.x}, {focus.y})")
    print(f"  Cost: {focus.cost} weeks = {focus.get_time_cost_days()} days")
    print(f"  Prerequisites: {len(focus.prerequisites)}")
    print(f"  Mutually exclusive: {len(focus.mutually_exclusive)}")
    print(f"  Is starting focus: {focus.is_starting_focus()}")
    print()
    
    # Test can_complete
    completed = ["prereq_focus_1", "prereq_focus_2"]
    print(f"Can complete with {completed}? {focus.can_complete(completed)}")
    
    completed_mutex = ["prereq_focus_1", "prereq_focus_2", "mutex_focus"]
    print(f"Can complete with mutex conflict? {focus.can_complete(completed_mutex)}")
    print()


def test_focus_tree_model():
    """Test the FocusTree model."""
    print("=" * 80)
    print("Test 2: FocusTree Model")
    print("=" * 80)
    
    # Create a simple focus tree
    tree = FocusTree(
        id="test_tree",
        country_tags=["TST"],
        default=True
    )
    
    # Add some focuses
    start_focus = Focus(id="start", x=0, y=0, cost=10)
    tree.add_focus(start_focus)
    
    branch_left = Focus(
        id="branch_left",
        x=-2,
        y=1,
        cost=10,
        prerequisites=["start"]
    )
    tree.add_focus(branch_left)
    
    branch_right = Focus(
        id="branch_right",
        x=2,
        y=1,
        cost=10,
        prerequisites=["start"],
        mutually_exclusive=["branch_left"]
    )
    tree.add_focus(branch_right)
    
    end_focus = Focus(
        id="end",
        x=0,
        y=2,
        cost=10,
        prerequisites=["branch_left"]
    )
    tree.add_focus(end_focus)
    
    print(f"Focus tree: {tree.id}")
    print(f"  Total focuses: {len(tree)}")
    print(f"  Country tags: {tree.country_tags}")
    print(f"  Starting focuses: {[f.id for f in tree.get_starting_focuses()]}")
    print()
    
    # Test available focuses
    completed = []
    available = tree.get_available_focuses(completed)
    print(f"Available with no focuses completed: {[f.id for f in available]}")
    
    completed = ["start"]
    available = tree.get_available_focuses(completed)
    print(f"Available after 'start': {[f.id for f in available]}")
    
    completed = ["start", "branch_left"]
    available = tree.get_available_focuses(completed)
    print(f"Available after 'start' and 'branch_left': {[f.id for f in available]}")
    print()
    
    # Test cost calculations
    print(f"Chain length to 'end': {tree.get_focus_chain_length('end')}")
    print(f"Total cost to 'end': {tree.get_total_cost_to_focus('end')} days")
    print()
    
    # Validate tree
    errors = tree.validate_tree()
    if errors:
        print("Validation errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("✓ Focus tree is valid")
    print()


def test_focus_parser():
    """Test parsing focus tree files."""
    print("=" * 80)
    print("Test 3: Focus Tree Parser")
    print("=" * 80)
    
    parser = FocusParser()
    
    # Parse a focus tree file
    data_dir = Path("games/hoi4/data/national_focus")
    focus_file = data_dir / "china_communist.txt"
    
    if focus_file.exists():
        print(f"Parsing {focus_file.name}...")
        trees = parser.parse_file(focus_file)
        
        print(f"  Parsed {len(trees)} focus tree(s)")
        
        for tree_id, tree in trees.items():
            print(f"\n  Focus Tree: {tree_id}")
            print(f"    Country tags: {tree.country_tags}")
            print(f"    Total focuses: {len(tree)}")
            print(f"    Starting focuses: {len(tree.get_starting_focuses())}")
            print(f"    Shared focuses: {len(tree.shared_focuses)}")
            
            # Show some example focuses
            if len(tree.focuses) > 0:
                print(f"\n    Sample focuses:")
                for i, (focus_id, focus) in enumerate(tree.focuses.items()):
                    if i >= 3:  # Show first 3
                        break
                    print(f"      {focus_id}:")
                    print(f"        Cost: {focus.cost} weeks")
                    print(f"        Prerequisites: {len(focus.prerequisites)}")
                    if focus.search_filters:
                        filters = [f.value for f in focus.search_filters]
                        print(f"        Categories: {filters}")
            
            # Validate
            errors = tree.validate_tree()
            if errors:
                print(f"\n    Validation: {len(errors)} error(s)")
                for error in errors[:3]:  # Show first 3
                    print(f"      - {error}")
            else:
                print(f"\n    ✓ Tree validated successfully")
    else:
        print(f"  Focus tree file not found: {focus_file}")
    print()


def main():
    """Run all tests."""
    print("\n")
    print("=" * 80)
    print("PHASE 3: National Focus Trees System Tests")
    print("=" * 80)
    print()
    
    test_focus_model()
    test_focus_tree_model()
    test_focus_parser()
    
    print("=" * 80)
    print("All Phase 3 tests completed successfully!")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
