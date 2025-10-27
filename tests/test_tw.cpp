#include <gtest/gtest.h>
#include "tw/problem.h"
#include "tw/province.h"
#include "tw/building.h"

using namespace twoptimizer::tw;

class TWProblemTest : public ::testing::Test {
protected:
    void SetUp() override {
        // Set up test fixtures
    }
};

TEST_F(TWProblemTest, CreateProblem) {
    Problem problem;
    EXPECT_EQ(problem.getState(), ProblemState::INIT);
}

TEST_F(TWProblemTest, AddProvince) {
    Problem problem;
    auto province = std::make_shared<Province>("TestProvince");
    
    problem.addProvince(province);
    EXPECT_EQ(problem.getState(), ProblemState::PROVINCES_ADDED);
}

TEST_F(TWProblemTest, AddBuilding) {
    Problem problem;
    auto province = std::make_shared<Province>("TestProvince");
    auto region = std::make_shared<Region>("TestRegion");
    auto building = std::make_shared<Building>("TestBuilding", "Test Building");
    
    region->addBuilding(building);
    province->addRegion(region);
    problem.addProvince(province);
    
    problem.addBuildings();
    EXPECT_EQ(problem.getState(), ProblemState::BUILDINGS_ADDED);
}

TEST_F(TWProblemTest, BuildingEffects) {
    auto building = std::make_shared<Building>("Farm", "Farm Building");
    building->setGdp(100.0);
    building->setFood(50.0);
    
    EXPECT_EQ(building->gdp(), 100.0);
    EXPECT_EQ(building->food(), 50.0);
}

TEST_F(TWProblemTest, RegionWithMultipleBuildings) {
    auto region = std::make_shared<Region>("TestRegion");
    auto building1 = std::make_shared<Building>("Farm");
    auto building2 = std::make_shared<Building>("Mine");
    
    region->addBuilding(building1);
    region->addBuilding(building2);
    
    EXPECT_EQ(region->getBuildings().size(), 2);
}

int main(int argc, char **argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
