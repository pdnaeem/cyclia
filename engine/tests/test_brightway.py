"""Comparison with Brightway's calculation library (bw2calc).

These tests run the real Brightway code when bw2calc and bw_processing are installed (the release builds install
them on Windows, macOS and Linux) and are skipped otherwise."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import brightway_check  # noqa: E402
import calc  # noqa: E402
from bench_db import synthetic_database  # noqa: E402
from importers import demo  # noqa: E402
from store import Workspace  # noqa: E402

HAVE_BW = brightway_check.available()


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.ws = Workspace(self.dir)
        self.st = self.ws.create("T")
        calc.invalidate()

    def tearDown(self):
        self.ws.close_all()
        calc.invalidate()
        shutil.rmtree(self.dir, ignore_errors=True)


class TestWithoutBrightway(Base):
    def test_clear_message_when_not_installed(self):
        real = brightway_check.available
        brightway_check.available = lambda: False
        try:
            demo.install_database(self.st)
            with self.assertRaises(ValueError) as cm:
                brightway_check.compare(self.st, self.st.databases()[0]["id"], [m["id"] for m in self.st.methods()])
            self.assertIn("not available", str(cm.exception))
        finally:
            brightway_check.available = real


@unittest.skipUnless(HAVE_BW, "bw2calc is not installed")
class TestBrightway(Base):
    def test_demo_database_agrees(self):
        demo.install_database(self.st)
        db = self.st.databases()[0]["id"]
        r = brightway_check.compare(self.st, db, [m["id"] for m in self.st.methods()])
        self.assertTrue(r["passed"], r["verdict"])
        self.assertLess(r["max_relative_difference"], 1e-9)
        self.assertEqual(r["datasets"], r["datasets_in_database"])

    def test_large_structure_with_waste_infrastructure_and_loops(self):
        """Markets, loops, waste treatment with negative production, infrastructure at 1e-13 to 1e-9 per unit and
        recycling credits: Brightway and Cyclia agree on every result."""
        info = synthetic_database(self.st, n=800, flows=150, methods=4)
        db = self.st.databases()[0]["id"]
        r = brightway_check.compare(self.st, db, info["method_ids"])
        self.assertTrue(r["passed"], r["verdict"])
        self.assertLess(r["max_relative_difference"], 1e-9)
        self.assertEqual(r["results"], 800 * 4)
        out = brightway_check.excel(os.path.join(self.dir, "bw.xlsx"), r)
        from openpyxl import load_workbook
        wb = load_workbook(out)
        self.assertEqual(wb["By category"].max_row, 5)

    def test_a_difference_is_found(self):
        """The check is not blind: one technosphere amount changed on Brightway's side is reported."""
        info = synthetic_database(self.st, n=200, flows=60, methods=2)
        db = self.st.databases()[0]["id"]
        real = brightway_check._packages

        def changed(acts, tech, bio, cfs):
            tech = [dict(t) for t in tech]
            tech[0]["amount"] *= 1.5
            return real(acts, tech, bio, cfs)
        brightway_check._packages = changed
        try:
            r = brightway_check.compare(self.st, db, info["method_ids"])
        finally:
            brightway_check._packages = real
        self.assertFalse(r["passed"])
        self.assertGreater(r["max_relative_difference"], 1e-6)

    def test_sample(self):
        info = synthetic_database(self.st, n=300, flows=60, methods=1)
        r = brightway_check.compare(self.st, self.st.databases()[0]["id"], info["method_ids"], sample=50)
        self.assertEqual(r["datasets"], 50)
        self.assertTrue(r["passed"])


if __name__ == "__main__":
    unittest.main()
