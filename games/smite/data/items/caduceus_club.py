"""
Item Type:	Offensive, Defensive, Utility
Item Tier:	Tier 3
Cost:	1100
Total Cost:	2400
Stats:	+20 Physical Power
+200 Health
+20 MP5
+10% Cooldown Reduction
Passive Effect:	PASSIVE - Healing Dealt is increased by 30%.

AURA - Allied gods within 70 units have 10% increased Crowd Control Reduction and 3% Movement Speed.
"""

from games.smite.item import Item
from games.smite.spells import Buff

caduceus_club = Item(
    name="Caduceus Club",
    cost=2400,
    buff=Buff(
        power_physical=20,
        hp=200,
        mp5=20,
        cdr=10
    )
)
