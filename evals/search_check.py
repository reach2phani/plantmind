"""
Search ranking check (Phase 3, pulled forward 6 Oct 2026): does each
investigation search DELIVER the piece that holds the needed fact?

WHY (plain words)
    A specialist only sees what its search hands it: today the top 4 pieces
    (score >= 0.4) of one document type. If the piece with the answer ranks 5th,
    no prompt can fix the report. Fresh question FR-01 (restart after the
    weekend) needed SOP section 9; the SOP search ranked it 7th, so the report
    filled the gap with "test mode, watch 5 minutes".

WHAT IT MEASURES (labels: evals/search_labels.json)
    For each question and each needed fact:
      delivered         is a piece with ALL the fact's evidence phrases in what
                        the app's real search function (search_plantmind) hands
                        the specialist? The number that matters.
      rank by meaning   where the first such piece sits in a wide list (top 25)
                        by meaning alone, with the app's search wording
      rank, own words   the same with the operator's words only (no fixed prefix)
      in documents      is the evidence in the source document at all (labels
                        check), and in ONE stored piece (or cut apart)?

COST
    Free: Pinecone only (embeddings + queries). No Groq tokens. The app does
    NOT need to be running.

RUN
    venv\\Scripts\\python.exe evals\\search_check.py --tag before
    (after a search change, run again with another --tag and compare)

OUTPUT
    evals/search_results/search_<tag>.md   read this one
    evals/search_results/search_<tag>.json
"""

import argparse
import contextlib
import datetime as dt
import io
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))
os.environ["LANGSMITH_TRACING"] = "false"

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from graph_value_test import _norm  # noqa: E402
from context_attribution import AGENTS  # noqa: E402  (each specialist's doc type + search wording)

LABELS = ROOT / "evals" / "search_labels.json"
OUT_DIR = ROOT / "evals" / "search_results"
RAW_DOCS = {"FL-101": ROOT / "demo_data" / "fl101"}
SEARCH_TO_AGENT = {"sop": "SOP Agent", "maintenance": "Maintenance Agent",
                   "ncr": "NCR Agent", "alarm": "Alarm Agent"}
WIDE = 25


def flat(text):
    """Compare text ignoring case, line breaks and look-alike dashes/quotes."""
    return re.sub(r"\s+", " ", _norm(text or "")).strip().lower()


def has_all(text, phrases):
    t = flat(text)
    return all(flat(p) in t for p in phrases)


_ma = None


def ma():
    global _ma
    if _ma is None:
        with contextlib.redirect_stdout(io.StringIO()):
            import multi_agent
        _ma = multi_agent
    return _ma


def wide_list(query, doc_type, equipment):
    m = ma()
    vec = m.pc.inference.embed(model="multilingual-e5-large", inputs=[query],
                               parameters={"input_type": "query", "truncate": "END"})[0].values
    res = m.pine_index.query(vector=vec, top_k=WIDE, include_metadata=True,
                             filter={"equip_tag": {"$eq": equipment}, "doc_type": {"$eq": doc_type}})
    return [x.metadata.get("text", "") for x in res.matches]


def first_rank(pieces, phrases):
    return next((i + 1 for i, p in enumerate(pieces) if has_all(p, phrases)), None)


def raw_text(equipment):
    """The source documents themselves (labels check, independent of how they are cut)."""
    folder = RAW_DOCS.get(equipment)
    if not folder or not folder.exists():
        return ""
    return "\n".join(p.read_text(encoding="utf-8", errors="ignore")
                     for p in sorted(folder.rglob("*")) if p.suffix in (".txt", ".csv"))


