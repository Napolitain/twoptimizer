"""
Example script demonstrating the GodBuilder for Smite 1.
Shows how to optimize a god's build for maximum DPS.
"""

from games.smite.smite1.data.gods.gods_loader import _ALL_GODS
from games.smite.smite1.data.items.items_loader import ALL_ITEMS
from games.smite.smite1.god_builder import GodBuilder
from games.smite.smite1.enums import PowerType


def main():
    # Select a god
    god_name = 'ah_muzen_cab'
    god = _ALL_GODS[god_name]
    
    print("=" * 60)
    print(f"God Builder - Optimizing build for {god.name}")
    print("=" * 60)
    
    print(f"\nGod Type: {god.power_type.name}")
    print(f"Base Stats:")
    print(f"  - Basic Attack Damage: {god.stats.basic_attack_damage}")
    print(f"  - Basic Attack Speed: {god.stats.basic_attack_speed}")
    print(f"  - Physical Power: {god.stats.power_physical}")
    print(f"  - Scaling: {god.basic_attack_scaling}%")
    
    # Filter items based on god's power type
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
    
    print(f"\nAvailable items for optimization: {len(relevant_items)}")
    
    # Create builder and optimize
    print("\nOptimizing build using OR-TOOLS...")
    builder = GodBuilder(god, relevant_items)
    result = builder.optimize_build()
    
    if result:
        build, dps = result
        print(f"\n{'✅ OPTIMAL BUILD FOUND!' :^60}")
        print("=" * 60)
        print(f"\nMaximized DPS: {dps:.2f}")
        print(f"\nOptimal Items:")
        for i, item in enumerate([build.item1, build.item2, build.item3, 
                                   build.item4, build.item5, build.item6], 1):
            if item:
                stats_desc = []
                if item.stats.power_physical > 0:
                    stats_desc.append(f"+{item.stats.power_physical} Phys Power")
                if item.stats.power_magical > 0:
                    stats_desc.append(f"+{item.stats.power_magical} Mag Power")
                if item.stats.basic_attack_speed > 0:
                    stats_desc.append(f"+{item.stats.basic_attack_speed}% AS")
                
                print(f"  {i}. {item.name:30} ({', '.join(stats_desc)})")
        
        # Calculate contribution breakdown
        total_power = sum(
            item.stats.power_physical if item and item.stats else 0 
            for item in [build.item1, build.item2, build.item3, build.item4, build.item5, build.item6]
        )
        total_as = sum(
            item.stats.basic_attack_speed if item and item.stats else 0 
            for item in [build.item1, build.item2, build.item3, build.item4, build.item5, build.item6]
        )
        
        print(f"\nBuild Totals:")
        print(f"  - Total Physical Power from items: +{total_power}")
        print(f"  - Total Attack Speed from items: +{total_as}%")
        print(f"  - Final Physical Power: {god.stats.power_physical + total_power}")
        print(f"  - Final Attack Speed: {god.stats.basic_attack_speed + total_as/100:.2f}")
        
        final_damage = god.stats.basic_attack_damage + (god.basic_attack_scaling / 100) * (god.stats.power_physical + total_power)
        print(f"  - Final Basic Attack Damage: {final_damage:.2f}")
        
    else:
        print("\n❌ No optimal solution found")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
