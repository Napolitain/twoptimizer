"""
Item Type:	Offensive
Item Tier:	Tier 3
Cost:	1100
Total Cost:	2400
Stats:	+30 Physical Power
+15% Attack Speed
+20% Critical Strike Chance
Passive Effect:	PASSIVE - Your Critical Hits provide you with 10% Physical Penetration for 4s.
"""

from games.smite.smite1.item import Item
from games.smite.smite1.spells import Stats

demon_blade = Item(
    name="Demon Blade",
    cost=2400,
    stats=Stats(
        power_physical=30,
        basic_attack_speed=15,
        basic_attack_crit_rate=20
    )
)

item = demon_blade
