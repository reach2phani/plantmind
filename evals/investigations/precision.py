"""
precision.py - two precision metrics for search, from one shared "useful piece" check.

  retrieval precision  (heldout-v1/retrieval_precision.json)
      Did search bring back junk?   useful pieces / pieces returned
  context precision    (heldout-v1/context_precision.json)
      Did search put the useful pieces at the TOP?   rank-aware, per helper

A piece is "useful" when it contains at least one of that question's locked
facts (heldout-v1/retrieval_labels.json). The matching code is imported from
retrieval_recall.py, so "found" means exactly the same in all three metrics.

Each rubric has its own lock (<name>.lock.json); the facts are checked against
retrieval_labels.lock.json. The script stops if anything changed after locking,
or if a rubric asks for a rule it doesn't know.

Read-only. No tokens, no network: uses only the saved snapshot.

Usage:
  venv\\Scripts\\python.exe evals\\investigations\\precision.py
  venv\\Scripts\\python.exe evals\\investigations\\precision.py --side before
"""
import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retrieval_recall import fingerprint, make_matcher, HERE, SNAP  # noqa: E402  same matching as recall

USEFUL = "the piece contains at least one fact from that question's locked list"
KNOWN = {
    "retrieval_precision": {
        "score": "useful pieces / pieces returned",
        "also_report": {"per helper"},
    },
    "context_precision": {
        "score": ("per helper: at each rank that holds a useful piece, take (useful pieces so far / "
                  "pieces so far); average those values. Question score: the average over the helpers "
                  "that got at least one useful piece"),
        "also_report": {"per helper", "helpers with no useful piece"},
    },
}


def load_rubric(name):
    rub = json.loads((HERE / f"{name}.json").read_text(encoding="utf-8"))
    known = KNOWN[name]
    if rub.get("metric") != name:
        sys.exit(f"{name}.json: metric = {rub.get('metric')!r}, expected {name!r}")
    if rub.get("look_in") != "search_results":
        sys.exit(f"{name}.json: look_in = {rub.get('look_in')!r}: this script can only look in search_results")
    if rub.get("facts_from") != "retrieval_labels.json":
        sys.exit(f"{name}.json: facts_from must be retrieval_labels.json")
    rules = rub.get("rules", {})
    if set(rules) != {"ignore_case", "ignore_line_breaks", "useful_means", "score", "also_report"}:
        sys.exit(f"{name}.json: unexpected set of rules {sorted(rules)}")
    if rules["ignore_case"] not in (True, False) or rules["ignore_line_breaks"] not in (True, False):
        sys.exit(f"{name}.json: ignore_case / ignore_line_breaks must be true or false")
    if rules["useful_means"] != USEFUL:
        sys.exit(f"{name}.json: useful_means = {rules['useful_means']!r}: this script doesn't know how to apply it")
    if rules["score"] != known["score"]:
        sys.exit(f"{name}.json: score rule changed: this script doesn't know how to apply it")
    if not set(rules["also_report"]) <= known["also_report"]:
        sys.exit(f"{name}.json: unknown also_report item(s)")
    lock_path = HERE / f"{name}.lock.json"
    if not lock_path.is_file():
        sys.exit(f"No {name}.lock.json: lock the rubric before scoring")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if fingerprint(rub) != lock["rubric_fingerprint"]:
        sys.exit(f"{name}.json changed after it was locked: make a new version instead")
    return rub, lock


def check_fact_locks(labels):
    flock = json.loads((HERE / "retrieval_labels.lock.json").read_text(encoding="utf-8"))
    for case, lab in labels["cases"].items():
        locked = flock["cases"].get(case)
        if not locked or fingerprint(lab) != locked["fingerprint"]:
            sys.exit(f"{case}'s facts are not locked or changed after locking")


