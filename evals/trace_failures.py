"""
trace_failures.py - where did each failed check go wrong? (two levels)

  Level 1  what went wrong and why it matters   (from evals/fl101/failure_map.json,
                                                 written and reviewed by a person)
  Level 2  which pipeline step to look at       (traced here, from saved data)

For a missing-fact check, the fact is followed through PlantMind's real steps:

  Source documents -> Routing (supervisor) -> Chunking -> Embedding + vector
  search -> Reranking -> Context and token limits -> Knowledge graph ->
  AI generation (specialist) -> AI generation (writer)

Evidence comes from the baseline folder (runs.json = the run records), the
FL-101 documents, the chunks stored in Pinecone, a replay of each saved
search question (Pinecone, top 15 by meaning, no reranker call) and the
fault chain rebuilt from Neo4j. NO Groq tokens: the fault matcher's AI
tie-break is switched off (every baseline match was 'sure').

Usage:
  venv\\Scripts\\python.exe evals\\trace_failures.py --name baseline-v1
Writes attribution.json + attribution.md into the baseline folder.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from pinecone import Pinecone  # noqa: E402
import knowledge_graph as kg  # noqa: E402

MAP_FILE = ROOT / "evals" / "fl101" / "failure_map.json"
DOCS_DIR = ROOT / "demo_data" / "fl101"
EQUIPMENT = "FL-101"
POOL = 15            # candidates by meaning before reranking (multi_agent.RERANK_POOL)
STRONG = 0.4         # score a match needs to be used (multi_agent.search_plantmind)
QUERY_SAVED = 300    # the run record keeps the first 300 characters of a search question
STEP_OF_TYPE = {"SOP": "sop", "Work Instruction": "maintenance", "Shift Log": "alarm", "NCR": "ncr"}
AGENT_OF_STEP = {"sop": "SOP Agent", "maintenance": "Maintenance Agent",
                 "alarm": "Alarm Agent", "ncr": "NCR Agent"}
EXPECTED = {"TC1": "HIGH", "TC2": "HIGH", "TC3": "HIGH", "TC4": "CRITICAL", "TC5": "LOW"}

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(os.getenv("PINECONE_INDEX"))

# The graph rebuild must not spend tokens: force the fault matcher's
# small-model tie-break off (get_fault_chain calls match_faults by name).
_match = kg.match_faults
kg.match_faults = lambda nodes, edges, text, use_ai=True: _match(nodes, edges, text, use_ai=False)


# ── helpers ──────────────────────────────────────────────────────────────────

def norm(t):
    """Same text, plain dashes and spaces, so phrases match AI output."""
    t = t or ""
    for a, b in (("‑", "-"), ("‐", "-"), ("–", "-"), ("—", "-"),
                 (" ", " "), (" ", " "), ("’", "'")):
        t = t.replace(a, b)
    return t


def find(phrases, text):
    """First phrase that matches, and a short quote around it (or None)."""
    t = norm(text)
    for ph in phrases:
        m = re.search(ph, t, re.I)
        if m:
            a, b = max(0, m.start() - 60), min(len(t), m.end() + 60)
            return " ".join(t[a:b].split())
    return None


def immediate_actions(report):
    t = norm(report)
    at = t.find("Immediate action")
    if at == -1:
        return ""
    end = t.find("Root cause fix", at)
    return t[at:end if end != -1 else len(t)]


def step(name, status, evidence=""):
    """status: ok | fail | warn | na | unknown"""
    return {"step": name, "status": status, "evidence": evidence}


# ── evidence sources (cached) ────────────────────────────────────────────────

_doc_texts = {p.name: p.read_text(encoding="utf-8", errors="ignore") for p in DOCS_DIR.glob("*.txt")}
_chunks, _graph, _replays = {}, {}, {}


def doc_chunks(doc_name, runs):
    """Every chunk Pinecone holds for this document: [(chunk_id, doc_type, text)]."""
    if doc_name in _chunks:
        return _chunks[doc_name]
    prefix = None
    for r in runs.values():
        for p in r["details"].get("pieces") or []:
            if p.get("document") == doc_name and "_chunk_" in str(p.get("chunk_id")):
                prefix = p["chunk_id"].split("_chunk_")[0] + "_chunk_"
                break
        if prefix:
            break
    out = []
    if prefix:
        ids = []
        for page in index.list(prefix=prefix):
            ids.extend(getattr(i, "id", i) for i in page)
        for i in range(0, len(ids), 100):
            res = index.fetch(ids=ids[i:i + 100])
            for vid, v in res.vectors.items():
                meta = v.metadata or {}
                out.append((vid, meta.get("doc_type", ""), meta.get("text", "")))
        out.sort(key=lambda c: int(c[0].rsplit("_", 1)[-1]) if c[0].rsplit("_", 1)[-1].isdigit() else 0)
    _chunks[doc_name] = out
    return out


def graph_for(question):
    if question not in _graph:
        try:
            _graph[question] = kg.get_fault_chain(EQUIPMENT, incident_text=question)
        except Exception as e:
            _graph[question] = {"has_data": False, "error": str(e)[:120]}
    return _graph[question]


def replay(query, doc_type):
    """Top-15 chunk ids by meaning for this saved search question."""
    key = (query, doc_type)
    if key not in _replays:
        emb = pc.inference.embed(model="multilingual-e5-large", inputs=[query],
                                 parameters={"input_type": "query", "truncate": "END"})
        res = index.query(vector=emb[0].values, top_k=POOL, include_metadata=False,
                          filter={"equip_tag": {"$eq": EQUIPMENT}, "doc_type": {"$eq": doc_type}})
        _replays[key] = [(m.id, round(m.score, 4)) for m in res.matches if m.score >= STRONG]
    return _replays[key]


def full_query(saved, question):
    """The run record keeps 300 characters; rebuild the rest from the question."""
    if len(saved) < QUERY_SAVED:
        return saved, True
    at = saved.find(question[:40])
    if at != -1:
        return saved[:at] + question, True
    return saved, False


# ── tracing ──────────────────────────────────────────────────────────────────

def trace_fact(cfg, ans, run, runs):
    phrases = cfg.get("phrases") or []
    s, d = run["summary"], run["details"]
    question = s.get("question") or ans.get("question") or ""
    steps = []

    # 1 Source documents
    docs = {n: find(phrases, t) for n, t in _doc_texts.items()}
    docs = {n: q for n, q in docs.items() if q}
    if docs:
        steps.append(step("Source documents", "ok", "; ".join(f"{n}: \"{q}\"" for n, q in docs.items())))
    else:
        steps.append(step("Source documents", "warn",
                          "only implied, not written: " + cfg.get("source", "")))

    # 2-7 the search path, per document that holds the fact; keep the best one
    events = [e for e in d.get("events") or [] if e.get("kind") == "search"]
    ran = {e.get("step") for e in events}
    paths = []
    for doc in docs:
        chunks = doc_chunks(doc, runs)
        dtype = next((c[1] for c in chunks if c[1]), "")
        sp = STEP_OF_TYPE.get(dtype)
        path = []
        if not sp:
            path.append(step("Routing (supervisor)", "unknown", f"{doc}: unknown document type"))
            paths.append(path)
            continue
        if sp not in ran:
            path.append(step("Routing (supervisor)", "fail",
                             f"the {sp} specialist (searches {dtype}) was not sent; sent: {', '.join(sorted(x for x in ran if x))}"))
            paths.append(path)
            continue
        path.append(step("Routing (supervisor)", "ok", f"the {sp} specialist searched {dtype}"))

        holding = [c for c in chunks if find(phrases, c[2])]
        if not chunks:
            path.append(step("Chunking", "unknown", f"no stored chunks found for {doc}"))
            paths.append(path)
            continue
        if not holding:
            path.append(step("Chunking", "fail", f"{doc}: no single chunk holds the fact (split across chunks?)"))
            paths.append(path)
            continue
        ids = [c[0] for c in holding]
        path.append(step("Chunking", "ok", "whole in " + ", ".join("chunk " + i.rsplit("_", 1)[-1] for i in ids)))

        ev = next((e for e in events if e.get("step") == sp), {})
        q, exact = full_query(ev.get("query", ""), question)
        cands = replay(q, dtype)
        hit = [(r, cid, sc) for r, (cid, sc) in enumerate(cands, 1) if cid in ids]
        note = "" if exact else " (approximate: saved question was cut)"
        if hit:
            r, cid, sc = hit[0]
            path.append(step("Embedding + vector search", "ok",
                             f"chunk {cid.rsplit('_', 1)[-1]} was #{r} of {len(cands)} by meaning (score {sc}){note}"))
        else:
            path.append(step("Embedding + vector search", "fail",
                             f"not in the {len(cands)} closest chunks{note}"))
            paths.append(path)
            continue

        got = [p for p in d.get("pieces") or [] if p.get("step") == sp and p.get("chunk_id") in ids]
        handed = [p for p in d.get("pieces") or [] if p.get("step") == sp]
        reranked = any(p.get("reranked") for p in handed)
        if got:
            path.append(step("Reranking", "ok",
                             f"kept: rank {got[0]['rank']} of {len(handed)}" + ("" if reranked else " (no reranker for this type)")))
        else:
            path.append(step("Reranking", "fail",
                             f"dropped: not in the {len(handed)} chunks handed to the {sp} specialist"
                             + ("" if reranked else " (meaning order, no reranker)")))
            paths.append(path)
            continue

        whole = find(phrases, got[0].get("text", ""))
        trunc = s.get("truncated_calls") or 0
        path.append(step("Context and token limits", "ok" if whole and not trunc else "fail",
                         ("chunk handed over whole" if whole else "fact cut out of the handed-over text")
                         + f"; {trunc} AI call(s) cut off by the token limit"))
        if not whole or trunc:
            paths.append(path)
            continue

        fnd = next((f for f in d.get("findings") or [] if f.get("agent") == AGENT_OF_STEP[sp]), None)
        q2 = find(phrases, (fnd or {}).get("findings", ""))
        path.append(step("AI generation - specialist", "ok" if q2 else "fail",
                         f"{AGENT_OF_STEP[sp]} kept it: \"{q2}\"" if q2
                         else f"{AGENT_OF_STEP[sp]} read it but left it out of its finding"))
        paths.append(path)

    def score(p):
        return sum(1 for x in p if x["status"] == "ok") + (5 if p and p[-1]["step"] == "AI generation - specialist" and p[-1]["status"] == "ok" else 0)
    best = max(paths, key=score) if paths else [
        step("Routing (supervisor)", "na", "no document states the fact, nothing to search for")]
    steps += best
    via_search = bool(best) and best[-1]["step"] == "AI generation - specialist" and best[-1]["status"] == "ok"

    # Knowledge graph
    g = graph_for(question)
    gq = find(phrases, g.get("chain_text", "")) if g.get("has_data") else None
    wq = next((w for w in d.get("graph_warnings") or [] if find(phrases, w)), None)
    # The must-show warnings list is for safety warnings only; a value or a
    # step is fine in the graph text alone.
    must_show = cfg.get("type") == "missing_safety_warning"
    if gq and wq:
        steps.append(step("Knowledge graph", "ok", f"in the graph text and on the must-show warnings list: \"{gq}\""))
    elif gq and not must_show:
        steps.append(step("Knowledge graph", "ok", f"in the graph text: \"{gq}\""))
    elif gq:
        steps.append(step("Knowledge graph", "warn",
                          f"in the graph text, but NOT on the must-show warnings list: \"{gq}\""))
    else:
        steps.append(step("Knowledge graph", "fail" if g.get("has_data") else "unknown",
                          "not in the graph text" if g.get("has_data") else "graph not available"))
    via_graph = bool(gq)

    # AI generation - writer
    report = d.get("report") or ""
    in_report, in_actions = find(phrases, report), find(phrases, immediate_actions(report))
    if in_actions:
        steps.append(step("AI generation - writer", "warn",
                          f"the words ARE in the immediate actions: \"{in_actions}\" - the judge still failed it"))
    elif in_report:
        steps.append(step("AI generation - writer", "fail",
                          f"in the report, but not in the immediate actions: \"{in_report}\""))
    else:
        steps.append(step("AI generation - writer", "fail" if (via_search or via_graph) else "na",
                          "had the fact and left it out of the report" if (via_search or via_graph)
                          else "never received the fact"))

    # Lost at
    if not docs:
        lost, comp = "Source documents", "Source documents (only implied) + AI generation - writer"
    elif in_actions:
        lost, comp = "Rubric / judge", "Rubric / judge: the words are there, please check the verdict"
    elif via_search or via_graph:
        lost = "AI generation - writer"
        comp = "AI generation - writer" + (" (in the wrong place)" if in_report else " (dropped)")
        if any(x["step"] == "Knowledge graph" and x["status"] == "warn" for x in steps):
            comp += " + Knowledge graph (not on the must-show list)"
    else:
        first = next((x["step"] for x in best if x["status"] == "fail"), "unknown")
        lost, comp = first, first
    return {"steps": steps, "lost_at": lost, "component": comp,
            "reached_writer": {"search": via_search, "graph": via_graph}}


def trace_criticality(ans, run):
    s = run["summary"]
    tc, got = ans["tc"], ans.get("criticality") or s.get("criticality")
    g = graph_for(s.get("question") or ans.get("question") or "")
    fault = s.get("fault_matched")
    crit = ""
    for n in g.get("chain_nodes") or []:
        if n.get("type") == "Fault" and n.get("label") == fault:
            crit = str((n.get("properties") or {}).get("criticality", ""))
    floor = "CRITICAL" if crit.upper().startswith("CRITICAL") and s.get("match_confidence") == "sure" else None
    steps = [
        step("Knowledge graph", "ok" if fault else "fail",
             f"matched fault: {fault} ({s.get('match_confidence')})" if fault else "no fault matched"),
        step("Knowledge graph", "warn" if not crit else "ok",
             f"rating in the graph: {crit[:80]}" if crit else "the graph gives NO rating for this fault"),
        step("Report rules (guardrail)", "warn" if not floor else "ok",
             f"floor {floor}" if floor else "no floor: the guardrail only enforces CRITICAL faults"),
        step("AI generation - writer", "fail", f"rated {got}, expected {EXPECTED.get(tc, '?')}"),
    ]
    return {"steps": steps, "lost_at": "AI generation - writer",
            "component": "AI generation - writer (chose the rating)"
                         + ("" if floor else " + Report rules (no floor for this fault)")}


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="baseline folder name, e.g. baseline-v1")
    ap.add_argument("--root", default="evals/baselines/fl101_eval")
    args = ap.parse_args()
    folder = ROOT / args.root / args.name
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    runs = json.loads((folder / "runs.json").read_text(encoding="utf-8"))
    fmap = json.loads(MAP_FILE.read_text(encoding="utf-8"))
    types = fmap["failure_types"]

    items, unmapped = [], set()
    for ans in summary["answers"]:
        run = runs.get(ans.get("run_id"))
        for c in ans.get("checks") or []:
            if c.get("pass") is not False:
                continue
            cfg = fmap["checks"].get(c["metric"])
            if not cfg:
                unmapped.add(c["metric"])
                continue
            print(f"  tracing {ans['tc']} {ans['run_label'][-2:]} {c['metric']}")
            t = types[cfg["type"]]
            item = {"tc": ans["tc"], "description": ans.get("description", ans["tc"]),
                    "run_label": ans["run_label"], "run_id": ans.get("run_id"),
                    "metric": c["metric"], "dim": c.get("dim"), "reason": c.get("reason", ""),
                    "type": cfg["type"], "label": t["label"], "why_it_matters": t["why_it_matters"],
                    "severity": t["severity"], "fact": cfg.get("fact", ""), "source": cfg.get("source", ""),
                    "note": cfg.get("note") or cfg.get("decision") or ""}
            if not run:
                item.update(trace=None, lost_at="unknown", component="no run record")
            elif cfg.get("trace") == "pipeline":
                tr = trace_fact(cfg, ans, run, runs)
                item.update(trace=tr["steps"], lost_at=tr["lost_at"], component=tr["component"],
                            reached_writer=tr["reached_writer"])
            elif cfg.get("trace") == "criticality":
                tr = trace_criticality(ans, run)
                item.update(trace=tr["steps"], lost_at=tr["lost_at"], component=tr["component"])
            else:
                item.update(trace=None, lost_at=cfg.get("component", "not traced"),
                            component=cfg.get("component", "not traced"))
            items.append(item)

    # Groups (Level 1), sorted by severity then size
    groups = defaultdict(list)
    for it in items:
        groups[it["type"]].append(it)
    out_groups = []
    for ty, its in groups.items():
        t = types[ty]
        per_tc = Counter(i["tc"] for i in its)
        comps = Counter(i["lost_at"] for i in its)
        out_groups.append({"type": ty, "label": t["label"], "why_it_matters": t["why_it_matters"],
                           "severity": t["severity"], "severity_name": fmap["severity_levels"][str(t["severity"])],
                           "count": len(its), "answers": len({(i["tc"], i["run_label"]) for i in its}),
                           "per_scenario": dict(sorted(per_tc.items())),
                           "lost_at": comps.most_common()})
    out_groups.sort(key=lambda g: (g["severity"], -g["count"]))

    by_step = Counter(i["lost_at"] for i in items)
    top = out_groups[0] if out_groups else None
    top_step = Counter(i["lost_at"] for i in items if top and i["type"] == top["type"]).most_common(1)
    headline = (f"Most serious and most frequent: {top['label']} ({top['count']} failed checks) - "
                f"lost at {top_step[0][0]} in {top_step[0][1]} of them." if top and top_step else "No failures.")

    result = {"name": args.name, "written_utc": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
              "map": {"file": str(MAP_FILE.relative_to(ROOT)).replace("\\", "/"),
                      "status": fmap.get("status"), "reviewed_on": fmap.get("reviewed_on")},
              "method": "Facts followed with key phrases (code). Search replayed in Pinecone (top 15 by meaning, "
                        "no reranker call); graph rebuilt from Neo4j without the AI tie-break. 0 Groq tokens.",
              "pipeline_steps": fmap["pipeline_steps"],
              "headline": headline, "groups": out_groups,
              "by_step": by_step.most_common(), "items": items,
              "unmapped_checks": sorted(unmapped)}
    (folder / "attribution.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    write_md(folder / "attribution.md", result)
    print(f"\nWritten: {folder / 'attribution.json'}\n         {folder / 'attribution.md'}")
    print("\n" + headline)
    if unmapped:
        print("NOTE: failed checks not in the failure map:", ", ".join(sorted(unmapped)))


ICON = {"ok": "✅", "fail": "❌", "warn": "⚠", "na": "–", "unknown": "?"}


def write_md(path, r):
    L = [f"# Failure analysis - {r['name']}", "", f"**{r['headline']}**", "",
         f"Written {r['written_utc']}. Failure map: `{r['map']['file']}` ({r['map']['status']}, {r['map']['reviewed_on']}).",
         f"Method: {r['method']}", "", "## Level 1 - what went wrong and why it matters", "",
         "| Severity | What went wrong | Failed checks | Scenarios | Why it matters | Mostly lost at |",
         "|---|---|---|---|---|---|"]
    for g in r["groups"]:
        sc = ", ".join(f"{k} x{v}" for k, v in g["per_scenario"].items())
        L.append(f"| {g['severity']} {g['severity_name']} | {g['label']} | {g['count']} | {sc} | "
                 f"{g['why_it_matters']} | {g['lost_at'][0][0]} |")
    L += ["", "## Level 2 - where in the pipeline", "", "| Step | Failed checks |", "|---|---|"]
    L += [f"| {s} | {n} |" for s, n in r["by_step"]]
    L += ["", "## Each traced failure", ""]
    for it in r["items"]:
        if not it.get("trace"):
            continue
        L.append(f"### {it['tc']} {it['run_label'][-2:]} - {it['metric']} ({it['label']})")
        if it.get("fact"):
            L.append(f"Fact: {it['fact']}  ")
        L.append("Path: " + " → ".join(f"{s['step']} {ICON[s['status']]}" for s in it["trace"]) + "  ")
        L.append(f"**Lost at: {it['lost_at']}** · component: {it['component']}")
        L += [f"- {s['step']} {ICON[s['status']]}: {s['evidence']}" for s in it["trace"]]
        L.append("")
    path.write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
