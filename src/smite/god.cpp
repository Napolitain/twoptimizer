#include "smite/god.h"

namespace twoptimizer::smite {

God::God(const std::string& name, PowerType powerType, const Stats& baseStats)
    : name_(name), power_type_(powerType), stats_(baseStats) {
}

double God::getDpsBasicAttack() const {
    // Base DPS calculation
    double power = (power_type_ == PowerType::PHYSICAL) ? stats_.power_physical : stats_.power_magical;
    double attack_speed = stats_.basic_attack_speed;
    
    // Simple DPS formula: power * attack_speed
    return power * (1.0 + attack_speed / 100.0);
}

double God::getDpsBasicAttack(const Build& build) const {
    // Calculate total stats with build
    double total_power = (power_type_ == PowerType::PHYSICAL) ? stats_.power_physical : stats_.power_magical;
    double total_attack_speed = stats_.basic_attack_speed;
    
    auto items = {build.item1, build.item2, build.item3, build.item4, build.item5, build.item6};
    for (const auto& item : items) {
        if (item) {
            if (power_type_ == PowerType::PHYSICAL) {
                total_power += item->getStats().power_physical;
            } else {
                total_power += item->getStats().power_magical;
            }
            total_attack_speed += item->getStats().basic_attack_speed;
        }
    }
    
    return total_power * (1.0 + total_attack_speed / 100.0);
}

} // namespace twoptimizer::smite
