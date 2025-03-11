"""
Item Type:	Defensive
Item Tier:	Tier 3
Cost:	950
Total Cost:	2150
Stats:	+45 Magical Protection
+250 Health
+20 HP5
Passive Effect:	PASSIVE - Whenever you take Magical Damage from an enemy ability you unleash a shockwave that Silences all enemies within a range of 30 units for 1s. This effect cannot trigger more than once every 30s. While this effect is on cooldown, gain 20 Physical Power and 35 Magical Power.
"""

from games.smite.item import Item
from games.smite.spells import Buff

ancile = Item(
    name='Ancile',
    cost=2150,
    buff=Buff(
        hp=250,
        prot_magical=45,
        hp5=20
    )
)
