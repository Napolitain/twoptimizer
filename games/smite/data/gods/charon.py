from games.smite.enums import PowerType
from games.smite.god import God
from games.smite.spells import Buff, Spell, Spells

charon_passive = Buff("Ferryman of souls", hp=998)
charon_spell1 = Spell("Spectral surge", damage=200, scaling=0.45, cooldown=10, mana_cost=60, range=55)
charon_spell2 = Spell("Stygian torment", damage=250, scaling=0.6, cooldown=15, mana_cost=70, range=60)
charon_spell3 = Spell("Blight", damage=150, scaling=0.3, cooldown=12, mana_cost=50, range=40)
charon_spell4 = Spell("Styx", damage=500, scaling=1.2, cooldown=100, mana_cost=100, range=70)
charon = God("Charon", 2270, 970, 370, 55, 1.24, 65, 20, 79, 53, 21, 13, PowerType.MAGICAL,
             Spells(charon_passive, charon_spell1, charon_spell2, charon_spell3, charon_spell4))
