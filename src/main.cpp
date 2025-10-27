#include <iostream>
#include "tw/problem.h"
#include "smite/god_builder.h"

int main(int argc, char* argv[]) {
    std::cout << "TwOptimizer - C++ version" << std::endl;
    std::cout << "Optimization tool for Total War, Smite, and other games" << std::endl;
    
    // Example: Create a simple TW problem
    try {
        twoptimizer::tw::Problem problem;
        std::cout << "TW Problem initialized successfully" << std::endl;
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }
    
    return 0;
}
