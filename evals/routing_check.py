"""
routing_check.py — which specialists does the supervisor send, and is it consistent?

WHAT THIS IS (simple version)
    The supervisor is the "manager" that decides which document searches run
    for a question. This asks it about the six graph-value test questions,
    3 times each, and shows who it sent. It runs ONLY the graph lookup and the
    supervisor, not the specialists or the report, so it is cheap.

    It answers three questions per case:
        REQUIRED  were the searches the graph says matter all sent?
                  (the matched fault's documents: SOP -> sop, Work Instruction
                   -> maintenance, NCR -> ncr; plus alarm and expert_fix
                   whenever the machine is known)
        STABLE    did all 3 runs send the same set?
        SENT      what was sent, run by run

COST
    18 small calls on gpt-oss-20b, about 20K tokens. No 120b, no judge.

RUN (from C:\\plantmind — the app does not need to be running)
    venv\\Scripts\\python.exe evals\\routing_check.py --tag before
    venv\\Scripts\\python.exe evals\\routing_check.py --tag after

OUTPUT
    A table on screen and evals/routing/routing_<tag>.json
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
import multi_agent as ma      # noqa: E402

CASES_FILE = ROOT / "evals" / "graph_value_cases.json"
OUT_DIR = ROOT / "evals" / "routing"
DOC_TO_AGENT = {"SOP": "sop", "Work Instruction": "maintenance", "NCR": "ncr"}


def required_agents(graph):
    """What the graph says must be searched, worked out here independently."""
    need = {"alarm", "expert_fix"}
    if graph.get("matched_faults"):
        by_id = {n["id"]: n for n in graph.get("chain_nodes", [])}
        for nid in graph.get("relevant_node_ids", []):
            n = by_id.get(nid)
            if n and n["type"] == "Document":
                agent = DOC_TO_AGENT.get((n["properties"] or {}).get("type", ""))
                if agent:
                    need.add(agent)
    return need


def route(incident, equipment, graph):
    """Call the supervisor the way the pipeline does, before or after step 4."""
    try:
        return ma.supervisor_route(incident, equipment, graph_context=graph)
    except TypeError:   # before step 4: the supervisor cannot take the graph yet
        return ma.supervisor_route(incident, equipment)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--runs", type=int, default=3)
    args = ap.parse_args()

    spec = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    equip = spec["equipment"]
    rows = []
    print(f"\nROUTING CHECK — {args.tag}   ({len(spec['cases'])} cases x {args.runs} runs)\n" + "=" * 78)
    for case in spec["cases"]:
        graph = kg.get_fault_chain(equip, incident_text=case["incident"])
        need = required_agents(graph)
        sent = []
        for _ in range(args.runs):
            agents, reason = route(case["incident"], equip, graph)
            sent.append(sorted(set(agents)))
        missing = sorted({a for s in sent for a in need - set(s)})
        stable = all(s == sent[0] for s in sent)
        rows.append({"case": case["id"], "name": case["name"],
                     "matched": graph.get("matched_faults", []),
                     "required": sorted(need), "sent": sent,
                     "required_ok": not missing, "missing": missing, "stable": stable})
        print(f"\n{case['id']} {case['name']}   graph matched: {', '.join(graph.get('matched_faults', [])) or '—'}")
        print(f"   required: {', '.join(sorted(need))}")
        for i, s in enumerate(sent, 1):
            print(f"   run {i}:   {', '.join(s)}")
        print(f"   REQUIRED {'OK' if not missing else 'MISSING ' + ', '.join(missing)}   "
              f"STABLE {'yes' if stable else 'no'}")

    ok = sum(r["required_ok"] for r in rows)
    st = sum(r["stable"] for r in rows)
    print("\n" + "=" * 78)
    print(f"Required searches always sent: {ok}/{len(rows)} cases   Same set every run: {st}/{len(rows)} cases")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"routing_{args.tag}.json"
    out.write_text(json.dumps({"tag": args.tag, "at": dt.datetime.now().isoformat(timespec="seconds"),
                               "required_ok": ok, "stable": st, "cases": rows}, indent=2), encoding="utf-8")
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
