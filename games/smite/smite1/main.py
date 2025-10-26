"""
Main entry point for Smite 1 optimization.
Demonstrates god builder functionality.
"""

from games.smite.smite1.data.gods.gods_loader import _ALL_GODS
from games.smite.smite1.data.items.items_loader import ALL_ITEMS
from games.smite.smite1.god_builder import GodBuilder
from games.smite.smite1.enums import PowerType


def optimize_god_build(god_name: str):
    """
    Optimize build for a specific god.
    
    Args:
        god_name: Sanitized god name (e.g., 'ah_muzen_cab')
    """
    if god_name not in _ALL_GODS:
        print(f"God '{god_name}' not found")
        return
    
    god = _ALL_GODS[god_name]
    
    print(f"\n{'='*60}")
    print(f"Optimizing build for {god.name}")
    print(f"{'='*60}")
    
    # Filter items based on god type
    if god.power_type == PowerType.PHYSICAL:
        relevant_items = [
            item for item in ALL_ITEMS 
            if item.stats and (
                item.stats.power_physical > 0 or 
                (item.stats.basic_attack_speed > 0 and item.stats.power_magical == 0)
            )
        ]
    else:
        relevant_items = [
            item for item in ALL_ITEMS 
            if item.stats and (
                item.stats.power_magical > 0 or 
                (item.stats.basic_attack_speed > 0 and item.stats.power_physical == 0)
            )
        ]
    
    print(f"God type: {god.power_type.name}")
    print(f"Available items: {len(relevant_items)}")
    
    # Create builder and optimize
    builder = GodBuilder(god, relevant_items)
    result = builder.optimize_build()
    
    if result:
        build, dps = result
        print(f"\n✅ Optimal build found!")
        print(f"DPS: {dps:.2f}")
        print(f"\nItems:")
        for i, item in enumerate([build.item1, build.item2, build.item3, 
                                   build.item4, build.item5, build.item6], 1):
            if item:
                print(f"  {i}. {item.name}")
    else:
        print("\n❌ No optimal solution found")
    
    print(f"{'='*60}\n")


if __name__ == "__main__":
    # Example optimizations
    optimize_god_build('ah_muzen_cab')
    optimize_god_build('agni')
    optimize_god_build('achilles')

