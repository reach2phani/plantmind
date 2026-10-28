"""
run_record_selftest.py — offline checks for run_record.py (no AI calls, no Supabase).

    venv\\Scripts\\python.exe evals\\run_record_selftest.py

What it proves:
  1. Thread safety: 20 threads add tokens at once; the totals are exact.
  2. Steps: each specialist thread's calls are labelled with its own step.
  3. Status: the real investigate_incident wrapper writes ok / error /
     cancelled (caller stopped reading) / rate_limited, exactly once.
  4. Never lost: a failing or hanging Supabase write is counted and the run
     goes to the backup file; the investigation itself is not affected.
  5. Reading the report: criticality and SOURCE DATA lines, by code.
"""

import os
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import contextvars

os.environ["LANGSMITH_TRACING"] = "false"   # never send test traces
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import run_record  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))


class FakeTable:
    def __init__(self, db, name):
        self.db, self.name, self.op, self.row = db, name, None, None

    def insert(self, row):
        self.op, self.row = "insert", row
        return self

    def upsert(self, row):
        self.op, self.row = "upsert", row
        return self

    def execute(self):
        if self.db.fail:
            raise RuntimeError("simulated Supabase failure")
        if self.db.hang:
            time.sleep(self.db.hang)
        self.db.writes.append((self.name, self.op, dict(self.row)))
        return self


class FakeDB:
    def __init__(self, fail=False, hang=0):
        self.fail, self.hang, self.writes = fail, hang, []

    def table(self, name):
        return FakeTable(self, name)


def use_db(db):
    run_record._supabase = lambda: db


print("\n1. Thread safety")
use_db(FakeDB())
rec = run_record.RunRecord("q", "FL-101")


def worker(i):
    for _ in range(500):
        rec.llm_call("specialist", "openai/gpt-oss-20b", 3, 2, 1)


threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
for t in threads:
    t.start()
for t in threads:
    t.join()
summary, detail = rec._final_rows("ok", None)
check("tokens_in exact (20 x 500 x 3 = 30000)", summary["tokens_in"] == 30000, summary["tokens_in"])
check("tokens_out exact (20000)", summary["tokens_out"] == 20000, summary["tokens_out"])
check("llm_calls exact (10000)", summary["llm_calls"] == 10000, summary["llm_calls"])
check("one event per call", len(detail["events"]) == 10000, len(detail["events"]))

print("\n2. Steps inside parallel specialists")
rec = run_record.RunRecord("q", "FL-101")


def specialist():
    run_record.current().llm_call("specialist", "openai/gpt-oss-20b", 1, 1, 1)
    return run_record.current() is rec


with ThreadPoolExecutor(max_workers=2) as ex:
    futs = [ex.submit(contextvars.copy_context().run, run_record.in_thread(rec, step, specialist))
            for step in ("alarm", "sop", "ncr", "maintenance")]
    found = [f.result() for f in futs]
steps = sorted(e["step"] for e in rec.detail["events"])
check("every thread found the record", all(found))
check("each call labelled with its step", steps == ["alarm", "maintenance", "ncr", "sop"], steps)
check("no record left current afterwards", run_record.current() is None)

print("\n3. Status written by the real investigate_incident wrapper")
import multi_agent as ma  # noqa: E402

real_steps = ma._investigate_steps


def fake_steps(outcome):
    def gen(incident, equipment_id, rec):
        rec.llm_call("orchestrator", "openai/gpt-oss-120b", 100, 50, 1)
        yield "progress\n"
        if outcome == "raise":
            raise RuntimeError("boom")
        if outcome == "rate":
            return "rate_limited", Exception("429 rate_limit")
        yield "report"
        return "ok", None
    return gen


def final_status(db):
    rows = [w for w in db.writes if w[0] == "investigation_runs"]
    return rows[-1][2]["status"] if rows else None, len([w for w in rows if w[1] == "upsert"])


for label, outcome, consume, expect in [
    ("finished", "ok", "all", "ok"),
    ("caller stops reading", "ok", "first", "cancelled"),
    ("step raises", "raise", "all", "error"),
    ("rate limit", "rate", "all", "rate_limited"),
]:
    db = FakeDB()
    use_db(db)
    ma._investigate_steps = fake_steps(outcome)
    gen = ma.investigate_incident("underfill alarm", equipment_id="FL-101", run_tag="t", source="eval")
    try:
        if consume == "first":
            next(gen)
            gen.close()           # what Flask does when the client disconnects
        else:
            list(gen)
    except RuntimeError:
        pass
    status, finals = final_status(db)
    check(f"{label} -> {expect}", status == expect, status)
    check(f"{label}: final row written once", finals == 1, finals)
ma._investigate_steps = real_steps

db_start = [w for w in db.writes if w[1] == "insert"]
check("a 'running' row is written at the start", bool(db_start) and db_start[0][2]["status"] == "running")
detail_rows = [w for w in db.writes if w[0] == "investigation_run_details"]
check("detail row carries the same run_id", detail_rows and detail_rows[-1][2]["run_id"] == db_start[0][2]["id"])

print("\n4. A failing or hanging Supabase never loses the run")
tmp = tempfile.mkdtemp()
run_record.BACKUP_FILE = os.path.join(tmp, "run_write_failures.jsonl")
before = run_record.write_failures()["count"]
use_db(FakeDB(fail=True))
r = run_record.start("q", "FL-101")
r.finish("ok")
lines = open(run_record.BACKUP_FILE, encoding="utf-8").read().splitlines()
check("failures counted (start + finish)", run_record.write_failures()["count"] - before == 2,
      run_record.write_failures())
check("final run saved to the backup file", any('"finish"' in ln for ln in lines))

run_record.START_TIMEOUT_S, run_record.FINISH_TIMEOUT_S = 0.2, 0.3
use_db(FakeDB(hang=2))
t0 = time.time()
r = run_record.start("q", "FL-101")
r.finish("ok")
took = time.time() - t0
check("a hanging Supabase is abandoned quickly", took < 1.5, f"{took:.2f}s")

print("\n5. Reading the report by code")
report = """SOURCE DATA:
- FL-101-SOP.txt (Revision 1.0) - Sections 6.2, 12.1
- FL-101-NCR.txt (NCR-2026-012)

WHAT IS THE ISSUE:
- Root cause: worn seal

HOW CRITICAL IS IT:
- HIGH - three alarms in one shift
"""
check("criticality = HIGH", run_record.criticality(report) == "HIGH")
check("2 sources read", run_record.sources_cited(report) ==
      ["FL-101-SOP.txt (Revision 1.0) - Sections 6.2, 12.1", "FL-101-NCR.txt (NCR-2026-012)"],
      run_record.sources_cited(report))

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
