"""Supplier data requests (1.8.0): request workbook, filled response, preview without change, apply.

Reference system of test_custom_data (2.70 kg CO2-eq per kg of steel sheet). The supplier answers:
- CO2 1.8 kg (measured);
- solvent 12 000 mg (calculated, plausible 8 000 to 15 000 mg): 12 g x 0.005 = 0.06;
- electricity left empty (not answered, stays 1 kWh x 0.5 = 0.5);
- waste 'abc' (error, stays 0.2 x 1 = 0.2);
- avoided electricity in kg (error: not an energy unit, stays -0.1 x 0.5 = -0.05).
New total 1.8 + 0.5 + 0.2 + 0.06 - 0.05 = 2.51.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl  # noqa: E402

import custom_data as cd  # noqa: E402
import supplier  # noqa: E402
from test_custom_data import Base  # noqa: E402


class TestSupplierRequest(Base):
    def request(self, **kw):
        self.build()
        self.path = os.path.join(self.dir, "request.xlsx")
        self.rid = supplier.request_workbook(self.st, self.steel, self.path, "Rolling mill Ltd", "N. Rehman", **kw)
        return openpyxl.load_workbook(self.path)

    def fill(self, wb, answers, extra=()):
        wx = wb["Inputs and outputs"]
        for row, vals in answers.items():
            for col, v in vals.items():
                wx.cell(row + 1, col, v)
        wp = wb["Process"]
        wp.cell(4, 2, "A. Supplier")
        wp.cell(5, 2, "2026-03-01")
        wp.cell(6, 2, "2025")
        for i, e in enumerate(extra, start=2):
            for j, v in enumerate(e, start=1):
                wb["Other items"].cell(i, j, v)
        out = os.path.join(self.dir, "response.xlsx")
        wb.save(out)
        return out

    def rows(self, wb):
        wx = wb["Inputs and outputs"]
        # item names can repeat (electricity used and credited): key by type and item
        return {(wx.cell(i, 2).value[:5] + " " + wx.cell(i, 3).value): i - 1 for i in range(2, wx.max_row + 1)}

    def test_workbook_content(self):
        wb = self.request()
        self.assertEqual(wb.sheetnames, ["Read me", "Process", "Inputs and outputs", "Other items", "_cyclia"])
        self.assertEqual(wb["_cyclia"].sheet_state, "veryHidden")
        self.assertIn("1 kg of steel sheet", wb["Process"]["B2"].value)
        rows = self.rows(wb)
        self.assertEqual(len(rows), 5)
        self.assertIsNone(wb["Inputs and outputs"].cell(2, 5).value)      # current amounts not shown by default
        wb2 = openpyxl.load_workbook(self.path)
        self.assertTrue(wb2["Inputs and outputs"].protection.sheet)
        self.assertEqual(supplier.requests(self.st, self.steel)[0]["status"], "sent")

    def test_preview_changes_nothing_and_apply(self):
        wb = self.request()
        r = self.rows(wb)
        co2 = [k for k in r if "Carbon dioxide" in k][0]
        sol = [k for k in r if "Solvent X" in k][0]
        el = [k for k in r if k.startswith("Produ") and "electricity" in k]
        inc = [k for k in r if "incineration" in k][0]
        out = self.fill(wb, {r[co2]: {5: 1.8, 7: "measured"},
                             r[sol]: {5: "12000", 6: "mg", 7: "calculated", 8: 8000, 9: 15000, 10: "mass balance"},
                             r[inc]: {5: "abc"},
                             r[el[0]]: {5: 0.1, 6: "kg"}},
                        extra=[("emission", "Zinc to water", "0.3", "g", "from wastewater analysis")])
        before = self.calc(self.steel)["results"][0]["total"]
        pv = supplier.read_response(self.st, out)
        self.assertAlmostEqual(self.calc(self.steel)["results"][0]["total"], before, places=12)
        self.assertEqual(len(pv["changes"]), 2)
        self.assertEqual(len(pv["unanswered"]), 1)
        self.assertEqual(len(pv["errors"]), 2)
        self.assertEqual(pv["extra"][0]["description"], "Zinc to water")
        res = supplier.apply_response(self.st, out, author="me")
        self.assertEqual(res["applied"], 2)
        self.assertAlmostEqual(self.calc(self.steel)["results"][0]["total"], 2.51, places=12)
        e = self.st.one("SELECT * FROM custom_exchanges WHERE process_uuid=? AND target=?", (self.steel, self.solv))
        self.assertEqual((e["amount"], e["unit"], e["uncertainty"]), (12000, "mg", "triangular"))
        self.assertIn("Rolling mill Ltd", e["source"])
        self.assertIn("2026-03-01", e["source"])
        c = self.st.one("SELECT * FROM custom_exchanges WHERE process_uuid=? AND target=?", (self.steel, self.co2))
        self.assertEqual((c["uncertainty"], c["pedigree"]), ("pedigree", "[2, 2, 1, 1, 2]"))   # spread kept
        it = cd._item(self.st, self.steel, "process")
        self.assertEqual(it["data"]["time_period"], "2025")
        self.assertEqual(it["data"]["data_type"], "primary")
        self.assertIn("plant A, 2025", it["source"])                       # the earlier source is kept
        self.assertEqual(supplier.requests(self.st, self.steel)[0]["status"], "received")

    def test_line_changed_after_request_is_not_overwritten(self):
        wb = self.request()
        r = self.rows(wb)
        co2 = [k for k in r if "Carbon dioxide" in k][0]
        e = self.st.one("SELECT id FROM custom_exchanges WHERE process_uuid=? AND target=?", (self.steel, self.co2))
        cd.save_exchange(self.st, self.steel, {"id": e["id"], "kind": "elementary", "flow": self.co2, "amount": 2.2,
                                               "unit": "kg"})
        out = self.fill(wb, {r[co2]: {5: 1.0}})
        res = supplier.apply_response(self.st, out)
        self.assertEqual(res["applied"], 0)
        self.assertEqual(len(res["conflicts"]), 1)
        self.assertAlmostEqual(self.st.one("SELECT amount FROM custom_exchanges WHERE id=?", (e["id"],))["amount"], 2.2)

    def test_foreign_or_broken_files(self):
        self.request()
        other = os.path.join(self.dir, "other.xlsx")
        openpyxl.Workbook().save(other)
        with self.assertRaises(supplier.SupplierError):
            supplier.read_response(self.st, other)
        wb = openpyxl.load_workbook(self.path)
        wb["_cyclia"]["B1"] = "not-a-token"
        wb.save(other)
        with self.assertRaises(supplier.SupplierError):
            supplier.read_response(self.st, other)

    def test_range_rules(self):
        wb = self.request()
        r = self.rows(wb)
        co2 = [k for k in r if "Carbon dioxide" in k][0]
        sol = [k for k in r if "Solvent X" in k][0]
        out = self.fill(wb, {r[co2]: {5: 2, 8: 3, 9: 4}, r[sol]: {8: 1, 9: 2}})
        pv = supplier.read_response(self.st, out)
        self.assertEqual(len(pv["errors"]), 2)                # amount outside the range; range without amount
        self.assertEqual(pv["changes"], [])

    def test_decimal_comma_and_zero(self):
        wb = self.request()
        r = self.rows(wb)
        co2 = [k for k in r if "Carbon dioxide" in k][0]
        sol = [k for k in r if "Solvent X" in k][0]
        out = self.fill(wb, {r[co2]: {5: "1,5"}, r[sol]: {5: 0}})
        pv = supplier.read_response(self.st, out)
        self.assertEqual(sorted(c["amount"] for c in pv["changes"]), [0.0, 1.5])

    def test_no_lines(self):
        self.build()
        p = cd.save_process(self.st, self.db, {"name": "empty", "product": self.p_steel, "amount": 1})
        with self.assertRaises(supplier.SupplierError):
            supplier.request_workbook(self.st, p, os.path.join(self.dir, "x.xlsx"), "S")


if __name__ == "__main__":
    unittest.main()
