"""The scorer against RUBRIC.md: every check, the counting rules, the paper rule, novelty."""

import copy
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import rubric  # noqa: E402
from rubric.score import CHECKS  # noqa: E402

REAL = json.loads((ROOT / "tests" / "data" / "entrylib_2026.000001_v3.json").read_text(encoding="utf-8"))


def claim(cid="C1", **extra):
    c = {"id": cid, "statement": "Method M is calibrated on the sample.", "type": "descriptive", "role": "principal",
         "novelty": "extension", "scope": {"data_type": "series"},
         "support": [{"kind": "simulation", "evidence": "E1", "results": ["E1.R1"]}],
         "relations": [{"type": "extends", "target": "10.1000/x", "id_type": "doi"}],
         "planning": "confirmatory", "planned_at_anchor": "platform", "verifiability": "open",
         "verifiability_flags": []}
    c.update(extra)
    return c


def doc(*claims, limitations=(), public_record=False):
    d = {"paper": {"exploration": {"lab_record": "A1"}}, "claims": list(claims), "limitations": list(limitations),
         "artefacts": [{"id": "A1", "kind": "lab_record",
                        "availability": {"level": "public" if public_record else "author_only"}}]}
    return d


def problems(result, cid="C1"):
    return {result["problems"][p]["check"]: result["claims"][cid]["costs"][p] for p in result["claims"][cid]["problems"]}


