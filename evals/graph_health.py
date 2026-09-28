"""
graph_health.py — Phase 1B: is the knowledge graph itself accurate?

WHY THIS EXISTS (simple version)
    Your answer evals ask "was the reply good?". They cannot tell you WHY it was
    bad. This checks the graph itself, before any AI is involved, and turns
    "is my graph accurate?" into a pass/fail list you can re-run after a rebuild.

    Picture the graph as sticky notes joined by string. Rules 1-6 ask about
    the notes themselves; rules 7-8 (Phase 2a) about the text handed to the AI:
      1. SOURCE      does every note say where it came from?
      2. CONNECTED   is every note tied to something (no note floating alone)?
      3. STRINGS     do the strings join sensible kinds of note?
      4. COMPLETE    does every fault have at least one cause and one fix?
      5. AGREEMENT   do two notes contradict each other about the same number?
      6. BELONGING   does every note belong to a machine that exists here?
      7. HAND-OVER   does every fact on a fault's path reach the AI?
      8. RELEVANCE   does a fault's hand-over leave out other faults' facts?

COST
    Free. Read-only Cypher against Neo4j. No Groq tokens, no writes.

RUN (from C:\\plantmind; the app does NOT need to be running)
    venv\\Scripts\\python.exe evals\\graph_health.py
    venv\\Scripts\\python.exe evals\\graph_health.py --equip WM-101

OUTPUT
    A pass/fail line per rule, the offending notes, and a saved JSON file in
    evals/graph_health/ — the "before" number for the Phase 1B rebuild.
"""

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import knowledge_graph as kg  # noqa: E402

OUT_DIR = ROOT / "evals" / "graph_health"

# ── Rule 3's rulebook ────────────────────────────────────────────────────────
# The allowed (from) -[string]-> (to) combinations. This is a small, written-down
# ontology: the one-page version of "which notes may be joined by which string".
# Anything not listed is reported, which is how a "specification" linked as a
# CAUSE of a fault gets caught.
ALLOWED_LINKS = {
    ("Equipment", "HAS_FAULT"):      {"Fault", "Pattern"},
    ("Equipment", "REQUIRES_SAFETY"): {"Safety"},             # PPE applies to the machine
    ("Equipment", "DOCUMENTED_IN"):  {"Document"},
    ("Fault", "CAUSED_BY"):          {"Component"},          # a cause, never a spec
    ("Fault", "CAUSES"):             {"Fault"},
    ("Fault", "TRIGGERS"):           {"Safety", "Pattern", "Procedure"},
    ("Fault", "REFERENCED_IN"):      {"Document"},
    ("Fault", "HAS_PARAMETER"):      {"Parameter"},          # the intended home for specs
    ("Component", "FIXED_BY"):       {"Procedure"},
    ("Component", "REPLACED_WITH"):  {"Part"},
    ("Component", "REFERENCED_IN"):  {"Document"},
    ("Component", "TRIGGERS"):       {"Pattern"},
    ("Component", "HAS_PARAMETER"):  {"Parameter"},
    ("Procedure", "REQUIRES"):       {"Procedure"},
    ("Procedure", "REQUIRES_SAFETY"): {"Safety"},
    ("Procedure", "INCLUDES"):       {"Procedure"},
    ("Procedure", "DOCUMENTED_IN"):  {"Document"},
    ("Procedure", "REFERENCED_IN"):  {"Document"},
    ("Pattern", "REQUIRES"):         {"Procedure"},
    # The blueprint/plant-map layers (ontology_bootstrap.py). A machine is
    # LOCATED_AT a place; only places CONTAIN places.
    ("Equipment", "IS_INSTANCE_OF"): {"Class"},
    ("Equipment", "IS_LOCATED_AT"):  {"WorkCenter", "Location", "Instance", "Area", "Site"},
}

# Note types that are allowed to have no source of their own.
# A Document IS the source; Equipment and Part are physical things, not claims.
SOURCE_EXEMPT = {"Document", "Equipment", "Part"}

# Note types that are allowed to sit unconnected — none. Every note should be
# reachable from the machine, or the AI can never find it.
RANGE_RE = re.compile(r"(\d{1,3})\s*(?:-|to)\s*(\d{1,3})\s*(V|A|bar|L/min|m/min)\b", re.I)


