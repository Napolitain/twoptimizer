"""
Item Type:	Defensive, Utility
Item Tier:	Tier 3
Cost:	1200
Total Cost:	2250
Stats:	+50 Physical Protection
+200 Health
+25 HP5
Passive Effect:	AURA - Enemy gods within 55 units have their healing reduced by 25%. This does not stack with similar Auras.

PASSIVE - When you are hit by a Hard Crowd Control, the enemy receives an aura that deals 25 Magical Damage per second to them and other enemies within a 25 unit radius for 5s. This aura is refreshed if an enemy applies additional Hard Crowd Control to you within 5s.
"""

from games.smite.smite1.item import Item
from games.smite.smite1.spells import Stats

contagion = Item(
    name='Contagion',
    cost=2250,
    stats=Stats(
        prot_physical=50,
        hp=200,
        hp5=25
    )
)

item = contagion
