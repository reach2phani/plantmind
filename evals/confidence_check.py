"""
confidence_check.py — is the report confidence (Phase 2a step B) worked out right?

WHAT THIS IS (simple version)
    Made-up situations, each with the answer a careful engineer would give:
    "fault confirmed, graph and documents found -> HIGH, no review",
    "fault not confirmed -> MEDIUM, review", and so on. The same code the
    investigation uses (multi_agent.assess_confidence) must give that answer.
    Plus one check that the confidence section lands under the report title
    and leaves the rest of the report untouched.

COST
    Free. No AI calls, no database. The app does not need to be running.

RUN (from C:\\plantmind)
    venv\\Scripts\\python.exe evals\\confidence_check.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import multi_agent as ma  # noqa: E402


def spec(agent, found=True):
    """A specialist result: found evidence, or searched and found nothing."""
    if found:
        return {"agent": agent, "findings": "... Data confidence: HIGH", "raw_data": "[doc chunk]"}
    return {"agent": agent, "findings": "... Data confidence: NO DATA",
            "raw_data": "NO_DATA: No documents found in PlantMind for this query."}


def graph(conf="sure", faults=("Underfill",), degraded=False):
    return {"has_data": True, "degraded": degraded, "match_confidence": conf,
            "matched_faults": list(faults)}


ALL_FOUND = [spec("Alarm Agent"), spec("SOP Agent"), spec("Maintenance Agent"),
             spec("Expert Fix Agent", found=False)]   # no operator fix is normal

SCENARIOS = [
    # (name, graph_context, specialist_results, guard_events, expected level, review?)
    ("Fault confirmed, graph + documents found", graph(), ALL_FOUND, [], "HIGH", False),
    ("No operator fix on record is not a doubt", graph(), ALL_FOUND, [], "HIGH", False),
    ("Fault not confirmed (close call)", graph("unsure", ("Overfill", "Underfill")), ALL_FOUND, [], "MEDIUM", True),
    ("No known fault matched", graph("none", ()), ALL_FOUND, [], "LOW", True),
    ("No graph for this machine, documents found", None, ALL_FOUND, [], "MEDIUM", True),
    ("Graph in backup mode", graph(degraded=True), ALL_FOUND, [], "MEDIUM", True),
    ("Meaning check down, word count used", graph("words only"), ALL_FOUND, [], "MEDIUM", True),
    ("No SOP section found", graph(),
     [spec("Alarm Agent"), spec("SOP Agent", found=False), spec("Maintenance Agent")], [], "MEDIUM", True),
    ("Only one source found anything", graph(),
     [spec("Alarm Agent"), spec("Maintenance Agent", found=False),
      spec("NCR Agent", found=False)], [], "MEDIUM", True),
    ("No documents found at all", graph(),
     [spec("Alarm Agent", False), spec("SOP Agent", False), spec("Maintenance Agent", False)], [], "LOW", True),
    ("Two doubts together (no graph + no SOP)", None,
     [spec("Alarm Agent"), spec("SOP Agent", found=False), spec("Maintenance Agent")], [], "LOW", True),
    ("A specialist crashed", graph(),
     ALL_FOUND + [{"agent": "NCR Agent", "findings": "Agent failed — error: timeout", "raw_data": ""}],
     [], "MEDIUM", True),
    ("Unreviewed tip reached the repair steps", graph(), ALL_FOUND,
     ["an UNREVIEWED operator tip in instructions: Step 3 raise tension 18 -> 22"], "HIGH", True),
    ("Rating raised by the safety floor", graph(), ALL_FOUND,
     ["criticality raised HIGH -> CRITICAL"], "HIGH", True),
]

REPORT = """INVESTIGATION REPORT — TECHNICAL
═══════════════════════════════════════
SOURCE DATA
- FL-101-SOP.txt

HOW CRITICAL IS IT
- MEDIUM
"""


def main():
    failed = 0
    print("\nREPORT CONFIDENCE CHECK — made-up situations with known answers\n")
    for name, ctx, results, events, want_level, want_review in SCENARIOS:
        a = ma.assess_confidence(ctx, results, events)
        ok = a["level"] == want_level and a["review"] == want_review
        failed += not ok
        print(f"  {'OK  ' if ok else 'FAIL'} {name:45s} -> {a['level']:6s} review "
              f"{'yes' if a['review'] else 'no ':3s}"
              + ("" if ok else f"   (want {want_level}, review {'yes' if want_review else 'no'})")
              + (f"   [{'; '.join(a['reasons'] + a['review_reasons'])}]" if a['reasons'] or a['review_reasons'] else ""))

    # Placement: under the title and its divider; the rest unchanged.
    out = ma.add_confidence_block(REPORT, ma.assess_confidence(graph(), ALL_FOUND), graph())
    title_then_block = out.index("REPORT CONFIDENCE") > out.index("═══") > out.index("INVESTIGATION REPORT")
    rest_intact = out.replace(out[out.index("REPORT CONFIDENCE"):out.index("SOURCE DATA")], "") \
        .replace("\n", "") == REPORT.replace("\n", "")
    ok = title_then_block and rest_intact
    failed += not ok
    print(f"\n  {'OK  ' if ok else 'FAIL'} confidence section sits under the title and changes nothing else")

    total = len(SCENARIOS) + 1
    print(f"\n{total - failed}/{total} pass")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
