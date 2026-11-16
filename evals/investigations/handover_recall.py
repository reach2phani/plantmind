"""
handover_recall.py - did the helpers keep the facts that search found?

PlantMind's writer never sees the raw search pieces: it sees only each helper's
summary (plus the knowledge-graph text). This checks the summarise step:

    handover recall = facts kept in the helper summaries / facts found by search

The RUBRIC lives in heldout-v1/handover_recall.json; this script only applies it
and stops if the rubric asks for a rule it doesn't know, or changed after locking.
The facts come from heldout-v1/retrieval_labels.json (checked against their own
lock), and "found by search" uses exactly the retrieval-recall matching code.

Also reported (information only, not the score):
  reached_writer       found facts that are in the summaries OR the graph text
  kept_without_search  facts in the summaries that search did NOT find
  per_helper           which facts each helper's summary kept

Facts counted DROPPED go to a person for the manual review (see the rubric).

Read-only. No tokens, no network: uses only the saved snapshot (runs + traces).

Usage:
  venv\\Scripts\\python.exe evals\\investigations\\handover_recall.py
  venv\\Scripts\\python.exe evals\\investigations\\handover_recall.py --side before
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retrieval_recall import fingerprint, make_matcher, HERE, SNAP  # noqa: E402  same matching as recall

NAME = "handover_recall"
# The only rubric content this script knows how to apply.
KNOWN = {
    "metric": NAME,
    "look_in": "helper_summaries",
    "facts_from": "retrieval_labels.json",
    "rules": {
        "kept_means": ("the fact matches (same all_of wordings as retrieval recall) inside at least one helper "
                       "summary; any helper counts, not only the one whose search found it"),
        "only_count_facts_found_by_search": True,
        "score": "facts kept in the helper summaries / facts found by search",
        "also_report": {"reached_writer", "kept_without_search", "per_helper"},
    },
}


def load_rubric():
    rub = json.loads((HERE / f"{NAME}.json").read_text(encoding="utf-8"))
    for key in ("metric", "look_in", "facts_from"):
        if rub.get(key) != KNOWN[key]:
            sys.exit(f"{NAME}.json: {key} = {rub.get(key)!r}, this script only knows {KNOWN[key]!r}")
    rules = rub.get("rules", {})
    expected = {"ignore_case", "ignore_line_breaks", "kept_means", "only_count_facts_found_by_search",
                "score", "also_report"}
    if set(rules) != expected:
        sys.exit(f"{NAME}.json: unexpected set of rules {sorted(rules)}")
    if rules["ignore_case"] not in (True, False) or rules["ignore_line_breaks"] not in (True, False):
        sys.exit(f"{NAME}.json: ignore_case / ignore_line_breaks must be true or false")
    for key in ("kept_means", "only_count_facts_found_by_search", "score"):
        if rules[key] != KNOWN["rules"][key]:
            sys.exit(f"{NAME}.json: rule {key!r} changed: this script doesn't know how to apply it")
    if set(rules["also_report"]) != KNOWN["rules"]["also_report"]:
        sys.exit(f"{NAME}.json: unknown also_report item(s)")
    lock_path = HERE / f"{NAME}.lock.json"
    if not lock_path.is_file():
        sys.exit(f"No {NAME}.lock.json: lock the rubric before scoring")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if fingerprint(rub) != lock["rubric_fingerprint"]:
        sys.exit(f"{NAME}.json changed after it was locked: make a new version instead")
    return rub, lock


def check_fact_locks(labels):
    flock = json.loads((HERE / "retrieval_labels.lock.json").read_text(encoding="utf-8"))
    if fingerprint(labels["rules"]) != flock["rules_fingerprint"]:
        sys.exit("retrieval_labels.json rules changed after locking")
    for case, lab in labels["cases"].items():
        locked = flock["cases"].get(case)
        if not locked or fingerprint(lab) != locked["fingerprint"]:
            sys.exit(f"{case}'s facts are not locked or changed after locking")


def writer_input(case, side):
    """Helper summaries and graph text exactly as the writer received them (saved trace)."""
    trace = json.loads((SNAP / "traces" / f"{case}-{side}.json").read_text(encoding="utf-8"))
    step = next((s for s in trace["steps"] if s["name"] == "orchestrator"), None)
    if not step:
        sys.exit(f"{case}-{side}: no orchestrator step in the trace")
    inp = step["input"]
    summaries = {r["agent"]: r.get("findings") or "" for r in inp.get("specialist_results") or []}
    g = inp.get("graph_context") or {}
    graph = ""
    if g.get("has_data"):
        parts = [g.get("chain_text") or "", "\n".join(g.get("warnings") or []),
                 "\n".join(map(str, g.get("exact_values") or [])), str(g.get("downtime") or "")]
        graph = "\n".join(p for p in parts if p)
    return summaries, graph


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--side", default="after", choices=["before", "after"])
    args = ap.parse_args()

    labels = json.loads((HERE / "retrieval_labels.json").read_text(encoding="utf-8"))
    check_fact_locks(labels)
    rub, lock = load_rubric()
    if rub["rules"]["ignore_case"] != labels["rules"]["ignore_case"] or \
       rub["rules"]["ignore_line_breaks"] != labels["rules"]["ignore_line_breaks"]:
        sys.exit("Matching rules must be the same as retrieval recall's")
    matches = make_matcher(rub["rules"])
    index = json.loads((SNAP / "chunks_fl101.json").read_text(encoding="utf-8"))["chunks"]

    out = {"run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "side": args.side,
           "metric": NAME, "rubric_version": rub["version"], "rubric_fingerprint": fingerprint(rub),
           "locked": lock["locked"], "cases": {}}
    tot = {"found": 0, "kept": 0, "reached": 0}

    for case, lab in labels["cases"].items():
        run = json.loads((SNAP / "runs" / f"{case}-{args.side}.json").read_text(encoding="utf-8"))
        pieces = (run.get("details") or {}).get("pieces") or []
        summaries, graph = writer_input(case, args.side)

        rows = []
        for f in lab["facts"]:
            in_index = any(matches(f, c["text"]) for c in index)
            found = any(matches(f, p.get("text")) for p in pieces)
            kept_by = [a for a, text in summaries.items() if matches(f, text)]
            in_graph = bool(graph) and matches(f, graph)
            if not in_index:
                result = "NOT IN DOCUMENTS"
            elif not found:
                result = "NOT FOUND BY SEARCH" + (" (but in a summary)" if kept_by else "")
            else:
                result = "KEPT" if kept_by else "DROPPED"
            rows.append({"id": f["id"], "fact": f["fact"], "found_by_search": found, "kept_by": kept_by,
                         "in_graph": in_graph, "result": result})

        counted = [r for r in rows if r["found_by_search"] and r["result"] != "NOT IN DOCUMENTS"]
        kept = sum(bool(r["kept_by"]) for r in counted)
        reached = sum(bool(r["kept_by"]) or r["in_graph"] for r in counted)
        without = [r["id"] for r in rows if not r["found_by_search"] and r["kept_by"]]
        per_helper = {a: [r["id"] for r in rows if a in r["kept_by"]] for a in summaries}
        n = len(counted)
        out["cases"][case] = {
            "case_fingerprint": fingerprint(lab), "blind_facts": lab["blind"],
            "found_by_search": n, "kept": kept, "handover_recall": kept / n if n else None,
            "reached_writer": {"count": reached, "score": reached / n if n else None},
            "kept_without_search": without, "per_helper": per_helper,
            "dropped_for_manual_review": [r["id"] for r in counted if not r["kept_by"]],
            "facts": rows}
        tot["found"] += n
        tot["kept"] += kept
        tot["reached"] += reached

        print(f"\n{case} ({args.side})")
        for r in rows:
            where = ", ".join(r["kept_by"]) or "-"
            g = "  +graph" if r["in_graph"] else ""
            print(f"  {r['id']:<4} {r['result']:<20} {r['fact'][:44]:<44}  summaries: {where}{g}")
        if n:
            print(f"  handover recall = {kept}/{n} = {kept / n:.0%}    reached writer = {reached}/{n} = {reached / n:.0%}")
        if without:
            print(f"  kept without search: {', '.join(without)}")

    out["total"] = {"found_by_search": tot["found"], "kept": tot["kept"],
                    "handover_recall": tot["kept"] / tot["found"] if tot["found"] else None,
                    "reached_writer": tot["reached"] / tot["found"] if tot["found"] else None,
                    "note": "automated checker only; corrected numbers come from the manual review"}
    dest = HERE / "results" / f"{NAME}_{args.side}.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    if tot["found"]:
        print(f"\nALL: handover recall = {tot['kept']}/{tot['found']} = {tot['kept'] / tot['found']:.0%}"
              f"    reached writer = {tot['reached']}/{tot['found']} = {tot['reached'] / tot['found']:.0%}"
              f"    (automated checker; DROPPED facts go to manual review)")
    print(f"Saved {dest.relative_to(HERE.parent.parent.parent)}")


if __name__ == "__main__":
    main()
