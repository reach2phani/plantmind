"""
teaching_components.py — Evals teaching set, step 7a: test each part on its own.

WHAT THIS IS (simple version)
    An investigation is a chain of parts. When the answer misses a line, one of
    them broke. This checks each part separately, for T-1, T-2 and T-3, with no
    report written:

      1. Machine finder   do the words find FL-101? (no machine picked)
      2. Fault matcher    does the graph pick Underfill?
      3. Search           do the SAME searches the investigation runs return a
                          piece containing the key sentence?
                            "Dripping means a worn seal"   (SOP)        -> L1
                            "weigh the first 20 bottles"   (WI and SOP) -> L4
                          rank in the top 12, inside the top 4 the
                          investigation actually takes, and whether the
                          sentence sits in the first 300 characters of the
                          piece (the specialist is only shown those).
      4. Graph hand-over  is the fact in the text the graph hands to the writer?
      5. Router           do the required searches include the SOP and the
                          work instruction? (the graph's rule, in code; the
                          supervisor AI can only add to it)

COST
    Search and graph: free. The fault matcher may ask the small model one
    short tie-break question per wording. No report is written.

RUN (from C:\\plantmind; the app does not need to be running)
    venv\\Scripts\\python.exe evals\\teaching_components.py

OUTPUT
    evals/fl101/results/teaching_step7a_components.md    read this one
    evals/fl101/results/teaching_step7a_components.json  raw results
"""

import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import graph_value_test as gv  # noqa: E402  (machine finder + text cleaner)
import knowledge_graph as kg   # noqa: E402
import multi_agent as ma       # noqa: E402

SPEC = json.loads((ROOT / "evals" / "fl101" / "teaching_cases.json").read_text(encoding="utf-8"))
OUT = ROOT / "evals" / "fl101" / "results"
EXPECT_MACHINE, EXPECT_FAULT = "FL-101", "Underfill"
# What search_plantmind() actually uses. SHOWN_CHARS is read from the app, so
# this check always measures the live code (300 before 2026-10-01, whole pieces after).
TAKEN, STRONG = 4, 0.4
SHOWN_CHARS = getattr(ma, "SEARCH_PIECE_MAX_CHARS", 300)

# The searches the investigation runs, word for word (multi_agent.py).
SEARCHES = {
    "SOP": ("SOP Agent", "procedure response steps specification for {m} alarm {i}"),
    "Work Instruction": ("Maintenance Agent", "maintenance service repair history for {m} {i}"),
}
SENTENCES = [
    ("L1", "Dripping means a worn seal", ["SOP"]),
    ("L4", "weigh the first 20 bottles", ["Work Instruction", "SOP"]),
]
# How the same fact reads in the graph hand-over.
GRAPH_FACTS = [("L1", "drips between fills"), ("L4", "weigh the first 20 bottles")]


def flat(text):
    return re.sub(r"\s+", " ", gv._norm(text)).lower()


