#pragma once

#include "tw/province.h"
#include "solver/solver.h"
#include <memory>
#include <vector>

namespace twoptimizer::tw {

enum class ProblemState {
    INIT,
    PROVINCES_ADDED,
    BUILDINGS_ADDED,
    CONSTRAINTS_ADDED,
    OBJECTIVE_ADDED,
    SOLVED
};

class Problem {
public:
    Problem();
    ~Problem() = default;
    
    void addProvince(std::shared_ptr<Province> province);
    void addProvinces(const std::vector<std::shared_ptr<Province>>& provinces);
    void addBuildings();
    void addObjective();
    void solve(bool verbose = false);
    
    std::vector<std::shared_ptr<Building>> getBuildings() const;
    ProblemState getState() const { return state_; }
    
    size_t numVariables() const;
    size_t numConstraints() const;
    
    double getObjectiveValue() const;

private:
    std::unique_ptr<Solver> solver_;
    std::vector<std::shared_ptr<Province>> provinces_;
    ProblemState state_;
};

} // namespace twoptimizer::tw
