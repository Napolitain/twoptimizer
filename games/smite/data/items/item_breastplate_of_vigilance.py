"""
Item Type:	Defensive, Utility
Item Tier:	Glyph
Cost:	600
Total Cost:	2850
Stats:	+50 Physical Protection
+300 Mana
+15 MP5
+20% Cooldown Reduction
Passive Effect:	GLYPH - When your ultimate ability has finished casting you provide an aura in a 70 unit range around you reducing basic attack damage from enemies by 25% for 5s. This effect may only occur once every 45s.
"""

from games.smite.item import Item
from games.smite.spells import Stats

breastplate_of_vigilance = Item(
    name='Brestplate of Vigilance',
    cost=2850,
    stats=Stats(
        prot_physical=50,
        mana=300,
        mp5=15,
        cdr=20
    )
)

item = breastplate_of_vigilance
