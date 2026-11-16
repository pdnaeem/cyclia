"""Full-library regression (1.9.0): every dataset under every impact category, every model and the factor matching of
the reference libraries shipped with Cyclia, against the snapshot committed in tests/data.

A failure here means a change in the engine, an importer or a reference library changed results. If the change is
intended, explain it in the CHANGELOG and rebuild the snapshot with: python engine/tools/regression.py reference"""
import json
import os
import shutil
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import calc  # noqa: E402
import regression  # noqa: E402
from store import Workspace  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN = os.path.join(HERE, "data", "reference_regression.json.gz")
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))


class TestRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        cls.ws = Workspace(cls.dir)
        cls.st = cls.ws.create("Reference")
        calc.invalidate()
        regression.build_reference(cls.st)
        cls.snap = regression.snapshot(cls.st, label="test")
        cls.golden = regression.load(GOLDEN)

    @classmethod
    def tearDownClass(cls):
        cls.ws.close_all()
        calc.invalidate()
        shutil.rmtree(cls.dir, ignore_errors=True)

    def test_reference_libraries_match_the_committed_snapshot(self):
        rep = regression.compare(self.golden, self.snap)
        self.assertTrue(rep["passed"], "\n" + regression.report_text(rep))
        # every dataset of both reference databases, every category, every model
        self.assertEqual(rep["values_compared"], len(self.golden["datasets"]) * len(self.golden["matching"])
                         + sum(len(v) for v in self.golden["models"].values()))
        self.assertGreaterEqual(len(self.golden["datasets"]), 60)
        self.assertGreaterEqual(len(self.golden["models"]), 7)
        self.assertFalse([m for m, v in self.golden["models"].items() if "error" in v])

    def test_transposed_solve_equals_one_solve_per_dataset(self):
        st = self.st
        mc = calc._cache.get(st)
        mids = [r["id"] for r in st.q("SELECT id FROM methods ORDER BY family, category, indicator")]
        scores, M = regression.dataset_scores(st, mids)
        for a in st.q("SELECT a.id, a.key, d.name db FROM activities a JOIN databases d ON d.id=a.db_id"):
            f = np.zeros(mc.n)
            f[mc.act_index[a["id"]]] = 1.0
            h = M.Q @ mc.solve(f)
            got = np.array(scores[(a["db"], a["key"])][4])
            self.assertTrue(np.array_equal(h == 0, got == 0), a["key"])          # exact zeros agree
            np.testing.assert_allclose(got, h, rtol=1e-10, atol=0)

    def test_model_results_are_those_of_the_calculation(self):
        m = self.st.models()[0]
        mids = [r["id"] for r in self.st.q("SELECT id FROM methods ORDER BY family, category, indicator")]
        r = calc.run(self.st, m["id"], mids, top=1)
        for x in r["results"]:
            self.assertEqual(self.snap["models"][m["name"]][regression._key(x)], regression._round(x["total"]))

    def test_snapshot_round_trip(self):
        p = os.path.join(self.dir, "s.json.gz")
        regression.save(self.snap, p)
        back = regression.load(p)
        self.assertTrue(regression.compare(self.snap, back, rtol=0, atol_share=0)["passed"])
        bad = os.path.join(self.dir, "x.json")
        with open(bad, "w") as fh:
            json.dump({"format": "other"}, fh)
        with self.assertRaises(ValueError):
            regression.load(bad)


