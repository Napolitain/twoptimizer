#pragma once

#include "solver/solver.h"
#include "ortools/linear_solver/linear_solver.h"
#include <memory>

namespace twoptimizer {

class SolverOrTools : public Solver {
public:
    SolverOrTools();
    ~SolverOrTools() override = default;
    
    void* createVariable(const std::string& name, const std::string& category) override;
    void addConstraint(const std::string& name) override;
    void setObjective(bool maximize = true) override;
    bool solve() override;
    double getVariableValue(void* variable) override;
    double getObjectiveValue() override;
    size_t numVariables() const override;
    size_t numConstraints() const override;
    
    // Get the underlying OR-Tools solver
    operations_research::MPSolver* getSolver() { return solver_.get(); }

private:
    std::unique_ptr<operations_research::MPSolver> solver_;
};

} // namespace twoptimizer
