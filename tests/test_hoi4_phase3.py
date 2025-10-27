"""
Unit tests for Phase 3: National Focus Trees functionality.

Tests the Focus, FocusTree, and FocusParser classes.
"""

import unittest
from games.hoi4.models.focus import Focus, FocusTree, FocusFilterCategory


class TestFocus(unittest.TestCase):
    """Test cases for the Focus model."""
    
    def test_focus_creation(self):
        """Test creating a Focus."""
        focus = Focus(
            id="test_focus",
            icon="GFX_test",
            x=5,
            y=2,
            cost=10
        )
        
        self.assertEqual(focus.id, "test_focus")
        self.assertEqual(focus.icon, "GFX_test")
        self.assertEqual(focus.x, 5)
        self.assertEqual(focus.y, 2)
        self.assertEqual(focus.cost, 10)
    
    def test_focus_time_cost(self):
        """Test time cost calculation."""
        focus = Focus(id="test", cost=10)
        
        # 10 weeks = 70 days
        self.assertEqual(focus.get_time_cost_days(), 70)
    
    def test_focus_is_starting(self):
        """Test identifying starting focuses."""
        start = Focus(id="start", cost=10)
        not_start = Focus(id="not_start", cost=10, prerequisites=["start"])
        
        self.assertTrue(start.is_starting_focus())
        self.assertFalse(not_start.is_starting_focus())
    
    def test_focus_can_complete_with_prereqs(self):
        """Test can_complete with prerequisites."""
        focus = Focus(
            id="test",
            prerequisites=["prereq1", "prereq2"]
        )
        
        # Missing prerequisites
        self.assertFalse(focus.can_complete([]))
        self.assertFalse(focus.can_complete(["prereq1"]))
        
        # All prerequisites met
        self.assertTrue(focus.can_complete(["prereq1", "prereq2"]))
        self.assertTrue(focus.can_complete(["prereq1", "prereq2", "other"]))
    
    def test_focus_can_complete_with_mutex(self):
        """Test can_complete with mutually exclusive focuses."""
        focus = Focus(
            id="test",
            mutually_exclusive=["mutex1", "mutex2"]
        )
        
        # No mutex completed
        self.assertTrue(focus.can_complete([]))
        self.assertTrue(focus.can_complete(["other"]))
        
        # Mutex completed
        self.assertFalse(focus.can_complete(["mutex1"]))
        self.assertFalse(focus.can_complete(["mutex2"]))
    
    def test_focus_can_complete_complex(self):
        """Test can_complete with both prerequisites and mutex."""
        focus = Focus(
            id="test",
            prerequisites=["prereq"],
            mutually_exclusive=["mutex"]
        )
        
        # Prereq missing
        self.assertFalse(focus.can_complete([]))
        
        # Prereq met, no mutex
        self.assertTrue(focus.can_complete(["prereq"]))
        
        # Prereq met, but mutex completed
        self.assertFalse(focus.can_complete(["prereq", "mutex"]))
    
    def test_focus_search_filters(self):
        """Test search filter categories."""
        focus = Focus(
            id="test",
            search_filters=[FocusFilterCategory.POLITICAL, FocusFilterCategory.INDUSTRY]
        )
        
        self.assertEqual(len(focus.search_filters), 2)
        self.assertIn(FocusFilterCategory.POLITICAL, focus.search_filters)
        self.assertIn(FocusFilterCategory.INDUSTRY, focus.search_filters)


