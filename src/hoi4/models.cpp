#include "hoi4/models.h"

namespace twoptimizer::hoi4 {

// BuildingType implementation
BuildingType::BuildingType(const std::string& name, BuildingCategory category,
                           double baseCost, int constructionTime)
    : name_(name), category_(category), base_cost_(baseCost), 
      construction_time_(constructionTime) {
}

void BuildingType::addModifier(const Modifier& modifier) {
    modifiers_.push_back(modifier);
}

// Focus implementation
Focus::Focus(const std::string& id, int x, int y, int cost)
    : id_(id), x_(x), y_(y), cost_(cost), category_(FocusCategory::POLITICAL) {
}

void Focus::addPrerequisite(const std::string& focusId) {
    prerequisites_.push_back(focusId);
}

void Focus::addMutuallyExclusive(const std::string& focusId) {
    mutually_exclusive_.push_back(focusId);
}

// Idea implementation
Idea::Idea(const std::string& name) : name_(name) {
}

void Idea::addModifier(const Modifier& modifier) {
    modifiers_.push_back(modifier);
}

} // namespace twoptimizer::hoi4
