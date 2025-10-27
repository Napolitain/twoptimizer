cmake_minimum_required(VERSION 3.20)
project(twoptimizer VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Download CPM.cmake
set(CPM_DOWNLOAD_VERSION 0.38.7)
set(CPM_DOWNLOAD_LOCATION "${CMAKE_BINARY_DIR}/cmake/CPM_${CPM_DOWNLOAD_VERSION}.cmake")

if(NOT (EXISTS ${CPM_DOWNLOAD_LOCATION}))
    message(STATUS "Downloading CPM.cmake to ${CPM_DOWNLOAD_LOCATION}")
    file(DOWNLOAD
         https://github.com/cpm-cmake/CPM.cmake/releases/download/v${CPM_DOWNLOAD_VERSION}/CPM.cmake
         ${CPM_DOWNLOAD_LOCATION}
    )
endif()

include(${CPM_DOWNLOAD_LOCATION})

# Add OR-Tools
CPMAddPackage(
    NAME ortools
    GITHUB_REPOSITORY google/or-tools
    GIT_TAG v9.9
    OPTIONS
        "BUILD_DEPS ON"
        "BUILD_SAMPLES OFF"
        "BUILD_EXAMPLES OFF"
)

# Add GoogleTest
CPMAddPackage(
    NAME googletest
    GITHUB_REPOSITORY google/googletest
    VERSION 1.15.2
    OPTIONS
        "INSTALL_GTEST OFF"
        "gtest_force_shared_crt ON"
)

# Enable testing
enable_testing()
include(GoogleTest)

# Common include directory
include_directories(${CMAKE_SOURCE_DIR}/include)

# Collect all source files recursively from src directory
# Exclude main.cpp and wasm_bindings.cpp as they are entry points
file(GLOB_RECURSE TWOPTIMIZER_SOURCES
    "src/*.cpp"
)
list(FILTER TWOPTIMIZER_SOURCES EXCLUDE REGEX "src/main\\.cpp$")
list(FILTER TWOPTIMIZER_SOURCES EXCLUDE REGEX "src/wasm_bindings\\.cpp$")

# Create static library
add_library(twoptimizer_lib STATIC ${TWOPTIMIZER_SOURCES})
target_include_directories(twoptimizer_lib PUBLIC ${CMAKE_SOURCE_DIR}/include)
target_link_libraries(twoptimizer_lib PUBLIC ortools::ortools)

# Executable target
add_executable(twoptimizer src/main.cpp)
target_link_libraries(twoptimizer PRIVATE twoptimizer_lib)

# WebAssembly target
if(EMSCRIPTEN)
    add_executable(twoptimizer_wasm src/wasm_bindings.cpp)
    target_link_libraries(twoptimizer_wasm PRIVATE twoptimizer_lib)
    set_target_properties(twoptimizer_wasm PROPERTIES
        LINK_FLAGS "-s WASM=1 -s EXPORTED_FUNCTIONS='[\"_optimize_build\"]' -s EXPORTED_RUNTIME_METHODS='[\"ccall\",\"cwrap\"]' -s MODULARIZE=1 -s EXPORT_NAME='TwOptimizerModule'"
    )
endif()

# Tests
add_subdirectory(tests)
