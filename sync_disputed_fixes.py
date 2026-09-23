"""
sync_disputed_fixes.py — Phase 1B: carry a reviewer's rejection across systems.

THE PROBLEM THIS SOLVES
    An operator's captured fix lives in TWO places:
      - Supabase + Pinecone, where the Expert Fix agent searches it
      - Neo4j, as a promoted note, if a reviewer approved it
    Marking the Neo4j note "disputed" told the search side nothing, so an
    investigation still quoted the rejected advice — and in a live test put a
    rejected voltage into the repair steps.

    This script reads every disputed note in the graph, finds the captures
    behind it (graph_candidates.fix_ids), and marks those rows disputed in
    Supabase. Retrieval then skips them (multi_agent._drop_disputed).

    Nothing is deleted. The operator still sees their capture in their own
    library, and the graph still shows the claim with the fact that beats it.

REQUIRES
    sql/06_expert_fix_status.sql to have been run first.

RUN (from C:\\plantmind)
    venv\\Scripts\\python.exe sync_disputed_fixes.py            <- preview only
    venv\\Scripts\\python.exe sync_disputed_fixes.py --apply
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import knowledge_graph as kg  # noqa: E402
from llm_logger import _get_supabase  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the changes")
    args = ap.parse_args()

    disputed = kg._run(
        "MATCH (p:Pattern) WHERE p.status = 'disputed' "
        "RETURN p._id AS node, p.candidate_id AS candidate, p.disputed_reason AS reason", {})
    if not disputed:
        print("No disputed notes in the graph. Nothing to do.")
        return

    sb = _get_supabase()
    print(f"\n{len(disputed)} disputed note(s) in the graph\n" + "=" * 70)

    for d in disputed:
        print(f"\nGraph note: {d['node']}")
        print(f"  Reason: {(d['reason'] or '')[:110]}")
        if not d.get("candidate"):
            print("  No candidate_id on the note — cannot trace the captures. Skipped.")
            continue

        rows = (sb.table("graph_candidates").select("fix_ids")
                .eq("id", d["candidate"]).execute().data or [])
        fix_ids = rows[0].get("fix_ids") if rows else None
        if not fix_ids:
            print("  Candidate has no fix_ids. Skipped.")
            continue

        for fid in fix_ids:
            cap = (sb.table("expert_fixes")
                   .select("id,captured_by_name,what_fixed_it,status")
                   .eq("id", fid).execute().data or [])
            if not cap:
                print(f"  - {fid}: capture not found (deleted?)")
                continue
            c = cap[0]
            already = (c.get("status") or "active") != "active"
            print(f"  - {fid}  by {c.get('captured_by_name', '?')}"
                  f"  {'[already disputed]' if already else '-> mark disputed'}")
            if args.apply and not already:
                sb.table("expert_fixes").update({
                    "status": "disputed",
                    "status_reason": (d["reason"] or "Overruled by a documented fact")[:500],
                }).eq("id", fid).execute()

    print("\n" + "=" * 70)
    if args.apply:
        print("Applied. Investigations will now skip these captures.")
        print("The operator still sees them in their own library.")
    else:
        print("Preview only. To apply:  venv\\Scripts\\python.exe sync_disputed_fixes.py --apply")


if __name__ == "__main__":
    main()
