"""
Context chapter, step C1: where did each missed fact get lost?

WHAT IT DOES (plain words)
    A report can miss a fact for very different reasons. This script takes
    every required fact that a saved report missed and follows it along the
    relay race, stopping at the FIRST hand-off where it went missing:

        documents -> search -> specialist (reads + summarises) -> writer -> report

    Buckets (first break wins):
      in report, marked missed   the words are in the report but the check said
                                 no: read by hand (a checker problem, or the
                                 fact was stated only half-way)
      reached the writer         the writer was given it and left it out
      not in the documents       nothing in the stored document pieces says it
      not searched               the router never ran a search that could find it
      searched, not found        that search ran, the fact wasn't in its top pieces
      found but cut              the piece was found, but the part holding the fact
                                 was cut off before the specialist saw it
                                 (pieces were cut at 300 characters before 1 Oct)
      summarised away            the specialist was given it; its summary dropped it
      not lost (checker wrong)   read by hand: the report does say it; the check was wrong

COST
    No AI calls. Pass/fail marks come from the saved runs: code checks are
    re-run, judge answers are read from the judge cache (a missing answer is
    reported as "not scored", never re-asked). Pinecone is used to read the
    stored document pieces and to repeat each specialist's search: the search
    wording is fixed (same template + question), so it re-creates the search.

HONEST LIMITS
    - Runs before 1 Oct only saved what the WRITER received. What each
      specialist received is re-created today by repeating the same search,
      not recorded on the day.
    - Facts are found by short word patterns (evals/context/context_facts.json).
      A reworded fact can slip past them, so "reached the writer" and
      "searched, not found" rows are read by hand before any number is used.

RUN
    venv\\Scripts\\python.exe evals\\context_attribution.py
    venv\\Scripts\\python.exe evals\\context_attribution.py --suites teaching

OUTPUT
    evals/context/attribution.md     read this one
    evals/context/attribution.json   every missed fact with its evidence
"""

import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))
os.environ["LANGSMITH_TRACING"] = "false"     # repeated searches are not app traffic

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from graph_value_test import check_code, check_rating, _norm  # noqa: E402  (same marking as the scorecards)

FACTS_FILE = ROOT / "evals" / "context" / "context_facts.json"
HAND_FILE = ROOT / "evals" / "context" / "hand_review.json"    # rows a person has read and decided
OUT_DIR = ROOT / "evals" / "context"

# Each specialist: the document type it searches and its ORIGINAL search wording
# (version 1, used by every run before 6 Oct 2026). Runs that record
# search_wording >= 2 are re-created with multi_agent.specialist_query instead.
AGENTS = {
    "Alarm Agent":       ("Shift Log",        "alarm history incidents for {eq} {inc}"),
    "Expert Fix Agent":  ("Expert Fix",       "fix for {eq} {inc}"),
    "Maintenance Agent": ("Work Instruction", "maintenance service repair history for {eq} {inc}"),
    "SOP Agent":         ("SOP",              "procedure response steps specification for {eq} alarm {inc}"),
    "NCR Agent":         ("NCR",              "non-conformance quality incident corrective action for {eq} {inc}"),
}
OLD_CUT = {"Expert Fix": 400}     # before 1 Oct: document pieces cut at 300, tips at 400
OLD_CUT_DEFAULT = 300
PIECE_SEP = "\n\n---\n\n"

BUCKETS = [
    ("in_report",     "in report, marked missed (read by hand)"),
    ("writer",        "reached the writer, left out"),
    ("not_in_docs",   "not in the documents"),
    ("not_searched",  "not searched (router)"),
    ("not_found",     "searched, not found (ranking)"),
    ("cut",           "found but cut"),
    ("summarised",    "found, summarised away"),
    ("evidence_cap",  "found, summarised away, and the evidence cap left the piece out (C2)"),
    ("checker_wrong", "not lost: the check marked a correct answer wrong (by hand)"),
]
LOST = [b for b, _ in BUCKETS if b not in ("in_report", "checker_wrong")]
BUCKET_LABEL = dict(BUCKETS)


# ── Small helpers ────────────────────────────────────────────────────────────

def has_fact(fact, text):
    """True when ALL patterns of ANY one group match the text."""
    t = _norm(text or "")
    return any(all(re.search(p, t, re.I | re.S) for p in group) for group in fact["look_for"])


