"""Social LCA Type I subcategory assessment (UNEP 2020): hand calculation of scores, coverage and missing data."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import slca_type1 as t1  # noqa: E402
from store import Workspace  # noqa: E402


class TestType1(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.ws = Workspace(self.dir)
        self.st = self.ws.create("T")
        self.m = self.st.save_model({"name": "shirt", "product": "shirt", "unit": "unit", "amount": 1,
                                     "scope": {"goal": "g", "boundary": "cradle-to-gate"}})

    def tearDown(self):
        self.ws.close_all()
        shutil.rmtree(self.dir, ignore_errors=True)

    def row(self, unit, sub, score, w, sh="workers", dt="site-specific primary", ind="indicator"):
        return t1.save_row(self.st, self.m, {"stakeholder": sh, "subcategory": sub, "unit": unit, "indicator": ind,
                                             "prp": "ILO convention / national law", "score": score, "weight": w,
                                             "weight_unit": "worker hours", "data_type": dt, "evidence": "audit",
                                             "source": "audit 2025"})

    def test_hand_calculation(self):
        # Fair salary: spinning mill (3 h, +1) and sewing factory (1 h, -2): (3 x 1 + 1 x -2) / 4 = 0.25
        self.row("spinning mill", "Fair salary", 1, 3)
        self.row("sewing factory", "Fair salary", -2, 1, dt="secondary generic")
        # two indicators of one organisation are averaged first: (0 + -1) / 2 = -0.5
        self.row("sewing factory", "Working hours", 0, 1, ind="overtime")
        self.row("sewing factory", "Working hours", -1, 1, ind="rest days")
        t1.set_scope(self.st, self.m, 8, "worker hours", "Ethical treatment of animals: no animals in the system")
        r = t1.assess(self.st, self.m)
        by = {x["subcategory"]: x for x in r["subcategories"]}
        self.assertAlmostEqual(by["Fair salary"]["score"], 0.25)
        self.assertAlmostEqual(by["Fair salary"]["coverage"], 4 / 8)
        self.assertAlmostEqual(by["Fair salary"]["primary_share"], 3 / 4)
        self.assertEqual([h["unit"] for h in by["Fair salary"]["hotspots"]], ["sewing factory"])
        self.assertAlmostEqual(by["Working hours"]["score"], -0.5)
        self.assertEqual(by["Working hours"]["organisations"], 1)
        w = [s for s in r["by_stakeholder"] if s["stakeholder"] == "workers"][0]
        self.assertEqual(w["assessed"], 2)
        self.assertEqual(w["lowest"], -0.5)
        miss = {m["subcategory"] for m in r["missing"]}
        self.assertIn("Child labour", miss)
        self.assertNotIn("Ethical treatment of animals", miss)       # excluded with a reason
        self.assertNotIn("Fair salary", miss)

    def test_rejections(self):
        bad = [dict(stakeholder="workers", subcategory="Happiness"), dict(stakeholder="planet"),
               dict(score=3), dict(score="1.5"), dict(weight=0), dict(data_type="rumour"), dict(prp="")]
        base = {"stakeholder": "workers", "subcategory": "Fair salary", "unit": "u", "indicator": "i", "prp": "law",
                "score": 0, "weight": 1, "weight_unit": "h", "data_type": "secondary generic", "evidence": "e",
                "source": "s"}
        for b in bad:
            with self.subTest(b=b), self.assertRaises(t1.SocialError):
                t1.save_row(self.st, self.m, {**base, **b})

    def test_mixed_weight_units_warn(self):
        self.row("a", "Fair salary", 1, 3)
        t1.save_row(self.st, self.m, {"stakeholder": "workers", "subcategory": "Fair salary", "unit": "b",
                                      "indicator": "i", "prp": "law", "score": 0, "weight": 1, "weight_unit": "EUR",
                                      "data_type": "secondary generic", "evidence": "e", "source": "s"})
        self.assertTrue(t1.assess(self.st, self.m)["warnings"])


if __name__ == "__main__":
    unittest.main()
