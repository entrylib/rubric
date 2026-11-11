"""The scores as a plain-text report (RUBRIC.md §4.3), for the authors and their agents: of a published claimset (the
portal's issues.txt) or of one not yet submitted (`claimset score`).

    report(scores, biggest_n=0) -> the report; `biggest_n` > 0 adds the problems that cost one claim the most
    open_problems(scores)     -> [(id, problem, {claim: cost})] of the problems that lower a score, in rubric order
    biggest(scores, n)        -> the n problems that cost one claim the most, most costly first

`scores` is what score() or assess() returns; assess() adds `novelty`, and only claims it compared (`checked`) can be
in question.
"""


def _sentence(words):
    words = str(words)
    return words if words.rstrip().endswith((".", "!", "?")) else words + "."


def open_problems(scores):
    """[(id, problem, {claim id: cost})] of every problem that lowers some claim's score, in the order of score()
    (those of the principal claims first, most costly first)."""
    out = []
    for pid, p in (scores.get("problems") or {}).items():
        lowers = {cid: c["costs"][pid] for cid, c in (scores.get("claims") or {}).items() if pid in c["problems"]}
        if lowers:
            out.append((pid, p, lowers))
    return out


def biggest(scores, n=3):
    """The n problems that cost one claim the most, most costly first (ties keep the rubric's order)."""
    return sorted(open_problems(scores), key=lambda x: -max(x[2].values()))[:n]


def report(scores, biggest_n=0):
    """The report of RUBRIC.md §4.3, as text ending in a newline."""
    out = []
    paper = scores.get("paper")
    if paper:
        out.append(f"PAPER: reliability {paper['score']} ({paper['band']}), the score of its lowest principal claim, "
                   f"{paper['lowest']}. Raising the lowest principal claim raises the paper.")
    else:
        out.append("PAPER: no score (no principal claim is scored).")
    out.append("")
    top = biggest(scores, biggest_n) if biggest_n else []
    if top:
        out.append("BIGGEST ISSUES, most costly first:")
        out += [f"  {pid} ({', '.join(f'{c} -{cost}' for c, cost in lowers.items())}): {_sentence(p['text'])} "
                f"To fix: {p['fix']}" for pid, p, lowers in top]
        out.append("")
    flagged = {cid: n for cid, n in (scores.get("novelty") or {}).items()
               if isinstance(n, dict) and n.get("check") == "unacknowledged" and n.get("checked", True)}
    if flagged:
        out.append("NOVELTY IN QUESTION: close matches on EntryLib that the claim does not relate to:")
        out += [f"  {cid}: " + ", ".join(f"{m['claim']} (similarity {m['similarity']})" for m in n["matches"]
                                        if not m["acknowledged"]) for cid, n in flagged.items()]
        out.append("")
    problems = open_problems(scores)
    if not problems:
        out.append("No issues: every scored claim keeps all its points.")
        return "\n".join(out) + "\n"
    out.append("ISSUES, those of the principal claims first, most costly first:")
    for pid, p, lowers in problems:
        out += ["", f"{pid}. {_sentence(p['text'])}",
                f"  Check: {p['check']} (group: {p['group']}); costs up to {p['cost']} points.",
                f"  Lowers: {', '.join(f'{c} (-{cost})' for c, cost in lowers.items())}."]
        if p.get("objects"):
            out.append(f"  Concerns: {', '.join(p['objects'])}.")
        out.append(f"  To fix: {p['fix']}")
    out += ["", "CLAIMS: score (band): issues"]
    for cid, c in scores["claims"].items():
        issues = ", ".join(f"{p} (-{c['costs'][p]})" for p in c["problems"]) or "none"
        out.append(f"{cid}: {c['score']} ({c['band']}): {issues}")
    return "\n".join(out) + "\n"