def old_cut(search_text, doc_type):
    """What the specialist saw before 1 Oct: each piece's text cut to its first 300 characters."""
    if not search_text or search_text.startswith(("NO_DATA", "LOW_CONFIDENCE")):
        return search_text
    limit = OLD_CUT.get(doc_type, OLD_CUT_DEFAULT)
    pieces = []
    for piece in search_text.split(PIECE_SEP):
        header, _, body = piece.partition("\n")
        pieces.append(f"{header}\n{body[:limit]}")
    return PIECE_SEP.join(pieces)


def piece_names(search_text):
    return sorted(re.findall(r"^\[(?:Source: )?([^|\]]+)", search_text or "", re.M))


_ma = None


def ma():
    global _ma
    if _ma is None:
        with contextlib.redirect_stdout(io.StringIO()):
            import multi_agent
        _ma = multi_agent
    return _ma


_search_cache = {}


AGENT_KEY = {"Alarm Agent": "alarm", "Expert Fix Agent": "expert_fix",
             "Maintenance Agent": "maintenance", "SOP Agent": "sop", "NCR Agent": "ncr"}


def search_now(agent, equipment, incident, wording=1):
    """Repeat a specialist's search today (whole pieces, as the app does now),
    with the search wording the run itself used."""
    key = (agent, equipment, incident, wording)
    if key not in _search_cache:
        doc_type, template = AGENTS[agent]
        query = (ma().specialist_query(AGENT_KEY[agent], incident, equipment) if wording >= 2
                 else template.format(eq=equipment or "equipment", inc=incident[:100]))
        if doc_type == "Expert Fix":
            text, _ = ma().search_expert_fixes(query, equipment_filter=equipment)
        else:
            text = ma().search_plantmind(query, doc_type_filter=doc_type, equipment_filter=equipment)
        _search_cache[key] = text
    return _search_cache[key]


_corpus = {}


def corpus(equipment):
    """Every stored document piece for this machine (what search can ever reach)."""
    if equipment not in _corpus:
        m = ma()
        vec = m.pc.inference.embed(model="multilingual-e5-large", inputs=["equipment"],
                                   parameters={"input_type": "query"})[0].values
        res = m.pine_index.query(vector=vec, top_k=1000, include_metadata=True,
                                 filter={"equip_tag": {"$eq": equipment}})
        _corpus[equipment] = [{"doc_type": x.metadata.get("doc_type", ""),
                               "text": x.metadata.get("text", "")} for x in res.matches]
    return _corpus[equipment]


# ── Marks (exactly as the scorecards) ────────────────────────────────────────

def mark(check, case_id, run, cache):
    if check["kind"] == "code":
        return check_code(check, run["report"])
    if check["kind"] == "rating":
        return check_rating(check, run["report"])
    digest = hashlib.sha1(run["report"].encode("utf-8")).hexdigest()[:12]
    return cache.get(f"{case_id}|{run['arm']}|{check['id']}|{digest}")   # None = not scored


# ── The walk ─────────────────────────────────────────────────────────────────

def attribute(fact, run, equipment, saved_components):
    """Follow one missed fact along the chain; return (bucket, evidence)."""
    ev = {}
    incident = run["_incident"]
    writer_input = run.get("sources", "")
    if writer_input.startswith(incident):
        writer_input = writer_input[len(incident):]

    if has_fact(fact, run["report"]):
        return "in_report", ev

    if has_fact(fact, writer_input):
        if saved_components:
            ev["via"] = ([s["agent"] for s in run.get("specialists", []) if has_fact(fact, s["findings"])]
                         + (["graph"] if has_fact(fact, run.get("graph_text", "")) else [])
                         + (["evidence pieces"] if has_fact(fact, run.get("evidence", "")) else []))
        return "writer", ev

    homes = sorted({p["doc_type"] for p in corpus(equipment) if has_fact(fact, p["text"])})
    ev["in_docs"] = homes
    if not homes:
        return "not_in_docs", ev

    ran = [a for a in run.get("agents", []) if a in AGENTS]
    ev["searched"] = ran
    if not any(AGENTS[a][0] in homes for a in ran):
        return "not_searched", ev

    whole = {a: search_now(a, equipment, incident, run.get("search_wording", 1)) for a in ran}
    found_by = [a for a in ran if has_fact(fact, whole[a])]
    ev["found_by"] = found_by
    if not found_by:
        return "not_found", ev

    if saved_components:
        delivered = {s["agent"]: s["search"] for s in run.get("specialists", [])}
        ev["specialist_input"] = "saved on the day"
    else:
        delivered = {a: old_cut(whole[a], AGENTS[a][0]) for a in ran}
        ev["specialist_input"] = "re-created today, with the old 300-character cut"
    given_to = [a for a in found_by if has_fact(fact, delivered.get(a, ""))]
    ev["given_to"] = given_to
    if not given_to:
        return "cut", ev
    if run.get("writer_evidence"):
        # C2 switch on: the writer gets the pieces too, so a summary alone can't
        # lose it. It was lost because the size cap left that piece out.
        return "evidence_cap", ev
    return "summarised", ev


