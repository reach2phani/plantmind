"""
retrieval_recall.py - did search bring back the facts the answer needs?

The RUBRIC (facts, wordings AND rules) lives in heldout-v1/retrieval_labels.json.
This script only applies it. It stops if the JSON asks for a rule it does not
know how to apply, so the rules can never silently differ from the JSON.

Read-only. No tokens, no network: uses only the saved snapshot.

For each case it checks every fact in two places:
  1. the WHOLE FL-101 index (snapshot/chunks_fl101.json): could search have found it?
  2. the pieces search handed to the helpers (run record -> details.pieces): did it?

Each result file records a fingerprint of the rules and of every case, so a
change to the marking sheet after a run is visible.

Usage:
  venv\\Scripts\\python.exe evals\\investigations\\retrieval_recall.py
  venv\\Scripts\\python.exe evals\\investigations\\retrieval_recall.py --side before
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent / "heldout-v1"
SNAP = HERE / "snapshot"

# The only rule values this script knows how to apply.
KNOWN_RULES = {
    "ignore_case": {True, False},
    "ignore_line_breaks": {True, False},
    "found_means": {"the fact is inside at least one piece search handed to the helpers"},
    "skip_facts_not_in_documents": {True, False},
    "score": {"facts found / facts that exist in the documents"},
}


# The only metric and place to look this script supports.
KNOWN_METRIC = "retrieval_recall"
KNOWN_LOOK_IN = {"search_results": lambda run: (run.get("details") or {}).get("pieces") or []}


def fingerprint(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def check_rules(rules):
    for key, allowed in KNOWN_RULES.items():
        if key not in rules:
            sys.exit(f"Rule '{key}' is missing from retrieval_labels.json")
        if rules[key] not in allowed:
            sys.exit(f"Rule '{key}' = {rules[key]!r}: this script doesn't know how to apply it")
    extra = set(rules) - set(KNOWN_RULES)
    if extra:
        sys.exit(f"Unknown rule(s) in retrieval_labels.json: {sorted(extra)}")


def make_matcher(rules):
    def norm(text):
        t = text or ""
        if rules["ignore_case"]:
            t = t.lower()
        if rules["ignore_line_breaks"]:
            t = re.sub(r"\s+", " ", t)
        return t

    def matches(fact, text):
        t = norm(text)
        return all(any(norm(w) in t for w in group) for group in fact["all_of"])
    return matches


def where(piece):
    return {"document": piece.get("document"), "rank": piece.get("rank"),
            "chunk": (piece.get("chunk_id") or "").rsplit("_", 1)[-1]}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--side", default="after", choices=["before", "after"])
    args = ap.parse_args()

    labels = json.loads((HERE / "retrieval_labels.json").read_text(encoding="utf-8"))
    if labels.get("metric") != KNOWN_METRIC:
        sys.exit(f"metric = {labels.get('metric')!r}: this script only measures {KNOWN_METRIC!r}")
    if labels.get("look_in") not in KNOWN_LOOK_IN:
        sys.exit(f"look_in = {labels.get('look_in')!r}: this script can only look in {sorted(KNOWN_LOOK_IN)}")
    get_evidence = KNOWN_LOOK_IN[labels["look_in"]]
    rules = labels["rules"]
    check_rules(rules)

    # The lock: the rubric must be exactly as it was when it was locked.
    lock_path = HERE / "retrieval_labels.lock.json"
    if not lock_path.is_file():
        sys.exit("No retrieval_labels.lock.json: lock the rubric before scoring")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if fingerprint(rules) != lock["rules_fingerprint"]:
        sys.exit("The rules changed after they were locked: make a new version instead")
    if fingerprint({k: labels[k] for k in ("metric", "look_in")}) != lock["header_fingerprint"]:
        sys.exit("metric/look_in changed after they were locked: make a new version instead")
    for case, lab in labels["cases"].items():
        locked = lock["cases"].get(case)
        if not locked:
            sys.exit(f"{case} is not locked yet: review and lock it before scoring")
        if fingerprint(lab) != locked["fingerprint"]:
            sys.exit(f"{case} changed after it was locked: make a new version instead")
    matches = make_matcher(rules)
    index = json.loads((SNAP / "chunks_fl101.json").read_text(encoding="utf-8"))["chunks"]
    out = {"run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "side": args.side, "labels_version": labels["version"],
           "metric": labels["metric"], "look_in": labels["look_in"], "locked": lock["locked"],
           "rules": rules, "rules_fingerprint": fingerprint(rules), "cases": {}}

    for case, lab in labels["cases"].items():
        run = json.loads((SNAP / "runs" / f"{case}-{args.side}.json").read_text(encoding="utf-8"))
        pieces = get_evidence(run)
        rows, found, counted = [], 0, 0
        for f in lab["facts"]:
            in_index = [f"{c['document']}#{c['n']}" for c in index if matches(f, c["text"])]
            in_search = [where(p) for p in pieces if matches(f, p.get("text"))]
            if in_index or not rules["skip_facts_not_in_documents"]:
                counted += 1
                found += bool(in_search)
            rows.append({"id": f["id"], "fact": f["fact"], "in_index": in_index, "found_in": in_search,
                         "result": "FOUND" if in_search else ("MISSED" if in_index else "NOT IN DOCUMENTS")})
        recall = found / counted if counted else None
        out["cases"][case] = {"case_fingerprint": fingerprint(lab), "blind": lab["blind"],
                              "pieces_returned": len(pieces), "found": found, "counted": counted,
                              "recall": recall, "facts": rows}

        print(f"\n{case} ({args.side})  blind label: {lab['blind']}  pieces returned: {len(pieces)}"
              f"  case fingerprint: {fingerprint(lab)}")
        for r in rows:
            loc = ", ".join(f"{w['document']} rank {w['rank']} (piece {w['chunk']})" for w in r["found_in"]) \
                or ("exists in " + ", ".join(r["in_index"]) if r["in_index"] else "")
            print(f"  {r['id']} {r['result']:<17} {r['fact']:<42} {loc}")
        print(f"  retrieval recall = {found} / {counted} = {recall:.0%}" if recall is not None else "  nothing to count")

    dest = HERE / "results" / f"retrieval_recall_{args.side}.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nRules fingerprint: {out['rules_fingerprint']}")
    print(f"Saved {dest.relative_to(HERE.parent.parent.parent)}")


if __name__ == "__main__":
    main()
