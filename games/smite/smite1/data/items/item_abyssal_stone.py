"""
Item Type:	Defensive
Item Tier:	Tier 3
Cost:	950
Total Cost:	2350
Stats:	+35 Physical Protection
+40 Magical Protection
+250 Health
Passive Effect:	PASSIVE - Successful ability damage to an enemy god applies a debuff that afflicts them with 20% Negative CDR for 5s.
"""

from games.smite.smite1.item import Item
from games.smite.smite1.spells import Stats

abyssal_stone = Item(
    name='Abyssal Stone',
    cost=2350,
    stats=Stats(
        hp=250,
        prot_physical=35,
        prot_magical=40
    )
)

item = abyssal_stone
