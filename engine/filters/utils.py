from engine.enums import EntryType


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
