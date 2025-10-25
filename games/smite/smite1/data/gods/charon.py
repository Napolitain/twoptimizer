from games.smite.smite1.enums import PowerType
from games.smite.smite1.god import God
from games.smite.smite1.spells import Buff, Spell, Spells, Stats

charon_passive = Buff("Ferryman of souls")
charon_spell1 = Spell("Spectral surge", damage=200, scaling=0.45, cooldown=10, mana_cost=60, range=55)
charon_spell2 = Spell("Stygian torment", damage=250, scaling=0.6, cooldown=15, mana_cost=70, range=60)
charon_spell3 = Spell("Blight", damage=150, scaling=0.3, cooldown=12, mana_cost=50, range=40)
charon_spell4 = Spell("Styx", damage=500, scaling=1.2, cooldown=100, mana_cost=100, range=70)
charon = God(
    name="Charon",
    stats=Stats(
        hp=2270,
        mana=970,
        basic_attack_damage=65,
        basic_attack_speed=1.24,
        prot_physical=79,
        prot_magical=30,
        hp5=21,
        mp5=13
    ),
    power_type=PowerType.MAGICAL,
    spells=Spells(charon_passive, charon_spell1, charon_spell2, charon_spell3, charon_spell4),
    build=None
)
