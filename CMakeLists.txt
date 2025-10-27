cmake_minimum_required(VERSION 3.20)
project(optimizer VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Download CPM.cmake
set(CPM_DOWNLOAD_VERSION 0.42.0)
set(CPM_DOWNLOAD_LOCATION "${CMAKE_BINARY_DIR}/cmake/CPM_${CPM_DOWNLOAD_VERSION}.cmake")

if(NOT (EXISTS ${CPM_DOWNLOAD_LOCATION}))
    message(STATUS "Downloading CPM.cmake to ${CPM_DOWNLOAD_LOCATION}")
    file(DOWNLOAD
         https://github.com/cpm-cmake/CPM.cmake/releases/download/v${CPM_DOWNLOAD_VERSION}/CPM.cmake
         ${CPM_DOWNLOAD_LOCATION}
    )
endif()

include(${CPM_DOWNLOAD_LOCATION})

# Add GoogleTest
CPMAddPackage(
    NAME googletest
    GITHUB_REPOSITORY google/googletest
    GIT_TAG v1.17.0
    OPTIONS
        "INSTALL_GTEST OFF"
        "gtest_force_shared_crt ON"
)

# Add OR-Tools
CPMAddPackage(
    NAME ortools
    GITHUB_REPOSITORY google/or-tools
    GIT_TAG v9.14
    OPTIONS
        "BUILD_DEPS ON"
        "BUILD_SAMPLES OFF"
        "BUILD_EXAMPLES OFF"
)

# Enable testing
enable_testing()
include(GoogleTest)

# Common include directory

# Collect all source files recursively from src directory
# Exclude main.cpp and wasm_bindings.cpp as they are entry points
file(GLOB_RECURSE SOURCES
    "src/*.cpp"
)
list(FILTER SOURCES EXCLUDE REGEX "src/main\\.cpp$")
list(FILTER SOURCES EXCLUDE REGEX "src/wasm_bindings\\.cpp$")

# Create static library
add_library(liboptimizer STATIC)
target_sources(liboptimizer PRIVATE ${SOURCES})
target_include_directories(liboptimizer PUBLIC ${CMAKE_SOURCE_DIR}/include)
target_link_libraries(liboptimizer PUBLIC ortools::ortools)
set_target_properties(liboptimizer PROPERTIES OUTPUT_NAME "optimizer")

# Executable target
add_executable(optimizer src/main.cpp)
target_link_libraries(optimizer PRIVATE liboptimizer)

# WebAssembly target
if(EMSCRIPTEN)
    add_executable(optimizer_wasm src/wasm_bindings.cpp)
    target_link_libraries(optimizer_wasm PRIVATE liboptimizer)
    set_target_properties(optimizer_wasm PROPERTIES
        LINK_FLAGS "-s WASM=1 -s EXPORTED_FUNCTIONS='[\"_optimize_build\"]' -s EXPORTED_RUNTIME_METHODS='[\"ccall\",\"cwrap\"]' -s MODULARIZE=1 -s EXPORT_NAME='TwOptimizerModule'"
    )
endif()

# Tests
add_subdirectory(tests)
