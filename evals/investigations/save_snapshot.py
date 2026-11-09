"""
save_snapshot.py - save everything the held-out investigation needs, before it expires.

Read-only. No Groq tokens. Nothing in Supabase, LangSmith, Neo4j or Pinecone is changed.
LangSmith keeps traces only ~14 days, so this is run once, early, and the folder committed.

For each answer in the promptfoo result files it saves:
  runs/<case>-<before|after>.json    run record (summary + details) + the checker's verdicts
  traces/<case>-<before|after>.json  the full LangSmith trace (every step's input and output)
Once for the investigation:
  graph_fl101.json    FL-101 graph as it is in Neo4j now (reconstructed evidence)
  chunks_fl101.json   every FL-101 chunk in Pinecone (what search could have found)
  versions.json       git commit/status, per-run code_hash/models/switches, file hashes
People's names are removed from everything (same scrubber as evals/export_trace.py).
If a trace can't be fetched any more, an existing saved copy is kept, never overwritten.

Usage:
  venv\\Scripts\\python.exe evals\\investigations\\save_snapshot.py
"""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

from dotenv import load_dotenv            # noqa: E402  (must come before the app imports)
load_dotenv(ROOT / ".env")

from eval_summary import load_results     # noqa: E402  reads promptfoo files + run_id header
from export_trace import known_names, make_scrubber, clean_step   # noqa: E402

EQUIP = "FL-101"
RUNS = {"before": "evals/results/heldout-before-1104.json",
        "after": "evals/results/heldout-after-1108.json"}


def sha(path):
    p = ROOT / path
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.is_file() else None


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False, default=str), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="evals/investigations/heldout-v1/snapshot")
    args = ap.parse_args()
    out = ROOT / args.out
    scrub = make_scrubber(known_names())

    from llm_logger import _get_supabase
    from langsmith import Client
    import os
    sb, ls = _get_supabase(), Client()
    project = os.getenv("LANGSMITH_PROJECT", "plantmind")

    versions = {"saved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "git_head": git("rev-parse", "HEAD"), "git_status": git("status", "--short"),
                "files": {}, "runs": {}}
    problems = []

    # ── Run records + traces, one per answer ────────────────────────────────
    for side, path in RUNS.items():
        for a in load_results(ROOT / path):
            case = (a["description"] or a["tc"]).split()[0]          # "H1 — ..." -> "H1"
            name = f"{case}-{side}"
            rid = a["run_id"]
            summ = (sb.table("investigation_runs").select("*").eq("id", rid).execute().data or [None])[0] if rid else None
            det = (sb.table("investigation_run_details").select("*").eq("run_id", rid).execute().data or [{}])[0] if rid else {}
            if not summ:
                problems.append(f"{name}: no run record (run_id {rid})")
            write(out / "runs" / f"{name}.json", scrub({
                "case": case, "side": side, "promptfoo_file": path, "eval_id": a["eval_id"],
                "run_label": a["run_label"], "question": a["question"], "run_id": rid,
                "report_as_graded": a["report"], "checks": a["checks"],
                "summary": summ, "details": det}))
            trace = (summ or {}).get("langsmith_trace_id")
            versions["runs"][name] = {k: (summ or {}).get(k) for k in (
                "run_tag", "created_at", "git_commit", "code_hash", "model_fast", "model_deep",
                "switches", "langsmith_trace_id")}

            tpath = out / "traces" / f"{name}.json"
            steps = []
            if trace:
                try:
                    steps = sorted((clean_step(r, scrub) for r in ls.list_runs(project_name=project, trace_id=trace)),
                                   key=lambda s: s["order"] or "")
                except Exception as e:
                    problems.append(f"{name}: trace fetch failed ({str(e)[:80]})")
            if steps:
                write(tpath, {"trace_id": trace, "case": name, "project": project,
                              "note": "Exported from LangSmith. People's names removed. Metadata left out.",
                              "steps": steps})
            elif tpath.is_file():
                problems.append(f"{name}: trace not fetched, kept the earlier saved copy")
            else:
                problems.append(f"{name}: NO TRACE saved (trace id {trace})")
            print(f"  {name:<10} run {'ok' if summ else 'MISSING':<8} trace {len(steps) or 'MISSING'} steps")

    # ── Graph as it is now (reconstructed evidence) ──────────────────────────
    try:
        import knowledge_graph as kg
        g = kg.get_full_graph(equip_tag=EQUIP)
        write(out / "graph_fl101.json", scrub({"equip_tag": EQUIP, "note":
              "Neo4j state on the save date. What the graph says NOW, not necessarily what a run saw.", **g}))
        print(f"  graph      {len(g.get('nodes', []))} nodes, {len(g.get('edges', []))} edges")
    except Exception as e:
        problems.append(f"graph: {str(e)[:100]}")

    # ── Every FL-101 chunk in Pinecone ───────────────────────────────────────
    try:
        from pinecone import Pinecone
        index = Pinecone(api_key=os.getenv("PINECONE_API_KEY")).Index(os.getenv("PINECONE_INDEX"))
        docs = sb.table("documents").select("id,name,doc_type,revision,last_embedded_at").eq("equip_tag", EQUIP).execute().data
        chunks = []
        for d in docs:
            ids = [getattr(i, "id", i) for page in index.list(prefix=f"{d['id']}_chunk_") for i in page]
            for i in range(0, len(ids), 100):
                for vid, v in index.fetch(ids=ids[i:i + 100]).vectors.items():
                    m = v.metadata or {}
                    chunks.append({"chunk_id": vid, "document": d["name"], "doc_type": m.get("doc_type"),
                                   "n": int(vid.rsplit("_", 1)[-1]), "text": m.get("text", "")})
        chunks.sort(key=lambda c: (c["document"], c["n"]))
        write(out / "chunks_fl101.json", scrub({"equip_tag": EQUIP, "documents": docs, "chunks": chunks}))
        print(f"  chunks     {len(chunks)} from {len(docs)} documents")
    except Exception as e:
        problems.append(f"chunks: {str(e)[:100]}")

    # ── File fingerprints (what the documents/graph/config were on save day) ─
    for p in ["fl101_graph.json", "multi_agent.py", "knowledge_graph.py", "models.py",
              "evals/promptfoo/eval_fl101_heldout.yaml", "evals/fl101/HELDOUT.md", *RUNS.values()]:
        versions["files"][p] = sha(p)
    for p in sorted((ROOT / "demo_data" / "fl101").rglob("*.*")):
        versions["files"][str(p.relative_to(ROOT)).replace("\\", "/")] = sha(p.relative_to(ROOT))
    versions["names_removed"] = sorted(scrub.removed)
    versions["problems"] = problems
    write(out / "versions.json", versions)

    print(f"\nSaved to {out.relative_to(ROOT)}")
    print("Problems:" if problems else "No problems.")
    for p in problems:
        print("  -", p)
    print(f"Removed as names (check none is a real word): {sorted(scrub.removed) or 'none'}")


if __name__ == "__main__":
    main()
