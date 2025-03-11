from games.smite.enums import PowerType
from games.smite.god import God
from games.smite.spells import Buff, Spell, Spells

amc_passive = Buff("Ferryman of souls", hp=998)
amc_spell1 = Spell("Spectral surge", damage=200, scaling=0.45, cooldown=10, mana_cost=60, range=55)
amc_spell2 = Spell("Stygian torment", damage=250, scaling=0.6, cooldown=15, mana_cost=70, range=60)
amc_spell3 = Spell("Blight", damage=150, scaling=0.3, cooldown=12, mana_cost=50, range=40)
amc_spell4 = Spell("Styx", damage=500, scaling=1.2, cooldown=100, mana_cost=100, range=70)
amc = God("Ah Muzen Cab", 2010, 1030, 365, 55, 1.27, 83, 100, 72, 49, 21.2, 12, PowerType.PHYSICAL,
          Spells(amc_passive, amc_spell1, amc_spell2, amc_spell3, amc_spell4),
          None)
