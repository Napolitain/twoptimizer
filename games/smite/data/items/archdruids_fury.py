"""
Item Type:	Defensive, Utility
Item Tier:	Tier 3
Cost:	900
Total Cost:	2300
Stats:	+35 Physical Protection
+35 Magical Protection
+250 Health
+15 MP5
Passive Effect:	PASSIVE - Gain a stack (up to a max of 6) each time you take damage from enemy gods equal to 5% of your maximum Health. Your next basic attack on an enemy god consumes all stacks and deals 25 (+ 2 Per Level) Magical Damage per stack. This effect can only occur once every 10 seconds.
"""

from games.smite.item import Item
from games.smite.spells import Buff

archdruids_fury = Item(
    name='Archdruid\'s Fury',
    cost=2300,
    buff=Buff(
        hp=250,
        prot_physical=35,
        prot_magical=35,
        mp5=15
    )
)
