"""
ops_report.py — Phase 1 step 1.6: what did a run cost, and how fast was it?

WHAT THIS IS FOR (simple version)
    Quality is only half the story. A correct answer that costs 12K tokens and
    takes 40 seconds is a different product from one that costs 3K and takes 2.
    This reads the app's own call log (Supabase llm_logs) for a time window —
    usually "the eval run I just did" — and summarises cost and speed.

WHAT IT SHOWS
    Per step (Docs answer, specialist, orchestrator...):
        calls, tokens in / out, typical time (p50), slowest time (p95),
        answers cut off, errors.
    Per model: total tokens, and the share of that model's 200K/day free quota.
    Per investigation: average tokens for one full investigation.

    p50 = half the calls were faster than this ("typical").
    p95 = only 1 in 20 calls was slower than this ("the bad case users notice").

TRUST NOTE
    Docs/Shift answers logged BEFORE 18 Sep 2026 ~18:00 UTC have ESTIMATED
    tokens (characters/4, no hidden reasoning — an undercount of ~3x) and a
    time that includes queueing. Fixed in step 1.6. Compare runs after the fix
    only. Investigation calls were always real.

COST
    Free — it only reads the log.

RUN (from C:\\plantmind; the app does NOT need to be running)
    venv\\Scripts\\python.exe evals\\ops_report.py --minutes 30
        -> everything logged in the last 30 minutes
    venv\\Scripts\\python.exe evals\\ops_report.py --since 2026-09-18T17:00
        -> everything since that time (UTC)
"""

import argparse
import datetime as dt
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DAILY_QUOTA = 200_000  # Groq free tier, per model, per day (plan page)

# Friendlier names for the log's call_type values.
STEP_NAMES = {
    "doc": "Docs answer",
    "qa": "Docs answer",
    "shift": "Shift answer",
    "supervisor": "Investigation: supervisor",
    "specialist": "Investigation: specialist",
    "orchestrator": "Investigation: orchestrator",
    "reflection": "Investigation: reflection",
    "work_order": "Work order agent",
}
INVESTIGATION_STEPS = {"supervisor", "specialist", "orchestrator", "reflection"}


def percentile(values, pct):
    if not values:
        return 0
    values = sorted(values)
    k = max(0, min(len(values) - 1, round(pct / 100 * (len(values) - 1))))
    return values[k]


def fetch(since_iso):
    from supabase import create_client
    key = (os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
           or os.getenv("SUPABASE_ANON_KEY"))
    sb = create_client(os.getenv("SUPABASE_URL"), key)
    rows, page = [], 0
    while True:  # page through, 1000 rows at a time
        batch = (sb.table("llm_logs").select("*")
                 .gte("created_at", since_iso)
                 .order("created_at")
                 .range(page * 1000, page * 1000 + 999)
                 .execute().data)
        rows.extend(batch)
        if len(batch) < 1000:
            return rows
        page += 1


def main():
    ap = argparse.ArgumentParser(description="Cost and speed of recent LLM calls.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--minutes", type=int, help="look back this many minutes")
    g.add_argument("--since", help="UTC start time, e.g. 2026-09-18T17:00")
    args = ap.parse_args()

    if args.minutes:
        since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=args.minutes)
        since_iso = since.isoformat(timespec="seconds")
    else:
        since_iso = args.since

    rows = fetch(since_iso)
    if not rows:
        sys.exit(f"No LLM calls logged since {since_iso}.")

    # ── per step ──────────────────────────────────────────────────────────────
    steps = defaultdict(list)
    for r in rows:
        steps[(r.get("call_type") or "?", r.get("model") or "?")].append(r)

    print(f"\nLLM calls since {since_iso} (UTC): {len(rows)}\n")
    head = f"{'STEP':<30}{'MODEL':<22}{'CALLS':>6}{'AVG IN':>8}{'AVG OUT':>8}{'p50 s':>7}{'p95 s':>7}{'CUT':>5}{'ERR':>5}"
    print(head)
    print("-" * len(head))
    for (ctype, model), rs in sorted(steps.items(), key=lambda kv: -len(kv[1])):
        ins = [r.get("input_tokens") or 0 for r in rs]
        outs = [r.get("output_tokens") or 0 for r in rs]
        lat = [(r.get("latency_ms") or 0) / 1000 for r in rs]
        cut = sum(1 for r in rs if r.get("truncated") or r.get("finish_reason") == "length")
        err = sum(1 for r in rs if r.get("error"))
        print(f"{STEP_NAMES.get(ctype, ctype):<30}{model.replace('openai/', ''):<22}"
              f"{len(rs):>6}{statistics.mean(ins):>8.0f}{statistics.mean(outs):>8.0f}"
              f"{percentile(lat, 50):>7.1f}{percentile(lat, 95):>7.1f}{cut:>5}{err:>5}")

    # ── per model: the quota view ─────────────────────────────────────────────
    print("\nPER MODEL (free tier: 200K tokens/day each)")
    per_model = defaultdict(int)
    for r in rows:
        per_model[r.get("model") or "?"] += (r.get("input_tokens") or 0) + (r.get("output_tokens") or 0)
    for model, tot in sorted(per_model.items(), key=lambda kv: -kv[1]):
        print(f"  {model:<28}{tot:>9,} tokens   {tot / DAILY_QUOTA:>5.0%} of a day's quota")

    # ── per investigation ────────────────────────────────────────────────────
    inv = [r for r in rows if r.get("call_type") in INVESTIGATION_STEPS]
    n_inv = sum(1 for r in inv if r.get("call_type") == "orchestrator")
    if n_inv:
        tot = sum((r.get("input_tokens") or 0) + (r.get("output_tokens") or 0) for r in inv)
        print(f"\nINVESTIGATIONS: {n_inv}   average {tot / n_inv:,.0f} tokens each "
              f"(supervisor + specialists + orchestrator + reflection)")

    cut_total = sum(1 for r in rows if r.get("truncated") or r.get("finish_reason") == "length")
    if cut_total:
        print(f"\nWARNING: {cut_total} answer(s) hit the output cap and were cut off.")


if __name__ == "__main__":
    main()
