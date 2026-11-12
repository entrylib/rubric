"""Reliability scores (RUBRIC.md §2–5).

score(doc, warnings=None) -> {
    "rubric": "0.4",
    "claims": {"C1": {"score": 94, "band": "high", "dots": {"support": "green", ...}, "problems": ["P3", ...],
                      "costs": {"P3": 6, ...}, "inherited": {"P5": ["C2"], ...}}, ...},
    "assumptions": ["C24", ...],                 # not scored
    "paper": {"score": 74, "band": "medium", "dots": {...}, "problems": [...], "principal": [...], "lowest": "C6",
              "lowest_score": 60, "lowest_problems": [...]} or None when no principal claim is scored,
    "problems": {"P1": {"check", "group", "cost", "claims", "arises_in", "objects", "text", "fix"}, ...},
}

`warnings` are the claimset validator's warnings for the file ([{rule, where, message}], its published validation
report), when given: warning 17 decides `numbers_without_results`, and a limitation with warning 46 (it restates the
declared competing interest) costs nothing.

A problem in "problems" is one aggregated problem (§3.6) over the principal claims and what they rest on (then over the
other claims); its "cost" is the most it costs any one claim, "claims" every claim it lowers and "arises_in" the claims
it is found on. A claim lists the problems that reach it, with what each costs that claim under "costs", and under
"inherited" the ones it has from what it rests on, with the claims they arise in. The paper's score is the mean of its
principal claims' (§5); "problems" of the paper are every problem open in its principal claims, for the explanation.
"""

import json
import re
from importlib import resources

RUBRIC = json.loads(resources.files(__package__).joinpath("rubric.json").read_text(encoding="utf-8"))
VERSION = RUBRIC["version"]
CHECKS = RUBRIC["checks"]
GROUPS = [g["name"] for g in RUBRIC["groups"]]

