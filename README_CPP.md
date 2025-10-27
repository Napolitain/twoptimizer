# TwOptimizer - C++ Edition

A high-performance optimization library for game mechanics, focusing on Total War, Smite, and Hearts of Iron 4. Completely rewritten in C++20 with OR-Tools for optimization.

## Features

- **C++20** modern C++ implementation
- **OR-Tools** for linear programming optimization
- **CMake** build system with CPM.cmake for dependency management
- **Google Test** for unit testing
- **WebAssembly** support for browser integration
- **Multi-game support**: Total War, Smite, HOI4

## Building

### Prerequisites

- CMake 3.20 or higher
- C++20 compatible compiler (GCC 11+, Clang 14+, MSVC 2019+)
- Internet connection (for downloading dependencies)
- **Note**: First build downloads and compiles OR-Tools (~10-20 minutes)

### Build Instructions

```bash
# Create build directory
mkdir build && cd build

# Configure (downloads OR-Tools and GoogleTest)
cmake ..

# Build (this may take 10-20 minutes on first run)
cmake --build . -j$(nproc)

# Run tests
ctest --output-on-failure
```

### Quick Build Options

For faster builds during development:
```bash
cmake .. -DCMAKE_BUILD_TYPE=Release
cmake --build . -j$(nproc)
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
