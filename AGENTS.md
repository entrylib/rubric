# Working on this repository

- `RUBRIC.md` is normative. Change it first, then `src/rubric/rubric.json` and the scorer, then the tests.
- Any change to a cost, band, check or rule is a new rubric version: raise `version` in `rubric.json`, the title of `RUBRIC.md` and `version` in `pyproject.toml`, and list the change under *Versions* in `RUBRIC.md`.
- Every check needs a test: a case that triggers it with its cost, and one that does not.
- Scores rest only on the published claimset file (and, for novelty, on claims the site supplies). Nothing in the rubric reads the network or the portal's database.
- The claimset format belongs to the `claimset` package; this repository reads published files and never reimplements their validation.
- Standard library only; Python 3.10+. Run `python3 -m unittest discover -s tests` before committing.
- Text is written for LLM readers as much as for people: plain, explicit, one meaning per term.

## Pull requests

- Keep the description short: a bulleted list of what was done, each item one or two sentences. No other sections.
- Pull requests are reviewed and merged by a maintainer, never by the author's agent.
