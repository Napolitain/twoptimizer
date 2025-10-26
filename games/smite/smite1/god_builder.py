"""
GodBuilder for Smite 1.
Optimizes god builds for maximum DPS using OR-TOOLS.
"""

from typing import List, Optional, Tuple
from ortools.linear_solver import pywraplp

from games.smite.smite1.god import God
from games.smite.smite1.item import Item, Build, Starter


class GodBuilder:
    """
    Builder class for optimizing god item builds to maximize DPS.
    
    Supports:
    - Exactly 6 items in a build
    - Maximum 1 starter item (included in the 6 total)
    - DPS optimization using OR-TOOLS
    """
    
    def __init__(self, god: God, available_items: List[Item]):
        """
        Initialize the GodBuilder.
        
        Args:
            god: The god to build for
            available_items: List of available items to choose from
        """
        self.god = god
        self.available_items = available_items
    
    def calculate_dps(self, items: List[Item]) -> float:
        """
        Calculate DPS for a given set of items.
        
        Args:
            items: List of items equipped
            
        Returns:
            Damage per second
        """
        # Sum up stats from items
        power_physical = sum(item.stats.power_physical if item.stats else 0 for item in items)
        basic_attack_speed = sum(item.stats.basic_attack_speed if item.stats else 0 for item in items)
        
        # Add base god stats
        total_power = self.god.stats.power_physical + power_physical
        total_attack_speed = self.god.stats.basic_attack_speed + basic_attack_speed / 100
        
        # Calculate basic attack damage
        # Formula: base_damage + (power * scaling)
        basic_attack_damage = self.god.stats.basic_attack_damage + (self.god.basic_attack_scaling / 100) * total_power
        
        # Apply limits
        basic_attack_damage = min(basic_attack_damage, self.god.limits.basic_attack_damage_limit)
        total_attack_speed = min(total_attack_speed, self.god.limits.basic_attack_sec_limit)
        
        # DPS = damage per hit * hits per second
        dps = basic_attack_damage * total_attack_speed
        
        return dps
    
    def optimize_build(self) -> Optional[Tuple[Build, float]]:
        """
        Optimize the build for maximum DPS using OR-TOOLS.
        
        Since DPS = damage * attack_speed is non-linear, we use a weighted sum approach:
        We maximize a linear combination that approximates DPS maximization.
        
        Returns:
            Tuple of (Build, DPS) if successful, None otherwise
        """
        solver = pywraplp.Solver.CreateSolver('SCIP')
        if not solver:
            raise Exception("Solver not available")
        
        # === Binary decision variables for item inclusion ===
        item_vars = [solver.BoolVar(f'item_{i}') for i in range(len(self.available_items))]
        
        # === Variables for stats ===
        power_physical = solver.NumVar(0, solver.infinity(), 'power_physical')
        basic_attack_speed = solver.NumVar(0, solver.infinity(), 'basic_attack_speed')
        
        # === Constraints ===
        
        # 1. Exactly 6 items must be selected
        solver.Add(sum(item_vars) == 6)
        
        # 2. At most one Starter item
        starter_indices = [i for i, item in enumerate(self.available_items) if isinstance(item, Starter)]
        if starter_indices:
            solver.Add(sum(item_vars[i] for i in starter_indices) <= 1)
        
        # 3. Calculate total power from items
        solver.Add(
            power_physical == sum(
                item_vars[i] * (item.stats.power_physical if item.stats else 0) 
                for i, item in enumerate(self.available_items)
            )
        )
        
        # 4. Calculate total attack speed from items
        solver.Add(
            basic_attack_speed == sum(
                item_vars[i] * (item.stats.basic_attack_speed if item.stats else 0) 
                for i, item in enumerate(self.available_items)
            )
        )
        
        # === Objective: Maximize DPS approximation ===
        # Since we can't multiply variables (non-linear), we maximize a weighted sum
        # The weights are chosen to balance attack speed and power
        # DPS = (base_damage + power * scaling) * (base_AS + item_AS)
        # We approximate by maximizing: power * base_AS + item_AS * base_damage + power * item_AS
        # Simplified: maximize power + attack_speed with appropriate weights
        
        base_damage = self.god.stats.basic_attack_damage
        base_as = self.god.stats.basic_attack_speed
        scaling = self.god.basic_attack_scaling / 100
        
        # Weight power by (scaling * base_AS) and attack_speed by base_damage
        # This gives a linear approximation that favors balanced builds
        power_weight = scaling * base_as
        as_weight = base_damage
        
        solver.Maximize(power_weight * power_physical + as_weight * basic_attack_speed)
        
        # === Solve ===
        status = solver.Solve()
        
        if status == pywraplp.Solver.OPTIMAL:
            # Extract selected items
            selected_items = [
                self.available_items[i] for i in range(len(self.available_items)) 
                if item_vars[i].solution_value() > 0.5
            ]
            
            # Ensure we have exactly 6 items
            if len(selected_items) != 6:
                return None
            
            # Calculate actual DPS with selected items
            final_dps = self.calculate_dps(selected_items)
            
            # Create Build (fill positions based on whether they are starters or regular items)
            starter_items = [item for item in selected_items if isinstance(item, Starter)]
            regular_items = [item for item in selected_items if not isinstance(item, Starter)]
            
            # Pad with None if necessary
            while len(regular_items) < 5:
                regular_items.append(None)
            
            build = Build(
                item1=starter_items[0] if starter_items else regular_items.pop(0),
                item2=regular_items[0] if regular_items else None,
                item3=regular_items[1] if len(regular_items) > 1 else None,
                item4=regular_items[2] if len(regular_items) > 2 else None,
                item5=regular_items[3] if len(regular_items) > 3 else None,
                item6=regular_items[4] if len(regular_items) > 4 else None,
            )
            
            return build, final_dps
        
        return None