class TestDetection(unittest.TestCase):
    """The comparison finds a change in a factor, in an exchange and in the library."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.ws = Workspace(self.dir)
        self.st = self.ws.create("R")
        calc.invalidate()
        regression.build_reference(self.st)
        self.ref = regression.snapshot(self.st, models=False)

    def tearDown(self):
        self.ws.close_all()
        calc.invalidate()
        shutil.rmtree(self.dir, ignore_errors=True)

    def again(self):
        calc.invalidate()
        return regression.compare(self.ref, regression.snapshot(self.st, models=False))

    def test_factor_change(self):
        r = self.st.one("SELECT method_id, flow_id, value FROM cfs WHERE value > 0 LIMIT 1")
        self.st.x("UPDATE cfs SET value=? WHERE method_id=? AND flow_id=?",
                  (r["value"] * (1 + 1e-6), r["method_id"], r["flow_id"]))
        rep = self.again()
        self.assertFalse(rep["passed"])
        self.assertEqual(len(rep["matching"]), 1)
        self.assertIn("fingerprint", rep["matching"][0]["changes"])
        self.assertGreater(rep["values_different"], 0)

    def test_exchange_change(self):
        t = self.st.one("SELECT rowid, amount FROM tech WHERE amount > 0 LIMIT 1")
        self.st.x("UPDATE tech SET amount=? WHERE rowid=?", (t["amount"] * 1.001, t["rowid"]))
        rep = self.again()
        self.assertFalse(rep["passed"])
        self.assertEqual(rep["matching"], [])
        self.assertGreater(rep["values_different"], 0)
        self.assertTrue(all(abs(d["change_percent"] or 1) < 1 for d in rep["differences"]))

    def test_unmatched_factor(self):
        r = self.st.one("SELECT method_id, flow_id FROM cfs LIMIT 1")
        self.st.x("DELETE FROM cfs WHERE method_id=? AND flow_id=?", (r["method_id"], r["flow_id"]))
        rep = self.again()
        ch = rep["matching"][0]["changes"]
        self.assertEqual(ch["flows_matched"][0] - 1, ch["flows_matched"][1])

    def test_round_off_is_not_a_difference(self):
        new = json.loads(json.dumps(self.ref))
        for d in new["datasets"].values():
            for c in d["scores"]:
                d["scores"][c] *= 1 + 1e-12
        self.assertTrue(regression.compare(self.ref, new)["passed"])


class TestTool(unittest.TestCase):
    def test_compare_exit_codes(self):
        import contextlib
        import importlib.util
        import io
        spec_path = os.path.join(os.path.dirname(HERE), "tools", "regression.py")
        spec = importlib.util.spec_from_file_location("regression_tool", spec_path)
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        d = tempfile.mkdtemp()
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                self.run_tool(tool, d)
        finally:
            shutil.rmtree(d, ignore_errors=True)
        self.assertIn("DIFFERENCES FOUND", out.getvalue())

    def run_tool(self, tool, d):
        self.assertEqual(tool.main(["compare", GOLDEN, GOLDEN]), 0)
        snap = regression.load(GOLDEN)
        k = next(iter(snap["datasets"]))
        c = next(c for c, v in snap["datasets"][k]["scores"].items() if v)
        snap["datasets"][k]["scores"][c] *= 1.01
        p = os.path.join(d, "changed.json")
        regression.save(snap, p)
        self.assertEqual(tool.main(["compare", GOLDEN, p]), 1)
        self.assertEqual(tool.main(["compare", GOLDEN, os.path.join(d, "missing.json")]), 2)


class TestApi(unittest.TestCase):
    def test_record_compare_and_publish(self):
        from importers import tutorial
        from test_features import Api
        d = tempfile.mkdtemp()
        api = Api(d)
        try:
            api("POST", "/api/projects", {"name": "Reg"})
            tutorial.install(api.st.store)
            calc.invalidate()
            p = os.path.join(d, "snap.json.gz")
            r = api.job("/api/regression/record", {"path": p})
            self.assertEqual(r["path"], p)
            self.assertGreater(r["datasets"], 30)
            rep = api.job("/api/regression/compare", {"path": p})
            self.assertTrue(rep["passed"], rep["text"])
            self.assertIn("PASSED", rep["text"])
            # a change in the library is found
            t = api.st.store.one("SELECT rowid, amount FROM tech WHERE amount > 0 LIMIT 1")
            api.st.store.x("UPDATE tech SET amount=? WHERE rowid=?", (t["amount"] * 2, t["rowid"]))
            calc.invalidate()
            rep = api.job("/api/regression/compare", {"path": p})
            self.assertFalse(rep["passed"])
            bad = api("POST", "/api/regression/compare", {"path": os.path.join(d, "none.json")}, ok=False)
            self.assertEqual(bad["_code"], 400)
            # no ecoinvent benchmark in this project: nothing to publish
            r = api("POST", "/api/benchmark/publish", {"folder": os.path.join(d, "pub")}, ok=False)
            self.assertIn("No ecoinvent benchmark", r["error"])
        finally:
            api.close()
            calc.invalidate()
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
