from unittest import TestCase

from engine.region import Region


class TestRegion(TestCase):
    def test_increment_hash_name(self):
        Region.HASH_NAME = "R1"
        for i in range(10):
            Region(5, "test")
        self.assertEqual("R11", Region.HASH_NAME)
