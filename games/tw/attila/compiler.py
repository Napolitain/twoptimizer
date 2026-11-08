"""Compile economic polynomials into one model's variables and constraints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from games.tw.attila.algebra import add

if TYPE_CHECKING:
    from games.tw.attila.economy import Economy


class PolynomialCompiler:
    def __init__(self, economy: Economy):
        self.economy = economy

    def variable(self, name, solver):
        if name not in self.economy.logic:
            return self.economy.by_id[name].lp_variable
        if name not in self.economy._logic_variables:
            indicator = self.economy.logic[name]
            terms, lower, upper, step = (
                indicator.expression,
                indicator.lower,
                indicator.upper,
                indicator.step,
            )
            variable = solver.create_auxiliary(name)
            self.economy._logic_variables[name] = variable
            expression = self.compile(terms, solver)
            solver.create_constraint(
                name + "_lower",
                [*expression, float(lower) * variable],
                constraint_fn=lambda x: x >= float(lower),
            )
            solver.create_constraint(
                name + "_upper",
                [*expression, -float(upper + step) * variable],
                constraint_fn=lambda x: x <= -float(step),
            )
        return self.economy._logic_variables[name]

    def compile(self, terms, solver):
        result = []
        for monomial, coefficient in terms.items():
            if not monomial:
                result.append(float(coefficient))
                continue
            key = (monomial[0],)
            variable = self.variable(key[0], solver)
            for name in monomial[1:]:
                key = tuple(sorted((*key, name)))
                if key not in self.economy.products:
                    self.economy.products[key] = solver.create_product(
                        variable,
                        self.variable(name, solver),
                        f"__and_{len(self.economy.products)}",
                    )
                variable = self.economy.products[key]
            result.append(float(coefficient) * variable)
        return result

    def install_constraints(self, solver):
        for province in self.economy.provinces:
            food = {}
            for region in province.regions:
                food = add(food, self.economy.food(region))
                solver.create_constraint(
                    f"{region.name}_Scoped_Sanitation",
                    self.compile(self.economy.sanitation(region), solver),
                    constraint_fn=lambda total, r=region: (
                        total >= self.economy.scenario.for_region(r).minimum_sanitation
                    ),
                )
            solver.create_constraint(
                f"{province.name}_Scoped_Food",
                self.compile(
                    add(food, {(): self.economy.scenario.for_province(province).food}), solver
                ),
                constraint_fn=lambda total, p=province: (
                    total >= self.economy.scenario.for_province(p).minimum_food
                ),
            )
            solver.create_constraint(
                f"{province.name}_Scoped_Order",
                self.compile(self.economy.public_order(province), solver),
                constraint_fn=lambda total, p=province: (
                    total >= self.economy.scenario.for_province(p).minimum_public_order
                ),
            )

        for i, target in enumerate(self.economy.scenario.targets):
            terms = self.economy.metric(target.metric, target.scope, target.recipient)
            solver.create_constraint(
                f"Scenario_Target_{i}",
                self.compile(terms, solver),
                constraint_fn=lambda x, t=target: x >= t.value,
            )
        if self.economy.scenario.project_budget is not None:
            solver.create_constraint(
                "Project_Budget",
                self.compile(self.economy.project_cost(), solver),
                constraint_fn=lambda x: x <= self.economy.scenario.project_budget,
            )
