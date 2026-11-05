"""Regression tests for Cyclia 1.3.8 (database integrity release).

Each test reproduces a finding of the third database audit (of 1.3.6) or checks a 1.3.8 change: non-finite values in
unresolved inputs, an explicit openLCA provider outside the import, the scope of the database check, the explorer
query, streaming imports, the import integrity report and rollback."""
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import calc  # noqa: E402
import linking  # noqa: E402
import server  # noqa: E402
import staging  # noqa: E402
from importers import jsonld, lcia, other_formats  # noqa: E402
from store import Workspace  # noqa: E402
from test_v136 import SP_HEAD, sp_process  # noqa: E402


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


def olca_zip(path, processes, extra_flows=()):
    """A minimal openLCA JSON-LD zip. processes: (id, name, reference flow, [exchanges])."""
    z = zipfile.ZipFile(path, "w")
    put = lambda pth, o: z.writestr(pth, json.dumps(o))
    put("unit_groups/ug.json", {"@id": "ug", "units": [{"@id": "kg", "name": "kg", "conversionFactor": 1, "isRefUnit": True}]})
    put("flow_properties/mass.json", {"@id": "mass", "unitGroup": {"@id": "ug"}})
    fl = [("fs", "steel", "PRODUCT_FLOW", "P"), ("fb", "bolt", "PRODUCT_FLOW", "P"),
          ("fe", "Carbon dioxide, fossil", "ELEMENTARY_FLOW", "Elementary flows/Emission to air/unspecified")] + list(extra_flows)
    for fid, name, ft, cat in fl:
        put(f"flows/{fid}.json", {"@id": fid, "name": name, "flowType": ft, "category": cat,
                                  "flowProperties": [{"flowProperty": {"@id": "mass"}, "conversionFactor": 1, "isRefFlowProperty": True}]})
    for pid, name, ref, exs in processes:
        put(f"processes/{pid}.json", {"@id": pid, "name": name, "exchanges": [ex(ref, "PRODUCT_FLOW", 1, False, ref=True)] + exs})
    z.close()
    return path


def ex(f, ft, amt, inp, ref=False, prov=None, **more):
    e = {"flow": {"@id": f, "flowType": ft}, "amount": amt, "isInput": inp, "isQuantitativeReference": ref,
         "unit": {"@id": "kg"}, "flowProperty": {"@id": "mass"}}
    if prov:
        e["defaultProvider"] = {"@id": prov, "name": "steel from another database"}
    e.update(more)
    return e


# ------------------------------------------------------------------------------------ A: non-finite values
class TestNonFinite(Base):
    def test_infinite_unresolved_amount_is_rejected_by_the_staged_import(self):
        """Audit P0 A: an unresolved supplier exchange of 1e309 was stored as Infinity and accepted."""
        tmp = os.path.join(self.dir, "inf.zip")
        # json.dumps writes 1e309 as Infinity, which Python's json reads back as inf (what openLCA files can contain)
        olca_zip(tmp, [("b", "bolt making", "fb", [ex("fx", "PRODUCT_FLOW", 1e309, True)])],
                 extra_flows=[("fx", "missing supply", "PRODUCT_FLOW", "P")])
        with self.assertRaises(ValueError) as cm:
            staging.staged(self.st, self.dir, lambda s, p: jsonld.import_jsonld(s, tmp, "Inf", p))
        self.assertIn("unresolved input amounts", str(cm.exception))
        self.assertFalse(any(d["name"] == "Inf" for d in self.st.databases()))

    def test_integrity_covers_uncertainty_production_and_types(self):
        b = other_formats._Builder(self.st, "Bad", "test")
        a1 = b.activity("a", "a", "a", "GLO", "kg")
        b.activity("z", "z", "z", "GLO", "kg", production=1.0)
        b.emission(a1, "u-1", "Carbon dioxide, fossil", "air", "", "kg", 1.0, (2, float("inf"), None, None))
        b.input(a1, "nothing", "kg", 2.0, "", (9, None, None, None))
        b.write(lambda *a: None)
        db = self.st.databases()[0]["id"]
        with self.st.lock:
            self.st.conn.execute("UPDATE activities SET production=0 WHERE key='z'")
            self.st.conn.commit()
        n = staging.integrity(self.st, db)
        self.assertEqual(n.get("uncertainty parameters"), 1)
        self.assertEqual(n.get("uncertainty types"), 1)
        self.assertEqual(n.get("production amounts"), 1)
        v = calc.validate_database(self.st, db)
        self.assertEqual(v["statuses"][0]["level"], "error")
        self.assertIn("production amounts", v["statuses"][0]["message"])

    def test_link_refuses_non_finite_inputs(self):
        b = other_formats._Builder(self.st, "Bad", "test")
        a1 = b.activity("a", "a", "a", "GLO", "kg")
        b.activity("s", "steel", "steel", "GLO", "kg")
        b.input(a1, "iron", "kg", 1.0)
        b.write(lambda *a: None)
        db = self.st.databases()[0]["id"]
        sup = self.st.one("SELECT id FROM activities WHERE key='s'")["id"]
        with self.st.lock:
            self.st.conn.execute("UPDATE unlinked SET amount=?", (float("inf"),))
            self.st.conn.commit()
        with self.assertRaises(ValueError) as cm:
            linking.link(self.st, db, "iron", "kg", sup)
        self.assertIn("not a finite number", str(cm.exception))
        self.assertEqual(self.st.one("SELECT COUNT(*) AS n FROM tech")["n"], 0)


