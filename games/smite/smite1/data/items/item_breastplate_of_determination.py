"""
Item Type:	Defensive, Utility
Item Tier:	Glyph
Cost:	600
Total Cost:	2850
Stats:	+50 Physical Protection
+300 Mana
+15 MP5
+20% Cooldown Reduction
Passive Effect:	GLYPH - Each time you are hit by an ability, gain a stack of 5 Protections that corresponds to the damage type you were hit with, up to a max of 4 of each type. Once you reach max stacks of both kinds, gain a burst of 20% Movement Speed and double your Protections gained by this effect for 8s, after which all stacks are removed.
"""

from games.smite.smite1.item import Item
from games.smite.smite1.spells import Stats

breastplate_of_determination = Item(
    name='Breastplate of Determination',
    cost=2850,
    stats=Stats(
        prot_physical=50,
        mana=300,
        mp5=15,
        cdr=20
    )
)

item = breastplate_of_determination
