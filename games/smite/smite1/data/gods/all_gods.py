"""
Auto-generated gods data for Smite 1.
Contains base statistics for all gods at max level.
"""

from games.smite.smite1.enums import PowerType
from games.smite.smite1.god import God
from games.smite.smite1.spells import Buff, Spell, Spells, Stats


# Placeholder spells for gods (to be filled in with actual ability data later)
def _create_placeholder_spells():
    passive = Buff("Passive")
    spell1 = Spell("Ability 1", damage=0, scaling=0, cooldown=0, mana_cost=0, range=0)
    spell2 = Spell("Ability 2", damage=0, scaling=0, cooldown=0, mana_cost=0, range=0)
    spell3 = Spell("Ability 3", damage=0, scaling=0, cooldown=0, mana_cost=0, range=0)
    spell4 = Spell("Ultimate", damage=0, scaling=0, cooldown=0, mana_cost=0, range=0)
    return Spells(passive, spell1, spell2, spell3, spell4)


# Achilles
achilles = God(
    name="Achilles",
    stats=Stats(
        hp=2175,
        mana=905,
        basic_attack_damage=78,
        basic_attack_speed=1.19,
        prot_physical=77,
        prot_magical=30,
        hp5=24,
        mp5=12.5
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Agni
agni = God(
    name="Agni",
    stats=Stats(
        hp=1780,
        mana=1155,
        basic_attack_damage=64,
        basic_attack_speed=1.24,
        prot_physical=63,
        prot_magical=30,
        hp5=16.4,
        mp5=12.1
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Ah Muzen Cab
ah_muzen_cab = God(
    name="Ah Muzen Cab",
    stats=Stats(
        hp=1910,
        mana=1030,
        basic_attack_damage=83,
        basic_attack_speed=1.27,
        prot_physical=72,
        prot_magical=30,
        hp5=21.2,
        mp5=12
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Ah Puch
ah_puch = God(
    name="Ah Puch",
    stats=Stats(
        hp=2010,
        mana=1365,
        basic_attack_damage=65,
        basic_attack_speed=1.02,
        prot_physical=67,
        prot_magical=30,
        hp5=15,
        mp5=13.3
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Amaterasu
amaterasu = God(
    name="Amaterasu",
    stats=Stats(
        hp=2180,
        mana=920,
        basic_attack_damage=79,
        basic_attack_speed=1.28,
        prot_physical=78,
        prot_magical=30,
        hp5=24,
        mp5=12.8
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Anhur
anhur = God(
    name="Anhur",
    stats=Stats(
        hp=2020,
        mana=920,
        basic_attack_damage=85,
        basic_attack_speed=1.34,
        prot_physical=67,
        prot_magical=30,
        hp5=21.8,
        mp5=10.9
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Anubis
anubis = God(
    name="Anubis",
    stats=Stats(
        hp=1860,
        mana=1440,
        basic_attack_damage=65,
        basic_attack_speed=1.03,
        prot_physical=60,
        prot_magical=30,
        hp5=16,
        mp5=12
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Ao Kuang
ao_kuang = God(
    name="Ao Kuang",
    stats=Stats(
        hp=2040,
        mana=1000,
        basic_attack_damage=83,
        basic_attack_speed=1.39,
        prot_physical=72,
        prot_magical=30,
        hp5=24,
        mp5=13
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Aphrodite
aphrodite = God(
    name="Aphrodite",
    stats=Stats(
        hp=1740,
        mana=1100,
        basic_attack_damage=61,
        basic_attack_speed=1.04,
        prot_physical=63,
        prot_magical=30,
        hp5=15,
        mp5=13
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Apollo
apollo = God(
    name="Apollo",
    stats=Stats(
        hp=1990,
        mana=1025,
        basic_attack_damage=87,
        basic_attack_speed=1.27,
        prot_physical=66,
        prot_magical=30,
        hp5=21.8,
        mp5=12.6
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Arachne
arachne = God(
    name="Arachne",
    stats=Stats(
        hp=2025,
        mana=1030,
        basic_attack_damage=82,
        basic_attack_speed=1.4,
        prot_physical=73,
        prot_magical=30,
        hp5=22.4,
        mp5=14
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Ares
ares = God(
    name="Ares",
    stats=Stats(
        hp=2285,
        mana=940,
        basic_attack_damage=120,
        basic_attack_speed=1.12,
        prot_physical=80,
        prot_magical=30,
        hp5=21.4,
        mp5=13
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Artemis
artemis = God(
    name="Artemis",
    stats=Stats(
        hp=2040,
        mana=885,
        basic_attack_damage=80,
        basic_attack_speed=1.27,
        prot_physical=72,
        prot_magical=30,
        hp5=21.6,
        mp5=9.4
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Artio
artio = God(
    name="Artio",
    stats=Stats(
        hp=2400,
        mana=990,
        basic_attack_damage=68,
        basic_attack_speed=1.24,
        prot_physical=84,
        prot_magical=30,
        hp5=26,
        mp5=13.2
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Athena
athena = God(
    name="Athena",
    stats=Stats(
        hp=2500,
        mana=870,
        basic_attack_damage=65,
        basic_attack_speed=1.24,
        prot_physical=84,
        prot_magical=30,
        hp5=24,
        mp5=13
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Atlas
atlas = God(
    name="Atlas",
    stats=Stats(
        hp=2510,
        mana=890,
        basic_attack_damage=67,
        basic_attack_speed=1.18,
        prot_physical=88,
        prot_magical=30,
        hp5=24,
        mp5=13
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Awilix
awilix = God(
    name="Awilix",
    stats=Stats(
        hp=2015,
        mana=1000,
        basic_attack_damage=81,
        basic_attack_speed=1.38,
        prot_physical=73,
        prot_magical=30,
        hp5=23.6,
        mp5=13.1
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Baba Yaga
baba_yaga = God(
    name="Baba Yaga",
    stats=Stats(
        hp=1860,
        mana=1280,
        basic_attack_damage=65,
        basic_attack_speed=1.14,
        prot_physical=65,
        prot_magical=30,
        hp5=18,
        mp5=17
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Bacchus
bacchus = God(
    name="Bacchus",
    stats=Stats(
        hp=2215,
        mana=1000,
        basic_attack_damage=67,
        basic_attack_speed=1.06,
        prot_physical=79,
        prot_magical=30,
        hp5=24,
        mp5=12.8
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Bakasura
bakasura = God(
    name="Bakasura",
    stats=Stats(
        hp=2015,
        mana=980,
        basic_attack_damage=82,
        basic_attack_speed=1.32,
        prot_physical=69,
        prot_magical=30,
        hp5=22.6,
        mp5=14
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Bake Kujira
bake_kujira = God(
    name="Bake Kujira",
    stats=Stats(
        hp=2500,
        mana=960,
        basic_attack_damage=54,
        basic_attack_speed=1.25,
        prot_physical=87,
        prot_magical=30,
        hp5=23,
        mp5=13
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Baron Samedi
baron_samedi = God(
    name="Baron Samedi",
    stats=Stats(
        hp=1980,
        mana=1180,
        basic_attack_damage=64,
        basic_attack_speed=1.04,
        prot_physical=70,
        prot_magical=30,
        hp5=19,
        mp5=14
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Bastet
bastet = God(
    name="Bastet",
    stats=Stats(
        hp=2015,
        mana=1010,
        basic_attack_damage=81,
        basic_attack_speed=1.4,
        prot_physical=70,
        prot_magical=30,
        hp5=23.4,
        mp5=9.4
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Bellona
bellona = God(
    name="Bellona",
    stats=Stats(
        hp=2350,
        mana=920,
        basic_attack_damage=76,
        basic_attack_speed=1.24,
        prot_physical=78,
        prot_magical=30,
        hp5=24,
        mp5=12.8
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Cabrakan
cabrakan = God(
    name="Cabrakan",
    stats=Stats(
        hp=2290,
        mana=960,
        basic_attack_damage=100,
        basic_attack_speed=1.12,
        prot_physical=93,
        prot_magical=30,
        hp5=23,
        mp5=24
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Camazotz
camazotz = God(
    name="Camazotz",
    stats=Stats(
        hp=2000,
        mana=940,
        basic_attack_damage=85,
        basic_attack_speed=1.4,
        prot_physical=71,
        prot_magical=30,
        hp5=21.4,
        mp5=10.4
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Cerberus
cerberus = God(
    name="Cerberus",
    stats=Stats(
        hp=2390,
        mana=900,
        basic_attack_damage=68,
        basic_attack_speed=1.2,
        prot_physical=79,
        prot_magical=30,
        hp5=22,
        mp5=12.6
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Cernunnos
cernunnos = God(
    name="Cernunnos",
    stats=Stats(
        hp=2080,
        mana=960,
        basic_attack_damage=82,
        basic_attack_speed=1.28,
        prot_physical=71,
        prot_magical=30,
        hp5=21.8,
        mp5=10.9
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Chaac
chaac = God(
    name="Chaac",
    stats=Stats(
        hp=2250,
        mana=905,
        basic_attack_damage=81,
        basic_attack_speed=1.24,
        prot_physical=78,
        prot_magical=30,
        hp5=23,
        mp5=12.5
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Chang'e
change = God(
    name="Chang'e",
    stats=Stats(
        hp=2144,
        mana=1270,
        basic_attack_damage=61,
        basic_attack_speed=1.19,
        prot_physical=65,
        prot_magical=30,
        hp5=15,
        mp5=14.3
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Charon
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
    spells=_create_placeholder_spells(),
    build=None
)

# Charybdis
charybdis = God(
    name="Charybdis",
    stats=Stats(
        hp=1980,
        mana=980,
        basic_attack_damage=85,
        basic_attack_speed=1.25,
        prot_physical=69,
        prot_magical=30,
        hp5=20.8,
        mp5=12
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Chernobog
chernobog = God(
    name="Chernobog",
    stats=Stats(
        hp=2050,
        mana=980,
        basic_attack_damage=83,
        basic_attack_speed=1.27,
        prot_physical=71,
        prot_magical=30,
        hp5=21.4,
        mp5=11.4
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Chiron
chiron = God(
    name="Chiron",
    stats=Stats(
        hp=1960,
        mana=1025,
        basic_attack_damage=77,
        basic_attack_speed=1.28,
        prot_physical=68,
        prot_magical=30,
        hp5=19,
        mp5=12
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Chronos
chronos = God(
    name="Chronos",
    stats=Stats(
        hp=1900,
        mana=1080,
        basic_attack_damage=70,
        basic_attack_speed=1.36,
        prot_physical=70,
        prot_magical=30,
        hp5=16.6,
        mp5=13.2
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Cliodhna
cliodhna = God(
    name="Cliodhna",
    stats=Stats(
        hp=2015,
        mana=1025,
        basic_attack_damage=86,
        basic_attack_speed=1.43,
        prot_physical=74,
        prot_magical=30,
        hp5=26,
        mp5=12.3
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Cthulhu
cthulhu = God(
    name="Cthulhu",
    stats=Stats(
        hp=2400,
        mana=970,
        basic_attack_damage=68,
        basic_attack_speed=1.12,
        prot_physical=85,
        prot_magical=30,
        hp5=24,
        mp5=13
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Cu Chulainn
cu_chulainn = God(
    name="Cu Chulainn",
    stats=Stats(
        hp=2180,
        mana=100,
        basic_attack_damage=79,
        basic_attack_speed=1.25,
        prot_physical=77,
        prot_magical=30,
        hp5=22,
        mp5=0
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Cupid
cupid = God(
    name="Cupid",
    stats=Stats(
        hp=1885,
        mana=1010,
        basic_attack_damage=85,
        basic_attack_speed=1.29,
        prot_physical=71,
        prot_magical=30,
        hp5=21.4,
        mp5=11.6
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Da Ji
da_ji = God(
    name="Da Ji",
    stats=Stats(
        hp=1960,
        mana=1010,
        basic_attack_damage=84,
        basic_attack_speed=1.4,
        prot_physical=74,
        prot_magical=30,
        hp5=23,
        mp5=12
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Danzaburou
danzaburou = God(
    name="Danzaburou",
    stats=Stats(
        hp=2020,
        mana=990,
        basic_attack_damage=87,
        basic_attack_speed=1.28,
        prot_physical=71,
        prot_magical=30,
        hp5=20.8,
        mp5=12
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Discordia
discordia = God(
    name="Discordia",
    stats=Stats(
        hp=1730,
        mana=1300,
        basic_attack_damage=64,
        basic_attack_speed=1.08,
        prot_physical=63,
        prot_magical=30,
        hp5=16,
        mp5=13.6
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Erlang Shen
erlang_shen = God(
    name="Erlang Shen",
    stats=Stats(
        hp=2185,
        mana=920,
        basic_attack_damage=79,
        basic_attack_speed=1.2,
        prot_physical=77,
        prot_magical=30,
        hp5=20,
        mp5=10.7
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Eset
eset = God(
    name="Eset",
    stats=Stats(
        hp=1820,
        mana=1300,
        basic_attack_damage=65,
        basic_attack_speed=1,
        prot_physical=63,
        prot_magical=30,
        hp5=15,
        mp5=13.4
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Fafnir
fafnir = God(
    name="Fafnir",
    stats=Stats(
        hp=2295,
        mana=1000,
        basic_attack_damage=68,
        basic_attack_speed=1.12,
        prot_physical=89,
        prot_magical=30,
        hp5=17.8,
        mp5=13.5
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Fenrir
fenrir = God(
    name="Fenrir",
    stats=Stats(
        hp=2015,
        mana=930,
        basic_attack_damage=84,
        basic_attack_speed=1.34,
        prot_physical=74,
        prot_magical=30,
        hp5=22.6,
        mp5=9.4
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Freya
freya = God(
    name="Freya",
    stats=Stats(
        hp=2036,
        mana=960,
        basic_attack_damage=65,
        basic_attack_speed=1.39,
        prot_physical=70,
        prot_magical=30,
        hp5=17.4,
        mp5=12.3
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Ganesha
ganesha = God(
    name="Ganesha",
    stats=Stats(
        hp=2395,
        mana=1000,
        basic_attack_damage=69,
        basic_attack_speed=1.24,
        prot_physical=84,
        prot_magical=30,
        hp5=19.4,
        mp5=13
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Geb
geb = God(
    name="Geb",
    stats=Stats(
        hp=2310,
        mana=870,
        basic_attack_damage=68,
        basic_attack_speed=1.24,
        prot_physical=79,
        prot_magical=30,
        hp5=24,
        mp5=12.6
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Gilgamesh
gilgamesh = God(
    name="Gilgamesh",
    stats=Stats(
        hp=2180,
        mana=910,
        basic_attack_damage=85,
        basic_attack_speed=1.25,
        prot_physical=78,
        prot_magical=30,
        hp5=26,
        mp5=12.1
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Guan Yu
guan_yu = God(
    name="Guan Yu",
    stats=Stats(
        hp=2220,
        mana=1000,
        basic_attack_damage=77,
        basic_attack_speed=1.24,
        prot_physical=77,
        prot_magical=30,
        hp5=20,
        mp5=13.8
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Hachiman
hachiman = God(
    name="Hachiman",
    stats=Stats(
        hp=1995,
        mana=950,
        basic_attack_damage=81,
        basic_attack_speed=1.26,
        prot_physical=67,
        prot_magical=30,
        hp5=20.8,
        mp5=11.9
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Hades
hades = God(
    name="Hades",
    stats=Stats(
        hp=2175,
        mana=1325,
        basic_attack_damage=62,
        basic_attack_speed=1.15,
        prot_physical=70,
        prot_magical=30,
        hp5=15.8,
        mp5=12.2
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# He Bo
he_bo = God(
    name="He Bo",
    stats=Stats(
        hp=1925,
        mana=1418,
        basic_attack_damage=63,
        basic_attack_speed=1.01,
        prot_physical=61,
        prot_magical=30,
        hp5=15,
        mp5=12.9
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Heimdallr
heimdallr = God(
    name="Heimdallr",
    stats=Stats(
        hp=2080,
        mana=910,
        basic_attack_damage=87,
        basic_attack_speed=1.25,
        prot_physical=76,
        prot_magical=30,
        hp5=24,
        mp5=12.5
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Hel
hel = God(
    name="Hel",
    stats=Stats(
        hp=1750,
        mana=1500,
        basic_attack_damage=63,
        basic_attack_speed=1.01,
        prot_physical=61,
        prot_magical=30,
        hp5=13.6,
        mp5=14
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Hera
hera = God(
    name="Hera",
    stats=Stats(
        hp=1740,
        mana=1165,
        basic_attack_damage=63,
        basic_attack_speed=1.08,
        prot_physical=63,
        prot_magical=30,
        hp5=15,
        mp5=13
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Hercules
hercules = God(
    name="Hercules",
    stats=Stats(
        hp=2270,
        mana=845,
        basic_attack_damage=79,
        basic_attack_speed=1.2,
        prot_physical=78,
        prot_magical=30,
        hp5=19.6,
        mp5=12.3
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Horus
horus = God(
    name="Horus",
    stats=Stats(
        hp=2388,
        mana=970,
        basic_attack_damage=79,
        basic_attack_speed=1.24,
        prot_physical=77,
        prot_magical=30,
        hp5=22,
        mp5=13.7
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Hou Yi
hou_yi = God(
    name="Hou Yi",
    stats=Stats(
        hp=2040,
        mana=1000,
        basic_attack_damage=91,
        basic_attack_speed=1.22,
        prot_physical=73,
        prot_magical=30,
        hp5=21.6,
        mp5=12
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Hun Batz
hun_batz = God(
    name="Hun Batz",
    stats=Stats(
        hp=1960,
        mana=980,
        basic_attack_damage=81,
        basic_attack_speed=1.38,
        prot_physical=73,
        prot_magical=30,
        hp5=23.6,
        mp5=12
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Ishtar
ishtar = God(
    name="Ishtar",
    stats=Stats(
        hp=2030,
        mana=980,
        basic_attack_damage=83,
        basic_attack_speed=1.32,
        prot_physical=71,
        prot_magical=30,
        hp5=21,
        mp5=12.1
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Ix Chel
ix_chel = God(
    name="Ix Chel",
    stats=Stats(
        hp=1980,
        mana=1180,
        basic_attack_damage=64,
        basic_attack_speed=1.04,
        prot_physical=68,
        prot_magical=30,
        hp5=19,
        mp5=14
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Izanami
izanami = God(
    name="Izanami",
    stats=Stats(
        hp=1990,
        mana=910,
        basic_attack_damage=77,
        basic_attack_speed=1.23,
        prot_physical=69,
        prot_magical=30,
        hp5=20,
        mp5=12
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Janus
janus = God(
    name="Janus",
    stats=Stats(
        hp=1800,
        mana=1510,
        basic_attack_damage=63,
        basic_attack_speed=1.16,
        prot_physical=66,
        prot_magical=30,
        hp5=15,
        mp5=14
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Jing Wei
jing_wei = God(
    name="Jing Wei",
    stats=Stats(
        hp=2005,
        mana=925,
        basic_attack_damage=87,
        basic_attack_speed=1.32,
        prot_physical=69,
        prot_magical=30,
        hp5=20.6,
        mp5=10.4
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Jormungandr
jormungandr = God(
    name="Jormungandr",
    stats=Stats(
        hp=2495,
        mana=990,
        basic_attack_damage=76,
        basic_attack_speed=1.2,
        prot_physical=91,
        prot_magical=30,
        hp5=25,
        mp5=13.5
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Kali
kali = God(
    name="Kali",
    stats=Stats(
        hp=1950,
        mana=905,
        basic_attack_damage=83,
        basic_attack_speed=1.43,
        prot_physical=73,
        prot_magical=30,
        hp5=22.6,
        mp5=8.5
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Khepri
khepri = God(
    name="Khepri",
    stats=Stats(
        hp=2290,
        mana=870,
        basic_attack_damage=68,
        basic_attack_speed=1.24,
        prot_physical=79,
        prot_magical=30,
        hp5=24,
        mp5=12.6
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# King Arthur
king_arthur = God(
    name="King Arthur",
    stats=Stats(
        hp=2145,
        mana=1030,
        basic_attack_damage=79,
        basic_attack_speed=1,
        prot_physical=77,
        prot_magical=30,
        hp5=25,
        mp5=12.4
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Kukulkan
kukulkan = God(
    name="Kukulkan",
    stats=Stats(
        hp=1880,
        mana=1165,
        basic_attack_damage=63,
        basic_attack_speed=1.03,
        prot_physical=73,
        prot_magical=30,
        hp5=16.2,
        mp5=14
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Kumbhakarna
kumbhakarna = God(
    name="Kumbhakarna",
    stats=Stats(
        hp=2490,
        mana=880,
        basic_attack_damage=68,
        basic_attack_speed=1.24,
        prot_physical=84,
        prot_magical=30,
        hp5=23,
        mp5=13
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Kuzenbo
kuzenbo = God(
    name="Kuzenbo",
    stats=Stats(
        hp=2500,
        mana=880,
        basic_attack_damage=68,
        basic_attack_speed=1.24,
        prot_physical=82,
        prot_magical=30,
        hp5=25,
        mp5=13
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Lancelot
lancelot = God(
    name="Lancelot",
    stats=Stats(
        hp=2000,
        mana=1030,
        basic_attack_damage=84,
        basic_attack_speed=1.38,
        prot_physical=72,
        prot_magical=30,
        hp5=23,
        mp5=13.8
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Loki
loki = God(
    name="Loki",
    stats=Stats(
        hp=1895,
        mana=910,
        basic_attack_damage=86,
        basic_attack_speed=1.38,
        prot_physical=69,
        prot_magical=30,
        hp5=22,
        mp5=11.2
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Maman Brigitte
maman_brigitte = God(
    name="Maman Brigitte",
    stats=Stats(
        hp=1947,
        mana=960,
        basic_attack_damage=83,
        basic_attack_speed=1.36,
        prot_physical=72,
        prot_magical=30,
        hp5=22,
        mp5=12.8
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Martichoras
martichoras = God(
    name="Martichoras",
    stats=Stats(
        hp=2126,
        mana=1000,
        basic_attack_damage=85,
        basic_attack_speed=1.18,
        prot_physical=78,
        prot_magical=30,
        hp5=21,
        mp5=12.5
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Maui
maui = God(
    name="Maui",
    stats=Stats(
        hp=2500,
        mana=920,
        basic_attack_damage=76,
        basic_attack_speed=1.15,
        prot_physical=89,
        prot_magical=30,
        hp5=24,
        mp5=12.9
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Medusa
medusa = God(
    name="Medusa",
    stats=Stats(
        hp=2010,
        mana=900,
        basic_attack_damage=85,
        basic_attack_speed=1.22,
        prot_physical=72,
        prot_magical=30,
        hp5=21.6,
        mp5=9.4
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Mercury
mercury = God(
    name="Mercury",
    stats=Stats(
        hp=1900,
        mana=1000,
        basic_attack_damage=81,
        basic_attack_speed=1.48,
        prot_physical=70,
        prot_magical=30,
        hp5=24,
        mp5=11.4
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Merlin
merlin = God(
    name="Merlin",
    stats=Stats(
        hp=1870,
        mana=1350,
        basic_attack_damage=64,
        basic_attack_speed=1.16,
        prot_physical=70,
        prot_magical=30,
        hp5=15.6,
        mp5=13.6
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Morgan Le Fay
morgan_le_fay = God(
    name="Morgan Le Fay",
    stats=Stats(
        hp=1970,
        mana=1350,
        basic_attack_damage=65,
        basic_attack_speed=1.16,
        prot_physical=74,
        prot_magical=30,
        hp5=17.6,
        mp5=13.6
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Mulan
mulan = God(
    name="Mulan",
    stats=Stats(
        hp=2170,
        mana=980,
        basic_attack_damage=83,
        basic_attack_speed=1.2,
        prot_physical=78,
        prot_magical=30,
        hp5=23,
        mp5=12.7
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Ne Zha
ne_zha = God(
    name="Ne Zha",
    stats=Stats(
        hp=1900,
        mana=900,
        basic_attack_damage=83,
        basic_attack_speed=1.42,
        prot_physical=70,
        prot_magical=30,
        hp5=24.2,
        mp5=9.3
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Neith
neith = God(
    name="Neith",
    stats=Stats(
        hp=1935,
        mana=1010,
        basic_attack_damage=83,
        basic_attack_speed=1.32,
        prot_physical=72,
        prot_magical=30,
        hp5=16.8,
        mp5=11.4
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Nemesis
nemesis = God(
    name="Nemesis",
    stats=Stats(
        hp=1990,
        mana=970,
        basic_attack_damage=84,
        basic_attack_speed=1.43,
        prot_physical=71,
        prot_magical=30,
        hp5=22,
        mp5=12.3
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Nike
nike = God(
    name="Nike",
    stats=Stats(
        hp=2240,
        mana=980,
        basic_attack_damage=77,
        basic_attack_speed=1.24,
        prot_physical=75,
        prot_magical=30,
        hp5=26,
        mp5=12.4
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Nox
nox = God(
    name="Nox",
    stats=Stats(
        hp=1865,
        mana=1010,
        basic_attack_damage=64,
        basic_attack_speed=1.16,
        prot_physical=70,
        prot_magical=30,
        hp5=20,
        mp5=13
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Nu Wa
nu_wa = God(
    name="Nu Wa",
    stats=Stats(
        hp=1900,
        mana=1125,
        basic_attack_damage=65,
        basic_attack_speed=1.34,
        prot_physical=63,
        prot_magical=30,
        hp5=16,
        mp5=13.2
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Nut
nut = God(
    name="Nut",
    stats=Stats(
        hp=2000,
        mana=970,
        basic_attack_damage=89,
        basic_attack_speed=1.34,
        prot_physical=71,
        prot_magical=30,
        hp5=21.2,
        mp5=12.5
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Odin
odin = God(
    name="Odin",
    stats=Stats(
        hp=2130,
        mana=900,
        basic_attack_damage=78,
        basic_attack_speed=1.22,
        prot_physical=76,
        prot_magical=30,
        hp5=21.6,
        mp5=12.1
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Olorun
olorun = God(
    name="Olorun",
    stats=Stats(
        hp=1950,
        mana=1400,
        basic_attack_damage=88,
        basic_attack_speed=1.36,
        prot_physical=73,
        prot_magical=30,
        hp5=16,
        mp5=13
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Osiris
osiris = God(
    name="Osiris",
    stats=Stats(
        hp=2245,
        mana=1030,
        basic_attack_damage=84,
        basic_attack_speed=1.26,
        prot_physical=77,
        prot_magical=30,
        hp5=25,
        mp5=12.5
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Pele
pele = God(
    name="Pele",
    stats=Stats(
        hp=2000,
        mana=1040,
        basic_attack_damage=84,
        basic_attack_speed=1.4,
        prot_physical=70,
        prot_magical=30,
        hp5=23,
        mp5=12.3
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Persephone
persephone = God(
    name="Persephone",
    stats=Stats(
        hp=1870,
        mana=1380,
        basic_attack_damage=68,
        basic_attack_speed=1.13,
        prot_physical=63,
        prot_magical=30,
        hp5=16,
        mp5=13.4
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Poseidon
poseidon = God(
    name="Poseidon",
    stats=Stats(
        hp=1720,
        mana=1045,
        basic_attack_damage=65,
        basic_attack_speed=1.18,
        prot_physical=60,
        prot_magical=30,
        hp5=16,
        mp5=12.6
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Ra
ra = God(
    name="Ra",
    stats=Stats(
        hp=1885,
        mana=1215,
        basic_attack_damage=64,
        basic_attack_speed=1.06,
        prot_physical=70,
        prot_magical=30,
        hp5=16.6,
        mp5=13.6
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Raijin
raijin = God(
    name="Raijin",
    stats=Stats(
        hp=1985,
        mana=1115,
        basic_attack_damage=64,
        basic_attack_speed=1.03,
        prot_physical=71,
        prot_magical=30,
        hp5=15,
        mp5=13.8
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Rama
rama = God(
    name="Rama",
    stats=Stats(
        hp=1980,
        mana=885,
        basic_attack_damage=85,
        basic_attack_speed=1.27,
        prot_physical=68,
        prot_magical=30,
        hp5=21,
        mp5=9.5
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Ratatoskr
ratatoskr = God(
    name="Ratatoskr",
    stats=Stats(
        hp=1880,
        mana=1060,
        basic_attack_damage=84,
        basic_attack_speed=1.4,
        prot_physical=72,
        prot_magical=30,
        hp5=23,
        mp5=13.8
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Ravana
ravana = God(
    name="Ravana",
    stats=Stats(
        hp=1900,
        mana=970,
        basic_attack_damage=83,
        basic_attack_speed=1.34,
        prot_physical=71,
        prot_magical=30,
        hp5=22,
        mp5=11.4
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Scylla
scylla = God(
    name="Scylla",
    stats=Stats(
        hp=1865,
        mana=1418,
        basic_attack_damage=63,
        basic_attack_speed=1.16,
        prot_physical=61,
        prot_magical=30,
        hp5=15,
        mp5=12.9
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Serqet
serqet = God(
    name="Serqet",
    stats=Stats(
        hp=1880,
        mana=1040,
        basic_attack_damage=84,
        basic_attack_speed=1.43,
        prot_physical=72,
        prot_magical=30,
        hp5=23,
        mp5=10.1
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Set
set = God(
    name="Set",
    stats=Stats(
        hp=1950,
        mana=970,
        basic_attack_damage=85,
        basic_attack_speed=1.38,
        prot_physical=71,
        prot_magical=30,
        hp5=23,
        mp5=11.8
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Shiva
shiva = God(
    name="Shiva",
    stats=Stats(
        hp=2135,
        mana=930,
        basic_attack_damage=79,
        basic_attack_speed=1.24,
        prot_physical=76,
        prot_magical=30,
        hp5=22,
        mp5=12.3
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Skadi
skadi = God(
    name="Skadi",
    stats=Stats(
        hp=2030,
        mana=920,
        basic_attack_damage=85,
        basic_attack_speed=1.25,
        prot_physical=67,
        prot_magical=30,
        hp5=21.8,
        mp5=10.9
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Sobek
sobek = God(
    name="Sobek",
    stats=Stats(
        hp=2390,
        mana=910,
        basic_attack_damage=68,
        basic_attack_speed=1.09,
        prot_physical=79,
        prot_magical=30,
        hp5=21,
        mp5=13.1
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Sol
sol = God(
    name="Sol",
    stats=Stats(
        hp=1900,
        mana=1440,
        basic_attack_damage=63,
        basic_attack_speed=1.36,
        prot_physical=61,
        prot_magical=30,
        hp5=15,
        mp5=12.9
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Sun Wukong
sun_wukong = God(
    name="Sun Wukong",
    stats=Stats(
        hp=2180,
        mana=905,
        basic_attack_damage=79,
        basic_attack_speed=1.18,
        prot_physical=78,
        prot_magical=30,
        hp5=24,
        mp5=11.9
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Surtr
surtr = God(
    name="Surtr",
    stats=Stats(
        hp=2159,
        mana=930,
        basic_attack_damage=83,
        basic_attack_speed=1.24,
        prot_physical=78,
        prot_magical=30,
        hp5=25,
        mp5=12.2
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Susano
susano = God(
    name="Susano",
    stats=Stats(
        hp=1955,
        mana=985,
        basic_attack_damage=82,
        basic_attack_speed=1.43,
        prot_physical=72,
        prot_magical=30,
        hp5=23,
        mp5=9.6
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Sylvanus
sylvanus = God(
    name="Sylvanus",
    stats=Stats(
        hp=2410,
        mana=870,
        basic_attack_damage=68,
        basic_attack_speed=1.04,
        prot_physical=89,
        prot_magical=30,
        hp5=24,
        mp5=12.6
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Terra
terra = God(
    name="Terra",
    stats=Stats(
        hp=2400,
        mana=900,
        basic_attack_damage=69,
        basic_attack_speed=1.15,
        prot_physical=84,
        prot_magical=30,
        hp5=24,
        mp5=12.6
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Thanatos
thanatos = God(
    name="Thanatos",
    stats=Stats(
        hp=1890,
        mana=1000,
        basic_attack_damage=85,
        basic_attack_speed=1.34,
        prot_physical=72,
        prot_magical=30,
        hp5=21.4,
        mp5=12
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# The Morrigan
the_morrigan = God(
    name="The Morrigan",
    stats=Stats(
        hp=1950,
        mana=1010,
        basic_attack_damage=82,
        basic_attack_speed=1.04,
        prot_physical=74,
        prot_magical=30,
        hp5=24,
        mp5=12.5
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Thor
thor = God(
    name="Thor",
    stats=Stats(
        hp=1980,
        mana=1000,
        basic_attack_damage=87,
        basic_attack_speed=1.29,
        prot_physical=72,
        prot_magical=30,
        hp5=22.8,
        mp5=10.2
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Thoth
thoth = God(
    name="Thoth",
    stats=Stats(
        hp=1865,
        mana=1225,
        basic_attack_damage=62,
        basic_attack_speed=1.24,
        prot_physical=61,
        prot_magical=30,
        hp5=15,
        mp5=13.4
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Tiamat
tiamat = God(
    name="Tiamat",
    stats=Stats(
        hp=1940,
        mana=1400,
        basic_attack_damage=64,
        basic_attack_speed=1.06,
        prot_physical=67,
        prot_magical=30,
        hp5=17,
        mp5=13.8
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Tsukuyomi
tsukuyomi = God(
    name="Tsukuyomi",
    stats=Stats(
        hp=2015,
        mana=905,
        basic_attack_damage=83,
        basic_attack_speed=1.26,
        prot_physical=69,
        prot_magical=30,
        hp5=21.6,
        mp5=13.7
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Tyr
tyr = God(
    name="Tyr",
    stats=Stats(
        hp=2145,
        mana=1030,
        basic_attack_damage=79,
        basic_attack_speed=1.18,
        prot_physical=78,
        prot_magical=30,
        hp5=22.4,
        mp5=10.2
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Ullr
ullr = God(
    name="Ullr",
    stats=Stats(
        hp=2080,
        mana=1030,
        basic_attack_damage=81,
        basic_attack_speed=1.23,
        prot_physical=73,
        prot_magical=30,
        hp5=22.2,
        mp5=12
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Vamana
vamana = God(
    name="Vamana",
    stats=Stats(
        hp=2250,
        mana=980,
        basic_attack_damage=77,
        basic_attack_speed=1.28,
        prot_physical=76,
        prot_magical=30,
        hp5=18,
        mp5=12.9
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Vulcan
vulcan = God(
    name="Vulcan",
    stats=Stats(
        hp=1800,
        mana=1045,
        basic_attack_damage=64,
        basic_attack_speed=1.1,
        prot_physical=73,
        prot_magical=30,
        hp5=16.6,
        mp5=13.8
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Xbalanque
xbalanque = God(
    name="Xbalanque",
    stats=Stats(
        hp=1955,
        mana=960,
        basic_attack_damage=85,
        basic_attack_speed=1.23,
        prot_physical=70,
        prot_magical=30,
        hp5=21.6,
        mp5=12.4
    ),
    power_type=PowerType.PHYSICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Xing Tian
xing_tian = God(
    name="Xing Tian",
    stats=Stats(
        hp=2295,
        mana=1000,
        basic_attack_damage=66,
        basic_attack_speed=1.12,
        prot_physical=89,
        prot_magical=30,
        hp5=15.8,
        mp5=13.5
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Yemoja
yemoja = God(
    name="Yemoja",
    stats=Stats(
        hp=2390,
        mana=0,
        basic_attack_damage=64,
        basic_attack_speed=1.24,
        prot_physical=79,
        prot_magical=30,
        hp5=20,
        mp5=0
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Ymir
ymir = God(
    name="Ymir",
    stats=Stats(
        hp=2590,
        mana=840,
        basic_attack_damage=69,
        basic_attack_speed=1.05,
        prot_physical=89,
        prot_magical=30,
        hp5=26,
        mp5=12.5
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Yu Huang
yu_huang = God(
    name="Yu Huang",
    stats=Stats(
        hp=1940,
        mana=1380,
        basic_attack_damage=65,
        basic_attack_speed=1.24,
        prot_physical=72,
        prot_magical=30,
        hp5=16.4,
        mp5=13.5
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Zeus
zeus = God(
    name="Zeus",
    stats=Stats(
        hp=1800,
        mana=1125,
        basic_attack_damage=65,
        basic_attack_speed=1.14,
        prot_physical=62,
        prot_magical=30,
        hp5=15,
        mp5=13.6
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)

# Zhong Kui
zhong_kui = God(
    name="Zhong Kui",
    stats=Stats(
        hp=2150,
        mana=1190,
        basic_attack_damage=63,
        basic_attack_speed=1.14,
        prot_physical=63,
        prot_magical=30,
        hp5=14.8,
        mp5=13.8
    ),
    power_type=PowerType.MAGICAL,
    spells=_create_placeholder_spells(),
    build=None
)


# Export all gods
__all__ = [
    "achilles",
    "agni",
    "ah_muzen_cab",
    "ah_puch",
    "amaterasu",
    "anhur",
    "anubis",
    "ao_kuang",
    "aphrodite",
    "apollo",
    "arachne",
    "ares",
    "artemis",
    "artio",
    "athena",
    "atlas",
    "awilix",
    "baba_yaga",
    "bacchus",
    "bakasura",
    "bake_kujira",
    "baron_samedi",
    "bastet",
    "bellona",
    "cabrakan",
    "camazotz",
    "cerberus",
    "cernunnos",
    "chaac",
    "change",
    "charon",
    "charybdis",
    "chernobog",
    "chiron",
    "chronos",
    "cliodhna",
    "cthulhu",
    "cu_chulainn",
    "cupid",
    "da_ji",
    "danzaburou",
    "discordia",
    "erlang_shen",
    "eset",
    "fafnir",
    "fenrir",
    "freya",
    "ganesha",
    "geb",
    "gilgamesh",
    "guan_yu",
    "hachiman",
    "hades",
    "he_bo",
    "heimdallr",
    "hel",
    "hera",
    "hercules",
    "horus",
    "hou_yi",
    "hun_batz",
    "ishtar",
    "ix_chel",
    "izanami",
    "janus",
    "jing_wei",
    "jormungandr",
    "kali",
    "khepri",
    "king_arthur",
    "kukulkan",
    "kumbhakarna",
    "kuzenbo",
    "lancelot",
    "loki",
    "maman_brigitte",
    "martichoras",
    "maui",
    "medusa",
    "mercury",
    "merlin",
    "morgan_le_fay",
    "mulan",
    "ne_zha",
    "neith",
    "nemesis",
    "nike",
    "nox",
    "nu_wa",
    "nut",
    "odin",
    "olorun",
    "osiris",
    "pele",
    "persephone",
    "poseidon",
    "ra",
    "raijin",
    "rama",
    "ratatoskr",
    "ravana",
    "scylla",
    "serqet",
    "set",
    "shiva",
    "skadi",
    "sobek",
    "sol",
    "sun_wukong",
    "surtr",
    "susano",
    "sylvanus",
    "terra",
    "thanatos",
    "the_morrigan",
    "thor",
    "thoth",
    "tiamat",
    "tsukuyomi",
    "tyr",
    "ullr",
    "vamana",
    "vulcan",
    "xbalanque",
    "xing_tian",
    "yemoja",
    "ymir",
    "yu_huang",
    "zeus",
    "zhong_kui",
]

