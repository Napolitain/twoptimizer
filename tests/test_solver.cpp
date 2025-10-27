#include <gtest/gtest.h>
#include "solver/solver.h"
#include "solver/solver_ortools.h"

using namespace twoptimizer;

class SolverTest : public ::testing::Test {
protected:
    void SetUp() override {
        solver = std::make_unique<SolverOrTools>();
    }
    
    std::unique_ptr<Solver> solver;
};

TEST_F(SolverTest, CreateSolver) {
    EXPECT_NE(solver, nullptr);
}

TEST_F(SolverTest, CreateVariable) {
    void* var = solver->createVariable("test_var", "Binary");
    EXPECT_NE(var, nullptr);
    EXPECT_EQ(solver->numVariables(), 1);
}

TEST_F(SolverTest, CreateMultipleVariables) {
    solver->createVariable("var1", "Binary");
    solver->createVariable("var2", "Binary");
    solver->createVariable("var3", "Integer");
    
    EXPECT_EQ(solver->numVariables(), 3);
}

TEST_F(SolverTest, SimpleSolve) {
    auto* var1 = solver->createVariable("x", "Binary");
    auto* var2 = solver->createVariable("y", "Binary");
    
    solver->setObjective(true);  // Maximize
    
    // Without constraints, solver should still work
    bool result = solver->solve();
    EXPECT_TRUE(result);
}

int main(int argc, char **argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
