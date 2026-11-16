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
               dict(score=3), dict(score="1.5"), dict(weight=0), dict(weight=float("inf")), dict(weight=float("nan")),
               dict(weight="Infinity"), dict(data_type="rumour"), dict(prp="")]
        base = {"stakeholder": "workers", "subcategory": "Fair salary", "unit": "u", "indicator": "i", "prp": "law",
                "score": 0, "weight": 1, "weight_unit": "h", "data_type": "secondary generic", "evidence": "e",
                "source": "s"}
        for b in bad:
            with self.subTest(b=b), self.assertRaises(t1.SocialError):
                t1.save_row(self.st, self.m, {**base, **b})

    def other(self, unit, w, wu, score=0, sub="Fair salary"):
        t1.save_row(self.st, self.m, {"stakeholder": "workers", "subcategory": sub, "unit": unit,
                                      "indicator": "i", "prp": "law", "score": score, "weight": w, "weight_unit": wu,
                                      "data_type": "secondary generic", "evidence": "e", "source": "s"})

    def test_mixed_weight_units_give_no_score(self):
        self.row("a", "Fair salary", 1, 3)
        self.other("b", 1, "EUR")
        self.row("c", "Working hours", 1, 2)
        r = t1.assess(self.st, self.m)
        by = {x["subcategory"]: x for x in r["subcategories"]}
        self.assertTrue(r["warnings"])
        self.assertIsNone(by["Fair salary"]["score"])               # worker hours and EUR are not combined
        self.assertIn("No score", by["Fair salary"]["error"])
        self.assertAlmostEqual(by["Working hours"]["score"], 1.0)  # the other subcategory is unaffected
        w = [s for s in r["by_stakeholder"] if s["stakeholder"] == "workers"][0]
        self.assertEqual((w["assessed"], w["mean_score"]), (1, 1.0))

    def test_convertible_units_are_combined(self):
        # 2 h with +1 and 60 min (1 h) with -2: (2 x 1 + 1 x -2) / 3 = 0; coverage 3 h of 6 h
        self.other("a", 2, "h", 1)
        self.other("b", 60, "min", -2)
        t1.set_scope(self.st, self.m, 6, "h")
        x = [x for x in t1.assess(self.st, self.m)["subcategories"] if x["subcategory"] == "Fair salary"][0]
        self.assertAlmostEqual(x["score"], 0.0, places=12)
        self.assertAlmostEqual(x["coverage"], 0.5, places=12)

    def test_infinite_total_refused(self):
        for t in (float("inf"), float("nan"), "Infinity", 0, -1):
            with self.subTest(t=t), self.assertRaises(t1.SocialError):
                t1.set_scope(self.st, self.m, t, "h")

    def test_contradictory_weights_of_one_organisation(self):
        self.other("a", 2, "h", 1)
        t1.save_row(self.st, self.m, {"stakeholder": "workers", "subcategory": "Fair salary", "unit": "a",
                                      "indicator": "other", "prp": "law", "score": 0, "weight": 5, "weight_unit": "h",
                                      "data_type": "secondary generic", "evidence": "e", "source": "s"})
        x = [x for x in t1.assess(self.st, self.m)["subcategories"] if x["subcategory"] == "Fair salary"][0]
        self.assertIsNone(x["score"])


if __name__ == "__main__":
    unittest.main()
