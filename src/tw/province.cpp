#include "tw/province.h"

namespace twoptimizer::tw {

Region::Region(const std::string& name) {
    name_ = name;
}

void Region::addBuilding(std::shared_ptr<Building> building) {
    buildings_.push_back(building);
}

Province::Province(const std::string& name) {
    name_ = name;
}

void Province::addRegion(std::shared_ptr<Region> region) {
    regions_.push_back(region);
}

} // namespace twoptimizer::tw