class TestFocusTree(unittest.TestCase):
    """Test cases for the FocusTree model."""
    
    def setUp(self):
        """Set up a test focus tree."""
        self.tree = FocusTree(
            id="test_tree",
            country_tags=["TST"]
        )
        
        # Create a simple tree structure
        #       start
        #      /     \
        #  left      right (mutex with left)
        #     |
        #    end
        
        self.start = Focus(id="start", x=0, y=0, cost=10)
        self.left = Focus(
            id="left",
            x=-2, y=1,
            cost=10,
            prerequisites=["start"]
        )
        self.right = Focus(
            id="right",
            x=2, y=1,
            cost=10,
            prerequisites=["start"],
            mutually_exclusive=["left"]
        )
        self.end = Focus(
            id="end",
            x=-2, y=2,
            cost=10,
            prerequisites=["left"]
        )
        
        self.tree.add_focus(self.start)
        self.tree.add_focus(self.left)
        self.tree.add_focus(self.right)
        self.tree.add_focus(self.end)
    
    def test_tree_creation(self):
        """Test creating a FocusTree."""
        tree = FocusTree(id="test", country_tags=["GER", "ITA"])
        
        self.assertEqual(tree.id, "test")
        self.assertEqual(len(tree.country_tags), 2)
        self.assertEqual(len(tree.focuses), 0)
    
    def test_add_focus(self):
        """Test adding focuses to tree."""
        tree = FocusTree(id="test")
        focus = Focus(id="f1")
        
        tree.add_focus(focus)
        
        self.assertEqual(len(tree.focuses), 1)
        self.assertEqual(tree.get_focus("f1"), focus)
    
    def test_get_focus(self):
        """Test retrieving focuses by ID."""
        self.assertEqual(self.tree.get_focus("start"), self.start)
        self.assertEqual(self.tree.get_focus("left"), self.left)
        self.assertIsNone(self.tree.get_focus("nonexistent"))
    
    def test_get_starting_focuses(self):
        """Test getting starting focuses."""
        starting = self.tree.get_starting_focuses()
        
        self.assertEqual(len(starting), 1)
        self.assertEqual(starting[0].id, "start")
    
    def test_get_available_focuses_start(self):
        """Test getting available focuses at start."""
        available = self.tree.get_available_focuses([])
        
        self.assertEqual(len(available), 1)
        self.assertEqual(available[0].id, "start")
    
    def test_get_available_focuses_after_start(self):
        """Test getting available focuses after completing start."""
        available = self.tree.get_available_focuses(["start"])
        
        self.assertEqual(len(available), 2)
        ids = [f.id for f in available]
        self.assertIn("left", ids)
        self.assertIn("right", ids)
    
    def test_get_available_focuses_mutex(self):
        """Test mutex prevents availability."""
        available = self.tree.get_available_focuses(["start", "left"])
        
        # Right should not be available because left was chosen (mutex)
        ids = [f.id for f in available]
        self.assertNotIn("right", ids)
        self.assertIn("end", ids)
    
    def test_get_focus_chain_length(self):
        """Test calculating chain length."""
        self.assertEqual(self.tree.get_focus_chain_length("start"), 0)
        self.assertEqual(self.tree.get_focus_chain_length("left"), 1)
        self.assertEqual(self.tree.get_focus_chain_length("right"), 1)
        self.assertEqual(self.tree.get_focus_chain_length("end"), 2)
    
    def test_get_total_cost_to_focus(self):
        """Test calculating total cost."""
        # start = 70 days
        self.assertEqual(self.tree.get_total_cost_to_focus("start"), 70)
        
        # start + left = 140 days
        self.assertEqual(self.tree.get_total_cost_to_focus("left"), 140)
        
        # start + left + end = 210 days
        self.assertEqual(self.tree.get_total_cost_to_focus("end"), 210)
    
    def test_validate_tree_valid(self):
        """Test validating a valid tree."""
        errors = self.tree.validate_tree()
        
        self.assertEqual(len(errors), 0)
    
    def test_validate_tree_invalid_prereq(self):
        """Test validation catches invalid prerequisites."""
        bad_focus = Focus(id="bad", prerequisites=["nonexistent"])
        self.tree.add_focus(bad_focus)
        
        errors = self.tree.validate_tree()
        
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("unknown prerequisite" in e for e in errors))
    
    def test_validate_tree_invalid_mutex(self):
        """Test validation catches invalid mutex."""
        bad_focus = Focus(id="bad", mutually_exclusive=["nonexistent"])
        self.tree.add_focus(bad_focus)
        
        errors = self.tree.validate_tree()
        
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("unknown mutex" in e for e in errors))
    
    def test_tree_len(self):
        """Test __len__ returns focus count."""
        self.assertEqual(len(self.tree), 4)


if __name__ == '__main__':
    unittest.main()
