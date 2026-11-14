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


def doc(*claims, limitations=None, public_record=False):
    """A claimset of these claims. Unless limitations are given, one addressed limitation affects every claim, so that
    no claim is charged for declaring none (no_limitation)."""
    if limitations is None:
        limitations = [{"id": "L0", "impact": "could_reverse", "mitigation": "addressed",
                        "affects": [c["id"] for c in claims]}]
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

    def test_exploratory_principal(self):
        """§3.2 (0.3): an exploratory principal claim of any type pays for being unplanned, less than an inference."""
        for t in ("descriptive", "methodological", "interpretive"):
            self.assertEqual(problems(rubric.score(doc(claim(type=t, planning="exploratory"))))
                             ["exploratory_principal"], 5, t)
        r = rubric.score(doc(claim(type="descriptive", planning="exploratory"), public_record=True))
        self.assertEqual(problems(r)["exploratory_principal"], 3)
        self.assertIn("A principal claim reported without a plan", r["problems"][r["claims"]["C1"]["problems"][0]]["text"])
        mixed = rubric.score(doc(claim("C1", planning="exploratory"),
                                 claim("C2", planning="exploratory", type="methodological")))
        texts = [p["text"] for p in mixed["problems"].values() if p["check"] == "exploratory_principal"]
        self.assertEqual(len(texts), 1)
        self.assertNotIn("descriptive", texts[0])           # one problem for both claims: it names no claim's type
        for quiet in (claim(planning="exploratory", role="supporting"), claim(planning="exploratory", type="formal",
                                                                               support=[{"kind": "formal_proof"}],
                                                                               verification="peer_checked")):
            self.assertNotIn("exploratory_principal", problems(rubric.score(doc(quiet))))

    def test_plan(self):
        causal = {"type": "causal"}                                       # unplanned it would cost 15: no cut
        self.assertEqual(problems(rubric.score(doc(claim(planned_at_anchor="git_remote"))))["plan_anchor"], 2)
        self.assertEqual(problems(rubric.score(doc(claim(planned_at_anchor="none", **causal))))["plan_anchor"], 10)
        self.assertEqual(problems(rubric.score(doc(claim(planning="confirmatory_with_deviations", **causal))))
                         ["plan_deviations"], 5)
        r = rubric.score(doc(claim(test={"flags": ["code_changed_after_plan", "a", "b"]}, **causal)))
        self.assertEqual(problems(r)["plan_flags"], 8)                     # repeated: 5 + 2 + 1

    def test_a_planned_estimate_is_planned(self):
        """§3.2 (0.4): a planned estimate costs nothing for being exploratory; its anchor and flags cost as a test's."""
        est = {"planning": "planned_estimate", "estimate": {"estimands": {"m": {"variable": "MASE"}}, "lab_plan": "PL1"}}
        found = problems(rubric.score(doc(claim(**est))))
        self.assertNotIn("exploratory_principal", found)
        self.assertNotIn("plan_anchor", found)
        unplanned = rubric.score(doc(claim(planning="exploratory")))["claims"]["C1"]["score"]
        self.assertGreater(rubric.score(doc(claim(**est)))["claims"]["C1"]["score"], unplanned)
        flagged = dict(est, planned_at_anchor="git_remote")
        flagged["estimate"] = dict(est["estimate"], flags=["diagnostic_missing"])
        found = problems(rubric.score(doc(claim(type="causal", **flagged))))
        self.assertEqual((found["plan_anchor"], found["plan_flags"]), (2, 5))

    def test_a_plan_never_costs_more_than_no_plan(self):
        """§3.2 (0.3): a plan's problems together cost at most what the same claim would cost unplanned."""
        worst = {"planning": "confirmatory_with_deviations", "planned_at_anchor": "none",
                 "test": {"flags": ["code_changed_after_plan"]}}
        for kind, record in (({}, False), ({}, True), ({"type": "causal"}, False), ({"type": "causal"}, True),
                             ({"role": "supporting"}, False)):
            planned = rubric.score(doc(claim(**kind, **worst), public_record=record))["claims"]["C1"]["score"]
            unplanned = rubric.score(doc(claim(**kind, planning="exploratory"), public_record=record))
            self.assertGreaterEqual(planned, unplanned["claims"]["C1"]["score"], (kind, record))
        r = rubric.score(doc(claim(**worst)))
        self.assertEqual(sum(v for k, v in problems(r).items() if k.startswith("plan_")), 5)   # cut to 5, 10 first
        self.assertEqual(problems(r)["plan_anchor"], 5)

    def test_checkable(self):
        self.assertEqual(problems(rubric.score(doc(claim(verifiability="audit_only"))))["verifiability"], 10)
        self.assertEqual(problems(rubric.score(doc(claim(verifiability="unverifiable"))))["verifiability"], 45)
        r = rubric.score(doc(claim(verifiability_flags=["figure_without_data", "unanchored_plan"])))
        self.assertEqual(problems(r)["verifiability_flags"], 5)            # unanchored_plan counted by plan_anchor
        r = rubric.score(doc(claim(verifiability_flags=["figure_without_data", "unpublished_prompts"])))
        self.assertEqual(problems(r)["verifiability_flags"], 7)

    def test_context(self):
        self.assertEqual(problems(rubric.score(doc(claim(scope={}))))["no_scope"], 10)
        self.assertNotIn("no_scope", problems(rubric.score(doc(claim(scope={}, type="formal",
                                                                         support=[{"kind": "formal_proof"}],
                                                                         verification="peer_checked")))))
        self.assertEqual(problems(rubric.score(doc(claim(relations=[]))))["no_prior_work"], 5)
        self.assertNotIn("no_prior_work", problems(rubric.score(doc(claim(relations=[], novelty="not_applicable")))))
        self.assertNotIn("no_prior_work", problems(rubric.score(doc(claim(relations=[], role="secondary")))))
        self.assertNotIn("no_prior_work", problems(rubric.score(doc(claim(relations=[], novelty="synthesis")))))  # 0.6
        numbers = claim(statement="Coverage is 0.81 on [[D6:M4 sample]].", support=[{"kind": "simulation"}])
        self.assertEqual(problems(rubric.score(doc(numbers)))["numbers_without_results"], 5)
        words = claim(statement="Coverage falls on the [[D6:M4 sample]] in $T_1$ (see E1.T1.r2).",
                      support=[{"kind": "simulation"}])
        self.assertNotIn("numbers_without_results", problems(rubric.score(doc(words))))
        names = claim(statement="Claims scored by claimset-haiku-2 and GPT-4o on M4.", support=[{"kind": "simulation"}])
        self.assertNotIn("numbers_without_results", problems(rubric.score(doc(names))))   # names are not numbers

    def test_numbers_by_the_validators_warning_17(self):
        """§3.4 (0.3): given the validator's warnings, warning 17 on the statement decides; results listed or not."""
        cited = claim(statement="Coverage is 0.81.", support=[{"kind": "simulation", "evidence": "E1",
                                                               "results": ["E1.R1"]}])
        w17 = [{"rule": "W17", "where": "claims:C1.statement", "message": "0.81 ... match no recorded result"}]
        self.assertEqual(problems(rubric.score(doc(cited), warnings=w17))["numbers_without_results"], 5)
        self.assertNotIn("numbers_without_results", problems(rubric.score(doc(cited), warnings=[])))
        bare = claim(statement="Coverage is 0.81.", support=[{"kind": "simulation"}])
        self.assertNotIn("numbers_without_results", problems(rubric.score(doc(bare), warnings=[])))

    def test_open_problems(self):
        lims = [{"id": "L1", "impact": "could_reverse", "mitigation": "none", "affects": ["C1"]},
                {"id": "L2", "impact": "could_bias_magnitude", "mitigation": "partial", "affects": ["C1"]},
                {"id": "L3", "impact": "reduces_precision", "mitigation": "addressed", "affects": ["C1"]},
                {"id": "L4", "impact": "could_reverse", "mitigation": "none", "affects": ["C1"]}]
        r = rubric.score(doc(claim(), limitations=lims))
        self.assertEqual(r["claims"]["C1"]["score"], 84)                   # repeated: 10 + 5 + 1 (3 halved twice)
        a = {"id": "C9", "statement": "Errors are Gaussian.", "type": "descriptive", "role": "supporting",
             "support": [{"kind": "assumption"}], "assumption_category": "statistical", "check": "unchecked"}
        r = rubric.score(doc(claim(assumptions=["C9"]), a))
        self.assertEqual(problems(r)["unchecked_assumption"], 3)
        self.assertEqual(r["assumptions"], ["C9"])
        self.assertNotIn("C9", r["claims"])
        a["check"] = "tested"
        self.assertEqual(rubric.score(doc(claim(assumptions=["C9"]), a))["claims"]["C1"]["score"], 100)

    def test_declaring_a_limitation_never_costs_more_than_declaring_none(self):
        """§3.5 (0.3): no_limitation, and one declared limitation of any impact costs at most as much."""
        silent = rubric.score(doc(claim(), limitations=[]))
        self.assertEqual(problems(silent)["no_limitation"], 10)
        for impact in ("could_reverse", "could_bias_magnitude", "reduces_precision", "reduces_transferability"):
            declared = rubric.score(doc(claim(), limitations=[{"id": "L1", "impact": impact, "mitigation": "none",
                                                                 "affects": ["C1"]}]))
            self.assertNotIn("no_limitation", problems(declared))
            self.assertGreaterEqual(declared["claims"]["C1"]["score"], silent["claims"]["C1"]["score"], impact)
        premise = claim("C2", role="supporting")                       # one on what it rests on is declared too
        r = rubric.score(doc(claim("C1", depends_on=["C2"]), premise,
                             limitations=[{"id": "L1", "impact": "reduces_precision", "mitigation": "none",
                                           "affects": ["C2"]}]))
        self.assertNotIn("no_limitation", problems(r))
        for quiet in (claim(role="supporting"), claim(type="formal", support=[{"kind": "formal_proof"}],
                                                      verification="peer_checked")):
            self.assertNotIn("no_limitation", problems(rubric.score(doc(quiet, limitations=[]))))

    def test_a_restated_competing_interest_costs_nothing(self):
        """§3.5 (0.3): a limitation with the validator's warning 46 is not charged, nor does it count as declared."""
        lims = [{"id": "L1", "impact": "could_bias_magnitude", "mitigation": "none", "affects": ["C1"]}]
        w46 = [{"rule": "W46", "where": "limitations:L1.statement", "message": "restates the competing interest"}]
        self.assertEqual(problems(rubric.score(doc(claim(), limitations=lims)))["limitation"], 6)
        r = rubric.score(doc(claim(), limitations=lims), warnings=w46)
        self.assertNotIn("limitation", problems(r))
        self.assertEqual(problems(r)["no_limitation"], 10)

    def test_evidence_names_the_observations(self):
        """§3.1 (0.3): naming evidence without its observations costs 10; a result, a row or data rows cost nothing."""
        ev = {"id": "E1", "results": [{"id": "R1"}], "tables": [{"id": "T1"}]}
        for results, cost in ((None, 10), (["E1.T1"], 10), (["E1.R1"], 0), (["E1.T1.r2"], 0), (["A4#row=12"], 0)):
            s = {"kind": "empirical_quant", "evidence": "E1", **({"results": results} if results else {})}
            d = doc(claim(support=[s]))
            d["evidence"] = [ev]
            self.assertEqual(problems(rubric.score(d)).get("support_kind", 0), cost, results)
        d = doc(claim(support=[{"kind": "simulation", "evidence": "E2"}]))
        d["evidence"] = [{"id": "E2", "estimate": 0.4}]                    # nothing but an estimate: specific
        self.assertNotIn("support_kind", problems(rubric.score(d)))
        qual = doc(claim(support=[{"kind": "empirical_qual", "evidence": "E1"}]))
        self.assertNotIn("support_kind", problems(rubric.score(qual)))

    def test_an_argument_from_scored_claims(self):
        """§3.1 (0.3): an argument from claims the file scores costs 10; from nothing, or assumptions only, 30."""
        arg = {"support": [{"kind": "argument"}], "type": "interpretive"}
        premise = claim("C2", role="supporting")
        assumption = {"id": "C3", "statement": "x", "type": "descriptive", "support": [{"kind": "assumption"}]}
        self.assertEqual(problems(rubric.score(doc(claim("C1", depends_on=["C2"], **arg), premise)))["support_kind"],
                         10)
        self.assertEqual(problems(rubric.score(doc(claim("C1", **arg))))["support_kind"], 30)
        self.assertEqual(problems(rubric.score(doc(claim("C1", depends_on=["C3"], **arg), assumption)))
                         ["support_kind"], 30)

    def test_a_studied_api_model_is_not_a_dependency(self):
        """§3.3 (0.3): api_model_dependency costs nothing when the API-only model is the subject or a baseline."""
        def scored(role):
            d = doc(claim(support=[{"kind": "empirical_quant", "evidence": "E1", "results": ["E1.R1"]}],
                          verifiability_flags=["api_model_dependency"]))
            d["models"] = [{"id": "M1", "weights": "api_only"}, {"id": "M2", "weights": "open"}]
            d["evidence"] = [{"id": "E1", "results": [{"id": "R1"}],
                              "models": [{"model": "M1", "role": role}, {"model": "M2", "role": "instrument"}]}]
            return problems(rubric.score(d)).get("verifiability_flags", 0)
        self.assertEqual((scored("subject"), scored("baseline")), (0, 0))
        self.assertEqual((scored("instrument"), scored("annotator"), scored(None)), (5, 5, 5))

    def test_every_check_is_in_the_rubric_document(self):
        text = (ROOT / "RUBRIC.md").read_text(encoding="utf-8")
        for name in CHECKS:
            self.assertIn(f"`{name}`", text, name)
        self.assertIn(f"v{rubric.VERSION}", text.splitlines()[0])
        self.assertRegex(text, rf"\*\*{re.escape(rubric.VERSION)}\*\*")


