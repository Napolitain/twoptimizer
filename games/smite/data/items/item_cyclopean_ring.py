"""
Item Type:	Offensive, Utility
Item Tier:	Tier 3
Cost:	1200
Total Cost:	2600
Stats:	+60 Magical Power
+25% Attack Speed
+10% Cooldown Reduction
Passive Effect:	PASSIVE - Your next basic attack against an enemy god deals bonus Magical Damage equal to 9% of the target's maximum Health. This effect can only occur once every 8s, reduced by 2s for each successful Basic Attack on an enemy god.
"""
from games.smite.enums import Damage
from games.smite.item import Item
from games.smite.spells import Stats

cyclopean_ring = Item(
    name='Cyclopean Ring',
    cost=2600,
    stats=Stats(
        power_magical=60,
        basic_attack_speed=25,
        cdr=10,
        target_max_hp_magical_damage=9
    )
)

item = cyclopean_ring


def calculate_bonus_damage(max_health: float, attack_speed: float, time: float) -> Damage:
    bonus_damage = max_health * 0.09
    ttz = calculate_time_to_zero_cooldown(attack_speed)
    number_of_proc = time // ttz
    bonus_damage = bonus_damage * number_of_proc
    damage = Damage(ability_magical=bonus_damage)
    return damage


def calculate_time_to_zero_cooldown(attack_speed: float):
    """
    Calculate the time required for the cooldown to reach 0.
    Each successful attack reduces the cooldown by 2 seconds.
    :param attack_speed: Attack speed (attacks per second)
    :return: Time in seconds to reach 0 cooldown
    """
    initial_cooldown = 8
    cooldown_reduction_per_attack = 2
    attacks_needed = initial_cooldown / cooldown_reduction_per_attack

    # Calculate the time taken for the required number of attacks
    time_for_attacks = attacks_needed / attack_speed

    # Check if the number of attacks is an integer or needs to be rounded up
    if attacks_needed % 1 != 0:
        time_for_attacks = (int(attacks_needed) + 1) / attack_speed

    return time_for_attacks


if __name__ == '__main__':
    attack_speed = 2.5
    time = 10
    max_health = 3000
    bonus_damage = calculate_bonus_damage(max_health, attack_speed, time)
    print(f"Bonus damage: {bonus_damage}")
