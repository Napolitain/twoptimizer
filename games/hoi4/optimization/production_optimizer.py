"""
Production optimizer for HOI4.

Uses OR-Tools to optimize factory allocation and production schedules.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from ortools.linear_solver import pywraplp
from ..models.equipment import Equipment, EquipmentCategory
from ..models.production import Production, ProductionLine
from ..models.game_date import GameDate


@dataclass
class ProductionGoal:
    """
    Represents a production goal for optimization.
    
    Attributes:
        equipment: Equipment to produce
        target_amount: Target amount to produce
        target_date: Date by which to produce
        weight: Relative importance (for multi-objective optimization)
        minimum_amount: Minimum acceptable amount
    """
    equipment: Equipment
    target_amount: float
    target_date: GameDate
    weight: float = 1.0
    minimum_amount: float = 0.0
    
    def __post_init__(self):
        """Validate goal attributes."""
        if self.target_amount < 0:
            raise ValueError("Target amount cannot be negative")
        if self.minimum_amount < 0:
            raise ValueError("Minimum amount cannot be negative")
        if self.minimum_amount > self.target_amount:
            raise ValueError("Minimum amount cannot exceed target amount")
        if self.weight < 0:
            raise ValueError("Weight cannot be negative")


@dataclass
class OptimizationResult:
    """
    Result of production optimization.
    
    Attributes:
        status: Solver status (OPTIMAL, FEASIBLE, INFEASIBLE, etc.)
        objective_value: Objective function value
        factory_allocations: Dictionary of equipment_name -> factories_assigned
        expected_output: Dictionary of equipment_name -> total_produced
        resource_usage: Dictionary of resource_name -> total_consumed
        execution_time: Solver execution time in seconds
        is_optimal: Whether solution is optimal
    """
    status: str
    objective_value: float
    factory_allocations: Dict[str, float] = field(default_factory=dict)
    expected_output: Dict[str, float] = field(default_factory=dict)
    resource_usage: Dict[str, float] = field(default_factory=dict)
    execution_time: float = 0.0
    is_optimal: bool = False
    
    def get_allocation(self, equipment_name: str) -> float:
        """Get factory allocation for specific equipment."""
        return self.factory_allocations.get(equipment_name, 0.0)
    
    def get_output(self, equipment_name: str) -> float:
        """Get expected output for specific equipment."""
        return self.expected_output.get(equipment_name, 0.0)
    
    def __str__(self) -> str:
        return (f"OptimizationResult(status={self.status}, "
                f"objective={self.objective_value:.2f}, "
                f"allocations={len(self.factory_allocations)})")


class ProductionOptimizer:
    """
    Optimizes factory allocation to maximize production goals.
    
    Uses linear programming to determine optimal factory allocation
    across different equipment types to achieve production goals.
    """
    
    def __init__(self):
        """Initialize optimizer."""
        self.solver = None
        self.variables = {}
        self.constraints = {}
    
    def optimize_production(
        self,
        available_military_factories: float,
        available_naval_factories: float,
        goals: List[ProductionGoal],
        start_date: GameDate,
        efficiency_modifiers: float = 0.0,
        available_resources: Optional[Dict[str, float]] = None,
        maximize_total_output: bool = False
    ) -> OptimizationResult:
        """
        Optimize factory allocation to meet production goals.
        
        Args:
            available_military_factories: Military factories available
            available_naval_factories: Naval factories available
            goals: List of production goals
            start_date: Production start date
            efficiency_modifiers: Production efficiency bonuses
            available_resources: Available resources (None = unlimited)
            maximize_total_output: If True, maximize total output; else minimize deviation from goals
            
        Returns:
            OptimizationResult with allocations and expected output
        """
        import time
        start_time = time.time()
        
        # Create solver
        self.solver = pywraplp.Solver.CreateSolver('GLOP')
        if not self.solver:
            return OptimizationResult(
                status="SOLVER_NOT_AVAILABLE",
                objective_value=0.0,
                is_optimal=False
            )
        
        self.variables = {}
        self.constraints = {}
        
        # Create variables for factory allocation
        for goal in goals:
            eq_name = goal.equipment.name
            
            # Variable: number of factories assigned to this equipment
            max_factories = (available_naval_factories if goal.equipment.category == EquipmentCategory.NAVAL
                           else available_military_factories)
            
            var = self.solver.NumVar(0, max_factories, f'factories_{eq_name}')
            self.variables[eq_name] = var
        
        # Constraint: Total military factory allocation
        military_goals = [g for g in goals if g.equipment.category != EquipmentCategory.NAVAL]
        if military_goals:
            military_constraint = self.solver.Constraint(0, available_military_factories)
            for goal in military_goals:
                military_constraint.SetCoefficient(self.variables[goal.equipment.name], 1.0)
            self.constraints['military_factories'] = military_constraint
        
        # Constraint: Total naval factory allocation
        naval_goals = [g for g in goals if g.equipment.category == EquipmentCategory.NAVAL]
        if naval_goals:
            naval_constraint = self.solver.Constraint(0, available_naval_factories)
            for goal in naval_goals:
                naval_constraint.SetCoefficient(self.variables[goal.equipment.name], 1.0)
            self.constraints['naval_factories'] = naval_constraint
        
        # Resource constraints (if specified)
        if available_resources:
            resource_constraints = self._add_resource_constraints(
                goals, start_date, efficiency_modifiers, available_resources
            )
            self.constraints.update(resource_constraints)
        
        # Objective function
        objective = self.solver.Objective()
        
        if maximize_total_output:
            # Maximize total production
            for goal in goals:
                eq_name = goal.equipment.name
                days = start_date.days_until(goal.target_date)
                
                # Calculate expected output per factory
                # Simplified: assume average efficiency
                avg_efficiency = 0.5 * (1.0 + efficiency_modifiers)  # Rough average
                
                if goal.equipment.production_cost > 0:
                    output_per_factory = (days * avg_efficiency) / goal.equipment.production_cost
                    coefficient = output_per_factory * goal.weight
                    objective.SetCoefficient(self.variables[eq_name], coefficient)
            
            objective.SetMaximization()
        else:
            # Minimize deviation from goals (weighted least squares)
            # This requires auxiliary variables for deviations
            deviation_vars = {}
            
            for goal in goals:
                eq_name = goal.equipment.name
                days = start_date.days_until(goal.target_date)
                
                # Calculate expected output per factory
                avg_efficiency = 0.5 * (1.0 + efficiency_modifiers)
                
                if goal.equipment.production_cost > 0:
                    output_per_factory = (days * avg_efficiency) / goal.equipment.production_cost
                    
                    # Create deviation variable (how far below target we are)
                    dev_var = self.solver.NumVar(0, goal.target_amount, f'deviation_{eq_name}')
                    deviation_vars[eq_name] = dev_var
                    
                    # Constraint: output + deviation = target
                    # factories * output_per_factory + deviation = target
                    dev_constraint = self.solver.Constraint(goal.target_amount, goal.target_amount)
                    dev_constraint.SetCoefficient(self.variables[eq_name], output_per_factory)
                    dev_constraint.SetCoefficient(dev_var, 1.0)
                    self.constraints[f'deviation_{eq_name}'] = dev_constraint
                    
                    # Penalize deviation in objective (weighted)
                    objective.SetCoefficient(dev_var, goal.weight)
            
            objective.SetMinimization()
        
        # Solve
        status = self.solver.Solve()
        
        # Extract results
        result = self._extract_results(goals, start_date, efficiency_modifiers, status)
        result.execution_time = time.time() - start_time
        
        return result
    
    def _add_resource_constraints(
        self,
        goals: List[ProductionGoal],
        start_date: GameDate,
        efficiency_modifiers: float,
        available_resources: Dict[str, float]
    ) -> Dict[str, pywraplp.Constraint]:
        """
        Add resource availability constraints.
        
        Args:
            goals: Production goals
            start_date: Production start date
            efficiency_modifiers: Efficiency bonuses
            available_resources: Available resource amounts
            
        Returns:
            Dictionary of constraint name -> constraint
        """
        resource_constraints = {}
        
        # Group by resource
        resources_needed = set()
        for goal in goals:
            resources_needed.update(goal.equipment.resource_cost.keys())
        
        for resource in resources_needed:
            if resource not in available_resources:
                continue
            
            constraint = self.solver.Constraint(0, available_resources[resource])
            
            for goal in goals:
                if resource in goal.equipment.resource_cost:
                    eq_name = goal.equipment.name
                    days = start_date.days_until(goal.target_date)
                    
                    # Resource consumption per factory over the period
                    avg_efficiency = 0.5 * (1.0 + efficiency_modifiers)
                    resource_per_unit = goal.equipment.resource_cost[resource]
                    
                    if goal.equipment.production_cost > 0:
                        output_per_factory = (days * avg_efficiency) / goal.equipment.production_cost
                        resource_per_factory = output_per_factory * resource_per_unit
                        
                        constraint.SetCoefficient(self.variables[eq_name], resource_per_factory)
            
            resource_constraints[f'resource_{resource}'] = constraint
        
        return resource_constraints
    
    def _extract_results(
        self,
        goals: List[ProductionGoal],
        start_date: GameDate,
        efficiency_modifiers: float,
        status: int
    ) -> OptimizationResult:
        """
        Extract results from solved model.
        
        Args:
            goals: Production goals
            start_date: Production start date
            efficiency_modifiers: Efficiency bonuses
            status: Solver status
            
        Returns:
            OptimizationResult with allocations and output
        """
        status_names = {
            pywraplp.Solver.OPTIMAL: "OPTIMAL",
            pywraplp.Solver.FEASIBLE: "FEASIBLE",
            pywraplp.Solver.INFEASIBLE: "INFEASIBLE",
            pywraplp.Solver.UNBOUNDED: "UNBOUNDED",
            pywraplp.Solver.ABNORMAL: "ABNORMAL",
            pywraplp.Solver.NOT_SOLVED: "NOT_SOLVED",
        }
        
        status_name = status_names.get(status, "UNKNOWN")
        is_optimal = (status == pywraplp.Solver.OPTIMAL)
        
        factory_allocations = {}
        expected_output = {}
        resource_usage = {}
        
        if status == pywraplp.Solver.OPTIMAL or status == pywraplp.Solver.FEASIBLE:
            # Extract variable values
            for goal in goals:
                eq_name = goal.equipment.name
                factories = self.variables[eq_name].solution_value()
                factory_allocations[eq_name] = factories
                
                # Calculate expected output
                days = start_date.days_until(goal.target_date)
                avg_efficiency = 0.5 * (1.0 + efficiency_modifiers)
                
                if goal.equipment.production_cost > 0:
                    total_output = (factories * days * avg_efficiency) / goal.equipment.production_cost
                    expected_output[eq_name] = total_output
                    
                    # Calculate resource usage
                    for resource, amount_per_unit in goal.equipment.resource_cost.items():
                        resource_usage[resource] = resource_usage.get(resource, 0.0) + (total_output * amount_per_unit)
        
        return OptimizationResult(
            status=status_name,
            objective_value=self.solver.Objective().Value() if status in [pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE] else 0.0,
            factory_allocations=factory_allocations,
            expected_output=expected_output,
            resource_usage=resource_usage,
            is_optimal=is_optimal
        )
    
    def optimize_single_equipment(
        self,
        equipment: Equipment,
        available_factories: float,
        target_date: GameDate,
        start_date: GameDate,
        efficiency_modifiers: float = 0.0
    ) -> float:
        """
        Calculate maximum output for a single equipment type.
        
        Simplified calculation without using the solver.
        
        Args:
            equipment: Equipment to produce
            available_factories: Factories available
            target_date: Target production date
            start_date: Production start date
            efficiency_modifiers: Efficiency bonuses
            
        Returns:
            Maximum equipment that can be produced
        """
        days = start_date.days_until(target_date)
        if days <= 0 or equipment.production_cost == 0:
            return 0.0
        
        # Average efficiency over period
        avg_efficiency = 0.5 * (1.0 + efficiency_modifiers)
        
        # Total output
        total_ic = available_factories * days * avg_efficiency
        return total_ic / equipment.production_cost
