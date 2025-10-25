"""
Item Type:	Offensive, Defensive, Utility
Item Tier:	Tier 3
Cost:	1150
Total Cost:	2350
Stats:	+40 Physical Power
+150 Health
+15 HP5
+20% Crowd Control Reduction
Passive Effect:	PASSIVE - When your Ultimate has finished casting, your Protections and Movement Speed are increased by 10% for 8s. These buffs are further increased for each enemy god within 55 units of you, stacking twice. This effect can only occur once every 30s.
"""

from games.smite.smite1.item import Item
from games.smite.smite1.spells import Stats

dawnbringer = Item(
    name='Dawnbringer',
    cost=2350,
    stats=Stats(
        power_physical=40,
        hp=150,
        hp5=15,
        cc=20
    )
)

item = dawnbringer
