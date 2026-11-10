"""Reliability scores (RUBRIC.md §2–5).

score(doc) -> {
    "rubric": "0.1",
    "claims": {"C1": {"score": 94, "band": "high", "dots": {"support": "green", ...}, "problems": ["P3", ...]}, ...},
    "assumptions": ["C24", ...],                 # not scored
    "paper": {"score": 60, "band": "medium", "dots": {...}, "problems": [...], "principal": [...], "lowest": "C6",
              "lowest_problems": [...]} or None when no principal claim is scored,
    "problems": {"P1": {"check", "group", "cost", "claims", "objects", "text", "fix"}, ...},
}

A problem in "problems" is one aggregated problem (§3.6) over the principal claims and what they rest on (then over the
other claims); its "cost" is the most it costs any one claim. A claim lists the problems that reach it, with what each
costs that claim under "costs". The paper's score is that of its lowest principal claim; "problems" of the paper are
every problem open in its principal claims, for the explanation.
"""

import json
import re
from importlib import resources

RUBRIC = json.loads(resources.files(__package__).joinpath("rubric.json").read_text(encoding="utf-8"))
VERSION = RUBRIC["version"]
CHECKS = RUBRIC["checks"]
GROUPS = [g["name"] for g in RUBRIC["groups"]]

EVIDENCE_KINDS = {"empirical_quant", "empirical_qual", "empirical_obs", "simulation", "demonstration"}
INFERENTIAL = {"associational", "causal", "mechanistic", "predictive"}
SUPPORT_WORDS = {"evidence": "evidence", "formal_checked": "a checked proof", "formal_unchecked": "an unchecked proof",
                 "formal_disputed": "a disputed proof", "cited": "cited work only", "consensus": "consensus only",
                 "argument": "argument only", "expert_judgement": "expert judgement only",
                 "unstated": "no stated support"}
TERM = re.compile(r"\[\[[^\]:]+:([^\]]*)\]\]")
MATH = re.compile(r"\$\$.+?\$\$|\$[^$]+\$|\\\(.+?\\\)", re.S)


def band(value):
    """The band of a score: high, medium or low (§4.1)."""
    if value is None:
        return None
    for b in RUBRIC["bands"]:
        if value >= b["min"]:
            return b["name"]
    return RUBRIC["bands"][-1]["name"]


def _dot(points):
    d = RUBRIC["dots"]
    return "green" if points <= d["green_max"] else "amber" if points <= d["amber_max"] else "red"


def _list(x):
    return x if isinstance(x, list) else []


def _dict(x):
    return x if isinstance(x, dict) else {}


def is_assumption(c):
    kinds = [s.get("kind") for s in _list(c.get("support")) if isinstance(s, dict)]
    return bool(kinds) and all(k == "assumption" for k in kinds)


def _public_record(doc):
    rid = _dict(_dict(doc.get("paper")).get("exploration")).get("lab_record")
    for a in _list(doc.get("artefacts")):
        if isinstance(a, dict) and a.get("id") == rid:
            return _dict(a.get("availability")).get("level") == "public"
    return False


def _support_cost(c):
    costs = CHECKS["support_kind"]["costs"]
    best = None
    for s in _list(c.get("support")):
        kind = s.get("kind") if isinstance(s, dict) else None
        if kind in EVIDENCE_KINDS:
            key = "evidence"
        elif kind == "formal_proof":
            v = c.get("verification")
            key = ("formal_checked" if v in ("machine_checked", "agent_checked", "peer_checked")
                   else "formal_disputed" if v == "disputed" else "formal_unchecked")
        elif kind in costs:
            key = kind
        else:
            continue
        if best is None or costs[key] < costs[best]:
            best = key
    return best


def _has_numbers(statement):
    text = MATH.sub(" ", TERM.sub(" ", statement if isinstance(statement, str) else ""))
    text = re.sub(r"\b[A-Z]{1,2}\d+(?:\.[A-Za-z]*\d+)*\b", " ", text)       # object IDs: C4, E1.T1.r2
    return re.search(r"\d", text) is not None