class TestChecks(unittest.TestCase):
    def test_a_clean_claim_scores_100(self):
        r = rubric.score(doc(claim()))
        self.assertEqual((r["claims"]["C1"]["score"], r["claims"]["C1"]["band"]), (100, "high"))
        self.assertEqual(set(r["claims"]["C1"]["dots"].values()), {"green"})
        self.assertEqual(r["rubric"], rubric.VERSION)

    def test_support_kind(self):
        for kind, extra, cost in [("cited", {}, 20), ("argument", {}, 30), ("expert_judgement", {}, 45),
                                  ("unstated", {}, 70), ("consensus", {}, 25),
                                  ("formal_proof", {"type": "formal"}, 25),
                                  ("formal_proof", {"type": "formal", "verification": "peer_checked"}, 0),
                                  ("formal_proof", {"type": "formal", "verification": "disputed"}, 45)]:
            with self.subTest(kind=kind, extra=extra):
                r = rubric.score(doc(claim(support=[{"kind": kind}], **extra)))
                self.assertEqual(problems(r).get("support_kind", 0), cost)
        both = rubric.score(doc(claim(support=[{"kind": "argument"}, {"kind": "simulation", "results": ["E1.R1"]}])))
        self.assertNotIn("support_kind", problems(both))                  # the strongest support counts

    def test_exploratory_inference(self):
        r = rubric.score(doc(claim(type="causal", planning="exploratory")))
        self.assertEqual(problems(r)["exploratory_inference"], 15)
        r = rubric.score(doc(claim(type="causal", planning="exploratory"), public_record=True))
        self.assertEqual(problems(r)["exploratory_inference"], 5)
        self.assertIn("A causal claim", r["problems"][r["claims"]["C1"]["problems"][0]]["text"])
        r = rubric.score(doc(claim(type="descriptive", planning="exploratory")))
        self.assertNotIn("exploratory_inference", problems(r))            # a measurement is not a test

    def test_plan(self):
        self.assertEqual(problems(rubric.score(doc(claim(planned_at_anchor="git_remote"))))["plan_anchor"], 3)
        self.assertEqual(problems(rubric.score(doc(claim(planned_at_anchor="none"))))["plan_anchor"], 10)
        self.assertEqual(problems(rubric.score(doc(claim(planning="confirmatory_with_deviations"))))
                         ["plan_deviations"], 5)
        r = rubric.score(doc(claim(test={"flags": ["code_changed_after_plan", "a", "b"]})))
        self.assertEqual(problems(r)["plan_flags"], 10)                    # capped

    def test_checkable(self):
        self.assertEqual(problems(rubric.score(doc(claim(verifiability="audit_only"))))["verifiability"], 10)
        self.assertEqual(problems(rubric.score(doc(claim(verifiability="unverifiable"))))["verifiability"], 45)
        r = rubric.score(doc(claim(verifiability_flags=["figure_without_data", "unanchored_plan"])))
        self.assertEqual(problems(r)["verifiability_flags"], 5)            # unanchored_plan counted by plan_anchor

    def test_context(self):
        self.assertEqual(problems(rubric.score(doc(claim(scope={}))))["no_scope"], 10)
        self.assertNotIn("no_scope", problems(rubric.score(doc(claim(scope={}, type="formal",
                                                                         support=[{"kind": "formal_proof"}],
                                                                         verification="peer_checked")))))
        self.assertEqual(problems(rubric.score(doc(claim(relations=[]))))["no_prior_work"], 5)
        self.assertNotIn("no_prior_work", problems(rubric.score(doc(claim(relations=[], novelty="not_applicable")))))
        self.assertNotIn("no_prior_work", problems(rubric.score(doc(claim(relations=[], role="secondary")))))
        numbers = claim(statement="Coverage is 0.81 on [[D6:M4 sample]].", support=[{"kind": "simulation"}])
        self.assertEqual(problems(rubric.score(doc(numbers)))["numbers_without_results"], 5)
        words = claim(statement="Coverage falls on the [[D6:M4 sample]] in $T_1$ (see E1.T1.r2).",
                      support=[{"kind": "simulation"}])
        self.assertNotIn("numbers_without_results", problems(rubric.score(doc(words))))

    def test_open_problems(self):
        lims = [{"id": "L1", "impact": "could_reverse", "mitigation": "none", "affects": ["C1"]},
                {"id": "L2", "impact": "could_bias_magnitude", "mitigation": "partial", "affects": ["C1"]},
                {"id": "L3", "impact": "reduces_precision", "mitigation": "addressed", "affects": ["C1"]},
                {"id": "L4", "impact": "could_reverse", "mitigation": "none", "affects": ["C1"]}]
        r = rubric.score(doc(claim(), limitations=lims))
        self.assertEqual(r["claims"]["C1"]["score"], 70)                   # 20 + 20 + 6, capped at 30
        a = {"id": "C9", "statement": "Errors are Gaussian.", "type": "descriptive", "role": "supporting",
             "support": [{"kind": "assumption"}], "assumption_category": "statistical", "check": "unchecked"}
        r = rubric.score(doc(claim(assumptions=["C9"]), a))
        self.assertEqual(problems(r)["unchecked_assumption"], 3)
        self.assertEqual(r["assumptions"], ["C9"])
        self.assertNotIn("C9", r["claims"])
        a["check"] = "tested"
        self.assertEqual(rubric.score(doc(claim(assumptions=["C9"]), a))["claims"]["C1"]["score"], 100)

    def test_every_check_is_in_the_rubric_document(self):
        text = (ROOT / "RUBRIC.md").read_text(encoding="utf-8")
        for name in CHECKS:
            self.assertIn(f"`{name}`", text, name)
        self.assertIn(f"v{rubric.VERSION}", text.splitlines()[0])
        self.assertRegex(text, rf"\*\*{re.escape(rubric.VERSION)}\*\*")


