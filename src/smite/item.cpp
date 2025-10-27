#include "smite/item.h"

namespace twoptimizer::smite {

Item::Item(const std::string& name, const Stats& stats, bool isStarter) 
    : name_(name), stats_(stats), is_starter_(isStarter) {
}

int Build::countItems() const {
    int count = 0;
    if (item1) count++;
    if (item2) count++;
    if (item3) count++;
    if (item4) count++;
    if (item5) count++;
    if (item6) count++;
    return count;
}

} // namespace twoptimizer::smite