# ------------------------------------------------------------------------------------ B: explicit provider
class TestExternalProvider(Base):
    def _zip(self):
        return olca_zip(os.path.join(self.dir, "ext.zip"), [
            ("s1", "steel, internal route", "fs", [ex("fe", "ELEMENTARY_FLOW", 1.0, False)]),
            ("b", "bolt making", "fb", [ex("fs", "PRODUCT_FLOW", 1, True, prov="ext-steel-uuid")])])

    def test_external_default_provider_is_not_replaced(self):
        """Audit P0 B: the sole internal producer was linked although the dataset named an external provider."""
        res = jsonld.import_jsonld(self.st, self._zip(), "J")
        self.assertEqual(res["external_provider_inputs"], 1)
        self.assertEqual(self.st.one("SELECT COUNT(*) AS n FROM tech")["n"], 0)
        u = self.st.one("SELECT reason, link_key FROM unlinked")
        self.assertTrue(u["reason"].startswith("default provider not in this import"))
        self.assertIn("steel from another database", u["reason"])
        self.assertEqual(u["link_key"], "ext-steel-uuid")
        db = self.st.one("SELECT id FROM databases WHERE name='J'")["id"]
        r = linking.auto_link(self.st, db)
        self.assertEqual(r["auto_linked"], 0)
        self.assertEqual(self.st.one("SELECT COUNT(*) AS n FROM tech")["n"], 0)

    def test_named_provider_in_another_database_is_suggested_first(self):
        b = other_formats._Builder(self.st, "Other", "test")
        b.activity("ext-steel-uuid", "steel, external", "steel", "GLO", "kg")
        b.activity("x", "steel, unrelated", "steel", "GLO", "kg")
        b.write(lambda *a: None)
        jsonld.import_jsonld(self.st, self._zip(), "J")
        db = self.st.one("SELECT id FROM databases WHERE name='J'")["id"]
        s = linking.suggest(self.st, db, "steel", "kg")
        self.assertEqual(s[0]["name"], "steel, external")
        self.assertTrue(s[0]["named_provider"])

    def test_without_default_provider_the_single_producer_is_linked(self):
        p = olca_zip(os.path.join(self.dir, "one.zip"), [
            ("s1", "steel", "fs", [ex("fe", "ELEMENTARY_FLOW", 1.0, False)]),
            ("b", "bolt making", "fb", [ex("fs", "PRODUCT_FLOW", 1, True)])])
        res = jsonld.import_jsonld(self.st, p, "J")
        self.assertEqual(res["external_provider_inputs"], 0)
        self.assertEqual(self.st.one("SELECT COUNT(*) AS n FROM tech")["n"], 1)


# ------------------------------------------------------------------------------------ C: database check scope
class TestCheckScope(Base):
    def test_flow_coverage_of_the_selected_database_only(self):
        """Audit P1 C: DB A (one CO2 flow with a factor) was reported as 1 of 2 flows (50 %)."""
        lcia.install_builtin(self.st)
        a = other_formats._Builder(self.st, "A", "test")
        i = a.activity("a", "a", "a", "GLO", "kg")
        a.emission(i, "co2", "Carbon dioxide, fossil", "air", "unspecified", "kg", 1.0)
        a.write(lambda *x: None)
        b = other_formats._Builder(self.st, "B", "test")
        j = b.activity("b", "b", "b", "GLO", "kg")
        b.emission(j, "odd", "Unobtainium dust", "air", "unspecified", "kg", 1.0)
        b.write(lambda *x: None)
        db_a = self.st.one("SELECT id FROM databases WHERE name='A'")["id"]
        v = calc.validate_database(self.st, db_a)
        self.assertEqual(v["flows_used"], 1)
        self.assertEqual(v["flows_without_any_factor"], 0)
        flows = next(s for s in v["statuses"] if s["key"] == "flows")
        self.assertAlmostEqual(flows["coverage"], 1.0)
        self.assertEqual(v["datasets"], 1)
        lc = next(s for s in v["statuses"] if s["key"] == "lcia")
        self.assertTrue(all(f["flows_with_factor"] <= 1 for f in lc["families"]))
        whole = calc.validate_database(self.st)
        self.assertEqual(whole["flows_used"], 2)


