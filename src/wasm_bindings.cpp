#include <emscripten/emscripten.h>
#include "smite/god_builder.h"
#include "tw/problem.h"

extern "C" {

EMSCRIPTEN_KEEPALIVE
double optimize_god_build(const char* god_name, int power_type) {
    // Simple example function for WebAssembly
    // In a real implementation, this would need more complex parameter passing
    return 0.0;
}

EMSCRIPTEN_KEEPALIVE
int solve_tw_problem() {
    try {
        twoptimizer::tw::Problem problem;
        return 1;  // Success
    } catch (...) {
        return 0;  // Failure
    }
}

} // extern "C"
