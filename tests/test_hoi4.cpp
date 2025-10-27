#include <gtest/gtest.h>
#include "hoi4/models.h"

using namespace twoptimizer::hoi4;

class HOI4Test : public ::testing::Test {
protected:
    void SetUp() override {
        // Set up test fixtures
    }
};

TEST_F(HOI4Test, CreateBuilding) {
    BuildingType civFactory("civilian_factory", BuildingCategory::INDUSTRIAL, 10800.0, 540);
    
    EXPECT_EQ(civFactory.getName(), "civilian_factory");
    EXPECT_EQ(civFactory.getCategory(), BuildingCategory::INDUSTRIAL);
    EXPECT_EQ(civFactory.getBaseCost(), 10800.0);
    EXPECT_EQ(civFactory.getConstructionTime(), 540);
}

TEST_F(HOI4Test, BuildingWithModifiers) {
    BuildingType infra("infrastructure", BuildingCategory::INFRASTRUCTURE, 3000.0, 120);
    
    Modifier mod1{"local_resources", 0.2, "state"};
    Modifier mod2{"supply_consumption", -0.1, "state"};
    
    infra.addModifier(mod1);
    infra.addModifier(mod2);
    
    EXPECT_EQ(infra.getModifiers().size(), 2);
    EXPECT_EQ(infra.getModifiers()[0].name, "local_resources");
    EXPECT_EQ(infra.getModifiers()[1].value, -0.1);
}

TEST_F(HOI4Test, CreateFocus) {
    Focus focus("political_effort", 5, 0, 70);
    
    EXPECT_EQ(focus.getId(), "political_effort");
    EXPECT_EQ(focus.getX(), 5);
    EXPECT_EQ(focus.getY(), 0);
    EXPECT_EQ(focus.getCost(), 70);
}

TEST_F(HOI4Test, FocusPrerequisites) {
    Focus focus("industrial_effort", 3, 2);
    focus.addPrerequisite("political_effort");
    focus.addPrerequisite("economic_effort");
    
    EXPECT_EQ(focus.getPrerequisites().size(), 2);
    EXPECT_EQ(focus.getPrerequisites()[0], "political_effort");
    EXPECT_EQ(focus.getPrerequisites()[1], "economic_effort");
}

TEST_F(HOI4Test, MutuallyExclusiveFocuses) {
    Focus focus("democracy", 3, 3);
    focus.addMutuallyExclusive("fascism");
    focus.addMutuallyExclusive("communism");
    
    EXPECT_EQ(focus.getMutuallyExclusive().size(), 2);
}

TEST_F(HOI4Test, CreateIdea) {
    Idea idea("national_spirit_war_economy");
    
    Modifier mod{"consumer_goods_factor", -0.3, "country"};
    idea.addModifier(mod);
    
    EXPECT_EQ(idea.getName(), "national_spirit_war_economy");
    EXPECT_EQ(idea.getModifiers().size(), 1);
    EXPECT_EQ(idea.getModifiers()[0].name, "consumer_goods_factor");
}

int main(int argc, char **argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
