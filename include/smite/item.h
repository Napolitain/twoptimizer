#pragma once

#include <string>
#include <memory>

namespace twoptimizer::smite {

enum class PowerType {
    PHYSICAL,
    MAGICAL
};

struct Stats {
    double power_physical = 0.0;
    double power_magical = 0.0;
    double basic_attack_speed = 0.0;
    double health = 0.0;
    double mana = 0.0;
    double physical_protection = 0.0;
    double magical_protection = 0.0;
};

class Item {
public:
    Item(const std::string& name, const Stats& stats, bool isStarter = false);
    ~Item() = default;
    
    const std::string& getName() const { return name_; }
    const Stats& getStats() const { return stats_; }
    bool isStarter() const { return is_starter_; }

private:
    std::string name_;
    Stats stats_;
    bool is_starter_;
};

struct Build {
    std::shared_ptr<Item> item1;
    std::shared_ptr<Item> item2;
    std::shared_ptr<Item> item3;
    std::shared_ptr<Item> item4;
    std::shared_ptr<Item> item5;
    std::shared_ptr<Item> item6;
    
    int countItems() const;
};

} // namespace twoptimizer::smite