def flatten(text):
    """
    Make dashes and spaces plain before reading numbers out of text.

    The first version of rule 5 PASSED while the graph held both "18 to 22V"
    and "15-16 V" — because the second one was written with a non-breaking
    hyphen (U+2011) and a non-breaking space, which did not match the pattern.
    The same trap caught an eval check earlier in this project: characters that
    LOOK plain but are not. A check that silently misses is worse than no check.
    """
    return (re.sub(r"[‐-―−]", "-", text or "")
            .replace(" ", " ").replace(" ", " "))


def q(cypher, **params):
    return kg._run(cypher, params)


def rule_source(equip):
    """1. Does every note say where it came from?"""
    rows = q("MATCH (n) WHERE n.equip_tag = $e AND (n.source IS NULL OR n.source = '') "
             "RETURN labels(n)[0] AS type, n._id AS id, n._label AS name", e=equip)
    bad = [r for r in rows if r["type"] not in SOURCE_EXEMPT]
    return bad, [f'{r["type"]}: {(r["name"] or r["id"])[:60]}' for r in bad]


def rule_connected(equip):
    """2. Is every note tied to something?"""
    rows = q("MATCH (n) WHERE n.equip_tag = $e AND NOT (n)--() "
             "RETURN labels(n)[0] AS type, n._id AS id, n._label AS name", e=equip)
    return rows, [f'{r["type"]}: {(r["name"] or r["id"])[:60]}' for r in rows]


def rule_strings(equip):
    """3. Do the strings join sensible kinds of note?"""
    rows = q("MATCH (a)-[r]->(b) WHERE a.equip_tag = $e "
             "RETURN labels(a)[0] AS a, type(r) AS rel, labels(b)[0] AS b, "
             "a._label AS a_name, b._label AS b_name", e=equip)
    bad = [r for r in rows if b_allowed(r) is False]
    return bad, [f'{r["a"]} -{r["rel"]}-> {r["b"]}  ({(r["a_name"] or "")[:28]} -> {(r["b_name"] or "")[:28]})'
                 for r in bad]


def b_allowed(r):
    allowed = ALLOWED_LINKS.get((r["a"], r["rel"]))
    return None if allowed is None else (r["b"] in allowed)


def rule_complete(equip):
    """4. Does every fault have at least one cause and one fix?"""
    rows = q("MATCH (f:Fault) WHERE f.equip_tag = $e "
             "OPTIONAL MATCH (f)-[:CAUSED_BY]->(c) "
             "OPTIONAL MATCH (f)-[:CAUSED_BY]->()-[:FIXED_BY]->(p) "
             "OPTIONAL MATCH (f)-[:TRIGGERS]->(p2:Procedure) "
             "RETURN f._label AS fault, count(DISTINCT c) AS causes, "
             "count(DISTINCT p) + count(DISTINCT p2) AS fixes", e=equip)
    bad = [r for r in rows if r["causes"] == 0 or r["fixes"] == 0]
    return bad, [f'{r["fault"]}: {r["causes"]} cause(s), {r["fixes"]} fix(es)' for r in bad]


def rule_agreement(equip):
    """
    5. Do two notes give different numbers for the same thing, with nothing
       saying which one wins?

    DISPUTED NOTES ARE SKIPPED, ON PURPOSE. A note marked status='disputed',
    with a reason and an 'overruled_by' pointing at the winning fact, is a
    RESOLVED disagreement: the graph is telling everyone which fact to trust.
    Keeping a wrong operator note, clearly labelled, is better than deleting it
    — the belief still exists on the floor, and the record shows it was judged.
    The rule exists to catch disagreements nobody has settled.

    (Rule changed after the first rebuild run, when this fired on exactly that
    case. The disputed notes are still printed below, so the exception can
    never hide a contradiction from you.)
    """
    rows = q("MATCH (n) WHERE n.equip_tag = $e AND coalesce(n.status,'') <> 'disputed' "
             "RETURN labels(n)[0] AS type, n._id AS id, "
             "n._label AS name, [k IN keys(n) WHERE k <> 'disputed_reason' "
             "| k + '=' + toString(n[k])] AS props", e=equip)
    claims = {}
    for r in rows:
        for prop in r["props"]:
            for lo, hi, unit in RANGE_RE.findall(flatten(prop)):
                claims.setdefault(unit.lower(), {}).setdefault(f"{lo}-{hi}", []).append(
                    f'{r["type"]}: {(r["name"] or r["id"])[:45]}')
    bad, detail = [], []
    for unit, ranges in claims.items():
        if len(ranges) > 1:
            bad.append({"unit": unit, "ranges": {k: v for k, v in ranges.items()}})
            detail.append(f"{unit}: " + " VS ".join(
                f'{rng} (said by {", ".join(sorted(set(who)))})' for rng, who in ranges.items()))

    # List what was skipped, so the exception is visible rather than silent.
    for d in q("MATCH (n) WHERE n.equip_tag = $e AND n.status = 'disputed' "
               "RETURN n._label AS name, n.overruled_by AS wins", e=equip):
        detail.append(f'settled: "{(d["name"] or "")[:50]}..." is disputed, '
                      f'overruled by {d["wins"]}')
    return bad, detail