def all_pieces(equipment, doc_type):
    """Every stored piece of one document type (to tell 'cut apart' from 'not found')."""
    m = ma()
    vec = m.pc.inference.embed(model="multilingual-e5-large", inputs=["document"],
                               parameters={"input_type": "query"})[0].values
    res = m.pine_index.query(vector=vec, top_k=1000, include_metadata=True,
                             filter={"equip_tag": {"$eq": equipment}, "doc_type": {"$eq": doc_type}})
    return [x.metadata.get("text", "") for x in res.matches]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, help="name for this result, e.g. before / sections")
    ap.add_argument("--sets", default="", help="only these sets, e.g. teaching,fresh")
    args = ap.parse_args()

    spec = json.loads(LABELS.read_text(encoding="utf-8"))
    equipment = spec["equipment"]
    sets = {s for s in args.sets.split(",") if s}
    raw = flat(raw_text(equipment))
    pieces_cache, search_cache, wide_cache = {}, {}, {}
    rows = []
    if hasattr(ma(), "search_stats"):
        ma().search_stats(reset=True)

    for q in spec["questions"]:
        if sets and q["set"] not in sets:
            continue
        facts = spec["fact_sets"][q["facts"]] if isinstance(q["facts"], str) else q["facts"]
        for f in facts:
            best = None
            for h in f["homes"]:
                agent = SEARCH_TO_AGENT[h["search"]]
                doc_type = AGENTS[agent][0]
                query = ma().specialist_query(h["search"], q["q"], equipment)   # exactly the app's wording
                if (agent, q["id"]) not in search_cache:
                    search_cache[(agent, q["id"])] = ma().search_plantmind(
                        query, doc_type_filter=doc_type, equipment_filter=equipment)
                delivered_text = search_cache[(agent, q["id"])]
                delivered = any(has_all(p, h["evidence"]) for p in delivered_text.split("\n\n---\n\n"))
                for key, qq in (("app", query), ("own", q["q"])):
                    if (key, agent, q["id"]) not in wide_cache:
                        wide_cache[(key, agent, q["id"])] = wide_list(qq, doc_type, equipment)
                if doc_type not in pieces_cache:
                    pieces_cache[doc_type] = all_pieces(equipment, doc_type)
                in_docs = (not raw) or all(flat(p) in raw for p in h["evidence"])
                in_one_piece = any(has_all(p, h["evidence"]) for p in pieces_cache[doc_type])
                result = {
                    "search": h["search"], "evidence": h["evidence"], "delivered": delivered,
                    "rank_app": first_rank(wide_cache[("app", agent, q["id"])], h["evidence"]),
                    "rank_own": first_rank(wide_cache[("own", agent, q["id"])], h["evidence"]),
                    "in_documents": in_docs, "in_one_piece": in_one_piece,
                }
                # Keep the best home: delivered first, then the highest rank.
                score = (result["delivered"], -(result["rank_app"] or 999))
                if best is None or score > best[0]:
                    best = (score, result)
            rows.append({"id": q["id"], "set": q["set"], "fact": f["fact"], **best[1]})
            r = best[1]
            print(f"  {q['id']:6} {'DELIVERED' if r['delivered'] else 'missed   '} {r['search']:11} "
                  f"rank {r['rank_app'] or '-':>3} (own words {r['rank_own'] or '-':>3})  {f['fact']}"
                  + ("" if r["in_documents"] else "   <-- LABEL: phrase not in the documents")
                  + ("" if r["in_one_piece"] else "   <-- cut apart: no single piece holds it"))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = f"{dt.datetime.now():%Y-%m-%d %H:%M}"
    (OUT_DIR / f"search_{args.tag}.json").write_text(
        json.dumps({"tag": args.tag, "at": stamp, "rows": rows}, indent=1, ensure_ascii=False), encoding="utf-8")

    by_set = defaultdict(list)
    for r in rows:
        by_set[r["set"]].append(r)

    def summary(rs):
        d = sum(r["delivered"] for r in rs)
        top4 = sum(bool(r["rank_app"] and r["rank_app"] <= 4) for r in rs)
        own4 = sum(bool(r["rank_own"] and r["rank_own"] <= 4) for r in rs)
        cut = sum(not r["in_one_piece"] for r in rs)
        return f"{d}/{len(rs)}", f"{top4}/{len(rs)}", f"{own4}/{len(rs)}", str(cut)

    L = [f"# Search check — {args.tag}", "",
         f"Run {stamp} by `evals/search_check.py` (free: Pinecone only). For each needed fact: did the "
         "app's real search hand the specialist a piece holding it? Labels: evals/search_labels.json.", "",
         "| Set | Delivered to the specialist | In top 4 by meaning (app's wording) | In top 4 (operator's words only) | Cut apart (no single piece holds it) |",
         "|---|---|---|---|---|"]
    for s, rs in by_set.items():
        L.append(f"| {s} | " + " | ".join(summary(rs)) + " |")
    L.append("| **All** | " + " | ".join(f"**{x}**" for x in summary(rows)) + " |")
    L += ["", "## Every fact", "", "| Question | Fact | Search | Delivered | Rank (app wording) | Rank (own words) | Note |",
          "|---|---|---|---|---|---|---|"]
    for r in rows:
        note = ("label phrase not in documents" if not r["in_documents"]
                else "cut apart" if not r["in_one_piece"] else "")
        L.append(f"| {r['id']} | {r['fact']} | {r['search']} | {'yes' if r['delivered'] else '**no**'} | "
                 f"{r['rank_app'] or 'not in top ' + str(WIDE)} | {r['rank_own'] or 'not in top ' + str(WIDE)} | {note} |")
    st = ma().search_stats() if hasattr(ma(), "search_stats") else {}
    if st:
        L += ["", f"Ranking used by the app's searches in this check: reranked {st['reranked']}, "
                  f"fell back to meaning order {st['fallback']}"
                  + (f" (last error: {st['last_error']})" if st.get("last_error") else "") + "."]
    L += ["", "How to read it: 'delivered' is what the specialist actually saw. A fact that is in one "
          "piece but ranks below 4 is a RANKING problem; a fact no single piece holds is a CUTTING "
          "problem (section chunking fixes that)."]
    out = OUT_DIR / f"search_{args.tag}.md"
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
