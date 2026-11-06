"""Scientific Benchmark Centre: the IPCC check, recording of runs, and the rule that only runs count."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import benchmark  # noqa: E402
import calc  # noqa: E402
from store import Workspace  # noqa: E402


class TestBenchmark(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.ws = Workspace(self.dir)
        self.st = self.ws.create("T")

    def tearDown(self):
        self.ws.close_all()
        calc.invalidate()
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_ipcc_check_reproduces_the_published_values(self):
        r = benchmark.ipcc_check()
        self.assertTrue(r["passed"], r)
        self.assertEqual(r["n"], 14)
        by = {x["gas"]: x["cyclia"] for x in r["rows"]}
        self.assertEqual(by["Methane, fossil"], 29.8)
        self.assertEqual(by["Dinitrogen monoxide"], 273.0)

    def test_nothing_counts_before_it_ran(self):
        c = benchmark.centre(self.st)
        statuses = {r["check"].split(":")[0].split(" (")[0]: r["status"] for r in c["rows"]}
        self.assertNotIn("Validated", statuses.values())
        self.assertTrue(all(r["status"] in ("Not run", "Not available") for r in c["rows"]))

    def test_recorded_runs_show_with_their_status(self):
        benchmark.record(self.st, "suite", "validation suite", {"passed": 35, "total": 35, "max_relative_error": 1e-15,
                                                                "max_absolute_error": 0.0})
        benchmark.record(self.st, "ipcc", "IPCC 2021 GWP100", {"passed": False, "n": 14, "max_relative_difference": 0.01,
                                                               "max_absolute_difference": 0.3})
        benchmark.record_ecoinvent(self.st, {"by_category": [
            {"family": "EF v3.1", "category": "climate change", "n": 100, "median": 1e-5, "max": 0.05,
             "within_0_1": 100.0, "within_1": 100.0},
            {"family": "EF v3.1", "category": "land use", "n": 100, "median": 2.0, "max": 14.0, "within_0_1": 40.0,
             "within_1": 60.0}], "databases_compared": ["ecoinvent 3.11 cut-off"]})
        rows = {r["check"]: r for r in benchmark.centre(self.st)["rows"]}
        self.assertEqual(rows["Calculation core: 35 systems with exact answers"]["status"], "Validated")
        self.assertEqual(rows["IPCC 2021 GWP100 (built-in method)"]["status"], "Deviations")
        ef = [r for k, r in rows.items() if k.startswith("EF v3.1")][0]
        self.assertEqual(ef["status"], "Deviations")              # 70 % within 0.1 %: not validated
        self.assertIn("land use", ef["note"])

    def test_package_checks(self):
        import regional
        regional.import_factors(self.st, "AWARE", "location,agri,non_agri,unknown\nFR,10,5,8\nES,40,30\n",
                                source="")
        p = {x["package"]: x for x in benchmark.package_checks(self.st)}["AWARE"]
        self.assertEqual(p["status"], "Package incomplete")
        txt = " ".join(p["problems"])
        self.assertIn("GLO", txt)
        self.assertIn("all three uses", txt)
        self.assertIn("not named", txt)
        regional.import_factors(self.st, "AWARE", "location,agri,non_agri,unknown\nFR,10,5,8\nGLO,45,20,43\n",
                                source="AWARE 2.0, WULCA, test copy")
        p = {x["package"]: x for x in benchmark.package_checks(self.st)}["AWARE"]
        self.assertEqual(p["status"], "Package checked", p)
        rows = [r for r in benchmark.centre(self.st)["rows"] if r["check"].startswith("AWARE")]
        self.assertEqual(rows[0]["status"], "Package checked")
        self.assertIn("not compared", rows[0]["note"])

    def test_excel(self):
        p = os.path.join(self.dir, "c.xlsx")
        benchmark.excel(p, benchmark.centre(self.st))
        self.assertTrue(os.path.getsize(p) > 1000)


if __name__ == "__main__":
    unittest.main()
