"""Cyclia 1.10, database management: suppliers chosen by geography with ecoinvent's linking rules, a log of linking
decisions that can each be undone, the extended database check, dataset provenance, and imports that reproduce the
regression snapshot."""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import calc  # noqa: E402
import dbquality  # noqa: E402
import geography as geo  # noqa: E402
import linking  # noqa: E402
from test_v138 import Base  # noqa: E402


class TestGeography(unittest.TestCase):
    def test_containment(self):
        self.assertTrue(geo.contains("RER", "FR"))
        self.assertTrue(geo.contains("GLO", "BR"))
        self.assertTrue(geo.contains("CN", "CN-HB"))
        self.assertTrue(geo.contains("Europe without Switzerland", "FR"))
        self.assertFalse(geo.contains("Europe without Switzerland", "CH"))
        self.assertFalse(geo.contains("FR", "RER"))
        self.assertTrue(geo.contains("US", "NPCC, US only"))          # old ecoinvent name, read as US-NPCC
        self.assertIsNone(geo.faces("RoW"))
        self.assertFalse(geo.known("XX"))
        self.assertTrue(geo.known("RoW"))
        self.assertIn("BSD", geo.source())

    def test_ecoinvent_linking_rules(self):
        b = geo.best
        self.assertEqual(b("FR", ["FR", "RER", "RoW"])[:2], (0, "same location (FR)"))
        # the smallest region that contains the location
        self.assertEqual(b("FR", ["DE", "RER", "Europe without Switzerland", "RoW"])[0], 2)
        self.assertEqual(b("CN-HB", ["CN", "RAS", "GLO"])[0], 0)
        # RoW only where no other supplier covers the location
        self.assertEqual(b("CH", ["DE", "Europe without Switzerland", "RoW"])[0], 2)
        self.assertEqual(b("BR", ["DE", "RER", "RoW", "GLO"])[0], 2)
        self.assertEqual(b("FR", ["DE", "RER", "RoW"])[0], 1)
        # GLO last
        self.assertEqual(b("BR", ["DE", "RER", "GLO"])[0], 2)
        # nothing covers it
        self.assertIsNone(b("BR", ["DE", "RER"])[0])
        # a region only partly supplied by the others: RoW with a lower rank, left for review by auto-link
        i, why, rank = b("RER", ["CH", "DE", "RoW"])
        self.assertEqual((i, rank), (2, 2.5))
        self.assertIn("part of RER", why)
        # a supplier inside the location, or only overlapping it, is not a match
        self.assertEqual(geo.relation("RER", "FR")[0], "inside")
        self.assertEqual(geo.relation("RU", "RER")[0], "overlaps")


class LinkBase(Base):
    """A supplier database with electricity markets at DE, RER, Europe without Switzerland, RoW, and a user database
    whose datasets need electricity at FR, DE, CH, BR, RER and an unknown location."""

    def setUp(self):
        super().setUp()
        st = self.st
        st.x("INSERT INTO databases(name, source) VALUES('Sup','test')")
        self.sup = st.one("SELECT id FROM databases WHERE name='Sup'")["id"]
        st.x("INSERT INTO databases(name, source) VALUES('User','test')")
        self.user = st.one("SELECT id FROM databases WHERE name='User'")["id"]
        self.m = {}
        for loc in ("DE", "RER", "Europe without Switzerland", "RoW"):
            st.x("INSERT INTO activities(db_id,key,name,product,location,unit,production) VALUES(?,?,?,?,?,?,1)",
                 (self.sup, f"m-{loc}", "market for electricity, low voltage", "electricity, low voltage", loc, "kWh"))
            self.m[loc] = st.one("SELECT id FROM activities WHERE key=?", (f"m-{loc}",))["id"]
        self.u = {}
        for loc in ("FR", "DE", "CH", "BR", "RER", "XX"):
            st.x("INSERT INTO activities(db_id,key,name,product,location,unit,production) VALUES(?,?,?,?,?,?,1)",
                 (self.user, f"u-{loc}", f"widget production {loc}", "widget", loc, "kg"))
            aid = st.one("SELECT id FROM activities WHERE key=?", (f"u-{loc}",))["id"]
            self.u[loc] = aid
            st.x("INSERT INTO unlinked(db_id,output_id,product,unit,amount,location,reason) VALUES(?,?,?,?,?,?,"
                 "'no producer')", (self.user, aid, "electricity, low voltage", "MWh", 0.002, loc))
        st.x("INSERT INTO lib.activities_fts(activities_fts) VALUES('rebuild')")
        calc.invalidate()

    def supplier(self, loc):
        r = self.st.one("SELECT linked_to FROM unlinked WHERE db_id=? AND location=?", (self.user, loc))
        return r["linked_to"]


