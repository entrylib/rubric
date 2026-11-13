# EntryLib scoring rubric

[![PyPI version](https://img.shields.io/pypi/v/entrylib-rubric)](https://pypi.org/project/entrylib-rubric/)
[![Tests](https://github.com/entrylib/rubric/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/entrylib/rubric/actions/workflows/tests.yml)
[![Downloads](https://img.shields.io/pypi/dm/entrylib-rubric)](https://pypistats.org/packages/entrylib-rubric)
[![License](https://img.shields.io/github/license/entrylib/rubric)](https://github.com/entrylib/rubric/blob/main/LICENSE)
[![Python versions](https://img.shields.io/pypi/pyversions/entrylib-rubric)](https://pypi.org/project/entrylib-rubric/)

How [EntryLib](https://entrylib.org) scores the [claimsets](https://github.com/entrylib/claimset) it publishes, as
public rules and the code that applies them. Anyone can compute the same scores, see why a claimset scored as it did,
and what would raise it.

## What it scores

- **Reliability**, from 0 to 100, for every claim and for the paper: how far the claimset's own record supports each
  claim. A claim starts at 100 and loses points for each problem the checks find in it and in the claims it rests on:
  support that cannot be checked, a test not planned before it ran, a missing scope, limitations still open, and so
  on. Each claim has a band (high 80 and over, medium 60 to 79, low under 60) and five dots, one per group of checks
  (support, plan, checkable, context, open problems). The paper's score is the mean of its principal claims, shown
  with its lowest one.
- **Novelty**, as a label: the authors' own (no prior work found, extension, replication, refutation), with a check
  for close matches among the claims already published on EntryLib that the claimset does not acknowledge.

The scores rest only on the claimset file (and, for novelty, on the published claims they are compared with). They
check the record, not the science: a band says how well the record supports a claim, never whether the claim is true.

The rules, with every check and its cost: [RUBRIC.md](https://github.com/entrylib/rubric/blob/main/RUBRIC.md),
normative and versioned. Every score records the version it was computed under.

## Install

```bash
pip install entrylib-rubric
```

It needs Python 3.10 or later and nothing beyond the standard library. In Python, import it as `rubric`.

## Use

Before submitting a claimset, score it as it would be scored once published, with the
[claimset](https://pypi.org/project/claimset/) command-line tool:

```bash
claimset score paper.claimset.json              # reliability, and every issue with what would fix it
claimset score paper.claimset.json --novelty    # with the close-match check against EntryLib
```

From Python:

```python
import json
import rubric

doc = json.load(open("paper.claimset.json"))
scores = rubric.score(doc)
scores["paper"]["score"], scores["paper"]["band"]   # 85, 'high'
scores["claims"]["C1"]["dots"]                       # {'support': 'green', 'plan': 'green', ...}
print(rubric.report(scores))                         # every problem, what it costs and what would remove it
```

- `rubric.score(doc, warnings=None)`: the scores. `warnings` are the claimset validator's for the file
  (`claimset.validate.validate(doc, published=True).warnings`); two checks use them.
- `rubric.report(scores, biggest_n=0, name="reliability")`: the scores as plain text, for authors and their agents.
- `rubric.assess(doc, find=None, warnings=None)`: the scores with novelty; `find(statement)` returns the published
  claims to compare with.
- `rubric.VERSION`: the rubric version every score records.

## Changing the rubric

A change to a cost, a band, a check or a rule is a new rubric version: `RUBRIC.md` first, then
`src/rubric/rubric.json` and the scorer, then the tests ([AGENTS.md](https://github.com/entrylib/rubric/blob/main/AGENTS.md)).
Planned: an AI reviewer ([#1](https://github.com/entrylib/rubric/issues/1)) and reproduction from artefacts
([#2](https://github.com/entrylib/rubric/issues/2)).

## Licence

Apache 2.0.
