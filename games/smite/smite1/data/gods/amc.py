from games.smite.smite1.enums import PowerType
from games.smite.smite1.god import God
from games.smite.smite1.spells import Buff, Spell, Spells, Stats

amc_passive = Buff("Ferryman of souls", hp=998)
amc_spell1 = Spell("Spectral surge", damage=200, scaling=0.45, cooldown=10, mana_cost=60, range=55)
amc_spell2 = Spell("Stygian torment", damage=250, scaling=0.6, cooldown=15, mana_cost=70, range=60)
amc_spell3 = Spell("Blight", damage=150, scaling=0.3, cooldown=12, mana_cost=50, range=40)
amc_spell4 = Spell("Styx", damage=500, scaling=1.2, cooldown=100, mana_cost=100, range=70)
amc = God(name="Ah Muzen Cab",
          stats=Stats(hp=2010, mana=1030, movement_speed=365, basic_attack_speed=1.27,
                      basic_attack_damage=83, prot_physical=72, prot_magical=49, hp5=21.2,
                      mp5=12),
          power_type=PowerType.PHYSICAL,
          basic_attack_scaling=100,
          spells=Spells(amc_passive, amc_spell1, amc_spell2, amc_spell3, amc_spell4),
          build=None)