class TestGeographicLinking(LinkBase):
    def test_suggestions_rank_by_geography(self):
        s = linking.suggest(self.st, self.user, "electricity, low voltage", "MWh", location="FR")
        self.assertEqual(s[0]["location"], "Europe without Switzerland")
        self.assertEqual(s[0]["geography"], "contains")
        self.assertEqual(s[0]["factor"], 1000.0)
        bad = next(x for x in s if x["location"] == "DE")
        self.assertEqual(bad["geography"], "other")
        # CH: "Europe without Switzerland" excludes it, RER contains it, and RoW is not for CH because RER covers it
        s = linking.suggest(self.st, self.user, "electricity, low voltage", "MWh", location="CH")
        self.assertEqual(s[0]["location"], "RER")
        self.assertEqual(next(x for x in s if x["location"] == "RoW")["geography"], "other")
        s = linking.suggest(self.st, self.user, "electricity, low voltage", "MWh", location="BR")
        self.assertEqual(s[0]["location"], "RoW")

    def test_auto_link_follows_ecoinvent_rules(self):
        r = linking.auto_link(self.st, self.user, author="tester")
        self.assertEqual(self.supplier("FR"), self.m["Europe without Switzerland"])
        self.assertEqual(self.supplier("DE"), self.m["DE"])
        self.assertEqual(self.supplier("CH"), self.m["RER"])
        self.assertEqual(self.supplier("BR"), self.m["RoW"])
        self.assertIsNone(self.supplier("XX"))                      # location unknown to the topology: left for review
        self.assertEqual(self.supplier("RER"), self.m["RER"])
        self.assertEqual(r["auto_linked"], 5)
        self.assertEqual(r["by_rule"], {"same location": 2, "containing region": 2, "rest of the world": 1})
        self.assertEqual(r["left_for_review"], 1)
        self.assertEqual(r["review"][0]["location"], "XX")
        # the conversion MWh -> kWh is applied to the matrix
        t = self.st.one("SELECT amount FROM tech WHERE output_id=?", (self.u["FR"],))
        self.assertAlmostEqual(t["amount"], 2.0)

    def test_decisions_are_logged_and_undone(self):
        st = self.st
        linking.auto_link(st, self.user, author="tester")
        log = linking.log(st, self.user)
        self.assertEqual(len(log), 5)
        fr = next(x for x in log if x["location"] == "FR")
        self.assertEqual((fr["method"], fr["author"], fr["target_location"]),
                         ("automatic", "tester", "Europe without Switzerland"))
        self.assertIn("contains FR", fr["rule"])
        # the user overrides FR with RER by hand, then undoes it: back to the automatic choice, factor included
        linking.link(st, self.user, "electricity, low voltage", "MWh", self.m["RER"], location="FR", author="me")
        self.assertEqual(self.supplier("FR"), self.m["RER"])
        manual = linking.log(st, self.user)[0]
        self.assertEqual((manual["method"], manual["rule"]), ("manual", "RER contains FR"))
        with self.assertRaises(ValueError):
            linking.undo(st, fr["id"])                              # a later decision changed these inputs
        linking.undo(st, manual["id"], author="me")
        self.assertEqual(self.supplier("FR"), self.m["Europe without Switzerland"])
        self.assertAlmostEqual(st.one("SELECT amount FROM tech WHERE output_id=?", (self.u["FR"],))["amount"], 2.0)
        with self.assertRaises(ValueError):
            linking.undo(st, manual["id"])                          # undone already
        # undoing the automatic link leaves the input unlinked, as before it
        linking.undo(st, fr["id"])
        self.assertIsNone(self.supplier("FR"))
        self.assertIsNone(st.one("SELECT amount FROM tech WHERE output_id=?", (self.u["FR"],)))
        # an unlink is a decision too
        linking.unlink(st, self.user, "electricity, low voltage", "MWh", location="DE")
        un = linking.log(st, self.user)[0]
        self.assertEqual(un["action"], "unlink")
        linking.undo(st, un["id"])
        self.assertEqual(self.supplier("DE"), self.m["DE"])
        actions = [x["action"] for x in linking.log(st, self.user)]
        self.assertEqual(actions.count("undo"), 3)

    def test_deleting_the_supplier_database_is_recorded(self):
        st = self.st
        linking.auto_link(st, self.user)
        st.delete_database(self.sup)
        log = linking.log(st, self.user)
        gone = [x for x in log if x["method"] == "database deleted"]
        self.assertEqual(sum(x["n"] for x in gone), 5)
        self.assertFalse(any(x["can_undo"] for x in gone))
        self.assertIsNone(self.supplier("FR"))

    def test_database_check_and_provenance(self):
        st = self.st
        linking.auto_link(st, self.user)
        # a manual link outside the geography rules is flagged
        linking.link(st, self.user, "electricity, low voltage", "MWh", self.m["DE"], location="FR")
        calc.invalidate()
        v = calc.validate_database(st, self.user)
        by = {x["key"]: x for x in v["statuses"]}
        self.assertEqual(by["links"]["level"], "warning")
        self.assertEqual(by["links"]["outside_geography"], 1)
        self.assertIn("FR -> DE (1)", by["links"]["outside_examples"])
        self.assertEqual(by["geography"]["unknown_locations"], [{"location": "XX", "datasets": 1}])
        self.assertEqual(by["provenance"]["level"], "warning")         # built in the test: no fingerprint
        self.assertEqual(by["duplicates"]["level"], "ok")
        p = dbquality.dataset_provenance(st, self.u["FR"])
        self.assertEqual(p["dataset"]["key"], "u-FR")
        self.assertEqual(p["inputs_linked_across"][0]["supplier_location"], "DE")
        self.assertEqual(p["inputs_linked_across"][0]["decision"]["method"], "manual")
        path = os.path.join(self.dir, "check.xlsx")
        dbquality.excel(path, v, linking.log(st, self.user))
        from openpyxl import load_workbook
        wb = load_workbook(path)
        self.assertEqual(wb.sheetnames, ["Checks", "Details", "Linking decisions"])
        self.assertEqual(wb["Checks"].max_row, len(v["statuses"]) + 3)


