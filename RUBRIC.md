# EntryLib scoring rubric, v0.4

How EntryLib scores the claimsets it publishes. This document is normative: the scorer (`src/rubric/`) implements it, and the costs in `src/rubric/rubric.json` are the ones stated here. Every score records the rubric version it was computed under.

## 1. What is scored

Two things, kept apart:

- **Reliability**, the main score: how far the claimset's own record supports each claim. A number from 0 to 100 for every claim that is not an assumption, and one for the paper.
- **Novelty**, secondary: what a claim adds to earlier work. In this version a label, not a number (§6).

A claim's reliability and its novelty do not affect each other. A careful replication can be highly reliable and not new.

In this version every score is computed by rules from the published claimset file and, where given, the warnings of the claimset validator published with it (its validation report): warning 17 (§3.4) and warning 46 (§3.5). The rules check the record, not the science: whether a claim follows from its evidence, whether its scope is narrower than the data, and what the authors did not declare are left to a reviewer (planned: issue #1). The page says so, and scores may change as the rubric and reviews develop.

## 2. Reliability of a claim

A claim starts at 100. Each **problem** found by the checks below costs points. The claim's score is 100 minus the costs of its problems and of the problems of every claim it rests on, `depends_on` and `assumptions`, followed to the end, with each problem counted once. It is never below 0. A problem a claim has from what it rests on is **inherited**: it lowers the claim like its own, and is reported with the claim it arises in (§4.3).

Assumption claims (whose only support kind is `assumption`, claimset §3.8) are not scored. They are taken as given; an unchecked assumption costs the claims that rest on it (check `unchecked_assumption`).

Every problem names its check, the objects it concerns and what would remove it. Nothing else lowers a score.

## 3. The checks

Each check belongs to one of five **groups**. A claim shows one dot per group (§4.2).

| Group | What it covers |
|---|---|
| Support | what the claim rests on |
| Plan | whether the test was planned before it was run, and how the plan was anchored |
| Checkable | whether a reader can obtain what is needed to check the claim |
| Context | where the claim holds, what earlier work it relates to, and which recorded results its numbers come from |
| Open problems | limitations and assumptions that are still open |

### 3.1 Support

`support_kind`: the cost of the claim's strongest support (the cheapest of its support entries):

| Support | Cost |
|---|---|
| evidence: `empirical_qual`, `demonstration`; `empirical_quant`, `empirical_obs`, `simulation` citing the observations the claim reports (below) | 0 |
| `empirical_quant`, `empirical_obs`, `simulation` naming the evidence without the observations the claim reports | 10 |
| `formal_proof`, with `verification` `machine_checked`, `agent_checked` or `peer_checked` | 0 |
| `formal_proof`, `unchecked` (or no verification) | 25 |
| `formal_proof`, `disputed` | 45 |
| `cited` | 20 |
| `consensus` | 25 |
| `argument` from claims the file scores (the claim's `depends_on` names a claim that is not an assumption) | 10 |
| `argument` | 30 |
| `expert_judgement` | 45 |
| `unstated` | 70 |

An `empirical_quant`, `empirical_obs` or `simulation` support entry **cites the observations** the claim reports when its `results` name a result entry (`E1.R3`), a table row (`E1.T1.r2`) or rows of a data artefact (`A4#row=12`), or when the evidence records no results or tables (only an `estimate`). Naming the evidence alone, or a whole table (`E1.T1`), is a pointer that does not say which numbers the claim rests on. Whether the cited observations show what the claim says is a reviewer's question (issue #1), not a rule's.

An argument from claims the file scores costs less than an argument alone: the premises' problems reach the claim anyway (§2), so it is not charged twice for them.

### 3.2 Plan

A claim is **planned** when its `planning` is `confirmatory`, `confirmatory_with_deviations` or `planned_estimate` (a value whose estimation a plan fixed in advance, claimset v0.42 §3.3.3); it then costs nothing for being exploratory. A plan never costs more than no plan. Every planned test or estimate is at least as reliable as the same claim unplanned, so the problems of a claim's plan together (`plan_anchor`, `plan_deviations`, `plan_flags`) cost at most what the same claim would cost unplanned; beyond that they are cut, the costliest kept first.

- `exploratory_inference`: a claim of type `associational`, `causal`, `mechanistic` or `predictive` whose `planning` is `exploratory` (or absent). What lowers its reliability is selection a reader cannot see: a result picked from many tries. Cost 5 when the paper's lab record (`paper.exploration.lab_record`) is public, so every run can be seen; 15 otherwise.
- `exploratory_principal`: a principal claim of any other type except `formal` whose `planning` is `exploratory` (or absent). Which measurements a paper reports first is a selection too, smaller than an inference's. Cost 3 when the lab record is public; 5 otherwise. Claims that are not principal cost nothing for being exploratory: a measurement that supports another claim is not a finding of its own.
- `plan_anchor`: a planned claim whose `planned_at_anchor` is `git_remote` costs 2; `none` (or absent) costs 10. `platform`, `rfc3161` and `registry` cost nothing.
- `plan_deviations`: `planning: confirmatory_with_deviations` costs 5. The deviations themselves are limitations (§3.5).
- `plan_flags`: each flag in the claim's `test.flags` or `estimate.flags` (set by the lab record, e.g. `code_changed_after_plan`, `diagnostic_missing`) costs 5; several are repeated problems (§3.6): 5, then 2, then 1 for each further flag.

### 3.3 Checkable

- `verifiability`: `audit_only` costs 10; `unverifiable` costs 45 (claimset §5).
- `verifiability_flags`: each of the claim's `verifiability_flags` costs 5; several are repeated problems (§3.6). `unstated_support` and `unanchored_plan` are not counted here: `support_kind` and `plan_anchor` already count them. `api_model_dependency` is not counted when every model with `weights: api_only` in the evidence the claim's support names has the role `subject` or `baseline` there (claimset §3.4): the model is what is studied, not a tool of the analysis, and a study of it cannot use another.

### 3.4 Context

- `no_scope`: a claim with no `scope`, or an empty one, costs 10. Formal claims are exempt.
- `no_prior_work`: a principal claim with no relation to work outside the paper (a relation whose `id_type` is not `local`, or `cited` support), unless its novelty is `not_applicable`, costs 5.
- `numbers_without_results`: a claim whose statement gives numbers that no recorded result holds costs 5: the validator's warning 17 on the claim's statement (claimset §10), which compares each number with the results and tables of the evidence the claim cites. Names with digits (`M4`, `GPT-4o`) are not numbers. Without the validator's warnings, the rule falls back to the claim's support listing no `results` while its statement gives numbers outside its mathematics, term labels and names. Formal claims are exempt.

### 3.5 Open problems

- `limitation`: each limitation that `affects` the claim (claimset §3.9). Declaring a limitation never costs more than declaring none (`no_limitation`, below), and less than the same problem found by a reviewer will cost (issue #1).

  | Impact | `none` | `partial` | `addressed` |
  |---|---|---|---|
  | `could_reverse` | 10 | 5 | 0 |
  | `could_bias_magnitude` | 6 | 3 | 0 |
  | `reduces_precision` | 3 | 1 | 0 |
  | `reduces_transferability` | 1 | 0 | 0 |

  Several limitations of one claim, its own and those it inherits, are repeated problems (§3.6), so together they cost less than twice the costliest: below 20. A limitation that only restates the paper's declared competing interest (the validator's warning 46) costs nothing: the declaration is shown with the paper, and who did the work is for readers to weigh, not a threat to a claim.
- `no_limitation`: a principal claim, not `formal`, that no limitation affects, neither its own nor one of what it rests on, costs 10. Every finding has limits; a claim that declares none leaves a reader to find them.
- `unchecked_assumption`: each assumption in the claim's `assumptions` whose `check` is `unchecked` costs 3; several are repeated problems (§3.6). `tested`, `sensitivity_analysed` and `untestable` cost nothing.

### 3.6 Counting

Each check has a **count**:

- `kind`: the check is one problem however often it occurs; it costs its largest instance.
- `each`: every instance (every limitation, every assumption) is its own problem.

**Repeated problems.** When one claim has several problems of the same check (several limitations, several unchecked assumptions, several flags), they are sorted from the costliest: the first costs in full, and each next one half the cost of the one before it in that order, rounded down and at least 1. Two limitations that could reverse a claim cost 10 + 5; mitigating one partly makes them 10 + 2; a third unmitigated one makes them 10 + 5 + 1. Every problem removed or mitigated therefore lowers the score, and the total stays below twice the costliest.

A problem's stated cost is the most it costs any one claim: the same limitation may cost one claim in full and another, where it comes second, half.

Problems a claim inherits from what it rests on are added to its own by the same counting: a claim and its premise both without a scope cost 10, not 20.

## 4. Display

### 4.1 Bands

| Band | Score |
|---|---|
| High | 80 and over |
| Medium | 60 to 79 |
| Low | under 60 |

The band is always shown as a word as well as a colour.

**What a band means.** A claim starts at 100 and loses the costs of its open problems, so a band is a budget of problems, and the costs (§3) are set so that a given problem falls in a given band:

- **High:** at most 20 points lost: one or two serious problems, declared (an unmitigated limitation that could reverse the claim costs 10), or a few minor ones (no scope, an unchecked assumption, a plan anchored only by a push: 10 + 3 + 2). Nothing a reader must check before relying on the claim, or one thing, and the authors say so.
- **Medium:** 21 to 40 lost: several real problems (an exploratory association whose lab record is not public, a missing scope and evidence named without the observations it reports: 15 + 10 + 10). Usable, after reading what the claim rests on.
- **Low:** more than 40 lost. Some problems put a claim here on their own: support nobody can check (`unverifiable`, 45). Not to be relied on without checking it.

Because repeated problems of one check cost half the one before (§3.6), minor problems piling up move a claim down a band without sinking it.

The edges, 80 and 60, are a judgement: they read like familiar marks, and they are not yet calibrated against how claims fare under independent review or reproduction (issue #6). A band says how well the claimset's own record supports a claim, never whether the claim is true. Changing an edge, or a cost so that a problem changes band, is a new version of this rubric (§7).

### 4.2 Dots

Every scored claim shows five dots, one per group, coloured by the points the group lost: green for 0 to 2, amber for 3 to 10, red for more than 10. A dot's explanation lists its problems. The paper's dots are, for each group, the worst dot among its principal claims.

### 4.3 Report

The scores are also given as a plain-text report (`rubric.report`), for the authors and their agents, whether the claimset is published or not yet submitted. It holds, in this order:

- the paper's score and band, and its lowest principal claim with that claim's score;
- optionally, the biggest issues: the problems that cost one claim the most points, most costly first;
- the claims whose novelty is in question (§6), when the close-match check was run;
- every problem that lowers a score, in the order of §5 (those of the principal claims first, most costly first), each with its check, its group, its cost, the claims it lowers and by how much (naming, for a claim that inherits it, the claim it arises in), the objects it concerns and what would remove it;
- every claim's score, band and problems.

The report says only what the scores say; it adds no cost of its own. It calls the score *reliability*, as this rubric does; a site that shows the score under another name (EntryLib calls it Support) passes that name (`rubric.report(scores, name="Support")`), and the report uses it in place of the word, nothing else changing.

## 5. Reliability of the paper

The paper's score is the mean of the scores of its principal claims, rounded to the nearest whole number; its lowest principal claim and that claim's score are always shown with it. A paper with no principal claim that is scored has no score.

The mean, not the lowest: a paper's lowest claim alone made one interpretive principal claim, or a weak one kept principal rather than moved to supporting, set the whole paper, so that offering fewer findings paid. The lowest claim is still named beside the score, so a reader sees how far the paper's findings differ.

The explanation of the paper's score names its principal claims' mean and the lowest principal claim with its problems, then lists every problem still open in the principal claims and what they rest on, each once, with what it costs, the claims it concerns and what would remove it. A kind of problem stays on that list until it is removed everywhere.

## 6. Novelty

Novelty is shown as the claim's label (claimset §3.7: `no_prior_found`, `extension`, `replication`, `refutation`; `not_applicable` shows nothing), as the authors' account, with the result of the **close-match check**:

- Every principal claim is compared with the claims of every claimset published on EntryLib before it, including the same guarantor's.
- A claimset not yet submitted (scored with `claimset score --novelty`) is compared with the claims published on EntryLib at the time. A check that was not run is reported as not run, never as no close match.
- Two statements match closely when their **similarity** (below) is at least 0.6.
- A close match is **acknowledged** when the claim has a relation (any type) to the matching claim or to its claimset; otherwise it is **unacknowledged**.
- The result is one of: no close match on EntryLib; close matches, all acknowledged; or unacknowledged close matches, listed. An unacknowledged close match puts the label in question.

**Similarity** of two statements: replace each term reference `[[ID:text]]` by its text and each mathematical expression `$…$` by nothing; lower-case; split into words (letters and digits); drop the stop words of `src/rubric/novelty.py`; reduce each word to its stem by removing one of the endings listed there; the similarity is the number of stems the two statements share divided by the number in the shorter one (overlap coefficient).

A novelty number, from a literature search, comes with the reviewer (issue #1).

## 7. Versions

A change of a cost, a band, a check or a rule is a new version of this rubric, listed below with what changed. Provisional scores are recomputed under the current version.

- **0.4** (2026-11): planned estimates (claimset v0.42) are planned claims (§3.2): no cost for being exploratory, `plan_anchor` as for a confirmatory claim, and the flags of `estimate.flags` (among them `diagnostic_missing`) cost as a test's do.
- **0.3** (2026-11): from a study with claimset-lab whose scores rewarded leaving things out.
  - A plan never costs more than no plan (§3.2): exploratory principal claims of any type cost 3 or 5 (`exploratory_principal`); a plan anchored by a push costs 2; a plan's problems together cost at most what the claim would cost unplanned.
  - Declaring limitations never costs more than declaring none (§3.5): their costs are halved (could reverse 10, could bias 6, precision 3, transferability 1), and a principal claim that declares none costs 10 (`no_limitation`). A limitation that restates the declared competing interest (warning 46) costs nothing.
  - Evidence named without the observations the claim reports costs 10 (§3.1); an argument from claims the file scores costs 10, not 30.
  - `numbers_without_results` uses the validator's warning 17, and names with digits are not numbers (§3.4).
  - `api_model_dependency` costs nothing when the API-only model is what is studied (§3.3).
  - The paper's score is the mean of its principal claims, with the lowest shown (§5).
  - Inherited problems are reported with the claim they arise in (§2, §4.3).
- **0.2** (2026-11): repeated problems on one claim cost half the one before instead of being capped (caps made a partial mitigation worth nothing once the cap was reached); a problem's stated cost is the most it costs any one claim.
- **0.1** (2026-11): first version.
