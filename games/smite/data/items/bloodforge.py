"""
Item Type:	Offensive, Utility
Item Tier:	Tier 3
Cost:	1100
Total Cost:	2500
Stats:	+50 Physical Power
+15% Physical Lifesteal
+7% Movement Speed
Passive Effect:	PASSIVE - Killing an enemy god forges a shield from their blood with Health equal to 200 + 10 per Player Level for 20s. While the Blood Shield is active you gain +10% Movement Speed.
"""

from games.smite.item import Item
from games.smite.spells import Buff

bloodforge = Item(
    name="Bloodforge",
    cost=2500,
    buff=Buff(
        power_physical=50,
        lifesteal_physical=15,
        movement_speed=7
    )
)
