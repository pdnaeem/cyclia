"""Collaborative critical review (1.8.0): practitioner and reviewer on separate workspaces exchange the project and
review files; comments merge without duplicates; the review closes only without open critical or major comments."""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import calc  # noqa: E402
import review  # noqa: E402
from store import Workspace  # noqa: E402
from test_custom_data import Base  # noqa: E402


class TestReview(Base):
    def setUp(self):
        super().setUp()
        self.build()
        self.m = self.st.save_model({"name": "steel study", "product": "sheet", "unit": "kg", "amount": 1,
                                     "scope": {"goal": "g", "boundary": "cradle-to-gate"}})
        self.line = self.st.add_input(self.m, "activity", self.ref(self.steel), 1.0)
        # the reviewer's own workspace, with the project sent by the practitioner
        self.dir2 = tempfile.mkdtemp()
        self.ws2 = Workspace(self.dir2)
        lca = os.path.join(self.dir, "study.lca")
        self.ws.export("T", lca)
        self.st2 = self.ws2.open(self.ws2.import_file(lca, "Received"))

    def tearDown(self):
        self.ws2.close_all()
        shutil.rmtree(self.dir2, ignore_errors=True)
        super().tearDown()

    def swap(self, src, dst, name):
        p = os.path.join(self.dir, name)
        review.export_file(src, self.m, p)
        return review.import_file(dst, self.m, p)

    def test_round_trip(self):
        rv, pr = self.st2, self.st
        self.assertEqual(review.fingerprint(rv, self.m), review.fingerprint(pr, self.m))
        c1 = review.add(rv, self.m, {"role": "reviewer", "author": "R. Viewer", "severity": "critical",
                                     "target": f"line:{self.line}", "text": "Source of the rolling data?"})
        review.add(rv, self.m, {"role": "reviewer", "author": "R. Viewer", "severity": "minor",
                                "target": "item:fu", "text": "State the thickness of the sheet."})
        r = self.swap(rv, pr, "r1.json")
        self.assertEqual((r["added"], r["same_model"]), (2, True))
        t = {x["uid"]: x for x in review.threads(pr, self.m)}
        self.assertTrue(t[c1]["target_label"].startswith("Line: "))
        self.assertIn("ISO 14044 4.2.3.2", [x for x in t.values() if x["uid"] != c1][0]["target_label"])
        review.add(pr, self.m, {"role": "practitioner", "author": "N. Rehman", "parent": c1,
                                "text": "Plant A measurements 2025, see annex."})
        self.assertEqual({x["uid"]: x for x in review.threads(pr, self.m)}[c1]["status"], "answered")
        with self.assertRaises(review.ReviewError):
            review.close(pr, self.m, "R. Viewer", "ok")                    # critical comment not resolved
        with self.assertRaises(review.ReviewError):
            review.set_status(pr, c1, "resolved", "N. Rehman", "practitioner")
        r = self.swap(pr, rv, "p1.json")
        self.assertEqual((r["added"], r["updated"]), (1, 1))
        review.set_status(rv, c1, "resolved", "R. Viewer", "reviewer")
        cl = review.close(rv, self.m, "R. Viewer", "The study conforms to ISO 14044.")
        self.assertEqual(cl["open_minor"], 1)
        r = self.swap(rv, pr, "r2.json")
        self.assertTrue(r["closure"])
        s = review.summary(pr, self.m)
        self.assertTrue(s["closure_current"])
        self.assertEqual(s["blocking"], 0)
        # merging the same file again changes nothing
        p = os.path.join(self.dir, "r2.json")
        r = review.import_file(pr, self.m, p)
        self.assertEqual((r["added"], r["updated"]), (0, 0))
        self.assertEqual(len(review.threads(pr, self.m)), 2)
        self.assertEqual(sum(len(t["replies"]) for t in review.threads(pr, self.m)), 1)
        # the model changes after the review: the closure refers to an earlier state
        self.st.update_input(self.line, {"amount": 2.0})
        self.assertFalse(review.summary(pr, self.m)["closure_current"])

    def test_both_sides_changed(self):
        rv, pr = self.st2, self.st
        c = review.add(rv, self.m, {"role": "reviewer", "author": "R", "severity": "major", "text": "Check allocation."})
        self.swap(rv, pr, "a.json")
        # fixed clocks, so the order does not depend on the resolution of the computer's clock
        real = review._now
        try:
            review._now = lambda: "2026-03-01T10:00:00.000000+00:00"
            review.set_status(pr, c, "answered", "P", "practitioner")
            review._now = lambda: "2026-03-01T10:05:00.000000+00:00"
            review.set_status(rv, c, "withdrawn", "R", "reviewer")         # later change wins
        finally:
            review._now = real
        r = self.swap(rv, pr, "b.json")
        self.assertEqual(r["updated"], 1)
        t = review.threads(pr, self.m)[0]
        self.assertEqual(t["status"], "withdrawn")
        self.assertTrue(any(h.get("merged") for h in t["history"]))       # the replaced state is kept
        # the practitioner's file merged into the reviewer's copy keeps the reviewer's later change
        r = self.swap(pr, rv, "c.json")
        self.assertEqual(review.threads(rv, self.m)[0]["status"], "withdrawn")

    def test_same_clock_value(self):
        """A clock that returns the same value twice (coarse clocks on Windows): changes still get increasing times,
        and two sides changed at exactly the same time agree on one result after merging both ways."""
        rv, pr = self.st2, self.st
        real = review._now
        try:
            review._now = lambda: "2026-03-01T10:00:00.000000+00:00"
            c = review.add(rv, self.m, {"role": "reviewer", "author": "R", "severity": "minor", "text": "Units?"})
            review.set_status(rv, c, "withdrawn", "R", "reviewer")
            review.set_status(rv, c, "open", "R", "reviewer")
            t = review.threads(rv, self.m)[0]
            self.assertGreater(t["modified"], "2026-03-01T10:00:00.000000+00:00")
            self.assertEqual(t["status"], "open")
            self.swap(rv, pr, "a.json")
            review.set_status(pr, c, "answered", "P", "practitioner")
            review.set_status(rv, c, "resolved", "R", "reviewer")        # same time on both sides
            self.swap(rv, pr, "b.json")
            self.swap(pr, rv, "c.json")
        finally:
            review._now = real
        a, b = review.threads(pr, self.m)[0], review.threads(rv, self.m)[0]
        self.assertEqual(a["status"], b["status"])

    def test_word_report(self):
        import docx
        import report
        c = review.add(self.st, self.m, {"role": "reviewer", "author": "R", "severity": "major", "text": "Allocation?"})
        review.add(self.st, self.m, {"role": "practitioner", "author": "P", "parent": c, "text": "Mass, see 3.2."})
        review.set_status(self.st, c, "resolved", "R", "reviewer")
        review.close(self.st, self.m, "R. Viewer", "Conforms to ISO 14044.")
        res = calc.run(self.st, self.m, [self.mid])
        p = os.path.join(self.dir, "r.docx")
        report.word_report(p, self.st.model(self.m), res, self.st.databases(), "test",
                           comments=review.summary(self.st, self.m))
        text = "\n".join(x.text for x in docx.Document(p).paragraphs)
        cells = " ".join(c.text for t in docx.Document(p).tables for r in t.rows for c in r.cells)
        self.assertIn("Review closed on", text)
        self.assertIn("Conforms to ISO 14044.", text)
        self.assertIn("Annex B3", text)
        self.assertIn("Mass, see 3.2.", cells)

    def test_rules(self):
        st = self.st
        with self.assertRaises(review.ReviewError):
            review.add(st, self.m, {"role": "practitioner", "author": "P", "severity": "minor", "text": "x"})
        with self.assertRaises(review.ReviewError):
            review.add(st, self.m, {"role": "reviewer", "author": "R", "severity": "huge", "text": "x"})
        with self.assertRaises(review.ReviewError):
            review.add(st, self.m, {"role": "reviewer", "author": "R", "severity": "minor", "text": "x",
                                    "target": "line:99999"})
        with self.assertRaises(review.ReviewError):
            review.add(st, self.m, {"role": "reviewer", "author": "", "severity": "minor", "text": "x"})
        bad = os.path.join(self.dir, "bad.json")
        with open(bad, "w") as fh:
            json.dump({"format": "other"}, fh)
        with self.assertRaises(review.ReviewError):
            review.import_file(st, self.m, bad)


if __name__ == "__main__":
    unittest.main()