class TestCounting(unittest.TestCase):
    def test_a_claim_pays_for_what_it_rests_on_once(self):
        premise = claim("C2", role="supporting", scope={})
        r = rubric.score(doc(claim("C1", scope={}, depends_on=["C2"]), premise))
        self.assertEqual(r["claims"]["C1"]["score"], 90)                   # one no_scope, not two
        self.assertEqual(r["claims"]["C2"]["score"], 90)
        cyclic = rubric.score(doc(claim("C1", depends_on=["C2"]), claim("C2", depends_on=["C1"], scope={})))
        self.assertEqual(cyclic["claims"]["C1"]["score"], 90)

    def test_dots(self):
        r = rubric.score(doc(claim(planned_at_anchor="git_remote", scope={}, verifiability="unverifiable")))
        self.assertEqual(r["claims"]["C1"]["dots"],
                         {"support": "green", "plan": "amber", "checkable": "red", "context": "amber", "open": "green"})

    def test_paper_is_its_lowest_principal_claim(self):
        r = rubric.score(doc(claim("C1", scope={}), claim("C2", scope={}, relations=[]),
                             claim("C3", role="secondary", support=[{"kind": "unstated"}])))
        self.assertEqual(r["paper"]["score"], 85)
        self.assertEqual(r["paper"]["lowest"], "C2")
        checks = [r["problems"][p]["check"] for p in r["paper"]["problems"]]
        self.assertEqual(sorted(checks), ["no_prior_work", "no_scope"])  # a secondary claim is not the paper's
        no_scope = next(p for p in r["paper"]["problems"] if r["problems"][p]["check"] == "no_scope")
        self.assertEqual(r["problems"][no_scope]["claims"], ["C1", "C2"])
        self.assertIsNone(rubric.score(doc(claim(role="secondary")))["paper"])

    def test_the_published_entry(self):
        r = rubric.score(REAL)
        self.assertEqual(r["paper"]["principal"], ["C1", "C2", "C3", "C4", "C5", "C6"])
        lowest = r["paper"]["lowest"]
        self.assertEqual(r["paper"]["score"], min(r["claims"][c]["score"] for c in r["paper"]["principal"]))
        self.assertEqual(r["claims"][lowest]["score"], r["paper"]["score"])
        self.assertEqual(r["claims"]["C1"]["score"], 94)
        for c in r["claims"].values():
            self.assertEqual(c["score"], 100 - sum(c["costs"].values()))

    def test_odd_files_do_not_break_it(self):
        for d in ({}, {"claims": None}, {"claims": [None, 3, {"id": 4}, {"id": "C1", "support": "x"}]},
                  {"claims": [claim(limitations="x", assumptions=[None], depends_on="C2", scope=[], relations=None,
                                    test="x", verifiability_flags=None)], "limitations": [None, {"affects": None}]}):
            rubric.score(d)


class TestNovelty(unittest.TestCase):
    def test_similarity(self):
        a = "On the [[D6:M4 sample]], the 80% coverage of AutoMSARIMA falls with the level ratio."
        b = "The coverage of AutoMSARIMA falls with the level ratio on M4 samples."
        self.assertGreaterEqual(rubric.similarity(a, b), 0.6)
        self.assertLess(rubric.similarity(a, "Exponential smoothing has an admissible region."), 0.3)
        self.assertEqual(rubric.similarity("", b), 0.0)

    def test_close_match(self):
        c = claim(statement="The coverage of AutoMSARIMA falls with the level ratio on the M4 sample.",
                  relations=[{"type": "extends", "target": "entrylib:2026.000014@v1#C3", "id_type": "claimset"}])
        same = "AutoMSARIMA coverage falls with the level ratio on M4."
        r = rubric.novelty(c, [{"claim": "entrylib:2026.000014#C3", "statement": same}], "entrylib:2026.000020")
        self.assertEqual((r["label"], r["check"]), ("extension", "acknowledged"))
        r = rubric.novelty(c, [{"claim": "entrylib:2026.000015#C1", "statement": same}], "entrylib:2026.000020")
        self.assertEqual(r["check"], "unacknowledged")
        self.assertEqual(r["matches"][0]["claim"], "entrylib:2026.000015#C1")
        r = rubric.novelty(c, [{"claim": "entrylib:2026.000020#C1", "statement": same},
                               {"claim": "entrylib:2026.000016#C1", "statement": "Something else entirely."}],
                           "entrylib:2026.000020")
        self.assertEqual((r["check"], r["matches"]), ("none", []))
        self.assertIsNone(rubric.novelty(claim(novelty="not_applicable"), [])["label"])


if __name__ == "__main__":
    unittest.main()