def rule_belonging(equip):
    """6. Does every note belong to a machine that exists in the graph?"""
    rows = q("MATCH (n) WHERE n.equip_tag IS NOT NULL AND n.equip_tag <> '' "
             "AND NOT EXISTS { MATCH (e:Equipment {_id: n.equip_tag}) } "
             "RETURN DISTINCT n.equip_tag AS equip, count(*) AS notes")
    return rows, [f'{r["equip"]}: {r["notes"]} note(s), but no Equipment node for it' for r in rows]


# ── Rules 7-8: what the AI is actually HANDED, not what the graph holds ─────
# Added Phase 2a after the graph value test: the graph held "allow 10 minutes
# cooling" and "20 bar", but the text built for the AI dropped them, while
# burn-in and tension advice leaked into gas and tip reports. Rules 1-6 all
# passed throughout, because they check the graph, not the hand-over.
#
# A fault's PATH is worked out here independently of knowledge_graph.py (a
# test that reuses the code it tests can share its bug): follow these links
# from the fault, as far as they go.
PATH_LINKS = {"CAUSED_BY", "FIXED_BY", "REPLACED_WITH", "REQUIRES",
              "REQUIRES_SAFETY", "HAS_PARAMETER", "TRIGGERS", "INCLUDES"}
# Bookkeeping fields, not facts for the AI.
INTERNAL_KEYS = {"equip_tag", "plant_site", "line", "line_name", "source", "added_by",
                 "created_at", "candidate_id", "reviewed_at", "repaired_at",
                 "flagged_critical", "status", "overruled_by", "confirmed_count",
                 "source_type", "contributors", "disputed_reason"}


def _norm(text):
    return re.sub(r"\s+", " ", flatten(kg._clean(str(text)))).strip().lower()


def _graph(equip):
    nodes = {r["id"]: r for r in q(
        "MATCH (n) WHERE n.equip_tag = $e AND NOT n:Equipment "
        "RETURN n._id AS id, labels(n)[0] AS type, n._label AS label, "
        "properties(n) AS props", e=equip)}
    edges = q("MATCH (a)-[r]->(b) WHERE a.equip_tag = $e AND b.equip_tag = $e "
              "RETURN a._id AS a, type(r) AS rel, b._id AS b", e=equip)
    return nodes, edges


def _path(fault_id, nodes, edges, equip=None):
    # Safety linked from the machine itself (PPE, LOTO) applies to every
    # fault's work, so it is part of every path.
    seen = {e["b"] for e in edges if e["a"] == equip and e["rel"] == "REQUIRES_SAFETY"}
    seen.add(fault_id)
    todo = list(seen)
    while todo:
        cur = todo.pop()
        for e in edges:
            if e["a"] == cur and e["rel"] in PATH_LINKS and e["b"] not in seen:
                seen.add(e["b"])
                todo.append(e["b"])
    # A disputed note belongs to the path of the fact that overrules it.
    for nid, n in nodes.items():
        if n["props"].get("overruled_by") in seen:
            seen.add(nid)
    return seen


def _handover(equip, fault):
    """The text built for the AI when an operator describes exactly this fault."""
    words = f'{fault["label"]} {fault["props"].get("alarm_message", "")}'
    return kg.get_fault_chain(equip, incident_text=words).get("chain_text", "")


def _facts(node):
    for k, v in node["props"].items():
        if k.startswith("_") or k in INTERNAL_KEYS or v in (None, "", True, False):
            continue
        yield k, str(v)