def search_recreation_check(runs, equipment_of):
    """Self-check: does today's repeated search return the same pieces as the saved one?"""
    same = total = 0
    for r in runs:
        for s in r.get("specialists", []):
            if s["agent"] not in AGENTS:
                continue
            total += 1
            now = search_now(s["agent"], equipment_of(r), r["_incident"], r.get("search_wording", 1))
            same += piece_names(now) == piece_names(s["search"])
    return same, total


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suites", default="", help="comma list, e.g. teaching,fl101 (default: all)")
    args = ap.parse_args()

    spec = json.loads(FACTS_FILE.read_text(encoding="utf-8"))
    suites = spec["suites"]
    hand = json.loads(HAND_FILE.read_text(encoding="utf-8")) if HAND_FILE.exists() else {}
    wanted = [s for s in args.suites.split(",") if s] or list(suites)
    for s in [s for s in wanted if not (ROOT / suites[s]["runs"]).exists()]:
        print(f"  {s}: no runs yet ({suites[s]['runs']}), skipped")
    wanted = [s for s in wanted if (ROOT / suites[s]["runs"]).exists()]

    rows, other_misses, unscored = [], [], []
    recreation = {}
    totals = defaultdict(Counter)    # suite -> fact checks scored / missed

    for name in wanted:
        s = suites[name]
        cases_doc = json.loads((ROOT / s["cases"]).read_text(encoding="utf-8"))
        cache_path = ROOT / s["judge_cache"]
        cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
        top_checks = cases_doc.get("checks", [])
        by_case = {c["id"]: c for c in cases_doc["cases"]}
        runs = [json.loads(line) for line in (ROOT / s["runs"]).read_text(encoding="utf-8").splitlines() if line.strip()]

        def equipment_of(r, _doc=cases_doc):
            return r.get("machine") or _doc.get("equipment")

        counter = Counter()
        kept = []
        for r in runs:
            case = by_case.get(r["case"])
            if not case or r.get("failed"):
                continue
            r["_incident"] = case["incident"]
            counter[(r["case"], r["arm"])] += 1
            run_no = counter[(r["case"], r["arm"])]
            kept.append(r)
            for ch in case.get("checks", top_checks):
                key = ch["id"] if not case.get("checks") else f"{r['case']}/{ch['id']}"
                fact = spec["facts"].get(key)
                if fact is None:
                    raise SystemExit(f"No entry for {key} in {FACTS_FILE.name}")
                ok = mark(ch, r["case"], r, cache)
                where = {"suite": name, "case": r["case"], "arm": r["arm"], "run": run_no,
                         "fact": key, "label": ch.get("label") or ch.get("q", "")}
                if ok is None:
                    unscored.append(where)
                    continue
                if fact["kind"] != "fact":
                    if not ok:
                        other_misses.append({**where, "kind": fact["kind"]})
                    continue
                totals[name]["scored"] += 1
                if ok:
                    continue
                totals[name]["missed"] += 1
                bucket, ev = attribute(fact, r, equipment_of(r), s["saved_components"])
                decided = hand.get(f"{name}|{r['case']}|{r['arm']}|{run_no}|{key}")
                if decided:
                    ev["by_hand"] = {"script_said": bucket, "note": decided["note"]}
                    bucket = decided["bucket"]
                rows.append({**where, "bucket": bucket, "evidence": ev})
                print(f"  {name} {r['case']} graph {r['arm']} run {run_no} {key}: {bucket}")

        if s["saved_components"]:
            recreation[name] = search_recreation_check(kept, equipment_of)

    write_outputs(spec, wanted, rows, other_misses, unscored, totals, recreation)


