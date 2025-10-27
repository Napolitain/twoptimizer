#pragma once

#include "smite/item.h"
#include <string>

namespace twoptimizer::smite {

class God {
public:
    God(const std::string& name, PowerType powerType, const Stats& baseStats);
    ~God() = default;
    
    const std::string& getName() const { return name_; }
    PowerType getPowerType() const { return power_type_; }
    const Stats& getStats() const { return stats_; }
    
    double getDpsBasicAttack() const;
    double getDpsBasicAttack(const Build& build) const;
    
    void setBuild(const Build& build) { build_ = build; }
    const Build& getBuild() const { return build_; }

private:
    std::string name_;
    PowerType power_type_;
    Stats stats_;
    Build build_;
};

} // namespace twoptimizer::smite
