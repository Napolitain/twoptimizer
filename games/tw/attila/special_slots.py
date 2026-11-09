"""Regional special slots identified by the bundled main-campaign start positions.

The five patriarchal sites have att_city_<name> secondary templates. Zafar's
att_city_zafar template is the Ma'rib Dam site, not a sixth patriarchal see.
This does not establish faction-wide limits for ordinary legendary buildings.
"""

from games.tw.attila.enums import AttilaRegionResources, AttilaReligion

PATRIARCHAL_SLOTS = frozenset(
    {
        "att_city_roma",
        "att_city_alexandria",
        "att_city_antiochia",
        "att_city_aelia_capitolina",
        "att_city_constantinopolis",
    }
)
PATRIARCHAL_RESOURCES = {
    AttilaReligion.CHRIST_CATHOLIC: AttilaRegionResources.ATTILA_REGION_CHURCH_CATHOLIC,
    AttilaReligion.CHRIST_ORTHODOX: AttilaRegionResources.ATTILA_REGION_CHURCH_ORTHODOX,
    AttilaReligion.CHRIST_ARIAN: AttilaRegionResources.ATTILA_REGION_CHURCH_ARIAN,
}


def church_resource(slot, religion):
    if slot not in PATRIARCHAL_SLOTS:
        return AttilaRegionResources.ATTILA_REGION_NO_RESSOURCE
    return PATRIARCHAL_RESOURCES.get(religion, AttilaRegionResources.ATTILA_REGION_CHURCH_ORTHODOX)


def special_allowed(region, building):
    if building.name.endswith("att_bld_eos_marib_dam"):
        return region.name == "att_reg_arabia_felix_zafar"
    for resource in PATRIARCHAL_RESOURCES.values():
        if resource.value in building.name:
            return region.has_ressource in PATRIARCHAL_RESOURCES.values()
    return True
