"""
Item Type:	Offensive, Defensive, Utility
Total Cost:	2400
Item Tier:	Evolved
Stats:	+75 Magical Power
+35 HP5 & MP5
+20% Magical Penetration
+8% Movement Speed
Passive Effect:	PASSIVE - On god kill or assist a coin is flipped. If heads, you gain 150 Health over 6 seconds. If tails, you gain 5% Movement Speed for 6 seconds. You also gain 15 gold every time the coin is flipped.
"""

from games.smite.item import Item
from games.smite.spells import Stats

charons_coin = Item(
    name="Charon's Coin",
    cost=2400,
    stats=Stats(
        power_magical=75,
        hp5=35,
        mp5=35,
        pen_percent=20,
        movement_speed=8
    )
)

item = charons_coin
