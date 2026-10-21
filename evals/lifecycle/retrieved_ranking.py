"""
Real ranking for the Retrieved stage of the "From Document to Answer" lesson in docs/preview.html.

Re-runs the maintenance specialist's work-instruction search exactly as multi_agent.search_plantmind()
does it, but prints the FULL order at each step instead of only the final 4:

  1. Pinecone: the operator's words, embedded as a query, nearest by meaning,
     filtered to FL-101 + Work Instruction (asks for 15; FL-101's WI has 8 sections)
  2. Pieces scoring below 0.4 are dropped (same threshold as the app)
  3. Reranker (pinecone-rerank-v0): the same pieces, re-scored against the question
  4. The app keeps the reranker's top 4

Free tier only: per question, one Pinecone embed, one query, one rerank call. No Groq tokens.
Run from the repo root:
    venv/Scripts/python.exe evals/lifecycle/retrieved_ranking.py ["question" "another question" ...]
With no question it uses the default below. Writes evals/lifecycle/retrieved_ranking.json (one entry per question).
The lesson uses the 4th question: "What checks are needed after changing the fill valve seals?"
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # repo root
import multi_agent as ma  # noqa: E402  (loads .env, Pinecone client, index)

DEFAULT_QUESTION = "Bottles aren't full enough. What should I check?"
MACHINE = "FL-101"
DOC_TYPE = "Work Instruction"


def first_line(text, n=90):
    lines = [l.strip() for l in (text or "").splitlines() if l.strip() and not set(l.strip()) <= set("━═─—=_-")]
    return (lines[0] if lines else "")[:n]


def piece_no(match_id):
    try:
        return int(str(match_id).rsplit("_chunk_", 1)[1]) + 1
    except Exception:
        return None


def rank(question):
    query = ma.specialist_query("maintenance", question, MACHINE)   # the app passes the operator's words
    vec = ma.pc.inference.embed(model="multilingual-e5-large", inputs=[query],
                                parameters={"input_type": "query", "truncate": "END"})[0].values
    res = ma.pine_index.query(vector=vec, top_k=ma.RERANK_POOL, include_metadata=True,
                              filter={"equip_tag": {"$eq": MACHINE}, "doc_type": {"$eq": DOC_TYPE}})
    matches = list(res.matches)
    strong = [m for m in matches if m.score >= 0.4]

    print(f"Question : {question}")
    print(f"Filter   : {MACHINE} + {DOC_TYPE}  ·  Pinecone returned {len(matches)}, {len(strong)} scored >= 0.4\n")

    print("1 · PINECONE ORDER (closest in meaning)")
    pine = []
    for r, m in enumerate(matches, 1):
        t = (m.metadata or {}).get("text", "")
        row = {"rank": r, "piece": piece_no(m.id), "id": m.id, "score": round(m.score, 4),
               "kept": m.score >= 0.4, "first_line": first_line(t), "text": t}
        pine.append(row)
        print(f"  {r}. piece {row['piece']}  score {m.score:.3f}{'' if row['kept'] else '  (below 0.4, dropped)'}  {row['first_line']}")

    rerank = []
    if len(strong) > 1:
        rr = ma.pc.inference.rerank(
            model=ma.RERANK_MODEL, query=query[:1000],
            documents=[(m.metadata or {}).get("text", "")[:ma.SEARCH_PIECE_MAX_CHARS] for m in strong],
            top_n=len(strong), return_documents=False)
        print("\n2 · RERANKER ORDER (most relevant to the question)")
        for r, item in enumerate(rr.data, 1):
            m = strong[item.index]
            row = {"rank": r, "piece": piece_no(m.id), "id": m.id, "rerank_score": round(item.score, 4),
                   "pinecone_rank": next(p["rank"] for p in pine if p["id"] == m.id),
                   "first_line": first_line((m.metadata or {}).get("text", ""))}
            rerank.append(row)
            move = row["pinecone_rank"] - r
            arrow = f"up {move}" if move > 0 else (f"down {-move}" if move < 0 else "same")
            print(f"  {r}. piece {row['piece']}  rerank {item.score:.3f}  (was #{row['pinecone_rank']}, {arrow})  {row['first_line']}")

    top4 = [r["piece"] for r in (rerank or pine)[:4]]
    print(f"\n3 · TOP K = 4 handed to the maintenance specialist: pieces {top4}")
    return {"question": question, "query": query, "filter": [MACHINE, DOC_TYPE],
            "pinecone": pine, "rerank": rerank, "top4_pieces": top4}


def main():
    questions = sys.argv[1:] or [DEFAULT_QUESTION]
    results = []
    for q in questions:
        results.append(rank(q))
        print("\n" + "-" * 70 + "\n")
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "retrieved_ranking.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
