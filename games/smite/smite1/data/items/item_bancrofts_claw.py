"""
Item Type:	Offensive, Utility
Item Tier:	Glyph
Cost:	600
Total Cost:	3000
Stats:	+80 Magical Power
+200 Mana
+15% Magical Lifesteal
Passive Effect:	PASSIVE - You gain additional Magical Power and Lifesteal scaled from missing Health. This caps at 70 power and 15% Lifesteal at 40% Health. GLYPH - Every 10s gain a stack of Hunger(max 3). Abilities cast within 30 units of enemy gods consume a stack, dealing bonus damage equal to 1% of their max HP for each 75 Magical Power you have. Each god damaged by Hunger provides you with a shield of 1% of your Max HP for each 75 Magical Power you have. This cannot exceed 35% of your Max HP.
"""

from games.smite.smite1.item import Item
from games.smite.smite1.spells import Stats

bancrofts_claw = Item(
    name='Bancroft\'s Claw',
    cost=3000,
    stats=Stats(
        power_magical=80,
        mana=200,
        lifesteal_magical=15
    )
)

item = bancrofts_claw
