"""The plain-text report (RUBRIC.md §4.3): what it holds and in which order; it adds no cost of its own."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import rubric  # noqa: E402
from rubric.report import biggest, open_problems  # noqa: E402

REAL = json.loads((ROOT / "tests" / "data" / "entrylib_2026.000001_v3.json").read_text(encoding="utf-8"))


class TestReport(unittest.TestCase):
    def setUp(self):
        self.scores = rubric.score(copy.deepcopy(REAL))
        self.text = rubric.report(self.scores)

    def test_every_open_problem_and_claim_is_listed_in_order(self):
        problems = open_problems(self.scores)
        self.assertTrue(problems)
        places = [self.text.index(f"\n{pid}. ") for pid, _, _ in problems]
        self.assertEqual(places, sorted(places))
        for pid, p, lowers in problems:
            self.assertIn(f"Check: {p['check']} (group: {p['group']}); costs up to {p['cost']} points.", self.text)
            self.assertIn("Lowers: " + ", ".join(f"{c} (-{v})" for c, v in lowers.items()) + ".", self.text)
        for cid, c in self.scores["claims"].items():
            self.assertIn(f"\n{cid}: {c['score']} ({c['band']}): ", self.text)
        paper = self.scores["paper"]
        self.assertTrue(self.text.startswith(f"PAPER: reliability {paper['score']} ({paper['band']})"))

    def test_the_biggest_issues_are_the_costliest_for_one_claim(self):
        top = biggest(self.scores, 3)
        costs = [max(lowers.values()) for _, _, lowers in top]
        self.assertEqual(costs, sorted(costs, reverse=True))
        everything = [max(lowers.values()) for _, _, lowers in open_problems(self.scores)]
        self.assertEqual(costs[0], max(everything))
        text = rubric.report(self.scores, 3)
        self.assertIn("BIGGEST ISSUES, most costly first:", text)
        first = ", ".join(f"{c} -{v}" for c, v in top[0][2].items())
        self.assertLess(text.index(f"  {top[0][0]} ({first}): "), text.index("ISSUES, those of the principal"))
        self.assertNotIn("BIGGEST ISSUES", self.text)

    def test_novelty_in_question(self):
        scores = dict(self.scores, novelty={
            "C1": {"label": "extension", "check": "unacknowledged",
                   "matches": [{"claim": "entrylib:2026.000009#C2", "similarity": 0.8, "acknowledged": False}]},
            "C2": {"label": "extension", "check": "none", "matches": []}})
        text = rubric.report(scores)
        self.assertIn("NOVELTY IN QUESTION", text)
        self.assertIn("  C1: entrylib:2026.000009#C2 (similarity 0.8)", text)
        self.assertNotIn("  C2: ", text)
        self.assertNotIn("NOVELTY IN QUESTION", self.text)

    def test_no_issues_and_no_paper_score(self):
        scores = {"rubric": rubric.VERSION, "paper": None, "claims": {"C1": {"score": 100, "band": "high",
                                                                            "problems": [], "costs": {}}},
                  "problems": {}}
        text = rubric.report(scores, 3)
        self.assertIn("PAPER: no score", text)
        self.assertIn("No issues: every scored claim keeps all its points.", text)
        self.assertNotIn("BIGGEST", text)


class TestAssess(unittest.TestCase):
    def test_principal_claims_are_compared_with_what_find_returns(self):
        d = copy.deepcopy(REAL)
        principal = next(c for c in d["claims"] if c.get("role") == "principal" and c.get("novelty"))
        asked = []

        def find(statement):
            asked.append(statement)
            return [{"claim": "entrylib:2026.000009#C1", "statement": principal["statement"]},
                    {"claim": f"{d['paper']['id']}#C9", "statement": principal["statement"]}]   # its own: ignored
        result = rubric.assess(d, find)
        n = result["novelty"][principal["id"]]
        self.assertTrue(n["checked"])
        self.assertEqual([m["claim"] for m in n["matches"]], ["entrylib:2026.000009#C1"])
        self.assertEqual(n["check"], "unacknowledged")
        self.assertIn(principal["statement"], asked)
        self.assertTrue(all(not v["checked"] for cid, v in result["novelty"].items()
                            if next(c for c in d["claims"] if c["id"] == cid).get("role") != "principal"))
        self.assertIn("NOVELTY IN QUESTION", rubric.report(result))
        self.assertEqual({k: v for k, v in result.items() if k != "novelty"}, rubric.score(copy.deepcopy(REAL)))

    def test_without_find_nothing_is_compared(self):
        result = rubric.assess(copy.deepcopy(REAL))
        self.assertTrue(result["novelty"])
        self.assertTrue(all(not n["checked"] and n["matches"] == [] for n in result["novelty"].values()))
        unchecked = dict(result, novelty={"C1": {"check": "unacknowledged", "checked": False, "matches": []}})
        self.assertNotIn("NOVELTY IN QUESTION", rubric.report(unchecked))


if __name__ == "__main__":
    unittest.main()
