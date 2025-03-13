"""
Item Type:	Offensive, Utility
Total Cost:	2500
Item Tier:	Evolved
Stats:	+60 Magical Power
+10 Magical Penetration
+800 Mana
+20 MP5
Passive Effect:	PASSIVE - You gain Magical Power equal to 7% of your Mana from items.
"""

from games.smite.item import Item
from games.smite.spells import Stats

book_of_thoth = Item(
    name="Book of Thoth",
    cost=2500,
    stats=Stats(
        power_magical=60,
        pen_flat=10,
        mana=800,
        mp5=20
    )
)

item = book_of_thoth
