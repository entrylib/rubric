"""Novelty in this version: the authors' label and the close-match check (RUBRIC.md §6).

similarity(a, b) -> 0..1, the overlap of the stems of two claim statements
novelty(claim, matches, concept=None) -> {"label", "check", "matches"}

`matches` are the claims of claimsets published on EntryLib before this one that the site found as candidates, each
{"claim": "entrylib:2026.000014#C3", "statement": "..."}; the site finds candidates (by full-text search), this module
decides which match closely and whether the claim acknowledges them.
"""

import re

CLOSE = 0.6

STOP = set("""
a about above after again against all also an and any are as at be because been before being below between both but by
can could did do does doing down during each either few for from further had has have having here how if in into is it
its itself just less more most much must no nor not of off on once only or other our out over own same shall should so
some such than that the their them then there these they this those through to too under until up upon very was we were
what when where whether which while who whom why will with within without would yet
""".split())

# Endings removed, longest first, when at least three letters remain (RUBRIC.md §6).
ENDINGS = ("ational", "ations", "ation", "ments", "ment", "ings", "ing", "ies", "ied", "ed", "es", "ly", "s")

TERM = re.compile(r"\[\[[^\]:]+:([^\]]*)\]\]")
MATH = re.compile(r"\$\$.+?\$\$|\$[^$]+\$|\\\(.+?\\\)", re.S)
WORD = re.compile(r"[^\W_]+")


def _stem(w):
    for e in ENDINGS:
        if w.endswith(e) and len(w) - len(e) >= 3:
            return w[: -len(e)]
    return w


def stems(statement):
    """The set of stems of a statement: terms as their text, mathematics removed, stop words dropped."""
    text = MATH.sub(" ", TERM.sub(lambda m: m.group(1), statement if isinstance(statement, str) else ""))
    return {_stem(w) for w in WORD.findall(text.lower()) if w not in STOP}


def similarity(a, b):
    """Overlap coefficient of the stems of two statements: shared stems over those of the shorter one."""
    sa, sb = stems(a), stems(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / min(len(sa), len(sb))


def _concept(global_id):
    """entrylib:2026.000014@v2#C3 -> entrylib:2026.000014"""
    return re.split(r"[@#]", global_id, maxsplit=1)[0] if isinstance(global_id, str) else ""


def novelty(claim, matches, concept=None):
    """The claim's novelty label and the close-match check: check is "none" (no close match on EntryLib),
    "acknowledged" (close matches, all related to by the claim) or "unacknowledged"; matches lists the close ones,
    each with its similarity and whether it is acknowledged. Matches from the claim's own claimset (`concept`) are
    ignored."""
    label = claim.get("novelty")
    targets = {r.get("target") for r in claim.get("relations") or [] if isinstance(r, dict)}
    targets |= {_concept(t) for t in targets}
    close = []
    for m in matches or []:
        gid = m.get("claim") if isinstance(m, dict) else None
        if not isinstance(gid, str) or (concept and _concept(gid) == concept):
            continue
        s = similarity(claim.get("statement"), m.get("statement"))
        if s >= CLOSE:
            close.append({"claim": gid, "similarity": round(s, 2),
                          "acknowledged": gid in targets or _concept(gid) in targets})
    close.sort(key=lambda m: -m["similarity"])
    check = ("none" if not close else "acknowledged" if all(m["acknowledged"] for m in close)
             else "unacknowledged")
    return {"label": label if label != "not_applicable" else None, "check": check, "matches": close}
