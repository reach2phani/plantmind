"""
graph_health.py — Phase 1B: is the knowledge graph itself accurate?

WHY THIS EXISTS (simple version)
    Your answer evals ask "was the reply good?". They cannot tell you WHY it was
    bad. This checks the graph itself, before any AI is involved, and turns
    "is my graph accurate?" into a pass/fail list you can re-run after a rebuild.

    Picture the graph as sticky notes joined by string. These six rules ask:
      1. SOURCE      does every note say where it came from?
      2. CONNECTED   is every note tied to something (no note floating alone)?
      3. STRINGS     do the strings join sensible kinds of note?
      4. COMPLETE    does every fault have at least one cause and one fix?
      5. AGREEMENT   do two notes contradict each other about the same number?
      6. BELONGING   does every note belong to a machine that exists here?

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


RULES = [
    ("1. SOURCE     every note says where it came from", rule_source),
    ("2. CONNECTED  no note is left floating on its own", rule_connected),
    ("3. STRINGS    strings join sensible kinds of note", rule_strings),
    ("4. COMPLETE   every fault has a cause and a fix", rule_complete),
    ("5. AGREEMENT  no two notes contradict each other", rule_agreement),
    ("6. BELONGING  every note belongs to a machine that exists", rule_belonging),
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
