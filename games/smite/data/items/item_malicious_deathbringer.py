"""
Item Type:	Offensive, Utility
Item Tier:	Glyph
Cost:	600
Total Cost:	3500
Stats:	+30 Physical Power
+30% Critical Strike Chance
Passive Effect:	PASSIVE - Critical Strike bonus damage dealt is increased by 75%. GLYPH - Successfully hitting an Enemy God with a Critical Strike will subtract 1s from all of your abilities currently on cooldown.
"""

from games.smite.item import Item
from games.smite.spells import Stats

malicious_deathbringer = Item(
    name="Malicious Deathbringer",
    cost=3500,
    stats=Stats(
        power_physical=30,
        basic_attack_crit_rate=30,
        basic_attack_crit_multiplier=1.25
    )
)

item = malicious_deathbringer