def rule_handover(equip):
    """7. For every fault, is every fact on its path in the text handed to the AI?"""
    nodes, edges = _graph(equip)
    bad, detail = [], []
    for fid, fault in nodes.items():
        if fault["type"] != "Fault":
            continue
        text = _norm(_handover(equip, fault))
        for nid in sorted(_path(fid, nodes, edges, equip)):
            n = nodes.get(nid)
            # Documents are listed by name. A disputed note is shown on purpose
            # as a short REJECTED claim, never as facts to use (rule 5 covers it).
            if not n or n["type"] == "Document" or n["props"].get("status") == "disputed":
                continue
            for k, v in _facts(n):
                if _norm(v) not in text:
                    bad.append({"fault": fault["label"], "node": n["label"], "fact": k})
                    detail.append(f'{fault["label"][:28]}: {n["label"][:30]} · {k} = "{v[:50]}"')
    return bad, detail


def rule_relevance(equip):
    """8. For every fault, does its hand-over leave out other faults' facts?"""
    nodes, edges = _graph(equip)
    paths = {fid: _path(fid, nodes, edges, equip) for fid, n in nodes.items() if n["type"] == "Fault"}
    bad, detail = [], []
    for fid, mine in paths.items():
        text = _norm(_handover(equip, nodes[fid]))
        others = set().union(*(p for f, p in paths.items() if f != fid)) - mine
        # Words that also belong to this fault's own notes are not a leak
        # (two parts on different paths share "maintenance cabinet shelf 3").
        own = {_norm(v) for m in mine if m in nodes for _, v in _facts(nodes[m])}
        for nid in sorted(others):
            n = nodes[nid]
            # Other faults may be NAMED ("other faults this machine can have");
            # documents are listed by name. Everything else is a leak.
            if n["type"] in ("Fault", "Document"):
                continue
            hits = [v for _, v in _facts(n)
                    if len(v) >= 15 and _norm(v) in text
                    and not any(_norm(v) in o for o in own)]
            if _norm(n["label"]) in text or hits:
                bad.append({"fault": nodes[fid]["label"], "leaked": n["label"]})
                detail.append(f'{nodes[fid]["label"][:28]}: shows {n["type"]} "{n["label"][:40]}"'
                              + (f' ("{hits[0][:40]}")' if hits else ""))
    return bad, detail


RULES = [
    ("1. SOURCE     every note says where it came from", rule_source),
    ("2. CONNECTED  no note is left floating on its own", rule_connected),
    ("3. STRINGS    strings join sensible kinds of note", rule_strings),
    ("4. COMPLETE   every fault has a cause and a fix", rule_complete),
    ("5. AGREEMENT  no two notes contradict each other", rule_agreement),
    ("6. BELONGING  every note belongs to a machine that exists", rule_belonging),
    ("7. HAND-OVER  every fact on a fault's path reaches the AI", rule_handover),
    ("8. RELEVANCE  a fault's hand-over leaves out other faults' facts", rule_relevance),
]


def main():
    ap = argparse.ArgumentParser(description="Check the knowledge graph itself.")
    ap.add_argument("--equip", default="WM-101")
    args = ap.parse_args()

    try:
        total = q("MATCH (n) RETURN count(n) AS n")[0]["n"]
    except Exception as e:
        sys.exit(f"Cannot reach Neo4j: {e}")

    print(f"\nGRAPH HEALTH — {args.equip}   ({total} nodes in the database)\n" + "=" * 72)
    results, failed = [], 0
    for title, fn in RULES:
        # Rule 6 looks across the whole database, not one machine.
        bad, detail = fn(None) if fn is rule_belonging else fn(args.equip)
        ok = not bad
        failed += 0 if ok else 1
        print(f"\n{'PASS' if ok else 'FAIL'}  {title}")
        for d in detail[:12]:
            print(f"        - {d}")
        if len(detail) > 12:
            print(f"        ... and {len(detail) - 12} more")
        results.append({"rule": title, "pass": ok, "problems": detail})

    print("\n" + "=" * 72)
    print(f"{len(RULES) - failed}/{len(RULES)} rules pass")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    out = OUT_DIR / f"graph_health_{args.equip}_{stamp}.json"
    out.write_text(json.dumps({
        "equip": args.equip, "run_at": stamp,
        "passed": len(RULES) - failed, "total": len(RULES), "rules": results,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
