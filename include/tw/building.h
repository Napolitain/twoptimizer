#pragma once

#include "tw/entity.h"
#include <memory>
#include <unordered_map>

namespace twoptimizer::tw {

class Building : public Effect, public Entity {
public:
    Building(const std::string& name, const std::string& printName = "", const std::string& hashName = "");
    ~Building() override = default;
    
    const std::string& getPrintName() const { return print_name_; }
    const std::string& getHashName() const { return hash_name_; }
    
    void* getLpVariable() const { return lp_variable_; }
    void setLpVariable(void* var) { lp_variable_ = var; }
    
    // Copy constructor
    Building(const Building& other);
    Building& operator=(const Building& other);
    
    // Effects to different scopes
    std::unordered_map<std::string, Effect> effectsToFaction;
    std::unordered_map<std::string, Effect> effectsToProvince;
    std::unordered_map<std::string, Effect> effectsToRegion;
    std::unordered_map<std::string, Effect> effectsToBuilding;

private:
    std::string print_name_;
    std::string hash_name_;
    void* lp_variable_ = nullptr;
};

} // namespace twoptimizer::tw
