"""
Item Type:	Offensive
Item Tier:	Tier 3
Cost:	1000
Total Cost:	2400
Stats:	+50 Physical Power
+20% Attack Speed
+25% Physical Lifesteal
Passive Effect:	PASSIVE - Lifestealing from enemies while at full Health grants you the value healed as a Shield, which may not exceed 15% of your Maximum Health.
"""

from games.smite.item import Item
from games.smite.spells import Stats

crimson_claws = Item(
    name='Crimson Claws',
    cost=2400,
    stats=Stats(
        power_physical=50,
        basic_attack_speed=20,
        lifesteal_physical=25
    )
)

item = crimson_claws
