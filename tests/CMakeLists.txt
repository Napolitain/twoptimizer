cmake_minimum_required(VERSION 3.20)

# Test executable for TW module
add_executable(test_tw
    test_tw.cpp
)

target_link_libraries(test_tw
    PRIVATE
    twoptimizer_lib
    gtest
    gtest_main
)

gtest_discover_tests(test_tw)

# Test executable for Smite module
add_executable(test_smite
    test_smite.cpp
)

target_link_libraries(test_smite
    PRIVATE
    twoptimizer_lib
    gtest
    gtest_main
)

gtest_discover_tests(test_smite)

# Test executable for HOI4 module
add_executable(test_hoi4
    test_hoi4.cpp
)

target_link_libraries(test_hoi4
    PRIVATE
    twoptimizer_lib
    gtest
    gtest_main
)

gtest_discover_tests(test_hoi4)

# Test executable for Solver module
add_executable(test_solver
    test_solver.cpp
)

target_link_libraries(test_solver
    PRIVATE
    twoptimizer_lib
    gtest
    gtest_main
)

gtest_discover_tests(test_solver)