class TestApi(unittest.TestCase):
    def test_routes(self):
        from test_features import Api
        d = tempfile.mkdtemp()
        api = Api(d)
        try:
            api("POST", "/api/settings", {"author": "Tester"})
            api("POST", "/api/projects", {"name": "P"})
            st = api.st.store
            st.x("INSERT INTO databases(name, source) VALUES('Sup','test')")
            sup = st.one("SELECT id FROM databases WHERE name='Sup'")["id"]
            st.x("INSERT INTO databases(name, source) VALUES('User','test')")
            user = st.one("SELECT id FROM databases WHERE name='User'")["id"]
            st.x("INSERT INTO activities(db_id,key,name,product,location,unit,production) VALUES(?,?,?,?,?,?,1)",
                 (sup, "m-RER", "market for heat", "heat", "RER", "MJ"))
            st.x("INSERT INTO activities(db_id,key,name,product,location,unit,production) VALUES(?,?,?,?,?,?,1)",
                 (user, "u-FR", "drying FR", "dried thing", "FR", "kg"))
            uid = st.one("SELECT id FROM activities WHERE key='u-FR'")["id"]
            st.x("INSERT INTO unlinked(db_id,output_id,product,unit,amount,location) VALUES(?,?,?,?,?,?)",
                 (user, uid, "heat", "MJ", 3.0, "FR"))
            st.x("INSERT INTO lib.activities_fts(activities_fts) VALUES('rebuild')")
            calc.invalidate()
            r = api("POST", f"/api/databases/{user}/autolink", {})
            self.assertEqual(r["by_rule"], {"containing region": 1})
            log = api("GET", f"/api/databases/{user}/link-log")["log"]
            self.assertEqual((log[0]["author"], log[0]["rule"]), ("Tester", "RER contains FR"))
            pv = api("GET", f"/api/activities/{uid}/provenance")
            self.assertEqual(pv["inputs_linked_across"][0]["decision"]["method"], "automatic")
            self.assertEqual(pv["geography"], "FR")
            x = api("POST", "/api/export/database-check", {"db_id": user, "path": os.path.join(d, "c.xlsx")})
            self.assertTrue(os.path.exists(x["path"]))
            r = api("POST", f"/api/link-log/{log[0]['id']}/undo", {})
            self.assertEqual(r["restored"], 1)
            r = api("POST", f"/api/link-log/{log[0]['id']}/undo", {}, ok=False)
            self.assertEqual(r["_code"], 400)
            r = api("GET", "/api/activities/999999/provenance", ok=False)
            self.assertEqual(r["_code"], 400)
        finally:
            api.close()
            calc.invalidate()
            shutil.rmtree(d, ignore_errors=True)


