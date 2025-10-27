#include "tw/entity.h"

namespace twoptimizer::tw {

// Effect methods
double Effect::gdp() const {
    return gdp_;
}

double Effect::publicOrder() const {
    return public_order_;
}

double Effect::sanitation() const {
    return sanitation_;
}

double Effect::food() const {
    return food_;
}

void Effect::setGdp(double value) {
    gdp_ = value;
}

void Effect::setPublicOrder(double value) {
    public_order_ = value;
}

void Effect::setSanitation(double value) {
    sanitation_ = value;
}

void Effect::setFood(double value) {
    food_ = value;
}

} // namespace twoptimizer::tw
