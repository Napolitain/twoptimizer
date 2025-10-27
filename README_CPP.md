# TwOptimizer - C++ Edition

A high-performance optimization library for game mechanics, focusing on Total War, Smite, and Hearts of Iron 4. Completely rewritten in C++23 with OR-Tools for optimization.

## Features

- **C++23** modern C++ implementation
- **OR-Tools** for linear programming optimization
- **CMake** build system with CPM.cmake for dependency management
- **Google Test** for unit testing
- **WebAssembly** support for browser integration
- **Multi-game support**: Total War, Smite, HOI4

## Building

### Prerequisites

- CMake 3.20 or higher
- C++23 compatible compiler (GCC 13+, Clang 16+, MSVC 2022+)
- Internet connection (for downloading dependencies)

### Build Instructions

```bash
# Create build directory
mkdir build && cd build

# Configure
cmake ..

# Build
cmake --build .

# Run tests
ctest
```

### WebAssembly Build

```bash
# Install Emscripten first
source /path/to/emsdk/emsdk_env.sh

# Configure for WebAssembly
mkdir build-wasm && cd build-wasm
emcmake cmake ..

# Build
emmake make

# Output: twoptimizer_wasm.wasm and twoptimizer_wasm.js
```

## Usage

### Binary Executable

```bash
./twoptimizer
```

### WebAssembly (JavaScript)

```javascript
const module = await TwOptimizerModule();
const result = module.ccall('optimize_god_build', 'number', ['string', 'number'], ['GodName', 0]);
```

## Architecture

- `include/solver/` - Solver abstraction layer
- `include/tw/` - Total War optimization
- `include/smite/` - Smite god/item optimization
- `src/` - Implementation files
- `tests/` - Google Test unit tests

## Dependencies

All dependencies are automatically downloaded via CPM.cmake:
- OR-Tools 9.10+
- Google Test 1.15+

## Testing

Run all tests:
```bash
cd build
ctest --verbose
```

Run specific test:
```bash
./test_tw
./test_smite
./test_solver
```

## License

See LICENSE file for details.
