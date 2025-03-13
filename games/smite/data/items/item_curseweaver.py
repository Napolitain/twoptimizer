"""
Item Type:	Offensive, Defensive, Utility
Item Tier:	Tier 3
Cost:	1200
Total Cost:	2500
Stats:	+60 Magical Power
+250 Health
+250 Mana
Passive Effect:	PASSIVE - Hitting an enemy god with a Basic Attack or Ability marks them for 4s. When the marked enemy god casts an ability, they take 5% of your Maximum Health + 7.5% of your Maximum Mana as Magical damage. You heal for 100% of the damage dealt. You may only apply a mark once every 20s. Each time an enemy casts an ability within 55 units of you, reduce the cooldown of this item by 1s.
"""

from games.smite.item import Item
from games.smite.spells import Stats

curseweaver = Item(
    name='Curseweaver',
    cost=2500,
    stats=Stats(
        power_magical=60,
        hp=250,
        mana=250
    )
)

item = curseweaver
