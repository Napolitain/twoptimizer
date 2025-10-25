"""
Item Type:	Offensive
Item Tier:	Tier 3
Cost:	1000
Total Cost:	2550
Stats:	+55 Physical Power
+15% Attack Speed
Passive Effect:	PASSIVE - Once every 3s, your next Basic Attack will deal an additional 30% of your Basic Attack Power as Physical Ability damage. This damage can trigger ability item effects.
"""
from games.smite.smite1.item import Item
from games.smite.smite1.spells import Stats

duality = Item(
    name='Duality',
    cost=2550,
    stats=Stats(
        power_physical=55,
        basic_attack_speed=15
    )
)

item = duality
