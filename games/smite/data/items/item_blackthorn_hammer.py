"""
Item Type:	Offensive, Defensive, Utility
Item Tier:	Tier 3
Cost:	1100
Total Cost:	2200
Stats:	+35 Physical Power
+300 Health
+200 Mana
Passive Effect:	PASSIVE - While over 25% Mana, you gain +10% Cooldown Reduction. While under 25% Mana, you gain +50 MP5.
"""

from games.smite.item import Item
from games.smite.spells import Stats

blackthorn_hammer = Item(
    name="Blackthorn Hammer",
    cost=2200,
    stats=Stats(
        power_physical=35,
        hp=300,
        mana=200
    )
)

item = blackthorn_hammer
