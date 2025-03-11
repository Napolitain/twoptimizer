"""
Item Type:	Defensive
Item Tier:	Tier 3
Cost:	900
Total Cost:	2150
Stats:	+60 Magical Protection
+300 Health
+20% Crowd Control Reduction
Passive Effect:	PASSIVE - When your Ultimate ability has finished casting, you pulse out a cleansing aura within 50 units, providing all allies with CC-immunity for 1.5s and restoring 10% of their max. Mana. This effect can only occur once every 40s.
"""

from games.smite.item import Item
from games.smite.spells import Buff

absolution = Item(
    name='Absolution',
    cost=2150,
    buff=Buff(
        hp=300,
        prot_magical=60,
        cc=20
    )
)