class TestImportsReproduceTheSnapshot(unittest.TestCase):
    """The same file imported into two libraries gives bit-identical results, and an import stopped by the staging
    checks leaves the library exactly as it was."""

    def snap(self, st):
        import regression
        calc.invalidate()
        return regression.snapshot(st, models=False)

    def test_reimport_and_rollback(self):
        import regression
        import staging
        from importers import jsonld, lcia
        from store import Workspace
        from test_v138 import ex, olca_zip
        snaps, dirs = [], []
        try:
            for _ in range(2):
                d = tempfile.mkdtemp()
                dirs.append(d)
                ws = Workspace(d)
                st = ws.create("P")
                lcia.install_builtin(st)
                z = os.path.join(d, "lib.zip")
                olca_zip(z, [("s", "steel making", "fs", [ex("fe", "ELEMENTARY_FLOW", 1.5, False)]),
                             ("b", "bolt making", "fb", [ex("fe", "ELEMENTARY_FLOW", 2.0, False),
                                                         ex("fs", "PRODUCT_FLOW", 0.3, True, provider="s")])])
                staging.staged(st, d, lambda s, p: jsonld.import_jsonld(s, z, "Lib", p))
                snaps.append(self.snap(st))
                if len(snaps) == 2:
                    before = json.dumps(snaps[1]["datasets"], sort_keys=True)
                    bad = os.path.join(d, "bad.zip")
                    olca_zip(bad, [("x", "broken", "fx", [ex("fe", "ELEMENTARY_FLOW", float("inf"), False)])])
                    with self.assertRaises(ValueError):
                        staging.staged(st, d, lambda s, p: jsonld.import_jsonld(s, bad, "Bad", p))
                    self.assertEqual(json.dumps(self.snap(st)["datasets"], sort_keys=True), before)
                    self.assertEqual([x["name"] for x in st.databases()], ["Lib"])
                ws.close_all()
            rep = regression.compare(snaps[0], snaps[1], rtol=0, atol_share=0)
            self.assertTrue(rep["passed"], regression.report_text(rep))
            self.assertGreater(rep["values_compared"], 0)
        finally:
            calc.invalidate()
            for d in dirs:
                shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()