class TestReview(unittest.TestCase):
    """§3.1 and §3.2 (0.5): reviews, from the claimset extension `review`."""

    def review(self, read="full_text", extract=None, searches=None, protocol=None, flags=None, **extra):
        c = claim(support=[{"kind": "cited", "reference": "B1", "locator": "Section 5"}], planning="exploratory",
                  type="methodological", **extra)
        c["ext"] = {"review": {"kind": "summary"}}
        if extract is not None:
            c["ext"]["review"]["extracts"] = [dict({"reference": "B1"}, **extract)]
        d = doc(c)
        d["references"] = [{"id": "B1", "target": "10.1198/jasa.2011.r10138", "id_type": "doi"}]
        if read:
            d["references"][0]["ext"] = {"review": {"read": read}}
        d["artefacts"].append({"id": "A2", "kind": "data", "reference": "B1"})
        block = {k: v for k, v in (("searches", searches), ("protocol", protocol), ("flags", flags)) if v}
        if block:
            d["paper"]["ext"] = {"review": block}
        return problems(rubric.score(d))

    def test_cited_by_how_the_work_was_read(self):
        quoted = {"exact": "the squared error scoring function is consistent for the mean", "artefact": "A2"}
        for read, extract, cost in [("full_text", quoted, 0), ("full_text", {"text": "squared error is consistent"}, 5),
                                    ("full_text", None, 15), ("abstract", quoted, 20), ("secondary", None, 20),
                                    (None, quoted, 20),
                                    ("full_text", {"exact": "words", "artefact": "A9"}, 5)]:   # no such artefact
            with self.subTest(read=read, extract=extract):
                self.assertEqual(self.review(read, extract).get("support_kind", 0), cost)

    def test_saying_how_a_work_was_read_never_costs_more(self):
        unsaid = self.review(None)["support_kind"]
        for read in ("full_text", "abstract", "secondary"):
            self.assertLessEqual(self.review(read).get("support_kind", 0), unsaid, read)

    def test_an_extract_for_another_work_does_not_count(self):
        self.assertEqual(self.review("full_text", {"reference": "B2", "exact": "x", "artefact": "A2"})["support_kind"], 15)

    def test_review_search(self):
        search = [{"source": "Google Scholar", "query": "consistent scoring", "date": "2026-11-13", "results": 12}]
        protocol = {"sources": ["Google Scholar"], "include": ["methodological papers"]}
        found = self.review()
        self.assertEqual(found["review_search"], 5)
        self.assertNotIn("exploratory_principal", found)                  # instead of it, never on top
        self.assertEqual(self.review(searches=search)["review_search"], 2)
        self.assertNotIn("review_search", self.review(searches=search, protocol=protocol))
        flagged = self.review(searches=search, protocol=protocol,
                              flags=["searched_before_protocol", "protocol_changed_after_search"])
        self.assertEqual(flagged["review_search"], 3)                     # repeated: 2 + 1
        self.assertEqual(self.review(searches=search, flags=["searched_before_protocol", "protocol_changed_after_search"])
                         ["review_search"], 4)                            # no protocol and two flags: 2 + 1 + 1
        self.assertLessEqual(self.review(searches=search, flags=["a", "b", "c", "d"])["review_search"], 5)

    def test_a_support_problem_names_each_kind(self):
        """§4.3 (0.5): one support problem over claims with different support names each kind, the costliest first."""
        r = rubric.score(doc(claim("C1", support=[{"kind": "cited"}]), claim("C2", support=[{"kind": "argument"}])))
        text = next(p["text"] for p in r["problems"].values() if p["check"] == "support_kind")
        self.assertEqual(text, "Rests on argument only; cited work only")
        self.assertEqual((r["claims"]["C1"]["score"], r["claims"]["C2"]["score"]), (80, 70))   # scores unchanged

    def test_without_the_extension_nothing_changes(self):
        c = claim(support=[{"kind": "cited", "reference": "B1"}], planning="exploratory", type="methodological")
        found = problems(rubric.score(doc(c)))
        self.assertEqual((found["support_kind"], found["exploratory_principal"]), (20, 5))
        self.assertNotIn("review_search", found)


