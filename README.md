# EntryLib scoring rubric

How [EntryLib](https://entrylib.org) scores the claimsets it publishes: a **reliability** score for every claim and for the paper, and a **novelty** label with a close-match check. The rules are public so that anyone can see why a claimset scored as it did, and what would raise it.

- [RUBRIC.md](https://github.com/entrylib/rubric/blob/main/RUBRIC.md): the rubric, normative and versioned.
- `src/rubric/`: the scorer that implements it (Python 3.10+, standard library only); the costs are in `src/rubric/rubric.json`.

```python
import json, claimset.validate, rubric
doc = json.load(open("claimset.json"))                    # a published claimset file
result = rubric.score(doc, warnings=claimset.validate.validate(doc, published=True).warnings)  # warnings optional
result["paper"]["score"], result["claims"]["C1"]["dots"]
```

`rubric.report(result)` gives the scores as plain text: every issue that lowers a score and what would fix it. Before submitting, `claimset score paper.claimset.json` ([claimset](https://github.com/entrylib/claimset)) scores a claimset this way on your own machine, as it would be scored once published.

Install: `pip install git+https://github.com/entrylib/rubric`. The portal installs it the same way and records the rubric version with every score.

Planned: an AI reviewer ([#1](https://github.com/entrylib/rubric/issues/1)) and reproduction from artefacts ([#2](https://github.com/entrylib/rubric/issues/2)).