EVIDENCE_KINDS = {"empirical_quant", "empirical_qual", "empirical_obs", "simulation", "demonstration"}
OBSERVATION_KINDS = {"empirical_quant", "empirical_obs", "simulation"}       # evidence whose observations are cited
SPECIFIC = re.compile(r"\.R\d+$|\.T\d+\.r\d+$|#row=")                  # a result entry, a table row, data rows
STUDIED_ROLES = {"subject", "baseline"}
INFERENTIAL = {"associational", "causal", "mechanistic", "predictive"}
SUPPORT_WORDS = {"evidence": "evidence",
                 "evidence_unspecified": "evidence named without the observations the claim reports",
                 "argument_from_claims": "an argument from other claims",
                 "formal_checked": "a checked proof", "formal_unchecked": "an unchecked proof",
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


def _cites_observations(s, evidence):
    """Whether a support entry names the observations its claim reports (§3.1): a result entry, a table row or data
    rows, or evidence that records no results or tables."""
    if any(isinstance(r, str) and SPECIFIC.search(r) for r in _list(s.get("results"))):
        return True
    e = _dict(evidence.get(s.get("evidence")))
    return bool(e) and not _list(e.get("results")) and not _list(e.get("tables"))


def _support_cost(c, by_id, evidence):
    costs = CHECKS["support_kind"]["costs"]
    best = None
    for s in _list(c.get("support")):
        kind = s.get("kind") if isinstance(s, dict) else None
        if kind in OBSERVATION_KINDS:
            key = "evidence" if _cites_observations(s, evidence) else "evidence_unspecified"
        elif kind in EVIDENCE_KINDS:
            key = "evidence"
        elif kind == "formal_proof":
            v = c.get("verification")
            key = ("formal_checked" if v in ("machine_checked", "agent_checked", "peer_checked")
                   else "formal_disputed" if v == "disputed" else "formal_unchecked")
        elif kind == "argument":
            premises = [by_id.get(d) for d in _list(c.get("depends_on")) if isinstance(d, str)]
            key = "argument_from_claims" if any(p and not is_assumption(p) for p in premises) else "argument"
        elif kind in costs:
            key = kind
        else:
            continue
        if best is None or costs[key] < costs[best]:
            best = key
    return best


def _api_model_studied(c, doc, evidence):
    """Whether every API-only model in the evidence the claim's support names is what is studied there (§3.3)."""
    weights = {m.get("id"): m.get("weights") for m in _list(doc.get("models")) if isinstance(m, dict)}
    roles = [_dict(dm).get("role") for s in _list(c.get("support")) if isinstance(s, dict)
             for dm in _list(_dict(evidence.get(s.get("evidence"))).get("models"))
             if weights.get(_dict(dm).get("model")) == "api_only"]
    return bool(roles) and all(r in STUDIED_ROLES for r in roles)


NAME_WITH_DIGITS = re.compile(r"(?<![\w.])[A-Za-z0-9_]+(?:-[A-Za-z0-9_]+)*")


def _has_numbers(statement):
    text = MATH.sub(" ", TERM.sub(" ", statement if isinstance(statement, str) else ""))
    text = re.sub(r"\b[A-Z]{1,2}\d+(?:\.[A-Za-z]*\d+)*\b", " ", text)       # object IDs: C4, E1.T1.r2
    text = NAME_WITH_DIGITS.sub(lambda m: " " if re.search(r"[A-Za-z]", m.group(0)) else m.group(0), text)  # GPT-4o
    return re.search(r"\d", text) is not None


#: Planning values of claims planned before they were run (§3.2): tests, and estimates (claimset v0.42).
PLANNED = ("confirmatory", "confirmatory_with_deviations", "planned_estimate")


def _unplanned_cost(c, public_record):
    """What the claim would cost for being exploratory (§3.2): the most its plan's problems may cost."""
    record = "with_public_record" if public_record else "without_public_record"
    if c.get("type") in INFERENTIAL:
        return CHECKS["exploratory_inference"]["costs"][record]
    if c.get("role") == "principal" and c.get("type") != "formal":
        return CHECKS["exploratory_principal"]["costs"][record]
    return 0


def _capped(plan, limit):
    """A plan's problems cut so that together they cost at most `limit`, the costliest kept first (§3.2)."""
    out = []
    for check, key, cost, claims, args in sorted(plan, key=lambda i: -i[2]):
        cost = min(cost, limit)
        limit -= cost
        if cost > 0:
            out.append((check, key, cost, claims, args))
    return out


def _instances(doc, c, by_id, public_record, evidence, warned):
    """The problems of one claim itself: [(check, key, cost, objects, args)]. `warned` is the set of (rule, where) of
    the validator's warnings, or None when they were not given."""
    out = []
    cid = c.get("id")
    formal = c.get("type") == "formal"

    key = _support_cost(c, by_id, evidence)
    cost = CHECKS["support_kind"]["costs"].get(key, 0) if key else CHECKS["support_kind"]["costs"]["unstated"]
    if cost:
        out.append(("support_kind", cid, cost, [cid], {"what": SUPPORT_WORDS.get(key or "unstated")}))

    planning = c.get("planning")
    record = "; the lab record shows every run" if public_record else ""
    if planning in (None, "exploratory"):
        t = c.get("type")
        cost = _unplanned_cost(c, public_record)
        if t in INFERENTIAL:
            out.append(("exploratory_inference", cid, cost, [cid],
                        {"type": ("An " if t[0] in "aeiou" else "A ") + t, "record": record}))
        elif cost:
            out.append(("exploratory_principal", cid, cost, [cid], {"type": t or "", "record": record}))
    plan = []
    if planning in PLANNED:
        anchor = c.get("planned_at_anchor")
        costs = CHECKS["plan_anchor"]["costs"]
        if anchor == "git_remote" or anchor in (None, "none"):
            how = "by a git push only" if anchor == "git_remote" else "by nothing"
            plan.append(("plan_anchor", cid, costs["git_remote" if anchor == "git_remote" else "none"], [cid],
                         {"how": how}))
    if planning == "confirmatory_with_deviations":
        plan.append(("plan_deviations", cid, CHECKS["plan_deviations"]["costs"]["deviations"], [cid], {}))
    flags = [f for f in _list(_dict(c.get("test")).get("flags")) + _list(_dict(c.get("estimate")).get("flags"))
             if isinstance(f, str)]
    if flags:
        ch = CHECKS["plan_flags"]
        plan.append(("plan_flags", cid, sum(repeated([ch["cost_each"]] * len(flags))), [cid],
                     {"flags": ", ".join(f.replace("_", " ") for f in flags)}))
    out += _capped(plan, _unplanned_cost(c, public_record)) if planning in PLANNED else plan

    level = c.get("verifiability")
    if level in CHECKS["verifiability"]["costs"]:
        out.append(("verifiability", cid, CHECKS["verifiability"]["costs"][level], [cid],
                    {"level": level.replace("_", " ")}))
    vflags = [f for f in _list(c.get("verifiability_flags"))
              if isinstance(f, str) and f not in ("unstated_support", "unanchored_plan")
              and not (f == "api_model_dependency" and _api_model_studied(c, doc, evidence))]
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
    if warned is not None:
        unsourced = not formal and ("W17", f"claims:{cid}.statement") in warned
    else:
        unsourced = not formal and _has_numbers(c.get("statement")) and not any(
            isinstance(s, dict) and _list(s.get("results")) for s in _list(c.get("support")))
    if unsourced:
        out.append(("numbers_without_results", cid, CHECKS["numbers_without_results"]["costs"]["missing"], [cid], {}))

    lim_costs = CHECKS["limitation"]["costs"]
    for lim in _list(doc.get("limitations")):
        if isinstance(lim, dict) and cid in _list(lim.get("affects")) and not _restated(lim, warned):
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


def _restated(lim, warned):
    """A limitation that only restates the declared competing interest (warning 46; §3.5)."""
    return warned is not None and ("W46", f"limitations:{lim.get('id')}.statement") in warned


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


def score(doc, warnings=None):
    """The reliability scores of a published claimset (RUBRIC.md §2–5), given the validator's warnings for it when
    they are available (its validation report)."""
    claims = [c for c in _list(doc.get("claims")) if isinstance(c, dict) and isinstance(c.get("id"), str)]
    by_id = {c["id"]: c for c in claims}
    evidence = {e.get("id"): e for e in _list(doc.get("evidence")) if isinstance(e, dict)}
    warned = None if warnings is None else {(_dict(w).get("rule"), _dict(w).get("where")) for w in _list(warnings)}
    public_record = _public_record(doc)
    own = {c["id"]: _instances(doc, c, by_id, public_record, evidence, warned) for c in claims if not is_assumption(c)}
    limited = {cid for lim in _list(doc.get("limitations")) if isinstance(lim, dict) and not _restated(lim, warned)
               for cid in _list(lim.get("affects")) if isinstance(cid, str)}
    for c in claims:                                            # no_limitation (§3.5): nothing it rests on declares one
        if (c["id"] in own and c.get("role") == "principal" and c.get("type") != "formal"
                and not limited & set(_closure(c["id"], by_id))):
            own[c["id"]].append(("no_limitation", c["id"], CHECKS["no_limitation"]["costs"]["missing"], [c["id"]], {}))

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
                "arises_in": _sort_claims(p["claims"]),
                "objects": [k[1]] if k[1] is not None else [], "text": text, "fix": ch["fix"]}

    problems = {pid[k]: describe(k, paper_agg.get(k) or everything[k]) for k in order}

    out_claims = {}
    for cid in own:
        agg = _aggregate(gathered([cid]))
        mine = set(_aggregate(own[cid]))
        value, dots = _result(agg)
        listed = sorted(agg, key=lambda k: (-agg[k]["cost"], pid[k]))
        out_claims[cid] = {"score": value, "band": band(value), "dots": dots,
                           "problems": [pid[k] for k in listed if agg[k]["cost"]],
                           "costs": {pid[k]: agg[k]["cost"] for k in listed if agg[k]["cost"]},
                           "inherited": {pid[k]: problems[pid[k]]["arises_in"] for k in listed
                                         if agg[k]["cost"] and k not in mine}}

    # A problem's cost is the most it costs any one claim (a repeated problem may cost one claim less than another);
    # its claims are every claim it lowers, as the claims' own lists say (§2: inherited problems).
    for k in order:
        lowered = [cid for cid, c in out_claims.items() if pid[k] in c["costs"]]
        if lowered:
            problems[pid[k]]["cost"] = max(out_claims[c]["costs"][pid[k]] for c in lowered)
            problems[pid[k]]["claims"] = _sort_claims(lowered)

    paper = None
    if principal:
        # The paper's score is the mean of its principal claims' (§5), shown with the lowest; its dots, the worst of
        # each group among them.
        lowest = min(principal, key=lambda c: (out_claims[c]["score"], len(c), c))
        value = int(sum(out_claims[c]["score"] for c in principal) / len(principal) + 0.5)
        rank = {"green": 0, "amber": 1, "red": 2}
        dots = {g: max((out_claims[c]["dots"][g] for c in principal), key=rank.get) for g in GROUPS}
        listed = [k for k in order if k in paper_agg and paper_agg[k]["cost"]]
        paper = {"score": value, "band": band(value), "dots": dots, "problems": [pid[k] for k in listed],
                 "principal": principal, "lowest": lowest, "lowest_score": out_claims[lowest]["score"],
                 "lowest_problems": out_claims[lowest]["problems"]}
    return {"rubric": VERSION, "claims": out_claims,
            "assumptions": [c["id"] for c in claims if is_assumption(c)], "paper": paper, "problems": problems}
