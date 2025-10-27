#include <gtest/gtest.h>
#include "smite/god.h"
#include "smite/god_builder.h"
#include "smite/item.h"

using namespace twoptimizer::smite;

class SmiteTest : public ::testing::Test {
protected:
    void SetUp() override {
        // Set up test fixtures
    }
};

TEST_F(SmiteTest, CreateGod) {
    Stats baseStats;
    baseStats.power_physical = 50.0;
    baseStats.basic_attack_speed = 100.0;
    
    God god("TestGod", PowerType::PHYSICAL, baseStats);
    
    EXPECT_EQ(god.getName(), "TestGod");
    EXPECT_EQ(god.getPowerType(), PowerType::PHYSICAL);
    EXPECT_EQ(god.getStats().power_physical, 50.0);
}

TEST_F(SmiteTest, CreateItem) {
    Stats itemStats;
    itemStats.power_physical = 30.0;
    itemStats.basic_attack_speed = 20.0;
    
    auto item = std::make_shared<Item>("DeathBringer", itemStats, false);
    
    EXPECT_EQ(item->getName(), "DeathBringer");
    EXPECT_EQ(item->getStats().power_physical, 30.0);
    EXPECT_FALSE(item->isStarter());
}

TEST_F(SmiteTest, CalculateDPS) {
    Stats baseStats;
    baseStats.power_physical = 50.0;
    baseStats.basic_attack_speed = 100.0;
    
    God god("TestGod", PowerType::PHYSICAL, baseStats);
    
    double baseDps = god.getDpsBasicAttack();
    EXPECT_GT(baseDps, 0.0);
}

TEST_F(SmiteTest, GodBuilderOptimization) {
    Stats baseStats;
    baseStats.power_physical = 50.0;
    baseStats.basic_attack_speed = 100.0;
    
    God god("TestGod", PowerType::PHYSICAL, baseStats);
    
    // Create some items
    std::vector<std::shared_ptr<Item>> items;
    for (int i = 0; i < 10; ++i) {
        Stats itemStats;
        itemStats.power_physical = 20.0 + i * 5.0;
        itemStats.basic_attack_speed = 10.0 + i * 2.0;
        items.push_back(std::make_shared<Item>("Item" + std::to_string(i), itemStats, false));
    }
    
    GodBuilder builder(god, items);
    auto result = builder.optimizeBuild();
    
    EXPECT_TRUE(result.has_value());
    if (result.has_value()) {
        auto [build, dps] = result.value();
        EXPECT_EQ(build.countItems(), 6);
        EXPECT_GT(dps, 0.0);
    }
}

TEST_F(SmiteTest, BuildCountItems) {
    Stats itemStats;
    itemStats.power_physical = 30.0;
    
    Build build;
    build.item1 = std::make_shared<Item>("Item1", itemStats);
    build.item2 = std::make_shared<Item>("Item2", itemStats);
    build.item3 = std::make_shared<Item>("Item3", itemStats);
    
    EXPECT_EQ(build.countItems(), 3);
}

int main(int argc, char **argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
