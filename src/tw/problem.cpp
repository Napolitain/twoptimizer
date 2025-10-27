#include "tw/problem.h"
#include "solver/solver_ortools.h"
#include <stdexcept>

namespace twoptimizer::tw {

Problem::Problem() {
    solver_ = std::make_unique<SolverOrTools>();
    state_ = ProblemState::INIT;
}

void Problem::addProvince(std::shared_ptr<Province> province) {
    provinces_.push_back(province);
    state_ = ProblemState::PROVINCES_ADDED;
}

void Problem::addProvinces(const std::vector<std::shared_ptr<Province>>& provinces) {
    for (const auto& province : provinces) {
        addProvince(province);
    }
}

void Problem::addBuildings() {
    if (state_ != ProblemState::PROVINCES_ADDED) {
        throw std::runtime_error("Provinces must be added first.");
    }
    // Buildings are already added to regions
    state_ = ProblemState::BUILDINGS_ADDED;
}

void Problem::addObjective() {
    if (state_ != ProblemState::CONSTRAINTS_ADDED && state_ != ProblemState::BUILDINGS_ADDED) {
        throw std::runtime_error("Constraints must be added first.");
    }
    
    // Set objective to maximize GDP
    solver_->setObjective(true);
    
    state_ = ProblemState::OBJECTIVE_ADDED;
}

void Problem::solve(bool verbose) {
    if (state_ != ProblemState::OBJECTIVE_ADDED) {
        throw std::runtime_error("Objective must be added first.");
    }
    
    bool success = solver_->solve();
    if (!success && verbose) {
        throw std::runtime_error("Failed to solve the problem.");
    }
    
    state_ = ProblemState::SOLVED;
}

std::vector<std::shared_ptr<Building>> Problem::getBuildings() const {
    std::vector<std::shared_ptr<Building>> buildings;
    for (const auto& province : provinces_) {
        for (const auto& region : province->getRegions()) {
            for (const auto& building : region->getBuildings()) {
                buildings.push_back(building);
            }
        }
    }
    return buildings;
}

size_t Problem::numVariables() const {
    return solver_->numVariables();
}

size_t Problem::numConstraints() const {
    return solver_->numConstraints();
}

double Problem::getObjectiveValue() const {
    if (state_ != ProblemState::SOLVED) {
        throw std::runtime_error("Problem must be solved first.");
    }
    return solver_->getObjectiveValue();
}

} // namespace twoptimizer::tw
