"""Scientific Benchmark Centre: the IPCC check, recording of runs, and the rule that only runs count."""
import json
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
             "within_1": 60.0}], "databases_compared": [{"name": "ecoinvent", "version": "3.11", "system_model": "cut-off"}]})
        rows = {r["check"]: r for r in benchmark.centre(self.st)["rows"]}
        self.assertEqual(rows["Calculation core: 35 systems with exact answers"]["status"], "Validated")
        self.assertEqual(rows["IPCC 2021 GWP100 (built-in method)"]["status"], "Deviations")
        ef = [r for k, r in rows.items() if k.startswith("EF v3.1")][0]
        self.assertEqual(ef["status"], "Deviations")              # 70 % within 0.1 %: not validated
        self.assertIn("land use", ef["note"])
        # the benchmark gives the compared databases as records (name, version, system model)
        self.assertIn("ecoinvent (3.11, cut-off)", json.dumps(ef))

    def bench(self, fam, cats, version="3.11"):
        benchmark.record_ecoinvent(self.st, {
            "by_category": [dict(c, family=fam, indicator=c["category"], unit="u") for c in cats],
            "databases_compared": [{"name": "ecoinvent", "version": version, "system_model": "cut-off"}],
            "datasets_matched": 400, "datasets_in_file": 21000})

    def test_publication(self):
        self.assertEqual(benchmark.publication(self.st), {})
        with self.assertRaises(ValueError):
            benchmark.write_publication(self.st, os.path.join(self.dir, "pub"))
        good = {"n": 400, "median": 1e-6, "p95": 1e-4, "max": 0.02, "within_0_1": 100.0, "within_1": 100.0,
                "median_signed": 0.0}
        self.bench("ReCiPe 2016 v1.03, midpoint (H)", [dict(good, category="climate change"),
                                                       dict(good, category="water use")])
        self.bench("CML v4.8 2016", [dict(good, category="acidification"),
                                     dict(good, category="eutrophication", median=3.0, max=9.0, within_0_1=20.0,
                                          within_1=40.0, median_signed=-3.0, hint="Cyclia is lower for most datasets")])
        self.bench("IPCC 2021", [dict(good, category="climate change: GWP 100a")])
        self.bench("EF v3.1", [dict(good, category="land use")])
        files = benchmark.publication(self.st, "1.9.0")
        self.assertEqual(sorted(files), ["README.md", "cml-ia-ecoinvent-3-11-cut-off.md", "ef-ecoinvent-3-11-cut-off.md",
                                         "ipcc-ecoinvent-3-11-cut-off.md", "recipe-ecoinvent-3-11-cut-off.md"])
        rec = files["recipe-ecoinvent-3-11-cut-off.md"]
        self.assertIn("ReCiPe 2016 v1.03, midpoint (H)**: Validated", rec)
        self.assertIn("| water use |", rec)
        self.assertIn("No ecoinvent data is reproduced", rec)
        cml = files["cml-ia-ecoinvent-3-11-cut-off.md"]
        self.assertIn("Deviations", cml)
        self.assertIn("eutrophication: Cyclia is lower", cml)
        self.assertIn("| [CML-IA](cml-ia-ecoinvent-3-11-cut-off.md) | ecoinvent (3.11, cut-off) | 800 | Deviations",
                      files["README.md"])
        # statistics only: the record and the report hold no reference or Cyclia values
        runs = self.st.q("SELECT summary FROM benchmark_runs WHERE kind='ecoinvent'")
        for r in runs:
            sm = json.loads(r["summary"])
            self.assertNotIn("rows", sm)
            self.assertFalse([k for c in sm["categories"] for k in c if k in ("reference", "cyclia", "rows", "worst")])
        out = benchmark.write_publication(self.st, os.path.join(self.dir, "pub"))
        self.assertEqual(len(out), 5)
        with open(out[0], encoding="utf-8") as fh:
            self.assertTrue(fh.read().startswith("# "))

    def test_method_groups(self):
        g = benchmark.method_group
        self.assertEqual(g("ReCiPe 2016 Midpoint (H) V1.03"), "ReCiPe")
        self.assertEqual(g("CML-IA baseline"), "CML-IA")
        self.assertEqual(g("IPCC 2021 (incl. biogenic CO2)"), "IPCC")
        self.assertEqual(g("EF v3.1"), "EF")
        self.assertEqual(g("Environmental Footprint 3.1"), "EF")
        self.assertEqual(g("USEtox 2"), "USEtox 2")

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
