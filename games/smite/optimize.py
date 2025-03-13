from __future__ import annotations

from typing import List, Callable, Optional

from ortools.linear_solver import pywraplp

from games.smite.god import God
from games.smite.item import Item, Build, RatatoskrAcorn, Starter

items = []


def optimize_build(
        source: God,
        target: God,
        items: List[Item],
        time_to_kill: Callable[[God, God], float]
) -> Optional[Build]:
    solver = pywraplp.Solver.CreateSolver('CBC')
    if not solver:
        raise Exception("Solver not available")

    # === Binary decision variables for item inclusion ===
    item_vars = [solver.BoolVar(f'item_{i}') for i in range(len(items))]

    # === Filters ===
    # If not ratatoskr, all acorns are removed
    if source.name != 'Ratatoskr':
        for i, item in reversed(list(enumerate(items))):
            if isinstance(item, RatatoskrAcorn):
                items.pop(i)

    # === Variables limits ===
    power_physical = solver.NumVar(0, solver.infinity(), 'power_physical')
    basic_attack_sec = solver.NumVar(0, solver.infinity(), 'basic_attack_sec')
    basic_attack_damage_clamped = solver.NumVar(
        0, source.limits.basic_attack_damage_limit, 'basic_attack_damage_clamped'
    )

    # Constrain basic attack damage to respect the limit
    solver.Add(basic_attack_damage_clamped <= source.basic_attack_damage + source.basic_attack_scaling * power_physical)
    solver.Add(basic_attack_damage_clamped <= source.limits.basic_attack_damage_limit)

    # === Constraints ===
    # 1. Exactly 6 items must be selected
    solver.Add(sum(item_vars) == 6)

    # 2. At most one Starter item
    solver.Add(sum(item_vars[i] for i, item in enumerate(items) if isinstance(item, Starter)) <= 1)

    # 3. At most one Ratatoskr Acorn if Ratatoskr
    if source.name == 'Ratatoskr':
        solver.Add(sum(item_vars[i] for i, item in enumerate(items) if isinstance(item, RatatoskrAcorn)) <= 1)

    # 4. Adjust stats based on selected items
    solver.Add(
        power_physical == sum(
            item_vars[i] * (item.stats.power_physical if item.stats else 0) for i, item in enumerate(items)
        )
    )
    solver.Add(
        basic_attack_sec == sum(
            item_vars[i] * (item.stats.basic_attack_sec if item.stats else 0) for i, item in enumerate(items)
        )
    )

    # === Objective: Minimize time to kill ===
    # TTK = target.health / (DPS)
    solver.Minimize(target.health / (basic_attack_damage_clamped * basic_attack_sec))

    # === Solve ===
    status = solver.Solve()

    if status == pywraplp.Solver.OPTIMAL:
        selected_items = [
            items[i] for i in range(len(items)) if item_vars[i].solution_value() == 1
        ]
        print("✅ Optimal solution found:")
        for item in selected_items:
            print(f"- {item.name}")

        # Compute final TTK using the callback
        final_power_physical = sum(
            item.stats.power_physical for item in selected_items if item.stats
        )
        final_attack_sec = sum(
            item.stats.basic_attack_sec for item in selected_items if item.stats
        )
        ttk = time_to_kill(source, target)

        print(f"Final DPS: {basic_attack_damage_clamped.solution_value() * basic_attack_sec.solution_value()}")
        print(f"Time to Kill: {ttk:.2f} sec")

        return Build(items=selected_items)
    else:
        print("❌ No optimal solution found.")
        return None
