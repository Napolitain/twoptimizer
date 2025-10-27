#pragma once

#include <string>
#include <vector>
#include <memory>

namespace twoptimizer::hoi4 {

enum class BuildingCategory {
    INFRASTRUCTURE,
    INDUSTRIAL,
    MILITARY,
    NAVAL,
    AIR,
    FORTIFICATION,
    RESOURCE,
    SPECIAL
};

enum class FocusCategory {
    POLITICAL,
    RESEARCH,
    INDUSTRY,
    STABILITY,
    WAR_SUPPORT,
    MANPOWER,
    ANNEXATION,
    MILITARY
};

struct Modifier {
    std::string name;
    double value;
    std::string scope;
};

class BuildingType {
public:
    BuildingType(const std::string& name, BuildingCategory category, 
                 double baseCost, int constructionTime);
    ~BuildingType() = default;
    
    const std::string& getName() const { return name_; }
    BuildingCategory getCategory() const { return category_; }
    double getBaseCost() const { return base_cost_; }
    int getConstructionTime() const { return construction_time_; }
    int getMaxLevel() const { return max_level_; }
    
    void setMaxLevel(int level) { max_level_ = level; }
    void addModifier(const Modifier& modifier);
    const std::vector<Modifier>& getModifiers() const { return modifiers_; }

private:
    std::string name_;
    BuildingCategory category_;
    double base_cost_;
    int construction_time_;
    int max_level_ = -1;  // -1 means unlimited
    std::vector<Modifier> modifiers_;
};

class Focus {
public:
    Focus(const std::string& id, int x, int y, int cost = 70);
    ~Focus() = default;
    
    const std::string& getId() const { return id_; }
    int getX() const { return x_; }
    int getY() const { return y_; }
    int getCost() const { return cost_; }
    
    void addPrerequisite(const std::string& focusId);
    void addMutuallyExclusive(const std::string& focusId);
    void setCategory(FocusCategory category) { category_ = category; }
    
    const std::vector<std::string>& getPrerequisites() const { return prerequisites_; }
    const std::vector<std::string>& getMutuallyExclusive() const { return mutually_exclusive_; }

private:
    std::string id_;
    int x_;
    int y_;
    int cost_;
    FocusCategory category_;
    std::vector<std::string> prerequisites_;
    std::vector<std::string> mutually_exclusive_;
};

class Idea {
public:
    Idea(const std::string& name);
    ~Idea() = default;
    
    const std::string& getName() const { return name_; }
    void addModifier(const Modifier& modifier);
    const std::vector<Modifier>& getModifiers() const { return modifiers_; }

private:
    std::string name_;
    std::vector<Modifier> modifiers_;
};

} // namespace twoptimizer::hoi4
