import enum

from engine.models.model import GameCampaign, GameFactions


class AttilaFactions(GameFactions):
    ATT_FACT_ABARSHAHR = 'att_fact_abarshahr'
    ATT_FACT_ABASGIA = 'att_fact_abasgia'
    ATT_FACT_AEGYPTUS = 'att_fact_aegyptus'
    ATT_FACT_AFRICA = 'att_fact_africa'
    ATT_FACT_AFRIGHIDS = 'att_fact_afrighids'
    ATT_FACT_ALAMANNI = 'att_fact_alamanni'
    ATT_FACT_ALANI = 'att_fact_alani'
    ATT_FACT_ANATOLIA = 'att_fact_anatolia'
    ATT_FACT_ANGLI = 'att_fact_angli'
    ATT_FACT_ANTES = 'att_fact_antes'
    ATT_FACT_ARIA = 'att_fact_aria'
    ATT_FACT_ARMENIA = 'att_fact_armenia'
    ATT_FACT_ARRAN = 'att_fact_arran'
    ATT_FACT_ASIA = 'att_fact_asia'
    ATT_FACT_ATURPATAKAN = 'att_fact_aturpatakan'
    ATT_FACT_AXUM = 'att_fact_axum'
    ATT_FACT_BASTARNAE = 'att_fact_bastarnae'
    ATT_FACT_BLUE = 'att_fact_blue'
    ATT_FACT_BRITANNIA = 'att_fact_britannia'
    ATT_FACT_BUDINI = 'att_fact_budini'
    ATT_FACT_BURGUNDII = 'att_fact_burgundii'
    ATT_FACT_DACIA = 'att_fact_dacia'
    ATT_FACT_DANI = 'att_fact_dani'
    ATT_FACT_EASTERN_ROMAN_EMPIRE = 'att_fact_eastern_roman_empire'
    ATT_FACT_EBDANI = 'att_fact_ebdani'
    ATT_FACT_FRANCI = 'att_fact_franci'
    ATT_FACT_GAETULI = 'att_fact_gaetuli'
    ATT_FACT_GALLIA = 'att_fact_gallia'
    ATT_FACT_GARAMANTES = 'att_fact_garamantes'
    ATT_FACT_GAUTI = 'att_fact_gauti'
    ATT_FACT_GEPIDAE = 'att_fact_gepidae'
    ATT_FACT_GHASSANIDS = 'att_fact_ghassanids'
    ATT_FACT_GREUTHINGI = 'att_fact_greuthingi'
    ATT_FACT_HIMYAR = 'att_fact_himyar'
    ATT_FACT_HISPANIA = 'att_fact_hispania'
    ATT_FACT_HUNNI = 'att_fact_hunni'
    ATT_FACT_IAZYGES = 'att_fact_iazyges'
    ATT_FACT_ILLYRICUM = 'att_fact_illyricum'
    ATT_FACT_ITALIA = 'att_fact_italia'
    ATT_FACT_IUTI = 'att_fact_iuti'
    ATT_FACT_JUDEA = 'att_fact_judea'
    ATT_FACT_KARTLI = 'att_fact_kartli'
    ATT_FACT_LAKHMIDS = 'att_fact_lakhmids'
    ATT_FACT_LANGOBARDI = 'att_fact_langobardi'
    ATT_FACT_LAZICA = 'att_fact_lazica'
    ATT_FACT_LUGII = 'att_fact_lugii'
    ATT_FACT_MACEDONIA = 'att_fact_macedonia'
    ATT_FACT_MAGYARS = 'att_fact_magyars'
    ATT_FACT_MAKRAN = 'att_fact_makran'
    ATT_FACT_MARCOMANNI = 'att_fact_marcomanni'
    ATT_FACT_MAURI = 'att_fact_mauri'
    ATT_FACT_MAZUN = 'att_fact_mazun'
    ATT_FACT_NOBATIA = 'att_fact_nobatia'
    ATT_FACT_ORIENS = 'att_fact_oriens'
    ATT_FACT_OSTROGOTHI = 'att_fact_ostrogothi'
    ATT_FACT_PALMYRA = 'att_fact_palmyra'
    ATT_FACT_PARTHIA = 'att_fact_parthia'
    ATT_FACT_PERSIS = 'att_fact_persis'
    ATT_FACT_PICTI = 'att_fact_picti'
    ATT_FACT_PONTUS = 'att_fact_pontus'
    ATT_FACT_QUADI = 'att_fact_quadi'
    ATT_FACT_REBEL_AETHIOPIAN = 'att_fact_rebel_aethiopian'
    ATT_FACT_REBEL_AFRICAN = 'att_fact_rebel_african'
    ATT_FACT_REBEL_ARABIAN = 'att_fact_rebel_arabian'
    ATT_FACT_REBEL_CAUCASIAN = 'att_fact_rebel_caucasian'
    ATT_FACT_REBEL_CELTIC = 'att_fact_rebel_celtic'
    ATT_FACT_REBEL_EASTERN = 'att_fact_rebel_eastern'
    ATT_FACT_REBEL_EASTERN_ROMAN = 'att_fact_rebel_eastern_roman'
    ATT_FACT_REBEL_GERMANIC_EAST = 'att_fact_rebel_germanic_east'
    ATT_FACT_REBEL_GERMANIC_NORTH = 'att_fact_rebel_germanic_north'
    ATT_FACT_REBEL_GERMANIC_WEST = 'att_fact_rebel_germanic_west'
    ATT_FACT_REBEL_HUNNIC = 'att_fact_rebel_hunnic'
    ATT_FACT_REBEL_NORDIC = 'att_fact_rebel_nordic'
    ATT_FACT_REBEL_SARMATIAN = 'att_fact_rebel_sarmatian'
    ATT_FACT_REBEL_SLAVS = 'att_fact_rebel_slavs'
    ATT_FACT_REBEL_WESTERN_ROMAN = 'att_fact_rebel_western_roman'
    ATT_FACT_REBEL_WHITE_HUNS = 'att_fact_rebel_white_huns'
    ATT_FACT_RED = 'att_fact_red'
    ATT_FACT_ROXOLANI = 'att_fact_roxolani'
    ATT_FACT_RUGII = 'att_fact_rugii'
    ATT_FACT_SABIRS = 'att_fact_sabirs'
    ATT_FACT_SASSANID_EMPIRE = 'att_fact_sassanid_empire'
    ATT_FACT_SAXONES = 'att_fact_saxones'
    ATT_FACT_SCLAVENI = 'att_fact_sclaveni'
    ATT_FACT_SEPARATIST_AETHIOPIAN = 'att_fact_separatist_aethiopian'
    ATT_FACT_SEPARATIST_AFRICAN = 'att_fact_separatist_african'
    ATT_FACT_SEPARATIST_ALAMANNI = 'att_fact_separatist_alamanni'
    ATT_FACT_SEPARATIST_ALANIC = 'att_fact_separatist_alanic'
    ATT_FACT_SEPARATIST_ANTES = 'att_fact_separatist_antes'
    ATT_FACT_SEPARATIST_ARABIAN = 'att_fact_separatist_arabian'
    ATT_FACT_SEPARATIST_AXUM = 'att_fact_separatist_axum'
    ATT_FACT_SEPARATIST_BURGUNDII = 'att_fact_separatist_burgundii'
    ATT_FACT_SEPARATIST_CAUCASIAN = 'att_fact_separatist_caucasian'
    ATT_FACT_SEPARATIST_CELTIC = 'att_fact_separatist_celtic'
    ATT_FACT_SEPARATIST_DANI = 'att_fact_separatist_dani'
    ATT_FACT_SEPARATIST_EASTERN = 'att_fact_separatist_eastern'
    ATT_FACT_SEPARATIST_EASTERN_ROMAN = 'att_fact_separatist_eastern_roman'
    ATT_FACT_SEPARATIST_EASTERN_ROMAN_NPC = 'att_fact_separatist_eastern_roman_npc'
    ATT_FACT_SEPARATIST_EBDANI = 'att_fact_separatist_ebdani'
    ATT_FACT_SEPARATIST_FRANKISH = 'att_fact_separatist_frankish'
    ATT_FACT_SEPARATIST_GARAMANTES = 'att_fact_separatist_garamantes'
    ATT_FACT_SEPARATIST_GAUT = 'att_fact_separatist_gaut'
    ATT_FACT_SEPARATIST_GERMANIC_EAST = 'att_fact_separatist_germanic_east'
    ATT_FACT_SEPARATIST_GERMANIC_NORTH = 'att_fact_separatist_germanic_north'
    ATT_FACT_SEPARATIST_GERMANIC_WEST = 'att_fact_separatist_germanic_west'
    ATT_FACT_SEPARATIST_HIMYAR = 'att_fact_separatist_himyar'
    ATT_FACT_SEPARATIST_HUNNIC = 'att_fact_separatist_hunnic'
    ATT_FACT_SEPARATIST_IUTI = 'att_fact_separatist_iuti'
    ATT_FACT_SEPARATIST_LAKHMIDS = 'att_fact_separatist_lakhmids'
    ATT_FACT_SEPARATIST_LANGOBARDI = 'att_fact_separatist_langobardi'
    ATT_FACT_SEPARATIST_NORDIC = 'att_fact_separatist_nordic'
    ATT_FACT_SEPARATIST_OSTROGOTHIC = 'att_fact_separatist_ostrogothic'
    ATT_FACT_SEPARATIST_PICTI = 'att_fact_separatist_picti'
    ATT_FACT_SEPARATIST_SARMATIAN = 'att_fact_separatist_sarmatian'
    ATT_FACT_SEPARATIST_SASSANID = 'att_fact_separatist_sassanid'
    ATT_FACT_SEPARATIST_SAXON = 'att_fact_separatist_saxon'
    ATT_FACT_SEPARATIST_SCLAVENI = 'att_fact_separatist_sclaveni'
    ATT_FACT_SEPARATIST_SUEBI = 'att_fact_separatist_suebi'
    ATT_FACT_SEPARATIST_TANUKHID = 'att_fact_separatist_tanukhid'
    ATT_FACT_SEPARATIST_VANDALIC = 'att_fact_separatist_vandalic'
    ATT_FACT_SEPARATIST_VENEDI = 'att_fact_separatist_venedi'
    ATT_FACT_SEPARATIST_VISIGOTHIC = 'att_fact_separatist_visigothic'
    ATT_FACT_SEPARATIST_VOTADINI = 'att_fact_separatist_votadini'
    ATT_FACT_SEPARATIST_WESTERN_ROMAN = 'att_fact_separatist_western_roman'
    ATT_FACT_SEPARATIST_WESTERN_ROMAN_NPC = 'att_fact_separatist_western_roman_npc'
    ATT_FACT_SEPARATIST_WHITE_HUNS = 'att_fact_separatist_white_huns'
    ATT_FACT_SEPTEM_PROVINCIEM = 'att_fact_septem_provinciem'
    ATT_FACT_SOISSONS = 'att_fact_soissons'
    ATT_FACT_SPAHAN = 'att_fact_spahan'
    ATT_FACT_SUEBI = 'att_fact_suebi'
    ATT_FACT_TANUKHIDS = 'att_fact_tanukhids'
    ATT_FACT_THURINGI = 'att_fact_thuringi'
    ATT_FACT_VANDALI = 'att_fact_vandali'
    ATT_FACT_VARINI = 'att_fact_varini'
    ATT_FACT_VENEDI = 'att_fact_venedi'
    ATT_FACT_VISIGOTHI = 'att_fact_visigothi'
    ATT_FACT_VOTADINI = 'att_fact_votadini'
    ATT_FACT_WESTERN_ROMAN_EMPIRE = 'att_fact_western_roman_empire'
    ATT_FACT_WHITE_HUNS = 'att_fact_white_huns'
    ATT_FACT_YELLOW = 'att_fact_yellow'
    BEL_FACT_BASQUES = 'bel_fact_basques'
    BEL_FACT_BERBERI = 'bel_fact_berberi'
    BEL_FACT_BRETONI = 'bel_fact_bretoni'
    BEL_FACT_BURGUNDII = 'bel_fact_burgundii'
    BEL_FACT_BYZANTINE_EMPIRE = 'bel_fact_byzantine_empire'
    BEL_FACT_BYZANTINE_EXPEDITION = 'bel_fact_byzantine_expedition'
    BEL_FACT_FRANCI = 'bel_fact_franci'
    BEL_FACT_LOMBARDI = 'bel_fact_lombardi'
    BEL_FACT_MAURI = 'bel_fact_mauri'
    BEL_FACT_OSTROGOTHI = 'bel_fact_ostrogothi'
    BEL_FACT_REBEL_AFRICAN = 'bel_fact_rebel_african'
    BEL_FACT_REBEL_GERMAN = 'bel_fact_rebel_german'
    BEL_FACT_REBEL_ROMAN = 'bel_fact_rebel_roman'
    BEL_FACT_SARDINII = 'bel_fact_sardinii'
    BEL_FACT_SEPARATIST_AFRICAN = 'bel_fact_separatist_african'
    BEL_FACT_SEPARATIST_BYZANTINE_EXPEDITION = 'bel_fact_separatist_byzantine_expedition'
    BEL_FACT_SEPARATIST_EASTERN = 'bel_fact_separatist_eastern'
    BEL_FACT_SEPARATIST_FRANKISH = 'bel_fact_separatist_frankish'
    BEL_FACT_SEPARATIST_OSTROGOTHI = 'bel_fact_separatist_ostrogothi'
    BEL_FACT_SEPARATIST_VANDALIC = 'bel_fact_separatist_vandalic'
    BEL_FACT_SEPARATIST_VISIGOTHIC = 'bel_fact_separatist_visigothic'
    BEL_FACT_SEPARATIST_WESTERN = 'bel_fact_separatist_western'
    BEL_FACT_SUEBI = 'bel_fact_suebi'
    BEL_FACT_VANDALI = 'bel_fact_vandali'
    BEL_FACT_VISIGOTHI = 'bel_fact_visigothi'
    CHA_FACT_AILECH = 'cha_fact_ailech'
    CHA_FACT_ALEMANNIA = 'cha_fact_alemannia'
    CHA_FACT_ALT_CLUT = 'cha_fact_alt_clut'
    CHA_FACT_ANGRIANS = 'cha_fact_angrians'
    CHA_FACT_AQUITANE = 'cha_fact_aquitane'
    CHA_FACT_ASTURIAS = 'cha_fact_asturias'
    CHA_FACT_AVARS = 'cha_fact_avars'
    CHA_FACT_BADAJOZ = 'cha_fact_badajoz'
    CHA_FACT_BARCELONA = 'cha_fact_barcelona'
    CHA_FACT_BAVARIA = 'cha_fact_bavaria'
    CHA_FACT_BENEVENTO = 'cha_fact_benevento'
    CHA_FACT_BOHEMIA = 'cha_fact_bohemia'
    CHA_FACT_BRITTANY = 'cha_fact_brittany'
    CHA_FACT_BURGUNDY = 'cha_fact_burgundy'
    CHA_FACT_CARLOMAN = 'cha_fact_carloman'
    CHA_FACT_CHARLEMAGNE = 'cha_fact_charlemagne'
    CHA_FACT_CONNACHTA = 'cha_fact_connachta'
    CHA_FACT_CORDOBA = 'cha_fact_cordoba'
    CHA_FACT_CROATIA = 'cha_fact_croatia'
    CHA_FACT_DANES = 'cha_fact_danes'
    CHA_FACT_EASTPHALIA = 'cha_fact_eastphalia'
    CHA_FACT_FRISIA = 'cha_fact_frisia'
    CHA_FACT_GASCONY = 'cha_fact_gascony'
    CHA_FACT_GLYWYSING = 'cha_fact_glywysing'
    CHA_FACT_GRANADA = 'cha_fact_granada'
    CHA_FACT_GWYNEDD = 'cha_fact_gwynedd'
    CHA_FACT_KENT = 'cha_fact_kent'
    CHA_FACT_LEINSTER = 'cha_fact_leinster'
    CHA_FACT_LOMBARDS = 'cha_fact_lombards'
    CHA_FACT_MERCIA = 'cha_fact_mercia'
    CHA_FACT_MUNSTER = 'cha_fact_munster'
    CHA_FACT_NORDALINGANS = 'cha_fact_nordalingans'
    CHA_FACT_NORTHUMBRIA = 'cha_fact_northumbria'
    CHA_FACT_OBODRITES = 'cha_fact_obodrites'
    CHA_FACT_PAMPLONA = 'cha_fact_pamplona'
    CHA_FACT_PAPAL_STATES = 'cha_fact_papal_states'
    CHA_FACT_PICTS = 'cha_fact_picts'
    CHA_FACT_POWYS = 'cha_fact_powys'
    CHA_FACT_PROVENCE = 'cha_fact_provence'
    CHA_FACT_REBEL_AVARS = 'cha_fact_rebel_avars'
    CHA_FACT_REBEL_CHRISTIAN = 'cha_fact_rebel_christian'
    CHA_FACT_REBEL_ENGLISH = 'cha_fact_rebel_english'
    CHA_FACT_REBEL_FRANKISH = 'cha_fact_rebel_frankish'
    CHA_FACT_REBEL_IRISH = 'cha_fact_rebel_irish'
    CHA_FACT_REBEL_ITALIAN = 'cha_fact_rebel_italian'
    CHA_FACT_REBEL_MUSLIM = 'cha_fact_rebel_muslim'
    CHA_FACT_REBEL_PICT = 'cha_fact_rebel_pict'
    CHA_FACT_REBEL_ROMAN = 'cha_fact_rebel_roman'
    CHA_FACT_REBEL_SAXON = 'cha_fact_rebel_saxon'
    CHA_FACT_REBEL_SLAVIC = 'cha_fact_rebel_slavic'
    CHA_FACT_REBEL_SPANISH = 'cha_fact_rebel_spanish'
    CHA_FACT_REBEL_VIKING = 'cha_fact_rebel_viking'
    CHA_FACT_REBEL_WELSH = 'cha_fact_rebel_welsh'
    CHA_FACT_SEPARATIST_AVARS = 'cha_fact_separatist_avars'
    CHA_FACT_SEPARATIST_AVARS_CW = 'cha_fact_separatist_avars_cw'
    CHA_FACT_SEPARATIST_CHRISTIAN = 'cha_fact_separatist_christian'
    CHA_FACT_SEPARATIST_ENGLISH = 'cha_fact_separatist_english'
    CHA_FACT_SEPARATIST_ENGLISH_CW = 'cha_fact_separatist_english_cw'
    CHA_FACT_SEPARATIST_FRANKISH = 'cha_fact_separatist_frankish'
    CHA_FACT_SEPARATIST_FRANKISH_CW = 'cha_fact_separatist_frankish_cw'
    CHA_FACT_SEPARATIST_GALLICIAN = 'cha_fact_separatist_gallician'
    CHA_FACT_SEPARATIST_GALLICIAN_CW = 'cha_fact_separatist_gallician_cw'
    CHA_FACT_SEPARATIST_IRISH = 'cha_fact_separatist_irish'
    CHA_FACT_SEPARATIST_ITALIAN = 'cha_fact_separatist_italian'
    CHA_FACT_SEPARATIST_ITALIAN_CW = 'cha_fact_separatist_italian_cw'
    CHA_FACT_SEPARATIST_MUSLIM = 'cha_fact_separatist_muslim'
    CHA_FACT_SEPARATIST_MUSLIM_CW = 'cha_fact_separatist_muslim_cw'
    CHA_FACT_SEPARATIST_PICT = 'cha_fact_separatist_pict'
    CHA_FACT_SEPARATIST_ROMAN = 'cha_fact_separatist_roman'
    CHA_FACT_SEPARATIST_SAXON = 'cha_fact_separatist_saxon'
    CHA_FACT_SEPARATIST_SAXON_CW = 'cha_fact_separatist_saxon_cw'
    CHA_FACT_SEPARATIST_SLAVIC = 'cha_fact_separatist_slavic'
    CHA_FACT_SEPARATIST_VIKING = 'cha_fact_separatist_viking'
    CHA_FACT_SEPARATIST_VIKING_CW = 'cha_fact_separatist_viking_cw'
    CHA_FACT_SEPARATIST_WELSH = 'cha_fact_separatist_welsh'
    CHA_FACT_SEVILLA = 'cha_fact_sevilla'
    CHA_FACT_SICILY = 'cha_fact_sicily'
    CHA_FACT_SPOLETO = 'cha_fact_spoleto'
    CHA_FACT_TOLEDO = 'cha_fact_toledo'
    CHA_FACT_ULAID = 'cha_fact_ulaid'
    CHA_FACT_VALENCIA = 'cha_fact_valencia'
    CHA_FACT_VENICE = 'cha_fact_venice'
    CHA_FACT_WESSEX = 'cha_fact_wessex'
    CHA_FACT_WESTPHALIA = 'cha_fact_westphalia'
    CHA_FACT_WILZI = 'cha_fact_wilzi'
    CHA_FACT_ZARAGOZA = 'cha_fact_zaragoza'


