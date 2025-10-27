#include "solver/solver_ortools.h"
#include <stdexcept>

namespace twoptimizer {

SolverOrTools::SolverOrTools() {
    solver_ = std::make_unique<operations_research::MPSolver>(
        "twoptimizer",
        operations_research::MPSolver::SCIP_MIXED_INTEGER_PROGRAMMING
    );
}

void* SolverOrTools::createVariable(const std::string& name, const std::string& category) {
    if (category == "Binary" || category == "binary") {
        return solver_->MakeBoolVar(name);
    } else if (category == "Integer" || category == "integer") {
        return solver_->MakeIntVar(0.0, operations_research::MPSolver::infinity(), name);
    } else {
        return solver_->MakeNumVar(0.0, operations_research::MPSolver::infinity(), name);
    }
}

void SolverOrTools::addConstraint(const std::string& name) {
    // Constraint creation is handled separately in OR-Tools
    // This is a placeholder for the interface
}

void SolverOrTools::setObjective(bool maximize) {
    if (maximize) {
        solver_->MutableObjective()->SetMaximization();
    } else {
        solver_->MutableObjective()->SetMinimization();
    }
}

bool SolverOrTools::solve() {
    auto result = solver_->Solve();
    return result == operations_research::MPSolver::OPTIMAL;
}

double SolverOrTools::getVariableValue(void* variable) {
    auto* var = static_cast<operations_research::MPVariable*>(variable);
    return var->solution_value();
}

double SolverOrTools::getObjectiveValue() {
    return solver_->Objective().Value();
}

size_t SolverOrTools::numVariables() const {
    return solver_->NumVariables();
}

size_t SolverOrTools::numConstraints() const {
    return solver_->NumConstraints();
}

} // namespace twoptimizer
