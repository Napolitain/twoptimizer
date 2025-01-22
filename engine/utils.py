from engine.enums import EntryType
from engine.games import Games
from engine.models.model_attila import AttilaFactions


def get_entry_name(name: str, entry_type: EntryType) -> str:
    """
    Get the building name from the full name.
    x_y_bld_z -> bld_z
    :param name: full name
    :param entry_type: type of the entry (building, region, province)
    :raise ValueError: if the entry type is not found in the name (e.g. bld, reg, prov not found in name)
    :return: name of the entry
    """
    split_name = name.split("_")
    i = 0
    while i < len(split_name) and split_name[i] != entry_type.value:
        i += 1
    if i == len(split_name):
        raise ValueError(f"Entry type {entry_type.value} not found in {name}.")
    # Return everything after the entry type unless it matches any other entry type (e.g. reg, prov)
    j = i + 1
    # Matches bld, reg, if we search prov, etc...
    entries = [entry.value for entry in EntryType if entry != entry_type]
    while j < len(split_name) and split_name[j] not in entries:
        j += 1
    if j == len(split_name):
        return "_".join(split_name[i:])
    return "_".join(split_name[i:j])


def building_is_major(building_name: str) -> bool:
    """
    Check if a building is major (city or town).
    :param building_name:
    :return:
    """
    if "major" in building_name or "civic" in building_name or "military_upgrade" in building_name or "aqueducts" in building_name or "sewers" in building_name:
        return True
    return False


def building_is_minor(building_name: str) -> bool:
    """
    Check if a building is minor (village).
    :param building_name:
    :return:
    """
    if "minor" in building_name or "agriculture" in building_name or "livestock" in building_name:
        return True
    return False


def building_is_not_of_faction(building_name: str) -> bool:
    """
    Check if a building is of the faction currently assigned in Games.
    :param building_name:
    :return:
    """
    split_name = building_name.split("_")
    if Games.instance.faction == AttilaFactions.ATTILA_ROMAN_EAST:
        if (
                "roman" in building_name and "west" not in building_name) or ("orthodox" in building_name) or (
                "all" in split_name and "camel" not in building_name and "pigs" not in building_name):
            return False
    if Games.instance.faction == AttilaFactions.ATTILA_ROMAN_WEST:
        if (
                "roman" in building_name and "east" not in building_name) or ("catholic" in building_name) or (
                "all" in split_name and "camel" not in building_name and "pigs" not in building_name):
            return False
    if Games.instance.faction == AttilaFactions.ATTILA_FRANKS:
        if "barbarian" in building_name or (
                "catholic" in building_name) or (
                "all" in split_name and "camel" not in building_name and "pigs" not in building_name):
            return False
    if Games.instance.faction == AttilaFactions.ATTILA_SASSANIDS:
        if "eastern" in building_name or (
                "zoro" in building_name) or (
                "all" in split_name and "cows" not in building_name and "pigs" not in building_name):
            return False
    return True


def building_is_resource(building):
    """
    Check if a building is a resource building.
    If the building contains resource but not port, it is a resource building.
    If the building contains spice, it is a resource building.
    :param building:
    :return:
    """
    return ("resource" in building.name and "port" not in building.name) or "spice" in building.name
