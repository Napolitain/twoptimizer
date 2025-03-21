import enum

from engine.models.model import GameCampaign, GameFactions


class Rome2Factions(GameFactions):
    THREE_C_ALANI = "3c_alani"
    THREE_C_ARMENIA = "3c_armenia"
    THREE_C_CALEDONI = "3c_caledoni"
    THREE_C_GALLICEMP = "3c_gallicemp"
    THREE_C_GOTHI = "3c_gothi"
    THREE_C_MARCOMANNI = "3c_marcomanni"
    THREE_C_PALMYRA = "3c_palmyra"
    THREE_C_ROME = "3c_rome"
    THREE_C_SASSANID = "3c_sassanid"
    THREE_C_SAXONI = "3c_saxoni"
    EMP_ANTONY = "emp_antony"
    EMP_ARMENIA = "emp_armenia"
    EMP_DACIA = "emp_dacia"
    EMP_EGYPT = "emp_egypt"
    EMP_ICENI = "emp_iceni"
    EMP_LEPIDUS = "emp_lepidus"
    EMP_MARCOMANNI = "emp_marcomanni"
    EMP_OCTAVIAN = "emp_octavian"
    EMP_PARTHIA = "emp_parthia"
    EMP_POMPEY = "emp_pompey"
    GAUL_ARVERNI = "gaul_arverni"
    GAUL_NERVII = "gaul_nervii"
    GAUL_ROME = "gaul_rome"
    GAUL_SUEBI = "gaul_suebi"
    INV_INSUBRES = "inv_insubres"
    INV_IOLEI = "inv_iolei"
    INV_ROME = "inv_rome"
    INV_SAMNITES = "inv_samnites"
    INV_SENONES = "inv_senones"
    INV_SYRACUSE = "inv_syracuse"
    INV_TARANTO = "inv_taranto"
    INV_TARCHUNA = "inv_tarchuna"
    INV_VENETI = "inv_veneti"
    PEL_ATHENAI = "pel_athenai"
    PEL_BOIOTIA = "pel_boiotia"
    PEL_KORINTHOS = "pel_korinthos"
    PEL_SPARTA = "pel_sparta"
    PUN_AREVACI = "pun_arevaci"
    PUN_CARTHAGE = "pun_carthage"
    PUN_LUSITANI = "pun_lusitani"
    PUN_ROME = "pun_rome"
    PUN_SYRACUSE = "pun_syracuse"
    ROM_ARDIAEI = "rom_ardiaei"
    ROM_AREVACI = "rom_arevaci"
    ROM_ARMENIA = "rom_armenia"
    ROM_ARVERNI = "rom_arverni"
    ROM_ATHENS = "rom_athens"
    ROM_BAKTRIA = "rom_baktria"
    ROM_BOII = "rom_boii"
    ROM_CARTHAGE = "rom_carthage"
    ROM_CIMMERIA = "rom_cimmeria"
    ROM_COLCHIS = "rom_colchis"
    ROM_EPIRUS = "rom_epirus"
    ROM_GALATIA = "rom_galatia"
    ROM_GETAE = "rom_getae"
    ROM_ICENI = "rom_iceni"
    ROM_KUSH = "rom_kush"
    ROM_LUSITANI = "rom_lusitani"
    ROM_MACEDON = "rom_macedon"
    ROM_MASAESYLI = "rom_masaesyli"
    ROM_MASSAGETAE = "rom_massagetae"
    ROM_MASSILIA = "rom_massilia"
    ROM_NABATEA = "rom_nabatea"
    ROM_NERVII = "rom_nervii"
    ROM_ODRYSSIA = "rom_odryssia"
    ROM_PARTHIA = "rom_parthia"
    ROM_PERGAMON = "rom_pergamon"
    ROM_PONTUS = "rom_pontus"
    ROM_PTOLEMAICS = "rom_ptolemaics"
    ROM_ROME = "rom_rome"
    ROM_ROXOLANI = "rom_roxolani"
    ROM_SABA = "rom_saba"
    ROM_SCYTHIA = "rom_scythia"
    ROM_SELEUCID = "rom_seleucid"
    ROM_SPARTA = "rom_sparta"
    ROM_SUEBI = "rom_suebi"
    ROM_SYRACUSE = "rom_syracuse"
    ROM_TYLIS = "rom_tylis"


class Rome2RegionResources(enum.Enum):
    RES_ROM_NONE = "res_rom_none"
    RES_ROM_AMBER = "res_rom_amber"
    RES_ROM_GLASS = "res_rom_glass"
    RES_ROM_HORSES = "res_rom_horses"
    RES_ROM_IRON = "res_rom_iron"
    RES_ROM_LEAD = "res_rom_lead"
    RES_ROM_LEATHER = "res_rom_leather"
    RES_ROM_MARBLE = "res_rom_marble"
    RES_ROM_OIL = "res_rom_oil"
    RES_ROM_SALT = "res_rom_salt"
    RES_ROM_SPICES = "res_rom_spices"
    RES_ROM_TEXTILES = "res_rom_textiles"
    RES_ROM_TIMBER = "res_rom_timber"
    RES_ROM_WINE = "res_rom_wine"


class Rome2Campaign(GameCampaign):
    ROME = ("main_rome", "rom")
    HANNIBAL = ("main_punic", "pun")
    EMPIRE_DIVIDED = ("main_3c", "emp")
    IMPERATOR_AUGUSTUS = ("main_emperor", "emp")  # same campaign map as 3c
    RISE_OF_THE_REPUBLIC = ("main_invasion", "inv")
    GAULS = ("main_gaul", "gaul")
    SPARTA = ("main_greek", "pel")
