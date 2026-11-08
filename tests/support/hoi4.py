"""Small source repositories shared by HoI4 ingestion integration tests."""

import subprocess
from pathlib import Path

from games.hoi4.data_pipeline import public_import as public


def write_source(root: Path, relative: str, text: str):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def source_git(root: Path, *args: str):
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def make_public_source(root: Path) -> Path:
    write_source(
        root,
        "history/states/1.txt",
        """\ufeffstate = {
        id = 1 name = "STATE_1" state_category = town manpower = 500
        resources = { steel = 7 }
        history = {
            owner = FRA add_core_of = FRA
            buildings = { industrial_complex = 2 arms_factory = 1 }
            if = { limit = { has_dlc = "Example" } buildings = { industrial_complex = 90 } }
            1939.1.1 = { buildings = { industrial_complex = 50 } }
        }
    }\r\n""",
    )
    write_source(
        root, "history/states/2.txt", "state = { id = 2 history = { owner = GER owner = FRA } }"
    )
    for tag, name in public.COUNTRIES.items():
        write_source(
            root,
            f"history/countries/{tag} - {name}.txt",
            "capital = 1 if = { limit = { has_dlc = x } capital = 2 } "
            'set_oob = "FRA_1936" add_ideas = { civilian_economy } '
            "set_technology = { infantry_weapons = 1 }",
        )
    write_source(
        root,
        "history/units/FRA_1936.txt",
        """division_template = {
        name = "Infantry" regiments = { infantry = { x = 0 y = 0 } infantry = { x = 0 y = 1 } }
        support = { engineer = { x = 0 y = 0 } }
    }
    instant_effect = {
        add_equipment_production = {
            requested_factories = 4 equipment = { type = infantry_equipment_1 }
        }
    }
    """,
    )
    write_source(
        root,
        "history/units/FRA_1936_nsb.txt",
        """division_template = { name = "Preserved" }
instant_effect = {
    add_equipment_production = { requested_factories = 99 }
""",
    )
    write_source(
        root,
        "common/units/equipment/infantry.txt",
        """equipments = {
        infantry_equipment = { is_archetype = yes build_cost_ic = 0.43 resources = { steel = 2 } }
        infantry_equipment_0 = { archetype = infantry_equipment active = yes }
    }""",
    )
    write_source(
        root,
        "common/units/infantry.txt",
        """sub_units = {
        infantry = { manpower = 1000 training_time = 90 need = { infantry_equipment = 100 } }
        ignored = yes
    }""",
    )
    write_source(
        root,
        "common/buildings/buildings.txt",
        """buildings = {
        industrial_complex = { base_cost = 10800 level_cap = { state_max = 20 shares_slots = yes } }
    }""",
    )
    write_source(
        root,
        "common/state_category/town.txt",
        "state_categories = { town = { local_building_slots = 4 } }",
    )
    write_source(
        root,
        "common/defines/00_defines.lua",
        """NDefines = {
NProduction = {
 BASE_FACTORY_SPEED = 4, -- literal
 POWERED_FACTORY_SPEED = 5,
 -- BASE_FACTORY_SPEED = 999,
 BASE_FACTORY_SPEED_MIL = 3 + 0.5,
},
}
""",
    )
    source_git(root, "init", "-q")
    source_git(root, "add", ".")
    source_git(
        root,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-qm",
        "fixture",
    )
    return root
