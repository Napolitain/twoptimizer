"""Independent small source catalogs for exhaustive economic comparisons."""


def effect(key, value, scope="this_building"):
    return {"id": key, "value": value, "scope": scope}


def tiny_catalog():
    def building(key, category, title, effects):
        return {
            "id": key,
            "name": key,
            "level": 4,
            "facts": [],
            "effects": effects,
            "occurrences": [
                {
                    "culture": "rom_Roman",
                    "category": category,
                    "chain_title": title,
                    "factions": ["rom_rome"],
                }
            ],
        }

    records = [
        building(
            "rome_city_4",
            "Provincial Capital",
            "Province Capital",
            [
                effect("rom_building_gdp_industry_manufacture", 100),
                effect("rom_building_gdp_mod_all", 10, "regions_in_this_province"),
            ],
        ),
        building(
            "rome_town_4",
            "Minor Settlement",
            "Minor Settlement",
            [effect("rom_building_gdp_industry_manufacture", 50)],
        ),
        building(
            "rome_religious_alpha_4",
            "Religious",
            "Religious",
            [
                effect("rom_building_gdp_mod_industry", 20, "regions_in_this_province"),
                effect("rom_building_public_order_happiness", 2, "this_province"),
                effect("rom_building_food_consumption", 1, "this_region"),
            ],
        ),
        building(
            "rome_religious_beta_4",
            "Religious",
            "Religious",
            [
                effect("rom_building_gdp_industry_manufacture", 80),
                effect("rom_building_public_order_attitude_squalor", -2, "this_province"),
                effect("rom_building_food_consumption", 2, "this_region"),
            ],
        ),
    ]
    return {
        "buildings": {b["id"]: b for b in records},
        "technologies": {"rom_rome": {}},
        "factions": {
            "rom_rome": {
                "id": "rom_rome",
                "name": "Rome",
                "traits": {
                    "culture_facts": [],
                    "parties": [
                        {"playable": True, "facts": ["Administrators: +10% tax rate"]},
                        {
                            "playable": True,
                            "facts": ["Industry: +20% wealth from industry"],
                        },
                        {"playable": True, "facts": []},
                    ],
                },
            }
        },
    }
