"""
Item Type:	Offensive, Utility
Item Tier:	Glyph
Cost:	600
Total Cost:	3000
Stats:	+80 Magical Power
+200 Mana
+15% Magical Lifesteal
Passive Effect:	PASSIVE - You gain additional Magical Power and Lifesteal scaled from missing Health. This caps at 70 power and 15% Lifesteal at 40% Health. GLYPH - For every 30 Magical Power you have, you gain 2 Basic Attack Damage and 2% Attack Speed.
"""

from games.smite.smite1.item import Item
from games.smite.smite1.spells import Stats

nimble_bancrofts_talon = Item(
    name='Nimble Bancroft\'s Talon',
    cost=3000,
    stats=Stats(
        power_magical=80,
        mana=200,
        lifesteal_magical=15
    )
)