def ranked_precision(flags):
    """Context precision of one ranked list (RAGAS style): the mean of
    precision@k over the ranks k that hold a useful piece. None if nothing useful."""
    hits, vals = 0, []
    for k, useful in enumerate(flags, start=1):
        if useful:
            hits += 1
            vals.append(hits / k)
    return sum(vals) / len(vals) if vals else None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--side", default="after", choices=["before", "after"])
    args = ap.parse_args()

    labels = json.loads((HERE / "retrieval_labels.json").read_text(encoding="utf-8"))
    check_fact_locks(labels)
    rp_rub, rp_lock = load_rubric("retrieval_precision")
    cp_rub, cp_lock = load_rubric("context_precision")
    if rp_rub["rules"]["ignore_case"] != cp_rub["rules"]["ignore_case"] or \
       rp_rub["rules"]["ignore_line_breaks"] != cp_rub["rules"]["ignore_line_breaks"]:
        sys.exit("The two rubrics must use the same matching rules")
    matches = make_matcher(rp_rub["rules"])

    out = {"run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "side": args.side,
           "rubrics": {n: {"version": r["version"], "fingerprint": fingerprint(r), "locked": l["locked"]}
                       for n, r, l in (("retrieval_precision", rp_rub, rp_lock),
                                       ("context_precision", cp_rub, cp_lock))},
           "cases": {}}
    tot_useful = tot_returned = 0
    cp_scores = []

    for case, lab in labels["cases"].items():
        run = json.loads((SNAP / "runs" / f"{case}-{args.side}.json").read_text(encoding="utf-8"))
        pieces = (run.get("details") or {}).get("pieces") or []
        lists = defaultdict(list)
        for p in pieces:
            facts = [f["id"] for f in lab["facts"] if matches(f, p.get("text"))]
            lists[p.get("step") or "?"].append({
                "rank": p.get("rank"), "document": p.get("document"),
                "chunk": (p.get("chunk_id") or "").rsplit("_", 1)[-1],
                "useful": bool(facts), "facts": facts})
        helpers = {}
        for step, items in lists.items():
            items.sort(key=lambda x: x["rank"] or 0)
            flags = [i["useful"] for i in items]
            helpers[step] = {"useful": sum(flags), "returned": len(flags),
                             "retrieval_precision": sum(flags) / len(flags),
                             "context_precision": ranked_precision(flags), "pieces": items}
        useful = sum(h["useful"] for h in helpers.values())
        returned = sum(h["returned"] for h in helpers.values())
        cps = [h["context_precision"] for h in helpers.values() if h["context_precision"] is not None]
        no_useful = [s for s, h in helpers.items() if h["context_precision"] is None]
        cp = sum(cps) / len(cps) if cps else None
        tot_useful += useful
        tot_returned += returned
        if cp is not None:
            cp_scores.append(cp)
        out["cases"][case] = {"blind_facts": lab["blind"],
                              "retrieval_precision": {"useful": useful, "returned": returned,
                                                      "score": useful / returned if returned else None},
                              "context_precision": {"score": cp, "helpers_scored": len(cps),
                                                    "helpers_with_no_useful_piece": no_useful},
                              "helpers": helpers}

        print(f"\n{case} ({args.side})   retrieval precision = {useful}/{returned} = {useful / returned:.0%}"
              f"   context precision = {cp:.2f}" if cp is not None else
              f"\n{case} ({args.side})   retrieval precision = {useful}/{returned}   context precision = n/a")
        for step, h in helpers.items():
            ranks = " ".join(("Y" if i["useful"] else "-") for i in h["pieces"])
            cpv = f"{h['context_precision']:.2f}" if h["context_precision"] is not None else "no useful piece"
            print(f"  {step:<12} ranks [{ranks}]   {h['useful']}/{h['returned']} useful   context precision {cpv}")
            for i in h["pieces"]:
                if i["useful"]:
                    print(f"      rank {i['rank']}: {i['document']} piece {i['chunk']}  {','.join(i['facts'])}")

    total_cp = sum(cp_scores) / len(cp_scores) if cp_scores else None
    out["total"] = {"retrieval_precision": {"useful": tot_useful, "returned": tot_returned,
                                            "score": tot_useful / tot_returned if tot_returned else None},
                    "context_precision": {"score": total_cp, "note": "average of the question scores"}}
    dest = HERE / "results" / f"precision_{args.side}.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nALL: retrieval precision = {tot_useful}/{tot_returned} = {tot_useful / tot_returned:.0%}"
          f"   context precision = {total_cp:.2f}")
    print(f"Saved {dest.relative_to(HERE.parent.parent.parent)}")


if __name__ == "__main__":
    main()