def search_rank(query, doc_type, machine, sentence):
    """Where the piece holding the sentence ranks, as the investigation searches."""
    vec = ma.pc.inference.embed(model="multilingual-e5-large", inputs=[query],
                                parameters={"input_type": "query", "truncate": "END"})[0].values
    res = ma.pine_index.query(vector=vec, top_k=12, include_metadata=True,
                              filter={"equip_tag": {"$eq": machine}, "doc_type": {"$eq": doc_type}})
    want = flat(sentence)
    for i, m in enumerate(res.matches, 1):
        text = flat(m.metadata.get("text", ""))
        if want in text:
            return {"rank": i, "score": round(m.score, 3),
                    "taken": i <= TAKEN and m.score >= STRONG,
                    "shown": want in flat(m.metadata.get("text", "")[:SHOWN_CHARS]),
                    "at_char": text.find(want)}
    return {"rank": None, "score": None, "taken": False, "shown": False, "at_char": None}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    print("\nSTEP 7a — EACH PART ON ITS OWN\n")
    for case in SPEC["cases"]:
        q = case["incident"]
        r = {"id": case["id"], "question": q}
        print(f"{case['id']}  {q}")

        r["machine"] = gv.find_machine(q)
        print(f"   1 machine finder : {r['machine']}  (want {EXPECT_MACHINE})")
        if r["machine"] != EXPECT_MACHINE:
            print("     -> stops here: the app shows 'No matching equipment manual found'")
            rows.append(r)
            continue

        ctx = kg.get_fault_chain(r["machine"], incident_text=q)
        r["fault"] = ctx.get("matched_faults") or []
        r["fault_confidence"], r["fault_method"] = ctx.get("match_confidence"), ctx.get("match_method")
        print(f"   2 fault matcher  : {', '.join(r['fault']) or 'none'}  "
              f"[{r['fault_confidence']}; {r['fault_method']}]  (want {EXPECT_FAULT})")

        r["search"] = []
        for line_id, sentence, doc_types in SENTENCES:
            for dtype in doc_types:
                agent, template = SEARCHES[dtype]
                query = template.format(m=r["machine"], i=q[:100])
                s = search_rank(query, dtype, r["machine"], sentence)
                s.update({"line": line_id, "sentence": sentence, "doc_type": dtype, "agent": agent})
                r["search"].append(s)
                rank = s["rank"] if s["rank"] else "not in top 12"
                print(f"   3 search ({line_id}, {dtype:16s}): rank {rank}"
                      + (f", score {s['score']}, taken {'yes' if s['taken'] else 'NO'}, "
                         f"shown to specialist {'yes' if s['shown'] else 'NO (sentence starts at char ' + str(s['at_char']) + ')'}"
                         if s["rank"] else ""))

        text = flat(ctx.get("chain_text", ""))
        r["graph"] = {lid: flat(fact) in text for lid, fact in GRAPH_FACTS}
        print("   4 graph hand-over: " + ", ".join(f"{lid} {'yes' if v else 'NO'}" for lid, v in r["graph"].items()))

        need, _ = ma.required_agents(ctx, r["machine"])
        r["required"] = need
        r["router_ok"] = {"sop", "maintenance"} <= set(need)
        print(f"   5 router (required by code): {', '.join(need)}  -> SOP + work instruction "
              f"{'both required' if r['router_ok'] else 'NOT both required'}")
        rows.append(r)
        print()

    # Scorecard
    def yn(v):
        return "✅" if v else "❌"
    lines = ["# Teaching set — step 7a: each part on its own", "",
             f"Run {dt.datetime.now():%Y-%m-%d %H:%M}. Same machine finder, fault matcher, searches "
             "and routing rule as a real investigation; no report written. "
             f"The investigation takes the top {TAKEN} search pieces scoring {STRONG}+, and shows the "
             f"specialist the first {SHOWN_CHARS} characters of each.", "",
             "| Part | " + " | ".join(r["id"] for r in rows) + " |", "|---|" + "---|" * len(rows)]
    lines.append("| 1 Machine finder → FL-101 | " + " | ".join(
        f"{yn(r['machine'] == EXPECT_MACHINE)} {r['machine'] or 'none'}" for r in rows) + " |")
    lines.append("| 2 Fault matcher → Underfill | " + " | ".join(
        f"{yn(r.get('fault') == [EXPECT_FAULT])} {', '.join(r.get('fault') or []) or '—'} "
        f"({r.get('fault_confidence') or '—'})" for r in rows) + " |")
    for line_id, sentence, doc_types in SENTENCES:
        for dtype in doc_types:
            cells = []
            for r in rows:
                s = next((x for x in r.get("search", []) if x["line"] == line_id and x["doc_type"] == dtype), None)
                if not s:
                    cells.append("—")
                elif not s["rank"]:
                    cells.append("❌ not in top 12")
                else:
                    cells.append(f"rank {s['rank']} · taken {yn(s['taken'])} · shown {yn(s['shown'])}")
            lines.append(f"| 3 Search {dtype}: \"{sentence}\" ({line_id}) | " + " | ".join(cells) + " |")
    for lid, fact in GRAPH_FACTS:
        lines.append(f"| 4 Graph hand-over: \"{fact}\" ({lid}) | " + " | ".join(
            yn(r.get("graph", {}).get(lid)) if r.get("graph") else "—" for r in rows) + " |")
    lines.append("| 5 Router: SOP + work instruction required | " + " | ".join(
        (yn(r["router_ok"]) + " " + ", ".join(r["required"])) if "required" in r else "—" for r in rows) + " |")
    lines += ["", "## How to read this", "",
              "- **taken** = the piece is in the top 4 with a score of 0.4+, so the investigation uses it.",
              f"- **shown** = the sentence is inside the first {SHOWN_CHARS} characters of the piece. The "
              "specialist never sees anything after that, even when the piece was found.",
              "- A part that fails here can explain a missing line in the real runs (step 7b).",
              "- Three wordings: a direction, not proof."]
    (OUT / "teaching_step7a_components.md").write_text("\n".join(lines), encoding="utf-8")
    (OUT / "teaching_step7a_components.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False),
                                                         encoding="utf-8")
    print(f"Scorecard: {OUT / 'teaching_step7a_components.md'}")


if __name__ == "__main__":
    main()
