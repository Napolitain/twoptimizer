"""
Item Type:	Offensive, Defensive
Item Tier:	Tier 3
Cost:	1050
Total Cost:	2250
Stats:	+50 Physical Protection
+150 Health
+25% Attack Speed
+20 HP5
Passive Effect:	PASSIVE - While below 60% Health you become Berserk for 5s. While Berserk, you gain 5% Damage Mitigation and 20% Attack Speed. This effect can only occur once every 15 seconds.
"""

from games.smite.item import Item
from games.smite.spells import Stats

berserkers_shield = Item(
    name="Berserker's Shield",
    cost=2250,
    stats=Stats(
        prot_physical=50,
        hp=150,
        basic_attack_speed=25,
        hp5=20
    )
)

item = berserkers_shield
