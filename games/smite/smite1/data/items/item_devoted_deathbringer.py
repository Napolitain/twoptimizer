"""
Item Type:	Offensive, Utility
Item Tier:	Glyph
Cost:	600
Total Cost:	3500
Stats:	+30 Physical Power
+30% Critical Strike Chance
Passive Effect:	PASSIVE - Critical Strike bonus damage dealt is increased by 25%. GLYPH - Your Critical Strike Chance is multiplied by 1.2. For each 5% Critical Strike Chance you go over 100% Critical Strike Chance, you gain 5 Physical Power.
"""

from games.smite.smite1.item import Item
from games.smite.smite1.spells import Stats

devoted_deathbringer = Item(
    name="Devoted Deathbringer",
    cost=3500,
    stats=Stats(
        power_physical=30,
        basic_attack_crit_rate=30,
        basic_attack_crit_multiplier=1.25,
        basic_attack_crit_rate_multiplier=1.2,
    )
)

item = devoted_deathbringer
