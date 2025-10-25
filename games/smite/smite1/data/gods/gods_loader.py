"""
Gods data loader for Smite 1.
Reads god statistics from CSV and creates God instances dynamically.
"""

import csv
from pathlib import Path
from typing import Dict

from games.smite.smite1.enums import PowerType
from games.smite.smite1.god import God
from games.smite.smite1.spells import Buff, Spell, Spells, Stats


# Shared placeholder spells (to avoid creating duplicate objects for each god)
_PLACEHOLDER_PASSIVE = Buff("Passive")
_PLACEHOLDER_SPELL1 = Spell("Ability 1", damage=0, scaling=0, cooldown=0, mana_cost=0, range=0)
_PLACEHOLDER_SPELL2 = Spell("Ability 2", damage=0, scaling=0, cooldown=0, mana_cost=0, range=0)
_PLACEHOLDER_SPELL3 = Spell("Ability 3", damage=0, scaling=0, cooldown=0, mana_cost=0, range=0)
_PLACEHOLDER_SPELL4 = Spell("Ultimate", damage=0, scaling=0, cooldown=0, mana_cost=0, range=0)
_PLACEHOLDER_SPELLS = Spells(_PLACEHOLDER_PASSIVE, _PLACEHOLDER_SPELL1, _PLACEHOLDER_SPELL2,
                            _PLACEHOLDER_SPELL3, _PLACEHOLDER_SPELL4)


def load_gods_from_csv() -> Dict[str, God]:
    """
    Load all gods from the CSV file and return a dictionary of god instances.
    
    Returns:
        Dictionary mapping sanitized god names to God instances
    """
    gods = {}
    csv_path = Path(__file__).parent / "gods_data.csv"
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Parse the data from CSV
            name = row['name']
            hp = float(row['health'])
            mana = float(row['mana'])
            basic_attack_damage = float(row['basic_attack_damage'])
            basic_attack_speed = float(row['attack_speed'])
            prot_physical = float(row['physical_protection'])
            hp5 = float(row['hp5'])
            mp5 = float(row['mp5'])
            power_type = PowerType[row['power_type']]
            
            # Create God instance
            god = God(
                name=name,
                stats=Stats(
                    hp=hp,
                    mana=mana,
                    basic_attack_damage=basic_attack_damage,
                    basic_attack_speed=basic_attack_speed,
                    prot_physical=prot_physical,
                    prot_magical=30,  # Base magical protection for all gods
                    hp5=hp5,
                    mp5=mp5,
                    movement_speed=365  # Base movement speed for all gods
                ),
                power_type=power_type,
                spells=_PLACEHOLDER_SPELLS,
                build=None
            )
            
            # Sanitize name for variable access
            var_name = name.lower().replace(" ", "_").replace("'", "")
            gods[var_name] = god
    
    return gods


# Load all gods on module import
_ALL_GODS = load_gods_from_csv()

# Create module-level variables for each god
globals().update(_ALL_GODS)

# Export all god names
__all__ = list(_ALL_GODS.keys())
