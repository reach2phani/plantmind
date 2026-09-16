"""
Phase 0 · Batch E1 — split WM-101 shift logs by machine.

THE PROBLEM
  Each Greenfield shift-log file is labelled WM-101 as a whole, but its rows
  also cover the furnace (HT-301), press (HC-401) and gas cutter (GC-201).
  Search chunks mixed those machines together, so a WM-101 question could
  return furnace events, and a GC-201 question found nothing.

THE FIX
  Re-index the 11 files with the new chunking: every chunk now holds ONE
  machine's rows and carries that machine's tag and line. Old chunks are
  replaced, and any leftover old chunks are deleted (no duplicates).

HOW TO RUN
  1. Preview (changes nothing):   python scripts\\phase0\\e1_reindex_shift_logs.py
  2. Apply:                       python scripts\\phase0\\e1_reindex_shift_logs.py --apply

COST
  No Groq tokens. Uses Pinecone's embedding service for roughly 70-90 chunks
  (one-time, small). Backup of the old vectors: C:\\plantmind-backups
"""
import os
import sys
import tempfile
from collections import Counter
from datetime import datetime

PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROJECT_DIR)
os.chdir(PROJECT_DIR)

from dotenv import load_dotenv            # noqa: E402
load_dotenv(os.path.join(PROJECT_DIR, ".env"))
from embedder import chunk_csv, embed_document, index, supabase, SUPABASE_BUCKET  # noqa: E402

APPLY = "--apply" in sys.argv

docs = (supabase.table("documents").select("*")
        .eq("plant_site", "Greenfield Steel Works").eq("file_type", "csv")
        .eq("status", "uploaded").execute().data or [])

print(f"\n{'APPLYING' if APPLY else 'PREVIEW (nothing will change)'} — {len(docs)} Greenfield shift-log files\n")
total_old, total_new, by_machine = 0, 0, Counter()

for d in sorted(docs, key=lambda x: x["name"]):
    old = 0
    for page in index.list(prefix=f"{d['id']}_chunk_"):
        old += len(page)

    data = supabase.storage.from_(SUPABASE_BUCKET).download(d["file_path"])
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        chunks = chunk_csv(tmp_path)
    finally:
        os.unlink(tmp_path)

    machines = Counter(c["equip_tag"] for c in chunks)
    by_machine.update(machines)
    total_old += old
    total_new += len(chunks)
    print(f"  {d['name']:44} old chunks: {old:>2} (all tagged {d.get('equip_tag')})  ->  "
          f"new: {len(chunks):>2}  " + ", ".join(f"{m} {n}" for m, n in sorted(machines.items())))

    if APPLY:
        supabase.table("documents").update({"embed_status": "pending"}).eq("id", d["id"]).execute()
        try:
            embed_document(d["id"], d["file_path"], d)
            supabase.table("documents").update({
                "embed_status": "done", "last_embedded_at": datetime.utcnow().isoformat()
            }).eq("id", d["id"]).execute()
        except Exception as e:
            supabase.table("documents").update({"embed_status": "failed"}).eq("id", d["id"]).execute()
            print(f"     FAILED: {e}")

print(f"\nTotal chunks: {total_old} old -> {total_new} new")
print("New chunks per machine:", dict(sorted(by_machine.items())))
if not APPLY:
    print("\nNothing changed. If this looks right, run again with --apply")
else:
    print("\nDone. Old mixed chunks have been replaced.")