# ------------------------------------------------------------------------------------ explorer
class TestExplorer(Base):
    def _many(self):
        b = other_formats._Builder(self.st, "Big", "test", version="3.10", system_model="cut-off")
        for k in range(150):
            i = b.activity(f"k{k:03d}", f"aaa {k:03d}", f"p{k}", "DE" if k % 2 else "FR", "kg")
            b.emission(i, "co2", "Carbon dioxide, fossil", "air", "", "kg", 1.0)
        z = b.activity("zzz", "zzz last dataset", "zz", "CH", "kg")
        b.input(z, "missing", "kg", 1.0)
        b.write(lambda *a: None)

    def q(self, **kw):
        return server.explore_search(type("S", (), {"store": self.st})(), {}, {k: [str(v)] for k, v in kw.items()})

    def test_unresolved_filter_is_in_the_query(self):
        """Audit: the unresolved filter ran on the first 100 rows only, so 'zzz' never showed."""
        self._many()
        r = self.q(unresolved=1)
        self.assertEqual(r["total"], 1)
        self.assertEqual(r["results"][0]["name"], "zzz last dataset")
        self.assertEqual(r["results"][0]["unresolved"], 1)

    def test_paging_filters_and_export(self):
        self._many()
        p1, p2 = self.q(limit=50), self.q(limit=50, offset=150)
        self.assertEqual(p1["total"], 151)
        self.assertEqual(len(p1["results"]), 50)
        self.assertEqual(len(p2["results"]), 1)
        self.assertEqual(self.q(location="de")["total"], 75)
        self.assertEqual(self.q(system_model="cut")["total"], 151)
        self.assertEqual(self.q(version="3.9")["total"], 0)
        self.assertEqual(self.q(flow="carbon dioxide")["total"], 150)
        ids = [x["id"] for x in p1["results"][:3]]
        st = type("S", (), {"store": self.st, "exports": self.dir})()
        out = server.explore_export(st, {"ids": ids}, {})
        from openpyxl import load_workbook
        wb = load_workbook(out["path"])
        self.assertEqual(wb["Datasets"].max_row, 4)
        self.assertEqual(wb["Elementary flows"].max_row, 4)


# ------------------------------------------------------------------------------------ streaming, report, rollback
class TestStreamingAndRecovery(Base):
    def test_simapro_large_file_is_streamed_and_identical(self):
        n = 600
        txt = SP_HEAD + "".join(sp_process(f"Product {k}", 0.5 + k, ident=f"ID{k}",
                                           inputs=f"Product {k - 1};kg;1;Undefined;0;0;0;" if k else "") for k in range(n))
        p = os.path.join(self.dir, "big.csv")
        with open(p, "w", encoding="cp1252") as fh:
            fh.write(txt.replace("Product 5;", "Prodüct 5;"))
        old = other_formats._Builder.BATCH
        other_formats._Builder.BATCH = 50   # several batches of elementary exchanges
        try:
            res = staging.staged(self.st, self.dir, lambda s, pr: other_formats.import_simapro_csv(s, p, "SP", pr))
        finally:
            other_formats._Builder.BATCH = old
        self.assertEqual(res["activities"], n)
        self.assertEqual(res["elementary_exchanges"], n)
        self.assertEqual(self.st.one("SELECT COUNT(*) AS n FROM tech")["n"], n - 1)
        self.assertTrue(self.st.one("SELECT 1 AS x FROM activities WHERE name='Prodüct 5'"))
        rep = res["integrity_report"]
        self.assertEqual(rep["result"], "passed")
        self.assertEqual(rep["contents"]["datasets"], n)
        self.assertLess(rep["matrix_residual"], 1e-9)

    def test_failure_while_reading_leaves_nothing(self):
        def broken(s, pr):
            b = other_formats._Builder(s, "Half", "test")
            b.activity("a", "a", "a", "GLO", "kg")
            raise RuntimeError("disk read error")
        with self.assertRaises(RuntimeError):
            staging.staged(self.st, self.dir, broken)
        self.assertEqual(self.st.databases(), [])
        self.assertFalse(any(x.startswith("cyclia-staging") for x in os.listdir(self.dir)))

    def test_failure_during_merge_rolls_back(self):
        """Recovery: an error inside the merge transaction leaves the library exactly as before."""
        b = other_formats._Builder(self.st, "Keep", "test")
        b.activity("k", "kept", "kept", "GLO", "kg")
        b.write(lambda *a: None)
        before = (self.st.one("SELECT COUNT(*) AS n FROM activities")["n"], len(self.st.databases()))
        real = staging.merge

        def failing(lib, store):
            store.conn.execute("CREATE TEMP TRIGGER boom BEFORE INSERT ON bio BEGIN SELECT RAISE(ABORT, 'boom'); END")
            try:
                return real(lib, store)
            finally:
                store.conn.execute("DROP TRIGGER IF EXISTS temp.boom")
        staging.merge = failing

        def imp(s, pr):
            x = other_formats._Builder(s, "New", "test")
            i = x.activity("n", "n", "n", "GLO", "kg")
            x.emission(i, "co2", "Carbon dioxide, fossil", "air", "", "kg", 1.0)
            return x.write(pr)
        try:
            with self.assertRaises(Exception):
                staging.staged(self.st, self.dir, imp)
        finally:
            staging.merge = real
        self.assertEqual((self.st.one("SELECT COUNT(*) AS n FROM activities")["n"], len(self.st.databases())), before)
        # the library still works afterwards
        res = staging.staged(self.st, self.dir, imp)
        self.assertEqual(res["activities"], 1)


if __name__ == "__main__":
    unittest.main()