class TestBackground(unittest.TestCase):
    """§2 and §3.1 (0.5): stating the earlier work a finding rests on never costs more than leaving it out, beyond what
    an unchecked assumption costs; a cited claim published on EntryLib costs by its score there."""

    def premise(self, **extra):
        return claim("C2", role="supporting", support=[{"kind": "cited", "reference": "B1"}], **extra)

    def test_a_cited_premise_costs_a_claim_with_evidence_at_most_3(self):
        alone = rubric.score(doc(claim()))["claims"]["C1"]["score"]
        r = rubric.score(doc(claim(depends_on=["C2"]), self.premise()))
        self.assertEqual(r["claims"]["C1"]["score"], alone - 3)
        self.assertEqual(r["claims"]["C2"]["score"], 80)                      # the premise keeps its own score

    def test_a_quoted_premise_costs_nothing(self):
        d = doc(claim(depends_on=["C2"]), self.premise())
        d["claims"][1]["ext"] = {"review": {"extracts": [{"reference": "B1", "exact": "w", "artefact": "A2"}]}}
        d["references"] = [{"id": "B1", "target": "10.1/x", "id_type": "doi", "ext": {"review": {"read": "full_text"}}}]
        d["artefacts"].append({"id": "A2", "kind": "data"})
        self.assertEqual(rubric.score(d)["claims"]["C1"]["score"], 100)

    def test_an_argument_from_cited_premises_pays_in_full(self):
        rec = claim(depends_on=["C2"], support=[{"kind": "argument", "warrant": "W1"}])
        self.assertEqual(problems(rubric.score(doc(rec, self.premise())))["support_kind"], 20)   # a review's recommendation

    def test_other_premises_are_not_capped(self):
        weak = claim("C2", role="supporting", support=[{"kind": "expert_judgement"}])
        self.assertEqual(problems(rubric.score(doc(claim(depends_on=["C2"]), weak)))["support_kind"], 45)

    def test_a_cited_claim_costs_by_its_score(self):
        target = "entrylib:2026.000014@v2#C3"
        c = claim(support=[{"kind": "cited", "target": target, "id_type": "claimset"}])
        self.assertEqual(problems(rubric.score(doc(c), cited={target: 92}))["support_kind"], 8)
        self.assertNotIn("support_kind", problems(rubric.score(doc(c), cited={target: 100})))
        self.assertEqual(problems(rubric.score(doc(c), cited={target: 40}))["support_kind"], 20)   # never above citing
        self.assertEqual(problems(rubric.score(doc(c)))["support_kind"], 20)                      # no score supplied
        via_ref = doc(claim(support=[{"kind": "cited", "reference": "B1"}]))
        via_ref["references"] = [{"id": "B1", "target": target, "id_type": "claimset"}]
        self.assertEqual(problems(rubric.score(via_ref, cited={target: 85}))["support_kind"], 15)
        self.assertEqual(problems(rubric.assess(doc(c), cited={target: 92}))["support_kind"], 8)


