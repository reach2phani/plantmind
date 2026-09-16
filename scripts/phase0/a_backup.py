"""
Phase 0 · Batch A — Backup everything before any data change.

WHAT IT DOES (read-only against every service):
  1. Supabase tables  -> one JSON file per table
  2. Supabase Storage -> copies of every uploaded document file
  3. Pinecone         -> every vector (id, values, metadata), so the index
                         can be restored WITHOUT re-embedding (no quota cost)
  4. Neo4j            -> every node and relationship, including promoted
                         operator patterns (a graph reload would delete those)
  5. manifest.json    -> row/vector/node counts, to prove the backup is complete

WHY IT MATTERS:
  Batches E and F change data. If a change goes wrong, this backup is how
  we undo it. Production teams take a backup before every data migration.

WHERE IT WRITES:
  C:\\plantmind-backups\\<date_time>\\   (outside the project, never committed)

RUN (from C:\\plantmind with the venv activated):
  python scripts\\phase0\\a_backup.py

COST: no Groq tokens. Pinecone "fetch" reads only; no embedding quota used.
"""

import json
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(PROJECT_DIR, ".env"))
sys.path.insert(0, PROJECT_DIR)

from supabase import create_client  # noqa: E402
from pinecone import Pinecone        # noqa: E402

BACKUP_ROOT = r"C:\plantmind-backups"
STAMP = datetime.now().strftime("%Y-%m-%d_%H%M")
OUT = os.path.join(BACKUP_ROOT, STAMP)
BUCKET = "plantmind-docs"

# Every table PlantMind uses. Missing tables are skipped, not treated as errors.
TABLES = [
    "plant_sites", "lines", "equipment", "documents",
    "expert_fixes", "graph_candidates", "graph_candidate_rejections", "graph_promotion_audit",
    "work_orders", "wo_audit", "parts_inventory", "technicians", "suppliers",
    "cost_thresholds", "bookings",
    "chat_history", "live_events", "llm_logs", "feedback",
]

manifest = {"created_at": STAMP, "supabase_tables": {}, "storage_files": 0,
            "pinecone_vectors": 0, "neo4j_nodes": 0, "neo4j_relationships": 0, "problems": []}


def save(name, data):
    path = os.path.join(OUT, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False, default=str)


def backup_supabase(sb):
    print("\n[1/4] Supabase tables")
    for table in TABLES:
        rows, start, page = [], 0, 1000   # Supabase returns max 1000 rows per request
        try:
            while True:
                batch = sb.table(table).select("*").range(start, start + page - 1).execute().data or []
                rows += batch
                if len(batch) < page:
                    break
                start += page
        except Exception as e:
            print(f"   skip {table}: {str(e)[:80]}")
            manifest["problems"].append(f"table {table}: {str(e)[:120]}")
            continue
        save(f"supabase/{table}.json", rows)
        manifest["supabase_tables"][table] = len(rows)
        print(f"   {table:28} {len(rows):>6} rows")


def backup_storage(sb):
    print("\n[2/4] Supabase Storage document files")
    docs = sb.table("documents").select("name,file_path").execute().data or []
    for d in docs:
        path = d.get("file_path")
        if not path:
            continue
        try:
            data = sb.storage.from_(BUCKET).download(path)
            dest = os.path.join(OUT, "storage", path)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as f:
                f.write(data)
            manifest["storage_files"] += 1
        except Exception as e:
            manifest["problems"].append(f"storage {path}: {str(e)[:120]}")
    print(f"   {manifest['storage_files']} of {len(docs)} files copied")


def backup_pinecone():
    print("\n[3/4] Pinecone vectors")
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index = pc.Index(os.getenv("PINECONE_INDEX"))
    ids = []
    for id_batch in index.list():          # yields pages of vector ids
        # Pinecone SDK 9 yields ListItem objects, not plain strings. fetch()
        # needs the string id, and silently returns nothing if given objects.
        ids.extend(getattr(item, "id", item) for item in id_batch)
    vectors = []
    for i in range(0, len(ids), 100):      # fetch in pages of 100
        res = index.fetch(ids=ids[i:i + 100])
        for vid, v in res.vectors.items():
            vectors.append({"id": vid, "values": list(v.values), "metadata": dict(v.metadata or {})})
    save("pinecone/vectors.json", vectors)
    manifest["pinecone_vectors"] = len(vectors)
    stats = index.describe_index_stats()
    expected = getattr(stats, "total_vector_count", None)
    print(f"   {len(vectors)} vectors saved (index reports {expected})")
    if expected is not None and expected != len(vectors):
        manifest["problems"].append(f"pinecone count mismatch: saved {len(vectors)}, index {expected}")


def backup_neo4j():
    print("\n[4/4] Neo4j graph")
    try:
        from knowledge_graph import _run
        nodes = _run("MATCH (n) RETURN labels(n) AS labels, properties(n) AS props")
        rels = _run("MATCH (a)-[r]->(b) RETURN a._id AS from_id, type(r) AS type, "
                    "properties(r) AS props, b._id AS to_id")
    except Exception as e:
        print(f"   FAILED: {str(e)[:120]}  (is the Aura instance resumed?)")
        manifest["problems"].append(f"neo4j: {str(e)[:120]}")
        return
    save("neo4j/nodes.json", nodes)
    save("neo4j/relationships.json", rels)
    manifest["neo4j_nodes"] = len(nodes)
    manifest["neo4j_relationships"] = len(rels)
    patterns = sum(1 for n in nodes if (n["props"] or {}).get("operator_summary"))
    print(f"   {len(nodes)} nodes ({patterns} promoted operator patterns), {len(rels)} relationships")


if __name__ == "__main__":
    # Optional: redo one part only, e.g. after a fix.
    #   python scripts\phase0\a_backup.py --only pinecone
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None

    os.makedirs(OUT, exist_ok=True)
    print(f"Backing up to {OUT}" + (f"  (only: {only})" if only else ""))
    if only in (None, "supabase", "storage"):
        sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
        if only in (None, "supabase"):
            backup_supabase(sb)
        if only in (None, "storage"):
            backup_storage(sb)
    if only in (None, "pinecone"):
        backup_pinecone()
    if only in (None, "neo4j"):
        backup_neo4j()
    save("manifest.json", manifest)
    print("\n" + "=" * 60)
    if manifest["problems"]:
        print(f"Finished WITH {len(manifest['problems'])} problem(s) — see manifest.json:")
        for p in manifest["problems"]:
            print("  -", p)
    else:
        print("Backup complete, no problems.")
    print(f"Folder: {OUT}")
