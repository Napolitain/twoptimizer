#include "tw/building.h"
#include <sstream>

namespace twoptimizer::tw {

static int hash_counter = 0;

Building::Building(const std::string& name, const std::string& printName, const std::string& hashName) {
    name_ = name;
    print_name_ = printName.empty() ? name : printName;
    
    if (hashName.empty()) {
        std::ostringstream oss;
        oss << "B" << hash_counter++;
        hash_name_ = oss.str();
    } else {
        hash_name_ = hashName;
    }
}

Building::Building(const Building& other) 
    : Effect(other), Entity(other) {
    print_name_ = other.print_name_;
    hash_name_ = other.hash_name_;
    lp_variable_ = other.lp_variable_;
    effectsToFaction = other.effectsToFaction;
    effectsToProvince = other.effectsToProvince;
    effectsToRegion = other.effectsToRegion;
    effectsToBuilding = other.effectsToBuilding;
}

Building& Building::operator=(const Building& other) {
    if (this != &other) {
        Effect::operator=(other);
        Entity::operator=(other);
        print_name_ = other.print_name_;
        hash_name_ = other.hash_name_;
        lp_variable_ = other.lp_variable_;
        effectsToFaction = other.effectsToFaction;
        effectsToProvince = other.effectsToProvince;
        effectsToRegion = other.effectsToRegion;
        effectsToBuilding = other.effectsToBuilding;
    }
    return *this;
}

} // namespace twoptimizer::tw
