#include "smite/god_builder.h"
#include "ortools/linear_solver/linear_solver.h"
#include <algorithm>

namespace twoptimizer::smite {

GodBuilder::GodBuilder(const God& god, const std::vector<std::shared_ptr<Item>>& availableItems)
    : god_(god), available_items_(availableItems) {
}

double GodBuilder::calculateDps(const std::vector<std::shared_ptr<Item>>& items) const {
    // Calculate total stats with items
    double total_power = (god_.getPowerType() == PowerType::PHYSICAL) 
        ? god_.getStats().power_physical 
        : god_.getStats().power_magical;
    double total_attack_speed = god_.getStats().basic_attack_speed;
    
    for (const auto& item : items) {
        if (item) {
            if (god_.getPowerType() == PowerType::PHYSICAL) {
                total_power += item->getStats().power_physical;
            } else {
                total_power += item->getStats().power_magical;
            }
            total_attack_speed += item->getStats().basic_attack_speed;
        }
    }
    
    return total_power * (1.0 + total_attack_speed / 100.0);
}

std::optional<std::pair<Build, double>> GodBuilder::optimizeBuild() {
    if (available_items_.size() < 6) {
        return std::nullopt;
    }
    
    // Create OR-Tools solver
    auto solver = std::make_unique<operations_research::MPSolver>(
        "god_builder",
        operations_research::MPSolver::SCIP_MIXED_INTEGER_PROGRAMMING
    );
    
    // Create binary variables for each item
    std::vector<operations_research::MPVariable*> item_vars;
    for (size_t i = 0; i < available_items_.size(); ++i) {
        item_vars.push_back(solver->MakeBoolVar("item_" + std::to_string(i)));
    }
    
    // Constraint: exactly 6 items
    auto* constraint = solver->MakeRowConstraint(6.0, 6.0, "exactly_6_items");
    for (auto* var : item_vars) {
        constraint->SetCoefficient(var, 1.0);
    }
    
    // Constraint: at most 1 starter item
    auto* starter_constraint = solver->MakeRowConstraint(0.0, 1.0, "at_most_1_starter");
    for (size_t i = 0; i < available_items_.size(); ++i) {
        if (available_items_[i]->isStarter()) {
            starter_constraint->SetCoefficient(item_vars[i], 1.0);
        }
    }
    
    // Objective: maximize DPS (approximate with linear combination of stats)
    auto* objective = solver->MutableObjective();
    objective->SetMaximization();
    
    for (size_t i = 0; i < available_items_.size(); ++i) {
        const auto& stats = available_items_[i]->getStats();
        double power = (god_.getPowerType() == PowerType::PHYSICAL) 
            ? stats.power_physical 
            : stats.power_magical;
        
        // Simplified objective: power + attack_speed factor
        double coefficient = power + stats.basic_attack_speed * 0.5;
        objective->SetCoefficient(item_vars[i], coefficient);
    }
    
    // Solve
    auto result = solver->Solve();
    if (result != operations_research::MPSolver::OPTIMAL) {
        return std::nullopt;
    }
    
    // Extract solution
    std::vector<std::shared_ptr<Item>> selected_items;
    for (size_t i = 0; i < available_items_.size(); ++i) {
        if (item_vars[i]->solution_value() > 0.5) {
            selected_items.push_back(available_items_[i]);
        }
    }
    
    // Ensure we have exactly 6 items
    if (selected_items.size() != 6) {
        return std::nullopt;
    }
    
    // Create build
    Build build;
    build.item1 = selected_items.size() > 0 ? selected_items[0] : nullptr;
    build.item2 = selected_items.size() > 1 ? selected_items[1] : nullptr;
    build.item3 = selected_items.size() > 2 ? selected_items[2] : nullptr;
    build.item4 = selected_items.size() > 3 ? selected_items[3] : nullptr;
    build.item5 = selected_items.size() > 4 ? selected_items[4] : nullptr;
    build.item6 = selected_items.size() > 5 ? selected_items[5] : nullptr;
    
    double dps = calculateDps(selected_items);
    
    return std::make_pair(build, dps);
}

} // namespace twoptimizer::smite
