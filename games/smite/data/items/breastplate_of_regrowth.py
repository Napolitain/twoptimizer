"""
Item Type:	Offensive, Defensive, Utility
Item Tier:	Tier 3
Cost:	1050
Total Cost:	2250
Stats:	+50 Physical Protection
+300 Mana
+15 MP5
+10% Cooldown Reduction
Passive Effect:	PASSIVE - After healing yourself from an ability, you gain 20% Movement Speed, 20 Physical Power, and 30 Magical Power for 5 seconds. This effect can only occur once every 10 seconds.
"""

from games.smite.item import Item
from games.smite.spells import Buff

breastplate_of_regrowth = Item(
    name="Breastplate of Regrowth",
    cost=2250,
    buff=Buff(
        prot_physical=50,
        mana=300,
        mp5=15,
        cdr=10
    )
)