class TestCounting(unittest.TestCase):
    def test_repeated_problems(self):
        from rubric.score import repeated
        self.assertEqual(repeated([20, 20]), [20, 10])
        self.assertEqual(repeated([10, 20]), [20, 5])
        self.assertEqual(repeated([3, 3, 3, 3]), [3, 1, 1, 1])
        self.assertEqual(repeated([2, 0]), [2, 0])

        def two(mitigation):
            lims = [{"id": "L1", "impact": "could_reverse", "mitigation": "none", "affects": ["C1"]},
                    {"id": "L2", "impact": "could_reverse", "mitigation": mitigation, "affects": ["C1"]}]
            return rubric.score(doc(claim(), limitations=lims))["claims"]["C1"]["score"]
        self.assertEqual([two("none"), two("partial"), two("addressed")], [85, 88, 90])   # every step counts
        self.assertGreater(two("partial"), two("none"))

    def test_a_problem_states_the_most_it_costs_a_claim(self):
        lims = [{"id": "L1", "impact": "could_reverse", "mitigation": "none", "affects": ["C1", "C2"]},
                {"id": "L2", "impact": "could_reverse", "mitigation": "none", "affects": ["C1"]},
                {"id": "L3", "impact": "could_reverse", "mitigation": "none", "affects": ["C1"]}]
        r = rubric.score(doc(claim("C1"), claim("C2"), limitations=lims))
        for p in r["problems"].values():
            charged = [c["costs"][pid] for c in r["claims"].values() for pid in c["costs"]
                       if r["problems"][pid] is p]
            self.assertEqual(p["cost"], max(charged))
        l1 = next(pid for pid, p in r["problems"].items() if p["objects"] == ["L1"])
        self.assertEqual(r["problems"][l1]["cost"], 10)


    def test_a_claim_pays_for_what_it_rests_on_once(self):
        premise = claim("C2", role="supporting", scope={})
        r = rubric.score(doc(claim("C1", scope={}, depends_on=["C2"]), premise))
        self.assertEqual(r["claims"]["C1"]["score"], 90)                   # one no_scope, not two
        self.assertEqual(r["claims"]["C2"]["score"], 90)
        cyclic = rubric.score(doc(claim("C1", depends_on=["C2"]), claim("C2", depends_on=["C1"], scope={})))
        self.assertEqual(cyclic["claims"]["C1"]["score"], 90)

    def test_inherited_problems_are_reported_with_the_claim_they_arise_in(self):
        """§2, §4.3 (0.3): a problem lists every claim it lowers; a claim names what it inherits and from where."""
        r = rubric.score(doc(claim("C1", depends_on=["C2"]), claim("C2", role="supporting", scope={})))
        pid = next(p for p, x in r["problems"].items() if x["check"] == "no_scope")
        self.assertEqual((r["problems"][pid]["claims"], r["problems"][pid]["arises_in"]), (["C1", "C2"], ["C2"]))
        self.assertEqual(r["claims"]["C1"]["inherited"], {pid: ["C2"]})
        self.assertEqual(r["claims"]["C2"]["inherited"], {})
        for p, x in r["problems"].items():                                # the two lists agree
            self.assertEqual(x["claims"], sorted(c for c, item in r["claims"].items() if p in item["costs"]))

    def test_dots(self):
        r = rubric.score(doc(claim(planned_at_anchor="none", scope={}, verifiability="unverifiable")))
        self.assertEqual(r["claims"]["C1"]["dots"],
                         {"support": "green", "plan": "amber", "checkable": "red", "context": "amber", "open": "green"})

    def test_paper_is_the_mean_of_its_principal_claims(self):
        r = rubric.score(doc(claim("C1", scope={}), claim("C2", scope={}, relations=[]),
                             claim("C3", role="secondary", support=[{"kind": "unstated"}])))
        self.assertEqual(r["paper"]["score"], 88)                          # (90 + 85) / 2, rounded half up
        self.assertEqual((r["paper"]["lowest"], r["paper"]["lowest_score"]), ("C2", 85))
        checks = [r["problems"][p]["check"] for p in r["paper"]["problems"]]
        self.assertEqual(sorted(checks), ["no_prior_work", "no_scope"])  # a secondary claim is not the paper's
        no_scope = next(p for p in r["paper"]["problems"] if r["problems"][p]["check"] == "no_scope")
        self.assertEqual(r["problems"][no_scope]["claims"], ["C1", "C2"])
        self.assertIsNone(rubric.score(doc(claim(role="secondary")))["paper"])

    def test_the_published_entry(self):
        r = rubric.score(REAL)
        self.assertEqual(r["paper"]["principal"], ["C1", "C2", "C3", "C4", "C5", "C6"])
        lowest = r["paper"]["lowest"]
        scores = [r["claims"][c]["score"] for c in r["paper"]["principal"]]
        self.assertEqual(r["paper"]["score"], int(sum(scores) / len(scores) + 0.5))
        self.assertEqual(r["claims"][lowest]["score"], min(scores))
        self.assertEqual(r["paper"]["lowest_score"], min(scores))
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

    def test_a_synthesis_acknowledges_what_it_cites(self):
        """§6 (0.6): a claim citing a published claim acknowledges a close match with it."""
        same = "AutoMSARIMA coverage falls with the level ratio on M4."
        c = claim(statement="The coverage of AutoMSARIMA falls with the level ratio on the M4 sample.",
                  novelty="synthesis", relations=[], support=[{"kind": "cited", "reference": "B1"}])
        refs = [{"id": "B1", "target": "entrylib:2026.000014@v1#C3", "id_type": "claimset"}]
        match = [{"claim": "entrylib:2026.000014#C3", "statement": same}]
        r = rubric.novelty(c, match, "entrylib:2026.000020", refs)
        self.assertEqual((r["label"], r["check"]), ("synthesis", "acknowledged"))
        self.assertEqual(rubric.novelty(c, match, "entrylib:2026.000020")["check"], "unacknowledged")   # no refs
        c["support"] = [{"kind": "cited", "target": "entrylib:2026.000014@v1#C3", "id_type": "claimset"}]
        self.assertEqual(rubric.novelty(c, match, "entrylib:2026.000020")["check"], "acknowledged")
        d = doc(c)
        d["references"] = refs
        self.assertEqual(rubric.assess(d, lambda s: match)["novelty"]["C1"]["check"], "acknowledged")


if __name__ == "__main__":
    unittest.main()
