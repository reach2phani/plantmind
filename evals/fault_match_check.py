"""
fault_match_check.py — does the graph pick the right fault from the operator's words?

WHAT THIS IS (simple version)
    Before the graph can help, it has to decide WHICH fault the operator is
    describing. Everything after depends on that choice: the facts handed to
    the AI, the required searches, the safety floor. This check asks that one
    question for every test sentence in evals/fault_match/questions.json and
    compares the answer with the expected fault.

    --words   today's word-count matcher (the "before")
    (default) the meaning matcher (Phase 2a step A)
    --no-ai   the meaning matcher without the AI tie-breaker (free)

MARKING
    right    exactly the expected fault, and the matcher was sure
    unsure   the expected fault is among the close candidates, marked unsure
             (safe, but not decided)
    wrong    anything else: wrong fault, wrong fault among a tie, or nothing
    false CRITICAL   a CRITICAL fault picked "sure" when the expected fault is
                     not CRITICAL (a pressure drop rated CRITICAL). Must be 0.

COST
    Free apart from embeddings (the same Pinecone model as document search)
    and, in default mode only, a short AI question for close calls.
    The app does NOT need to be running.

RUN (from C:\\plantmind)
    venv\\Scripts\\python.exe evals\\fault_match_check.py --words --tag before
    venv\\Scripts\\python.exe evals\\fault_match_check.py --tag after
    venv\\Scripts\\python.exe evals\\fault_match_check.py --set fresh --tag exam
"""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import knowledge_graph as kg  # noqa: E402

QUESTIONS = ROOT / "evals" / "fault_match" / "questions.json"
OUT_DIR = ROOT / "evals" / "fault_match"


def graph_for(equip):
    """The machine's nodes and edges, exactly as an investigation reads them."""
    ctx = kg.get_fault_chain(equip, incident_text="")
    if not ctx.get("has_data"):
        sys.exit(f"No graph data for {equip}. Is Neo4j reachable and the graph loaded?")
    return ctx["chain_nodes"], ctx["chain_edges"]


def pick(nodes, edges, q, mode):
    if mode == "words":
        rel, _, hit = kg._match_faults(nodes, edges, q)
        return {"faults": [f["label"] for f in rel] if hit else [],
                "confidence": "sure" if hit and len(rel) == 1 else ("unsure" if hit else "none"),
                "method": "word count", "scores": []}
    m = kg.match_faults(nodes, edges, q, use_ai=(mode == "meaning"))
    return {"faults": [f["label"] for f in m["relevant"]] if m["hit"] else [],
            "confidence": m["confidence"], "method": m["method"], "scores": m["scores"][:3]}


def mark(expect, got, critical_labels):
    """
    expect: a fault label, "none" (the operator reports no fault / not one of
    these: added 6 Oct 2026 after the fresh questions), or a list of answers
    that are all acceptable (e.g. ["Infeed Jam", "none"]).
    """
    accepted = expect if isinstance(expect, list) else [expect]
    no_fault = got["confidence"] == "none" and not got["faults"]
    if (got["confidence"] == "sure" and len(got["faults"]) == 1 and got["faults"][0] in accepted) \
            or ("none" in accepted and no_fault):
        verdict = "right"
    elif got["confidence"] == "unsure" and any(e in got["faults"] for e in accepted):
        verdict = "unsure"
    else:
        verdict = "wrong"
    false_critical = (got["confidence"] == "sure" and not any(e in critical_labels for e in accepted)
                      and any(f in critical_labels for f in got["faults"]))
    return verdict, false_critical


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--words", action="store_true", help="today's word-count matcher (before)")
    ap.add_argument("--no-ai", action="store_true", help="meaning matcher without the AI tie-breaker")
    ap.add_argument("--set", default="", help="only this set: user, everyday, alarm, fresh")
    ap.add_argument("--equip", default="", help="only this machine")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    mode = "words" if args.words else ("no-ai" if args.no_ai else "meaning")
    tag = args.tag or mode

    qs = json.loads(QUESTIONS.read_text(encoding="utf-8"))["questions"]
    if args.set:
        qs = [q for q in qs if q["set"] == args.set]
    if args.equip:
        qs = [q for q in qs if q["equip"] == args.equip]
    if not qs:
        sys.exit("No questions selected.")

    graphs, rows = {}, []
    print(f"\nFAULT MATCH CHECK — matcher: {mode}, {len(qs)} question(s)\n")
    for q in qs:
        if q["equip"] not in graphs:
            nodes, edges = graph_for(q["equip"])
            crit = {n["label"] for n in nodes if n["type"] == "Fault"
                    and str((n.get("properties") or {}).get("criticality", "")).upper().startswith("CRITICAL")}
            graphs[q["equip"]] = (nodes, edges, crit)
        nodes, edges, crit = graphs[q["equip"]]
        got = pick(nodes, edges, q["q"], mode)
        verdict, false_crit = mark(q["expect"], got, crit)
        rows.append({**q, **got, "verdict": verdict, "false_critical": false_crit})
        sign = {"right": "OK    ", "unsure": "UNSURE", "wrong": "WRONG "}[verdict]
        want = " or ".join(q["expect"]) if isinstance(q["expect"], list) else q["expect"]
        print(f"  {sign} {q['id']:7s} want {want:30s} got {', '.join(got['faults']) or '(none)':40s}"
              f" [{got['confidence']}; {got['method']}]" + ("  <-- FALSE CRITICAL" if false_crit else ""))

    # Summary per machine and set
    groups = {}
    for r in rows:
        groups.setdefault((r["equip"], r["set"]), []).append(r)
    lines = [f"# Fault match check — {tag}", "",
             f"Run {dt.datetime.now():%Y-%m-%d %H:%M}. Matcher: **{mode}**. "
             "Right = exactly the expected fault and sure. Unsure = expected fault among the "
             "close candidates, flagged. Wrong = anything else.", "",
             "| Machine | Set | Right | Unsure | Wrong | False CRITICAL |", "|---|---|---|---|---|---|"]
    for (equip, st), rs in sorted(groups.items()):
        n = len(rs)
        c = {v: sum(r["verdict"] == v for r in rs) for v in ("right", "unsure", "wrong")}
        fc = sum(r["false_critical"] for r in rs)
        lines.append(f"| {equip} | {st} | {c['right']}/{n} | {c['unsure']}/{n} | {c['wrong']}/{n} | {fc} |")
    n = len(rows)
    tot = {v: sum(r["verdict"] == v for r in rows) for v in ("right", "unsure", "wrong")}
    lines.append(f"| **All** | | **{tot['right']}/{n}** | {tot['unsure']}/{n} | {tot['wrong']}/{n} | "
                 f"{sum(r['false_critical'] for r in rows)} |")
    lines += ["", "## Every question", "", "| Id | Expected | Got | Confidence | How | Top scores |",
              "|---|---|---|---|---|---|"]
    for r in rows:
        sc = "; ".join(f"{l} {s}" for l, s in r["scores"])
        lines.append(f"| {r['id']} | {' or '.join(r['expect']) if isinstance(r['expect'], list) else r['expect']} |{', '.join(r['faults']) or '—'} | "
                     f"{r['confidence']} | {r['method']} | {sc} |")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{tag}_scorecard.md").write_text("\n".join(lines), encoding="utf-8")
    (OUT_DIR / f"{tag}_results.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\n" + "\n".join(lines[5:5 + len(groups) + 2]))
    print(f"\nScorecard: {OUT_DIR / (tag + '_scorecard.md')}")


if __name__ == "__main__":
    main()
