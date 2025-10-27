#!/bin/bash

# Build script for TwOptimizer C++

set -e

echo "=== TwOptimizer C++ Build Script ==="
echo ""

# Create build directory
if [ ! -d "build" ]; then
    echo "Creating build directory..."
    mkdir build
fi

cd build

# Configure
echo "Configuring CMake..."
echo "Note: First build will download OR-Tools and GoogleTest (may take 10-20 minutes)"
cmake .. -DCMAKE_BUILD_TYPE=Release

# Build
echo ""
echo "Building..."
cmake --build . -j$(nproc)

# Run tests
echo ""
echo "Running tests..."
ctest --output-on-failure

echo ""
echo "=== Build Complete ==="
echo "Binary: ./build/twoptimizer"
echo "Run tests: cd build && ctest"