def _instances(doc, c, by_id, public_record):
    """The problems of one claim itself: [(check, key, cost, objects, args)]."""
    out = []
    cid = c.get("id")
    formal = c.get("type") == "formal"

    key = _support_cost(c)
    cost = CHECKS["support_kind"]["costs"].get(key, 0) if key else CHECKS["support_kind"]["costs"]["unstated"]
    if cost:
        out.append(("support_kind", cid, cost, [cid], {"what": SUPPORT_WORDS.get(key or "unstated")}))

    planning = c.get("planning")
    if c.get("type") in INFERENTIAL and planning in (None, "exploratory"):
        costs = CHECKS["exploratory_inference"]["costs"]
        cost = costs["with_public_record" if public_record else "without_public_record"]
        t = c.get("type")
        out.append(("exploratory_inference", cid, cost, [cid],
                    {"type": ("An " if t[0] in "aeiou" else "A ") + t, "record": "; the lab record shows every run" if public_record else ""}))
    if planning in ("confirmatory", "confirmatory_with_deviations"):
        anchor = c.get("planned_at_anchor")
        costs = CHECKS["plan_anchor"]["costs"]
        if anchor == "git_remote" or anchor in (None, "none"):
            how = "by a git push only" if anchor == "git_remote" else "by nothing"
            out.append(("plan_anchor", cid, costs["git_remote" if anchor == "git_remote" else "none"], [cid],
                        {"how": how}))
    if planning == "confirmatory_with_deviations":
        out.append(("plan_deviations", cid, CHECKS["plan_deviations"]["costs"]["deviations"], [cid], {}))
    flags = [f for f in _list(_dict(c.get("test")).get("flags")) if isinstance(f, str)]
    if flags:
        ch = CHECKS["plan_flags"]
        out.append(("plan_flags", cid, sum(repeated([ch["cost_each"]] * len(flags))), [cid],
                    {"flags": ", ".join(f.replace("_", " ") for f in flags)}))

    level = c.get("verifiability")
    if level in CHECKS["verifiability"]["costs"]:
        out.append(("verifiability", cid, CHECKS["verifiability"]["costs"][level], [cid],
                    {"level": level.replace("_", " ")}))
    vflags = [f for f in _list(c.get("verifiability_flags"))
              if isinstance(f, str) and f not in ("unstated_support", "unanchored_plan")]
    if vflags:
        ch = CHECKS["verifiability_flags"]
        out.append(("verifiability_flags", cid, sum(repeated([ch["cost_each"]] * len(vflags))), [cid],
                    {"flags": ", ".join(f.replace("_", " ") for f in vflags)}))

    if not formal and not _dict(c.get("scope")):
        out.append(("no_scope", cid, CHECKS["no_scope"]["costs"]["missing"], [cid], {}))
    if c.get("role") == "principal" and c.get("novelty") != "not_applicable":
        outside = any(isinstance(r, dict) and r.get("id_type") != "local" for r in _list(c.get("relations")))
        cited = any(isinstance(s, dict) and s.get("kind") == "cited" for s in _list(c.get("support")))
        if not (outside or cited):
            out.append(("no_prior_work", cid, CHECKS["no_prior_work"]["costs"]["missing"], [cid], {}))
    if not formal and _has_numbers(c.get("statement")):
        if not any(isinstance(s, dict) and _list(s.get("results")) for s in _list(c.get("support"))):
            out.append(("numbers_without_results", cid, CHECKS["numbers_without_results"]["costs"]["missing"],
                        [cid], {}))

    lim_costs = CHECKS["limitation"]["costs"]
    for lim in _list(doc.get("limitations")):
        if isinstance(lim, dict) and cid in _list(lim.get("affects")):
            cost = _dict(lim_costs.get(lim.get("impact"))).get(lim.get("mitigation") or "none", 0)
            if cost:
                out.append(("limitation", lim.get("id"), cost, [cid],
                            {"id": lim.get("id"), "impact": str(lim.get("impact", "")).replace("_", " "),
                             "mitigation": "not mitigated" if (lim.get("mitigation") or "none") == "none"
                             else f"mitigation {lim.get('mitigation')}", "statement": lim.get("statement", "")}))
    for aid in _list(c.get("assumptions")):
        a = by_id.get(aid)
        if isinstance(a, dict) and a.get("check") == "unchecked":
            out.append(("unchecked_assumption", aid, CHECKS["unchecked_assumption"]["cost_each"], [cid],
                        {"id": aid, "statement": a.get("statement", "")}))
    return out


def _closure(cid, by_id):
    """The claim and everything it rests on (depends_on and assumptions), followed to the end."""
    seen, stack = [], [cid]
    while stack:
        x = stack.pop()
        if x in seen or x not in by_id:
            continue
        seen.append(x)
        c = by_id[x]
        stack.extend(i for i in _list(c.get("depends_on")) + _list(c.get("assumptions")) if isinstance(i, str))
    return seen


