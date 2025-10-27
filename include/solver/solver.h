#pragma once

#include <memory>
#include <string>
#include <vector>
#include <unordered_map>

namespace twoptimizer {

class Solver {
public:
    virtual ~Solver() = default;
    
    // Create a decision variable
    virtual void* createVariable(const std::string& name, const std::string& category) = 0;
    
    // Add a constraint
    virtual void addConstraint(const std::string& name) = 0;
    
    // Set objective function
    virtual void setObjective(bool maximize = true) = 0;
    
    // Solve the problem
    virtual bool solve() = 0;
    
    // Get variable value after solving
    virtual double getVariableValue(void* variable) = 0;
    
    // Get objective value
    virtual double getObjectiveValue() = 0;
    
    // Get number of variables
    virtual size_t numVariables() const = 0;
    
    // Get number of constraints
    virtual size_t numConstraints() const = 0;
};

} // namespace twoptimizer