def write_outputs(spec, wanted, rows, other_misses, unscored, totals, recreation):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "attribution.json").write_text(json.dumps(
        {"rows": rows, "other_misses": other_misses, "unscored": unscored,
         "recreation_check": recreation}, indent=1, ensure_ascii=False), encoding="utf-8")

    L = ["# Where missed facts got lost (Context chapter, C1)", "",
         "Made by `evals/context_attribution.py` from saved runs. No AI calls.",
         "Each missed required fact is followed along documents → search → specialist → writer, "
         "and counted at the FIRST hand-off where it went missing.", "",
         "## Headline", ""]
    head = "| Where it got lost | " + " | ".join(spec["suites"][n]["label"] for n in wanted) + " | All |"
    L += [head, "|" + "---|" * (len(wanted) + 2)]
    for b, label in BUCKETS:
        cells = [sum(1 for r in rows if r["suite"] == n and r["bucket"] == b) for n in wanted]
        L.append(f"| {label} | " + " | ".join(map(str, cells)) + f" | **{sum(cells)}** |")
    miss = [totals[n]["missed"] for n in wanted]
    scored = [totals[n]["scored"] for n in wanted]
    lost = [sum(1 for r in rows if r["suite"] == n and r["bucket"] in LOST) for n in wanted]
    L.append("| **Marked missed / required facts scored** | " +
             " | ".join(f"{m}/{s}" for m, s in zip(miss, scored)) + f" | **{sum(miss)}/{sum(scored)}** |")
    L.append("| **Really lost (after hand reading)** | " + " | ".join(map(str, lost)) + f" | **{sum(lost)}** |")
    L.append("")

    L += ["## By graph arm", "", "| Arm | " + " | ".join(lbl for _, lbl in BUCKETS) + " |",
          "|" + "---|" * (len(BUCKETS) + 1)]
    for arm in [a for a in ("off", "facts", "on") if a != "facts" or any(r["arm"] == "facts" for r in rows)]:
        L.append(f"| graph {arm.upper()} | " + " | ".join(
            str(sum(1 for r in rows if r["arm"] == arm and r["bucket"] == b)) for b, _ in BUCKETS) + " |")
    L.append("")

    L += ["## Every missed fact", "",
          "| Suite | Case | Graph | Run | Fact | Lost at | Evidence |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        ev = r["evidence"]
        bits = []
        if "in_docs" in ev:
            bits.append("in: " + (", ".join(ev["in_docs"]) or "-"))
        if "searched" in ev:
            bits.append("searched: " + ", ".join(a.replace(" Agent", "") for a in ev["searched"]))
        if "found_by" in ev:
            bits.append("found by: " + (", ".join(a.replace(" Agent", "") for a in ev["found_by"]) or "-"))
        if "given_to" in ev:
            bits.append("given to: " + (", ".join(a.replace(" Agent", "") for a in ev["given_to"]) or "-"))
        if "via" in ev:
            bits.append("writer got it from: " + (", ".join(a.replace(" Agent", "") for a in ev["via"]) or "?"))
        if "by_hand" in ev:
            bits.append(f"**by hand** (script said: {BUCKET_LABEL[ev['by_hand']['script_said']]}): "
                        + ev["by_hand"]["note"])
        L.append(f"| {r['suite']} | {r['case']} | {r['arm']} | {r['run']} | {r['label']} | "
                 f"{BUCKET_LABEL[r['bucket']]} | {'; '.join(bits)} |")
    L.append("")

    L += ["## Not attributed (counted only)", "",
          f"- Said something it must not, or wrong rating: {len(other_misses)}"]
    for m in other_misses:
        L.append(f"  - {m['suite']} {m['case']} graph {m['arm']} run {m['run']}: {m['label']} ({m['kind']})")
    L.append(f"- Judge answer missing from the cache (not scored, not re-asked): {len(unscored)}")
    L.append("")

    L += ["## Checks on this method", ""]
    for n, (same, total) in recreation.items():
        L.append(f"- {spec['suites'][n]['label']}: repeating the searches today returned the same pieces "
                 f"as saved on the day in **{same}/{total}** specialist searches.")
    L += ["- Runs before 1 Oct: what each specialist received is re-created today (same search "
          "wording, old 300-character cut), not recorded on the day.",
          "- Facts are found by word patterns (evals/context/context_facts.json). Rows in "
          "'reached the writer', 'searched, not found' and 'in report, marked missed' are read by hand "
          "before any number is used.", ""]
    (OUT_DIR / "attribution.md").write_text("\n".join(L), encoding="utf-8")
    print(f"\nWrote {OUT_DIR / 'attribution.md'}")


if __name__ == "__main__":
    main()