class AttilaRegionResources(enum.Enum):
    ATTILA_REGION_NO_RESSOURCE = "NONE"
    ATTILA_REGION_FURS = "furs"
    ATTILA_REGION_IRON = "iron"
    ATTILA_REGION_WINE = "wine"
    ATTILA_REGION_WOOD = "wood"
    ATTILA_REGION_GOLD = "gold"
    ATTILA_REGION_MARBLE = "marble"
    ATTILA_REGION_GEMS = "gems"
    ATTILA_REGION_SILK = "silk"
    ATTILA_REGION_SPICE = "spice"
    ATTILA_REGION_SALT = "salt"
    ATTILA_REGION_LEAD = "lead"
    ATTILA_REGION_OLIVES = "olives"
    ATTILA_REGION_CHURCH_CATHOLIC = "religion_catholic_legendary"
    ATTILA_REGION_CHURCH_ORTHODOX = "religion_orthodox_legendary"


class AttilaCampaign(GameCampaign):
    ATTILA = ("main_attila", "att")
    LAST_ROMAN = ("bel_attila", "bel")
    CHARLEMAGNE = ("cha_attila", "cha")


class AttilaReligion(enum.Enum):
    ANY = "any"
    CHRIST_CATHOLIC = "catholic"
    CHRIST_ARIAN = "arian"
    CHRIST_ORTHODOX = "orthodox"
    CHRIST_EAST = "eastern"
    PAGAN_GERMANIC = "germanic"
    PAGAN_CELTIC = "celtic"
    PAGAN_GRECO_ROMAN = "grecoroman"
    MANICHEIST = "manichaeist"
    ZOROASTRIAN = "zoroastrian"
    JUDAISM = "judaism"
    ISLAM = "islam"
    TENGRISM = "tengris"
    OTHER = "other"