def repeated(costs):
    """The costs of repeated problems of one check on one claim (RUBRIC.md §3.6): sorted from the largest, the first
    in full and each next one half the one before (rounded down, at least 1), so that every one removed or mitigated
    lowers the total and the total stays below twice the largest."""
    return [0 if c <= 0 else max(1, c // 2 ** i) for i, c in enumerate(sorted(costs, reverse=True))]


def _aggregate(instances):
    """Instances counted as RUBRIC.md §3.6: {(check, key): {cost, claims, objects, args}}; key is None for `kind`."""
    out = {}
    for check, key, cost, claims, args in instances:
        k = (check, None) if CHECKS[check]["count"] == "kind" else (check, key)
        p = out.setdefault(k, {"check": check, "cost": 0, "claims": [], "args": args})
        if cost > p["cost"]:
            p["cost"], p["args"] = cost, args
        for c in claims:
            if c not in p["claims"]:
                p["claims"].append(c)
    for check in {k[0] for k in out if CHECKS[k[0]]["count"] == "each"}:
        items = sorted((p for k, p in out.items() if k[0] == check), key=lambda p: -p["cost"])
        for p, cost in zip(items, repeated([p["cost"] for p in items])):
            p["cost"] = cost
    return out


def _sort_claims(ids):
    return sorted(ids, key=lambda i: (len(i), i))


def _result(agg):
    total = sum(p["cost"] for p in agg.values())
    value = max(0, 100 - total)
    lost = {g: 0 for g in GROUPS}
    for p in agg.values():
        lost[CHECKS[p["check"]]["group"]] += p["cost"]
    return value, {g: _dot(v) for g, v in lost.items()}


def score(doc):
    """The reliability scores of a published claimset (RUBRIC.md §2–5)."""
    claims = [c for c in _list(doc.get("claims")) if isinstance(c, dict) and isinstance(c.get("id"), str)]
    by_id = {c["id"]: c for c in claims}
    public_record = _public_record(doc)
    own = {c["id"]: _instances(doc, c, by_id, public_record) for c in claims if not is_assumption(c)}

    def gathered(ids):
        return [i for x in ids for cid in _closure(x, by_id) for i in own.get(cid, [])]

    principal = [c["id"] for c in claims if c.get("role") == "principal" and c["id"] in own]
    paper_agg = _aggregate(gathered(principal)) if principal else {}
    everything = _aggregate(gathered(list(own)))
    # Problem IDs: those of the paper first, by cost, then the rest; stable for a given file.
    order = sorted(paper_agg, key=lambda k: (-paper_agg[k]["cost"], k[0], str(k[1])))
    order += sorted((k for k in everything if k not in paper_agg), key=lambda k: (k[0], str(k[1])))
    pid = {k: f"P{i + 1}" for i, k in enumerate(order)}

    def describe(k, p):
        ch = CHECKS[k[0]]
        try:
            text = ch["text"].format(**p["args"])
        except (KeyError, IndexError):
            text = ch["text"]
        return {"check": k[0], "group": ch["group"], "cost": p["cost"], "claims": _sort_claims(p["claims"]),
                "objects": [k[1]] if k[1] is not None else [], "text": text, "fix": ch["fix"]}

    problems = {pid[k]: describe(k, paper_agg.get(k) or everything[k]) for k in order}

    out_claims = {}
    for cid in own:
        agg = _aggregate(gathered([cid]))
        value, dots = _result(agg)
        listed = sorted(agg, key=lambda k: (-agg[k]["cost"], pid[k]))
        out_claims[cid] = {"score": value, "band": band(value), "dots": dots,
                           "problems": [pid[k] for k in listed if agg[k]["cost"]],
                           "costs": {pid[k]: agg[k]["cost"] for k in listed if agg[k]["cost"]}}

    # A problem's cost is the most it costs any one claim (a repeated problem may cost one claim less than another).
    for k in order:
        charged = [c["costs"][pid[k]] for c in out_claims.values() if pid[k] in c["costs"]]
        if charged:
            problems[pid[k]]["cost"] = max(charged)

    paper = None
    if principal:
        # The paper's score is its lowest principal claim's (§5); its dots, the worst of each group among them.
        lowest = min(principal, key=lambda c: (out_claims[c]["score"], len(c), c))
        value = out_claims[lowest]["score"]
        rank = {"green": 0, "amber": 1, "red": 2}
        dots = {g: max((out_claims[c]["dots"][g] for c in principal), key=rank.get) for g in GROUPS}
        listed = [k for k in order if k in paper_agg and paper_agg[k]["cost"]]
        paper = {"score": value, "band": band(value), "dots": dots, "problems": [pid[k] for k in listed],
                 "principal": principal, "lowest": lowest,
                 "lowest_problems": out_claims[lowest]["problems"]}
    return {"rubric": VERSION, "claims": out_claims,
            "assumptions": [c["id"] for c in claims if is_assumption(c)], "paper": paper, "problems": problems}
