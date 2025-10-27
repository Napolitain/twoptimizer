#pragma once

#include "smite/god.h"
#include "smite/item.h"
#include <vector>
#include <memory>
#include <optional>

namespace twoptimizer::smite {

class GodBuilder {
public:
    GodBuilder(const God& god, const std::vector<std::shared_ptr<Item>>& availableItems);
    ~GodBuilder() = default;
    
    // Calculate DPS for a given set of items
    double calculateDps(const std::vector<std::shared_ptr<Item>>& items) const;
    
    // Optimize build for maximum DPS
    std::optional<std::pair<Build, double>> optimizeBuild();

private:
    God god_;
    std::vector<std::shared_ptr<Item>> available_items_;
};

} // namespace twoptimizer::smite
