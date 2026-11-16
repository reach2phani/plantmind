"""
grounding_card.py - the GROUNDING report card for the held-out questions.

The combiner: it does no measuring of its own. It reads
  - the five automated result files (one per metric), and checks each was made
    with the rubric that is locked now (fingerprint in the result = fingerprint
    in the lock file); it stops if not
  - heldout-v1/grounding_corrections.json: the person-checked numbers, each
    pointing to its review
  - heldout-v1/reports/grounding/findings.md: the conclusions, written by a person
and writes heldout-v1/reports/grounding/card.md.

Numbers come from code; conclusions come from a person. This script never
writes a conclusion.

Read-only. No tokens, no network.

Usage:
  venv\\Scripts\\python.exe evals\\investigations\\grounding_card.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent / "heldout-v1"
RES = HERE / "results"
OUT_DIR = HERE / "reports" / "grounding"

CASES = ["H1", "H2", "H3", "H4", "H5"]
SCENARIO = {
    "H1": "Scale test failed before start-up",
    "H2": "Jams after a changeover",
    "H3": "Underfill after new seals",
    "H4": "Broken glass on the floor",
    "H5": "Reject rate increasing",
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def lock_fp(name, key="rubric_fingerprint"):
    return load(HERE / f"{name}.lock.json")[key]


def check(label, got, want, problems):
    ok = got == want
    if not ok:
        problems.append(f"{label}: result made with {got}, lock says {want}")
    return ok


def pct(a, b):
    return f"{a / b:.0%}" if b else "n/a"


def frac(a, b):
    return f"{a} / {b}"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    problems, integrity = [], []
    corr = load(HERE / "grounding_corrections.json")

    # --- automated results, each checked against its lock ---
    rr = load(RES / "retrieval_recall_after.json")
    integrity.append(("Retrieval recall", "retrieval_labels.json", rr["rules_fingerprint"], rr["locked"],
                      check("retrieval recall", rr["rules_fingerprint"],
                            lock_fp("retrieval_labels", "rules_fingerprint"), problems)))
    pr = load(RES / "precision_after.json")
    for name in ("retrieval_precision", "context_precision"):
        r = pr["rubrics"][name]
        integrity.append((name.replace("_", " ").capitalize(), f"{name}.json", r["fingerprint"], r["locked"],
                          check(name, r["fingerprint"], lock_fp(name), problems)))
    hr = load(RES / "handover_recall_after.json")
    integrity.append(("Handover recall", "handover_recall.json", hr["rubric_fingerprint"], hr["locked"],
                      check("handover recall", hr["rubric_fingerprint"], lock_fp("handover_recall"), problems)))
    fa = {}
    for c in CASES:
        p = RES / f"faithfulness_v2_{c}_after.json"
        if p.is_file():
            d = load(p)
            check(f"faithfulness {c}", d["rubric_fingerprint"], lock_fp("faithfulness_v2"), problems)
            fa[c] = d
    any_fa = next(iter(fa.values()))
    integrity.append(("Faithfulness", "faithfulness_v2.json", any_fa["rubric_fingerprint"], any_fa["locked"],
                      not any(p.startswith("faithfulness") for p in problems)))
    if problems:
        sys.exit("A result was not made with the locked rubric:\n  " + "\n  ".join(problems))

    # --- per case: automated and corrected ---
    rows, T = {}, {k: 0 for k in ("needed", "found_a", "found_c", "useful_a", "useful_c", "returned",
                                  "kept_a", "kept_c", "reached_c", "hr_den", "stm", "sup")}
    cp_a, cp_c = [], []
    for c in CASES:
        r = rr["cases"][c]
        rc = corr["retrieval_recall"].get(c, {})
        p = pr["cases"][c]
        pc = corr["retrieval_precision"].get(c, {})
        cpc = corr["context_precision"].get(c, {})
        h = hr["cases"][c]
        hc = corr["handover_recall"]["cases"][c]
        row = {
            "rr_a": (r["found"], r["counted"]), "rr_c": (rc.get("found", r["found"]), rc.get("counted", r["counted"])),
            "rp_a": (p["retrieval_precision"]["useful"], p["retrieval_precision"]["returned"]),
            "rp_c": (pc.get("useful", p["retrieval_precision"]["useful"]),
                     pc.get("returned", p["retrieval_precision"]["returned"])),
            "cp_a": p["context_precision"]["score"], "cp_c": cpc.get("score", p["context_precision"]["score"]),
            "hr_a": (h["kept"], h["found_by_search"]), "hr_c": (hc["kept"], h["found_by_search"]),
            "reach_c": (hc["reached"], h["found_by_search"]),
        }
        if c in fa:
            st = fa[c]["cases"][c]["statements"]
            row["fa"] = (sum(bool(s["verdict"]) for s in st), len(st))
            row["fa_range"] = corr["faithfulness"]["cases"].get(c)
        rows[c] = row
        T["needed"] += r["counted"]
        T["found_a"] += r["found"]
        T["found_c"] += row["rr_c"][0]
        T["useful_a"] += row["rp_a"][0]
        T["useful_c"] += row["rp_c"][0]
        T["returned"] += row["rp_a"][1]
        T["kept_a"] += h["kept"]
        T["kept_c"] += hc["kept"]
        T["reached_c"] += hc["reached"]
        T["hr_den"] += h["found_by_search"]
        if "fa" in row:
            T["sup"] += row["fa"][0]
            T["stm"] += row["fa"][1]
        cp_a.append(row["cp_a"])
        cp_c.append(row["cp_c"])
    cpa, cpc_ = sum(cp_a) / len(cp_a), sum(cp_c) / len(cp_c)
    fa_cases = [c for c in CASES if c in fa]
    no_fa = [c for c in CASES if c not in fa]

    # --- write the card ---
    L = []
    L.append("# PlantMind evaluation: grounding report card\n")
    L.append("> **Does PlantMind's answer come from its documents?** 5 operator scenarios · FL-101 bottle filler · "
             "numbers after human review (automated checker in the tables)\n>")
    L.append(f"> | Retrieval recall | Retrieval precision | Context precision | Handover recall | Faithfulness |")
    L.append("> |---|---|---|---|---|")
    L.append(f"> | **{pct(T['found_c'], T['needed'])}** | **{pct(T['useful_c'], T['returned'])}** | "
             f"**{cpc_:.2f}** | **{pct(T['kept_c'], T['hr_den'])}** | **{pct(T['sup'], T['stm'])}** |")
    L.append(f"> | found the needed facts | useful pieces | useful pieces at the top | facts passed to the writer "
             f"| answer statements backed by evidence |\n")

    L.append("## Where the needed facts went\n")
    L.append("```")
    L.append(f"{T['needed']} facts the answers needed")
    L.append(f" └─ {T['found_c']} found by search                 ({pct(T['found_c'], T['needed'])})   "
             f"lost: {T['needed'] - T['found_c']} never found")
    L.append(f"     └─ {T['kept_c']} kept in the helper summaries   ({pct(T['kept_c'], T['needed'])} of needed)   "
             f"lost: {T['found_c'] - T['kept_c']} dropped by the helpers")
    L.append(f"         └─ {T['reached_c']} reached the writer, incl. graph  ({pct(T['reached_c'], T['needed'])} of needed)   "
             f"rescued by the graph: {T['reached_c'] - T['kept_c']}")
    L.append("```\n")
    L.append(f"Then, in the answer: **{pct(T['sup'], T['stm'])}** of statements were backed by the writer's "
             f"evidence ({T['sup']} of {T['stm']}, {len(fa_cases)} scenarios). "
             "Whether every fact that reached the writer is in the answer (answer completeness) is not measured yet.\n")

    L.append("## The five metrics\n")
    L.append("| Step | Metric | Question | Automated | **After review** | Evaluator |")
    L.append("|---|---|---|---|---|---|")
    L.append(f"| Search | Retrieval recall | Did search find the needed facts? | {pct(T['found_a'], T['needed'])} | "
             f"**{pct(T['found_c'], T['needed'])}** ({T['found_c']}/{T['needed']}) | code + person |")
    L.append(f"| Search | Retrieval precision | How many returned pieces were useful? | "
             f"{pct(T['useful_a'], T['returned'])} | **{pct(T['useful_c'], T['returned'])}** "
             f"({T['useful_c']}/{T['returned']}) | code + person |")
    L.append(f"| Search | Context precision | Were the useful pieces at the top? | {cpa:.2f} | **{cpc_:.2f}** | "
             f"code + person |")
    L.append(f"| Helpers | Handover recall | Did the helpers pass on what search found? | "
             f"{pct(T['kept_a'], T['hr_den'])} | **{pct(T['kept_c'], T['hr_den'])}** ({T['kept_c']}/{T['hr_den']}) "
             f"| code + person |")
    L.append(f"| Writer | Faithfulness | Is every answer statement backed by evidence? | "
             f"{pct(T['sup'], T['stm'])} | ranges per scenario below | AI judge (RAGAS + qwen), checked by a person |")
    L.append("")

    L.append("## By scenario (after review)\n")
    L.append("| Scenario | Recall | Precision | Context precision | Handover | Reached writer | Faithfulness |")
    L.append("|---|---|---|---|---|---|---|")
    for c in CASES:
        r = rows[c]
        if "fa" in r:
            f = f"{r['fa'][0] / r['fa'][1]:.2f}"
            if r.get("fa_range"):
                f += f" ({r['fa_range']['low']:.2f}–{r['fa_range']['high']:.2f})"
        else:
            f = "not run"
        L.append(f"| {c} {SCENARIO[c]} | {pct(*r['rr_c'])} | {pct(*r['rp_c'])} | {r['cp_c']:.2f} | "
                 f"{pct(*r['hr_c'])} | {pct(*r['reach_c'])} | {f} |")
    L.append("")
    L.append("*Faithfulness: judge score, with the range after a person checked its verdicts where one was done. "
             + (f"Not run on {', '.join(no_fa)}: too large for one judge call on the free tier. " if no_fa else "")
             + "Handover recall counts the facts the automated checker found by search (39); with the one "
             "retrieval correction (H5) it would be 27/40 = 68%.*\n")

    findings = OUT_DIR / "findings.md"
    if findings.is_file():
        L.append(findings.read_text(encoding="utf-8").strip() + "\n")
    else:
        L.append("## Findings\n\n*Not written yet (reports/grounding/findings.md).*\n")

    L.append("## Evidence and integrity\n")
    L.append("Every result below was made with the rubric that is locked now (checked by this script).\n")
    L.append("| Metric | Rubric | Fingerprint | Locked | Matches lock |")
    L.append("|---|---|---|---|---|")
    for name, rub, fp, locked, ok in integrity:
        L.append(f"| {name} | `{rub}` | `{fp}` | {locked} | {'✓' if ok else '✗'} |")
    L.append("")
    L.append("Human reviews: [retrieval recall](../retrieval-recall/summary.md) · "
             "[retrieval precision](../retrieval-precision/summary.md) · "
             "[handover recall](../handover-recall/manual-review.md) · "
             "[faithfulness H2](../faithfulness/H2-human-review.md) · "
             "[faithfulness H4–H5](../faithfulness/H4-H5-human-review.md) · "
             "corrections as data: `heldout-v1/grounding_corrections.json`\n")
    L.append(f"*Generated by `evals/investigations/grounding_card.py` on "
             f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}. Numbers from code; findings written by a person.*")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUT_DIR / "card.md"
    dest.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"Retrieval recall {pct(T['found_c'], T['needed'])} · precision {pct(T['useful_c'], T['returned'])} · "
          f"context precision {cpc_:.2f} · handover {pct(T['kept_c'], T['hr_den'])} · "
          f"faithfulness {pct(T['sup'], T['stm'])}")
    print(f"Saved {dest.relative_to(HERE.parent.parent.parent)}")


if __name__ == "__main__":
    main()
