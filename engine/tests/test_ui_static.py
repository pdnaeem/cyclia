"""Static checks of the interface files."""
import collections
import os
import re
import unittest

UI = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "app", "ui")


class TestInterface(unittest.TestCase):
    def test_element_ids_are_unique(self):
        """Two elements with one id make the second unreachable and bind handlers to the wrong one."""
        with open(os.path.join(UI, "index.html"), encoding="utf-8") as fh:
            ids = re.findall(r'\sid="([^"]+)"', fh.read())
        dup = [k for k, n in collections.Counter(ids).items() if n > 1]
        self.assertEqual(dup, [])


if __name__ == "__main__":
    unittest.main()
