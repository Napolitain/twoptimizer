#pragma once

#include "tw/building.h"
#include <vector>
#include <memory>

namespace twoptimizer::tw {

class Region : public Effect, public Entity {
public:
    Region(const std::string& name);
    ~Region() override = default;
    
    void addBuilding(std::shared_ptr<Building> building);
    const std::vector<std::shared_ptr<Building>>& getBuildings() const { return buildings_; }
    
private:
    std::vector<std::shared_ptr<Building>> buildings_;
};

class Province : public Effect, public Entity {
public:
    Province(const std::string& name);
    ~Province() override = default;
    
    void addRegion(std::shared_ptr<Region> region);
    const std::vector<std::shared_ptr<Region>>& getRegions() const { return regions_; }

private:
    std::vector<std::shared_ptr<Region>> regions_;
};

} // namespace twoptimizer::tw
