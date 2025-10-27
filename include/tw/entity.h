#pragma once

#include <string>
#include <unordered_map>

namespace twoptimizer::tw {

enum class Scope {
    FACTION,
    PROVINCE,
    REGION,
    BUILDING
};

class Effect {
public:
    Effect() = default;
    virtual ~Effect() = default;
    
    double gdp() const;
    double publicOrder() const;
    double sanitation() const;
    double food() const;
    
    void setGdp(double value);
    void setPublicOrder(double value);
    void setSanitation(double value);
    void setFood(double value);

protected:
    double gdp_ = 0.0;
    double public_order_ = 0.0;
    double sanitation_ = 0.0;
    double food_ = 0.0;
};

class Entity {
public:
    Entity() = default;
    virtual ~Entity() = default;
    
    const std::string& getName() const { return name_; }
    void setName(const std::string& name) { name_ = name; }

protected:
    std::string name_;
};

} // namespace twoptimizer::tw
