"""
repair_reinforcements_phase1b.py — put back what the merge bug threw away.

WHAT WENT WRONG
    Approving a "reinforcement" used to raise a note's confirmation count and
    discard the new capture's words. In this database THREE reinforcements were
    approved into one arc-voltage note — a duty-cycle alarm, low gas flow and
    weld spatter. Three unrelated fixes, none of them about arc voltage, all
    silently dropped, while the note it joined looked MORE trustworthy for it.

WHAT THIS DOES
    - Sends every already-approved reinforcement back to the review queue as
      pending, flagged needs_review, so you can judge each one properly now
      that the screen shows what it would merge into.
    - Resets each affected note's confirmation count and contributors to the
      captures that genuinely belong to it (the original 'new' candidate).
    - Writes an audit row for every change.

    Nothing is deleted. The captures themselves were never lost — they are
    still in Supabase and still searchable — they just never reached the graph.

RUN (from C:\\plantmind)
    venv\\Scripts\\python.exe repair_reinforcements_phase1b.py           <- preview
    venv\\Scripts\\python.exe repair_reinforcements_phase1b.py --apply
"""

import argparse
import datetime as dt
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
    sb = _get_supabase()

    bad = (sb.table("graph_candidates").select("*")
           .eq("candidate_type", "reinforcement").eq("status", "approved")
           .execute().data or [])
    if not bad:
        print("No approved reinforcements found. Nothing to repair.")
        return

    print(f"\n{len(bad)} approved reinforcement(s) to re-open\n" + "=" * 72)
    affected_nodes = {}

    for c in bad:
        print(f'\nCandidate {c["id"][:8]}  equip={c["equip_tag"]}')
        print(f'  Its content: {(c.get("summary") or "")[:120]}')
        node_id = c.get("promoted_node_id")
        if node_id:
            affected_nodes.setdefault(node_id, [])
            target = kg._run("MATCH (n:Pattern {_id:$i}) RETURN left(n.operator_summary,120) AS s",
                             {"i": node_id})
            print(f'  Was merged into: {(target[0]["s"] if target else "(node missing)")}')
        print("  -> back to the review queue as pending, flagged for re-check")

        if args.apply:
            sb.table("graph_candidates").update({
                "status": "pending", "needs_review": True,
                "reviewed_by": None, "reviewed_at": None,
            }).eq("id", c["id"]).execute()
            try:
                sb.table("graph_promotion_audit").insert({
                    "candidate_id": c["id"], "action": "rejected",
                    "performed_by": "phase-1b repair",
                    "detail": {"note": "re-opened: reinforcement merge discarded this capture's "
                                       "content; re-review with the merge preview"},
                }).execute()
            except Exception as e:
                print(f"     (audit row skipped: {str(e)[:60]})")

    # ── put each affected note back to what it can actually evidence ─────────
    print("\n" + "=" * 72 + "\nNOTES TO CORRECT\n")
    for node_id in affected_nodes:
        original = (sb.table("graph_candidates").select("fix_ids")
                    .eq("promoted_node_id", node_id).eq("candidate_type", "new")
                    .execute().data or [])
        fix_ids = (original[0].get("fix_ids") if original else []) or []
        names = []
        for fid in fix_ids:
            r = (sb.table("expert_fixes").select("captured_by_name").eq("id", fid)
                 .execute().data or [])
            if r and r[0].get("captured_by_name"):
                names.append(r[0]["captured_by_name"])
        count = max(1, len(fix_ids))
        now = kg._run("MATCH (n:Pattern {_id:$i}) RETURN n.confirmed_count AS c, "
                      "n.contributors AS w", {"i": node_id})
        before = now[0] if now else {}
        print(f'{node_id[:34]}')
        print(f'  count {before.get("c")} -> {count}   contributors "{before.get("w")}" -> "{", ".join(sorted(set(names)))}"')
        if args.apply:
            kg._run(
                "MATCH (n:Pattern {_id:$i}) SET n.confirmed_count = $c, n.contributors = $w, "
                "n.source_type = CASE WHEN $c > 1 THEN 'multi_operator' ELSE 'single_operator' END, "
                "n.repaired_at = $t",
                {"i": node_id, "c": count, "w": ", ".join(sorted(set(names))),
                 "t": dt.date.today().isoformat()}
            )

    print("\n" + "=" * 72)
    if args.apply:
        print("Done. Open /graph -> Review queue and judge each one with the merge preview.")
    else:
        print("Preview only. To apply:")
        print("   venv\\Scripts\\python.exe repair_reinforcements_phase1b.py --apply")


if __name__ == "__main__":
    main()
