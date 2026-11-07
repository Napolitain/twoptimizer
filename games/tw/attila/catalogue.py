"""Culture-specific technology availability from imported building metadata."""

CULTURE_SLUGS = {
    "att_sub_cult_barbarian_celtic": "celtic",
    "att_sub_cult_barbarian_germanic_east": "eastern-germanic",
    "att_sub_cult_barbarian_germanic_north": "northern-germanic",
    "att_sub_cult_barbarian_germanic_west": "western-germanic",
    "att_sub_cult_eastern_caucasian": "caucasian",
    "att_sub_cult_eastern_desert": "desert",
    "att_sub_cult_eastern_sassanid": "sassanid",
    "att_sub_cult_nomadic_hunnic": "hunnic",
    "att_sub_cult_nomadic_sarmatian": "sarmatian",
    "att_sub_cult_roman_east": "eastern-roman",
    "att_sub_cult_roman_west": "western-roman",
}


def technology_available(building, culture, researched):
    if researched is None:
        return True  # Explicit end-state scenario: all technologies available.
    if building.metadata is None or culture not in building.metadata["requirements_by_culture"]:
        raise ValueError(f"Missing technology metadata for {building.name} in {culture}")
    return all(
        set(alternatives) & researched
        for alternatives in building.metadata["requirements_by_culture"][culture]
    )
