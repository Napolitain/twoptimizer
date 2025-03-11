"""
Item Type:	Offensive, Utility
Item Tier:	Tier 3
Cost:	1000
Total Cost:	2500
Stats:	+50 Physical Power
+10% Cooldown Reduction
+7% Movement Speed
Passive Effect:	PASSIVE - When your Ultimate ability has finished casting, reveal all enemy gods within 120 units for 10s. While moving towards revealed enemies gain 20% Movement Speed. When first striking a revealed target they take an additional 30 + 50% of your Physical Power. This can only occur once every 45 seconds. This item is only available to Assassins, Warriors, and Hunters.
"""

from games.smite.item import Item
from games.smite.spells import Buff

arondight = Item(
    name='Arondight',
    cost=2500,
    buff=Buff(
        power_physical=50,
        cdr=10,
        movement_speed=7
    )
)
