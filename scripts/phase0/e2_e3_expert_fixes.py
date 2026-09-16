"""
Phase 0 · Batch E2 + E3 — clean up the saved operator tips (expert fixes).

THE PROBLEMS
  E2: 4 tips were saved when a job title was still recorded, so their stored
      search text says "captured by G. Phani (Senior Operator)". The AI keeps
      copying that label into reports, even though it was removed from the app.
  E3: all 7 tips have a blank plant and line, so any plant/line filter hides them.

THE FIX
  For each tip:
    - blank the job title
    - set plant and line from the equipment table (the official names)
    - rebuild its search entry, so the stored text matches
  The graph and review queue are NOT touched.

HOW TO RUN
  1. Preview (changes nothing):   python scripts\\phase0\\e2_e3_expert_fixes.py
  2. Apply:                       python scripts\\phase0\\e2_e3_expert_fixes.py --apply

COST
  No Groq tokens. 7 small embeddings on Pinecone's free embedding service.
"""
import os
import sys
from datetime import datetime

PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROJECT_DIR)
os.chdir(PROJECT_DIR)

from dotenv import load_dotenv            # noqa: E402
load_dotenv(os.path.join(PROJECT_DIR, ".env"))
from embedder import embed_expert_fix, index, supabase  # noqa: E402

APPLY = "--apply" in sys.argv

equipment = {e["equip_tag"]: e for e in (supabase.table("equipment")
             .select("equip_tag,plant_site,line").execute().data or [])}
fixes = supabase.table("expert_fixes").select("*").execute().data or []

print(f"\n{'APPLYING' if APPLY else 'PREVIEW (nothing will change)'} — {len(fixes)} operator tips\n")
changed = 0
for f in fixes:
    vec = index.fetch(ids=[f"expertfix_{f['id']}"]).vectors.get(f"expertfix_{f['id']}")
    stored_text = (vec.metadata or {}).get("text", "") if vec else ""
    eq = equipment.get(f["equip_tag"], {})

    target = {
        "captured_by_role": "",
        "plant_site": eq.get("plant_site") or f.get("plant_site") or "",
        "line":       eq.get("line") or f.get("line") or "",
    }
    diffs = {k: (f.get(k) or "", v) for k, v in target.items() if (f.get(k) or "") != v}
    label_in_index = "Senior Operator" in stored_text

    print(f"  {f['equip_tag']:7} {f['id'][:8]}  "
          f"role: {f.get('captured_by_role') or '(blank)'!r:20} "
          f"plant/line: {(f.get('plant_site') or '(blank)')} / {(f.get('line') or '(blank)')}"
          f"{'   <- label in search text' if label_in_index else ''}")
    for k, (old, new) in diffs.items():
        print(f"           {k}: {old!r} -> {new!r}")

    if not diffs and not label_in_index:
        continue
    changed += 1
    if APPLY:
        supabase.table("expert_fixes").update(target).eq("id", f["id"]).execute()
        row = {**f, **target}
        ok = embed_expert_fix(f["id"], row)
        supabase.table("expert_fixes").update({
            "embed_status": "done" if ok else "failed",
            "last_embedded_at": datetime.utcnow().isoformat(),
        }).eq("id", f["id"]).execute()
        print(f"           rebuilt search entry: {'OK' if ok else 'FAILED'}")

print(f"\n{changed} of {len(fixes)} tips {'updated' if APPLY else 'would be updated'}.")
if not APPLY:
    print("Nothing changed. If this looks right, run again with --apply")
