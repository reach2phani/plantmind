"""
retrieval_eval.py — Phase 1 step 1.5: did search find the right chunk?

WHAT THIS MEASURES (simple version)
    Before the AI writes a word, search picks the 12 document chunks that look
    most relevant, and ONLY those 12 go to the AI. If the chunk holding the
    answer is not among them, no prompt can fix the answer — the AI never saw
    the fact. This script checks, for each labelled question, where the right
    chunk ranked.

    It separates two very different failures:
        right chunk NOT found      -> fix search / chunking   (Phase 3)
        right chunk found, answer
        still wrong                -> fix the prompt / model  (Phase 2)

THE THREE SCORES
    Found in top 12  Did the right chunk reach the AI at all? The one that
                     matters most — the app sends all 12 to the AI.
    Found in top 3   Was it near the top, not buried at the bottom?
    MRR              Mean Reciprocal Rank: 1/rank, averaged. Rank 1 = 1.0,
                     rank 2 = 0.5, rank 4 = 0.25, not found = 0. One number for
                     "how high does the right chunk usually sit". Higher is better.

HOW A "HIT" IS DECIDED
    evals/retrieval_labels.json gives each question a few EVIDENCE PHRASES.
    A chunk is a hit if it contains all of them. Labels are text, not chunk ids,
    because Phase 3 re-cuts the documents and every chunk id will change — the
    words will not. That is what lets these numbers be compared before and
    after Phase 3.

COST
    Zero Groq tokens. It calls the app's read-only /api/eval/retrieve endpoint,
    which runs exactly the search /ask runs and stops before any AI call.
    18 Pinecone embedding calls, which are free.

RUN (from C:\\plantmind, with the app running: python app.py)
    venv\\Scripts\\python.exe evals\\retrieval_eval.py

OUTPUT
    A table on screen, and evals/retrieval_results/retrieval_<date>_<time>.json
    — keep these: they are the "before" numbers Phase 3 is measured against.
"""

import datetime as dt
import json
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
LABELS = ROOT / "evals" / "retrieval_labels.json"
OUT_DIR = ROOT / "evals" / "retrieval_results"
URL = "http://localhost:5000/api/eval/retrieve"

PLANT = "Greenfield Steel Works"
LINE = "Fabrication Line 1"


def norm(s):
    """Same flattening idea as the promptfoo checks: dashes, degree signs,
    spacing and case must not decide whether a phrase 'is there'."""
    s = re.sub(r"[\u2010-\u2015\u2212]", "-", s or "").replace("\u00b0", "")
    return re.sub(r"\s+", " ", s).lower()


def first_hit(chunks, evidence):
    """Rank of the first chunk containing ALL evidence phrases, or None."""
    wanted = [norm(p) for p in evidence]
    for ch in chunks:
        text = norm(ch["text"])
        if all(p in text for p in wanted):
            return ch["rank"], ch
    return None, None


def main():
    labels = json.loads(LABELS.read_text(encoding="utf-8"))["questions"]

    try:
        requests.get("http://localhost:5000/api/health", timeout=10)
    except requests.RequestException:
        sys.exit("The app is not reachable on localhost:5000 — start it with: python app.py")

    rows = []
    for q in labels:
        r = requests.post(URL, json={
            "question": q["question"], "equip_tag": q["equip_tag"],
            "plant_site": PLANT, "line": LINE, "mode": "doc",
        }, timeout=60)
        r.raise_for_status()
        res = r.json()

        rank, hit = first_hit(res["chunks"], q["evidence"])
        top = res["chunks"][0] if res["chunks"] else None
        rows.append({
            "id": q["id"],
            "question": q["question"],
            "evidence": q["evidence"],
            "rank": rank,
            "hit_chunk": hit["id"] if hit else None,
            "hit_doc": f'{hit["doc_type"]}: {hit["name"]}' if hit else None,
            "top_chunk": top["id"] if top else None,
            "top_doc": f'{top["doc_type"]}: {top["name"]}' if top else None,
            "top_score": top["score"] if top else None,
            "would_refuse": res["would_refuse"],
            "refuse_reason": res["refuse_reason"],
        })

    # ── scores ───────────────────────────────────────────────────────────────
    n = len(rows)
    in12 = sum(1 for r in rows if r["rank"] is not None)
    in3 = sum(1 for r in rows if r["rank"] is not None and r["rank"] <= 3)
    mrr = sum((1 / r["rank"]) if r["rank"] else 0 for r in rows) / n
    refused = sum(1 for r in rows if r["would_refuse"])

    # ── table ────────────────────────────────────────────────────────────────
    print(f"\n{'ID':<8}{'RANK':>6}  {'TOP SCORE':>9}  QUESTION")
    for r in rows:
        rank = str(r["rank"]) if r["rank"] else "MISS"
        flag = "  <- app would REFUSE" if r["would_refuse"] else ""
        print(f'{r["id"]:<8}{rank:>6}  {r["top_score"] or 0:>9.3f}  {r["question"][:62]}{flag}')

    print("\nSCORES")
    print(f"  Found in top 12 : {in12}/{n}  ({in12 / n:.0%})   <- did the right chunk reach the AI at all")
    print(f"  Found in top 3  : {in3}/{n}  ({in3 / n:.0%})")
    print(f"  MRR             : {mrr:.2f}          <- 1.0 = always ranked first")
    if refused:
        print(f"  App would refuse: {refused}  <- search stage said 'No manuals found' to a valid question")

    misses = [r for r in rows if r["rank"] is None]
    if misses:
        print("\nMISSES — check each one: a real search failure, or a label that is too strict?")
        for r in misses:
            print(f'  {r["id"]}: needed {r["evidence"]}')
            print(f'          top result was {r["top_doc"]} ({r["top_chunk"]})')

    # ── save ─────────────────────────────────────────────────────────────────
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"retrieval_{dt.datetime.now():%Y-%m-%d_%H%M}.json"
    out.write_text(json.dumps({
        "_meta": {
            "run_at": dt.datetime.now().isoformat(timespec="seconds"),
            "labels": str(LABELS.relative_to(ROOT)),
            "top_k": 12,
            "note": "Phase 1 baseline. Compare against this after every Phase 3 change.",
        },
        "scores": {"found_in_top_12": in12, "found_in_top_3": in3,
                   "mrr": round(mrr, 3), "n": n, "app_would_refuse": refused},
        "rows": rows,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
