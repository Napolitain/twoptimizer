"""
Item Type:	Defensive
Item Tier:	Tier 3
Cost:	500
Total Cost:	1850
Stats:	+30 Physical Protection
+30 Magical Protection
+250 Health
+20 HP5
Passive Effect:	PASSIVE - Your next successful basic attack on an enemy lane minion causes it to explode, instantly killing it, dealing 50 (+10 Per Level) magical damage to enemies in a small area and providing 20 bonus gold to your nearest ally within 80 ft. This can only happen once every 7s.
"""

from games.smite.item import Item
from games.smite.spells import Buff

cannoneers_cuirass = Item(
    name="Cannoneer's Cuirass",
    cost=1850,
    buff=Buff(
        prot_physical=30,
        prot_magical=30,
        hp=250,
        hp5=20
    )
)