class TestIterativeRefinement(unittest.TestCase):
    """1.10.0: every solve of the library matrix adds one step of iterative refinement. On a badly scaled system
    the plain LU solution of a component far smaller than the others can be wrong, even in sign; the refined one is
    right (the case of the ecoinvent 3.13 benchmark: 180 tiny 'biotic resources' results)."""

    def system(self):
        import numpy as np
        import scipy.sparse as sp
        from scipy.sparse.linalg import splu
        n = 60
        rng = np.random.default_rng(7)
        A = sp.lil_matrix((n, n))
        for i in range(n):
            A[i, i] = 1.0
        for j in range(1, n):                # a chain of suppliers with large and small amounts
            A[j - 1, j] = -rng.uniform(0.5, 2.0) * (1e6 if j % 7 == 0 else 1.0)
            A[0, j] = -rng.uniform(0.0, 1e-9)
        A = A.tocsc()

        class MC:
            pass
        mc = MC()
        mc.A, mc.lu, mc.n = A, splu(A), n
        mc.t_rows, mc.t_cols = A.nonzero()
        return mc, A

    def test_refined_solution_has_a_smaller_residual(self):
        import numpy as np
        mc, A = self.system()
        mc.reached = lambda d: np.ones(mc.n, dtype=bool)
        f = np.zeros(mc.n)
        f[-1] = 1.0
        plain = mc.lu.solve(f)
        refined = calc.MatrixCache.solve(mc, f)
        r_plain = np.abs(f - A @ plain).max()
        r_ref = np.abs(f - A @ refined).max()
        self.assertLessEqual(r_ref, r_plain)
        y = calc.solve_transposed(mc, np.ones(mc.n))
        self.assertAlmostEqual(float(y @ f), float(np.ones(mc.n) @ refined), delta=1e-9 * abs(float(y @ f)))

    def test_an_explicit_lu_is_not_refined_against_another_matrix(self):
        import numpy as np
        from scipy.sparse.linalg import splu
        mc, A = self.system()
        mc.reached = lambda d: np.ones(mc.n, dtype=bool)
        other = splu((A * 2).tocsc())
        f = np.zeros(mc.n)
        f[3] = 1.0
        np.testing.assert_array_equal(calc.MatrixCache.solve(mc, f, other), other.solve(f))


class TestPublicationUsesRefinedValues(Base):
    def test_refined(self):
        import benchmark
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Summary"
        for k, v in (("Cyclia", "1.9.2"), ("Date", "2026-11-17"), ("Database", "ecoinvent 3.13 cutoff"),
                     ("Database version", "3.13"), ("System model", "cutoff")):
            ws.append([k, v])
        bc = wb.create_sheet("By category")
        bc.append(["Family", "Category", "Indicator", "Unit", "Results", "Median |dev| %", "95th pct |dev| %",
                   "Max |dev| %", "Within 0.1 %", "Within 1 %", "Flows used without a factor", "Hint"])
        bc.append(["Ecological Scarcity 2021", "natural resources", "biotic resources", "UBP", 1, 0, 0, 0, 100, 100, 0,
                   None])
        ar = wb.create_sheet("All results")
        ar.append(["Group", "Dataset", "Location", "Product", "Category", "Indicator", "ecoinvent", "Cyclia",
                   "Deviation %", "Note", "Relative difference before the round-off rule %",
                   "Sum of absolute contributions", "Cyclia, adjoint solution", "Cyclia, refined solution"])
        ar.append(["O", "fodder yeast", "CH", "p", "natural resources", "biotic resources", 0.008, 0.008, 0.0, "",
                   0.0, 0.008, 0.008, 0.008])
        ar.append(["O", "irrigation", "GLO", "p", "natural resources", "biotic resources", 7.0353e-17, -4.4e-15, None,
                   "below numerical resolution: ...", -6354.0, 4.5e-15, -4.3e-15, 7.0354e-17])
        p = os.path.join(self.dir, "w.xlsx")
        wb.save(p)
        files = benchmark.publication_from_workbook(p)
        es = files["ecological-scarcity-2021-ecoinvent-3-13-cutoff.md"]
        self.assertIn("**Ecological Scarcity 2021**: Validated. 100.00 % of 2 results", es)
        self.assertIn("1 results that the run reported as below numerical resolution are compared with its refined", es)
