"""
Knowledge graph chapter: which facts appear only with the graph?

WHAT IT DOES (plain words)
    For each required fact: how often the report has it with the graph OFF and
    with the graph ON, and, for the graph-ON reports, where the writer could
    have got it from:
        graph only        only the graph's text carried it
        specialists only  only the specialists' summaries carried it
        both              both did
        neither           the writer got it from neither (it came from the
                          question itself or the model's own knowledge)
    A fact that is (nearly) always missing OFF, present ON, and came from the
    graph only, is a fact the app has ONLY because of the graph.

COST
    No AI calls. Marks are the scorecards' own (code checks re-run, judge
    answers read from the cache; a missing answer = "not scored").
    Needs runs saved with their parts (graph text + specialists' summaries):
    the teaching set and any run made after 1 Oct.

RUN
    venv\\Scripts\\python.exe evals\\graph_facts_table.py
    venv\\Scripts\\python.exe evals\\graph_facts_table.py --suites teaching,teaching_c2_before --name teaching

    --suites  runs to pool (names from evals/context/context_facts.json). Runs
              made with the C2 switch on (writer gets the pieces) are left
              out: they would mix two changes.

OUTPUT
    evals/graph_chapter/graph_facts_<name>.md
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evals"))

from context_attribution import FACTS_FILE, has_fact, mark  # noqa: E402  (same patterns + marks as C1)

OUT_DIR = ROOT / "evals" / "graph_chapter"
SOURCES = ["graph only", "specialists only", "both", "neither"]


def source_of(fact, run):
    in_graph = has_fact(fact, run.get("graph_text", ""))
    in_spec = any(has_fact(fact, s.get("findings", "")) for s in run.get("specialists", []))
    return {(True, False): "graph only", (False, True): "specialists only",
            (True, True): "both", (False, False): "neither"}[(in_graph, in_spec)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suites", default="teaching,teaching_c2_before")
    ap.add_argument("--name", default="teaching")
    args = ap.parse_args()

    spec = json.loads(FACTS_FILE.read_text(encoding="utf-8"))
    passed = defaultdict(Counter)        # fact -> {"off": n, "on": n}
    scored = defaultdict(Counter)
    where = defaultdict(Counter)         # fact -> where the ON writer could get it
    labels, kinds, used = {}, {}, []

    for name in [s for s in args.suites.split(",") if s]:
        s = spec["suites"][name]
        if not s.get("saved_components"):
            raise SystemExit(f"{name}: runs don't have their parts saved; can't tell where facts came from")
        cases_doc = json.loads((ROOT / s["cases"]).read_text(encoding="utf-8"))
        cache_path = ROOT / s["judge_cache"]
        cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
        by_case = {c["id"]: c for c in cases_doc["cases"]}
        n_runs = Counter()
        for line in (ROOT / s["runs"]).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            case = by_case.get(r["case"])
            if not case or r.get("failed") or r.get("writer_evidence"):
                continue
            n_runs[r["arm"]] += 1
            for ch in case.get("checks") or cases_doc.get("checks", []):
                key = ch["id"] if not case.get("checks") else f"{r['case']}/{ch['id']}"
                fact = spec["facts"][key]
                ok = mark(ch, r["case"], r, cache)
                if ok is None:
                    continue
                labels[key], kinds[key] = ch.get("label") or ch.get("q", ""), fact["kind"]
                scored[key][r["arm"]] += 1
                passed[key][r["arm"]] += bool(ok)
                if r["arm"] in ("on", "facts") and fact["kind"] == "fact":
                    where[(key, r["arm"])][source_of(fact, r)] += 1
        used.append(f"{name} ({s['runs']}): graph OFF {n_runs['off']} reports, graph ON {n_runs['on']}"
                    + (f", graph facts only {n_runs['facts']}" if n_runs["facts"] else ""))

    def cell(k, arm):
        return f"{passed[k][arm]}/{scored[k][arm]}" if scored[k][arm] else "—"

    def verdict(k):
        off = passed[k]["off"] / scored[k]["off"] if scored[k]["off"] else None
        on = passed[k]["on"] / scored[k]["on"] if scored[k]["on"] else None
        if kinds[k] != "fact" or off is None or on is None:
            return ""
        main_source = where[(k, "on")].most_common(1)[0][0] if where[(k, "on")] else ""
        if on - off >= 0.5 and main_source == "graph only":
            return "**only with the graph**"
        if on - off >= 0.5:
            return "much more often with the graph"
        if on - off > 0:
            return "a bit more often with the graph"
        return "no difference"

    has_facts_arm = any(scored[k]["facts"] for k in labels)

    def src(k, arm):
        if kinds[k] != "fact":
            return f"({kinds[k]}: a thing the report must NOT say)"
        return ", ".join(f"{s} {where[(k, arm)][s]}" for s in SOURCES if where[(k, arm)][s]) or "—"

    L = [f"# Facts that appear only with the graph ({args.name})", "",
         "Made by `evals/graph_facts_table.py` from saved runs. No AI calls.",
         "Runs: " + "; ".join(used) + ".", ""]
    if has_facts_arm:
        L += ["'Facts only' = separation run: the graph's facts reach the writer, but the searches are "
              "picked as with no graph. OFF → facts only = value of the facts; facts only → ON = extra "
              "value of the searches the graph forces.", "",
              "| Fact | Graph OFF | Facts only | Graph ON | Where the facts-only writer got it "
              "| Where the graph-ON writer got it | Verdict |", "|---|---|---|---|---|---|---|"]
        for k in labels:
            L.append(f"| {labels[k]} | {cell(k, 'off')} | {cell(k, 'facts')} | {cell(k, 'on')} | "
                     f"{src(k, 'facts')} | {src(k, 'on')} | {verdict(k)} |")
    else:
        L += ["| Fact | Graph OFF | Graph ON | Where the graph-ON writer could get it | Verdict |",
              "|---|---|---|---|---|"]
        for k in labels:
            L.append(f"| {labels[k]} | {cell(k, 'off')} | {cell(k, 'on')} | {src(k, 'on')} | {verdict(k)} |")
    L += ["", "How to read it:",
          "- 'graph only' = the fact was in the graph's text and in none of the specialists' summaries.",
          "- Facts are spotted by the word patterns in evals/context/context_facts.json (same as C1); "
          "judge-marked facts can be worded differently, so 'neither' rows are worth reading.",
          ""]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"graph_facts_{args.name}.md"
    out.write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
