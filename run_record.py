"""
run_record.py — one record per investigation, for evals and monitoring.

WHAT IT GIVES YOU
    Every investigation gets a run_id and two rows in Supabase:
      investigation_runs         the SUMMARY: plain columns a dashboard can chart
                                 (status, versions, tokens, cost, time, ...)
      investigation_run_details  the DETAIL: the report, every retrieved piece
                                 (full text), each specialist's findings, and
                                 an event list (every AI call and search)
    The same run_id is written on every llm_logs row of that investigation and
    on its LangSmith trace, so all three can be joined.

THE RULES IT FOLLOWS
    1. Logging can never break an investigation. Every write is wrapped; a
       failure prints a note, goes to a local backup file, and is counted.
    2. A run is written at the START (status "running") and updated at the
       END. If the process dies in between, the row stays "running": a lost
       run shows up as "never finished", it does not silently disappear.
    3. Writes are bounded: each waits at most a few seconds, then gives up and
       uses the backup file. A paused Supabase cannot hang an investigation.
    4. The specialists run in parallel threads and add to the same record, so
       every change goes through one lock (contextvars only lets the threads
       FIND the record; it does not stop two of them updating it at once).

COST
    Tokens are the fact; dollars are a calculation. cost_usd uses PRICES below
    and stores PRICE_VERSION next to it. Before/after reports should re-price
    both sides with one price table, so a price change never looks like a fix.
"""

import contextvars
import hashlib
import json
import os
import re
import subprocess
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

# ── Prices (USD per 1M tokens) ────────────────────────────────────────────
# NOT VERIFIED: copy the numbers from Groq's pricing page and change the
# version name when you do. Runs keep the version they were priced with.
PRICE_VERSION = "groq-list-unverified-2026-10"
PRICES = {
    "openai/gpt-oss-20b":  {"in": 0.10, "out": 0.50},
    "openai/gpt-oss-120b": {"in": 0.15, "out": 0.75},
}

START_TIMEOUT_S  = 3     # wait at most this long for the "running" row
FINISH_TIMEOUT_S = 10    # wait at most this long for the final write
BACKUP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "logs", "run_write_failures.jsonl")

_current = contextvars.ContextVar("pm_run_record", default=None)
_step    = contextvars.ContextVar("pm_run_step", default="")

_failures_lock = threading.Lock()
_failures = {"count": 0, "last_error": ""}


def write_failures():
    """How many run writes failed in this process (shown in /api/llm-stats)."""
    with _failures_lock:
        return dict(_failures)


# ── Versions: computed once per process ───────────────────────────────────

def _git_commit():
    sha = os.getenv("RENDER_GIT_COMMIT", "")[:7]   # Render has no .git folder
    if sha:
        return sha
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=here,
                             capture_output=True, text=True, timeout=5).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                               cwd=here, capture_output=True, text=True, timeout=5).stdout.strip()
        return (sha + ("+dirty" if dirty else "")) if sha else "unknown"
    except Exception:
        return "unknown"


def _code_hash():
    """Short fingerprint of the files that shape an answer. Changes whenever a
    prompt or rule changes, even before it is committed (git_commit says
    "+dirty" then, but not WHAT changed)."""
    here = os.path.dirname(os.path.abspath(__file__))
    h = hashlib.sha1()
    for name in ("multi_agent.py", "knowledge_graph.py", "models.py"):
        try:
            with open(os.path.join(here, name), "rb") as f:
                h.update(f.read())
        except OSError:
            pass
    return h.hexdigest()[:10]


GIT_COMMIT = _git_commit()
CODE_HASH  = _code_hash()


# ── The record ────────────────────────────────────────────────────────────

class RunRecord:
    def __init__(self, question, equip_tag, plant_site="", line="",
                 run_tag="", source="script", run_id=None):
        # The caller may choose the id (app.py sends it to promptfoo in a
        # header before the investigation starts); otherwise make one.
        self.run_id = run_id or str(uuid.uuid4())
        self._lock = threading.Lock()
        self._t0 = time.time()
        self._finished = False
        self._start_thread = None
        self.summary = {
            "id": self.run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "run_tag": run_tag or None,
            "source": source or "script",
            "question": question,
            "plant_site": plant_site or "",
            "line": line or "",
            "equip_tag": equip_tag or "",
            "status": "running",
            "git_commit": GIT_COMMIT,
            "code_hash": CODE_HASH,
        }
        self.detail = {"pieces": [], "findings": [], "events": [], "graph_warnings": [],
                       "guard_events": [], "sources_cited": [], "report": None,
                       "routing_reason": None}
        self._tokens = {}   # model -> {"in": n, "out": n}
        self._counts = {"llm_calls": 0, "llm_errors": 0, "retries": 0,
                        "truncated_calls": 0, "rerank_fallbacks": 0, "budget_wait_ms": 0}

    # -- adding to it (every method takes the lock) -------------------------

    def elapsed_ms(self):
        return int((time.time() - self._t0) * 1000)

    def set(self, **fields):
        with self._lock:
            self.summary.update(fields)

    def set_detail(self, **fields):
        with self._lock:
            self.detail.update(fields)

    def event(self, kind, **fields):
        ev = {"t_ms": self.elapsed_ms(), "kind": kind, "step": _step.get() or None}
        ev.update(fields)
        with self._lock:
            self.detail["events"].append(ev)

    def count(self, name, n=1):
        with self._lock:
            self._counts[name] = self._counts.get(name, 0) + n

    def llm_call(self, call_type, model, tokens_in, tokens_out, ms,
                 finish_reason=None, error=None):
        with self._lock:
            t = self._tokens.setdefault(model, {"in": 0, "out": 0})
            t["in"] += tokens_in or 0
            t["out"] += tokens_out or 0
            self._counts["llm_calls"] += 1
            if error:
                self._counts["llm_errors"] += 1
            if finish_reason == "length":
                self._counts["truncated_calls"] += 1
        self.event("llm_call", call_type=call_type, model=model,
                   tokens_in=tokens_in, tokens_out=tokens_out, ms=ms,
                   finish_reason=finish_reason,
                   error=str(error)[:300] if error else None)

    def pieces(self, search, doc_type, query, matches, reranked=None, outcome="ok"):
        """matches: list of Pinecone matches that were handed on to the specialist."""
        step = _step.get() or None
        rows = []
        for rank, m in enumerate(matches, start=1):
            meta = getattr(m, "metadata", None) or {}
            rows.append({
                "step": step, "search": search, "doc_type": doc_type,
                "rank": rank, "score": round(float(getattr(m, "score", 0) or 0), 4),
                "chunk_id": getattr(m, "id", None),
                "document": meta.get("name") or meta.get("captured_by_name"),
                "revision": meta.get("revision"),
                "reranked": reranked,
                "text": meta.get("text", ""),
            })
        with self._lock:
            self.detail["pieces"].extend(rows)
        self.event("search", search=search, doc_type=doc_type, query=query[:300],
                   pieces=len(rows), reranked=reranked, outcome=outcome)

    # -- finishing ----------------------------------------------------------

    def _totals(self):
        tin = sum(t["in"] for t in self._tokens.values())
        tout = sum(t["out"] for t in self._tokens.values())
        cost, priced = 0.0, True
        for model, t in self._tokens.items():
            p = PRICES.get(model)
            if not p:
                priced = False
                continue
            cost += t["in"] / 1e6 * p["in"] + t["out"] / 1e6 * p["out"]
        return {
            "tokens_in": tin, "tokens_out": tout, "tokens_total": tin + tout,
            "cost_usd": round(cost, 6) if priced else None,   # None = a model has no price
            "price_version": PRICE_VERSION,
        }

    def _final_rows(self, status, error):
        with self._lock:
            summary = dict(self.summary)
            detail = {k: (list(v) if isinstance(v, list) else v) for k, v in self.detail.items()}
            counts = dict(self._counts)
            tokens = {m: dict(t) for m, t in self._tokens.items()}
        summary.update(counts)
        summary.update(self._totals())
        summary.update({
            "status": status,
            "error": str(error)[:1000] if error else None,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "total_ms": self.elapsed_ms(),
            "pieces_count": len(detail["pieces"]),
            "warnings_count": len(detail["graph_warnings"]),
            "sources_cited_count": len(detail["sources_cited"]),
            "guard_events_count": len(detail["guard_events"]),
        })
        detail["run_id"] = self.run_id
        detail["tokens_by_model"] = tokens
        return summary, detail

    def finish(self, status, error=None):
        """Write the final summary + detail. Safe to call more than once."""
        with self._lock:
            if self._finished:
                return
            self._finished = True
        summary, detail = self._final_rows(status, error)
        if self._start_thread is not None:
            self._start_thread.join(START_TIMEOUT_S)   # never overwrite with a late "running"

        def write():
            sb = _supabase()
            sb.table("investigation_runs").upsert(summary).execute()
            sb.table("investigation_run_details").upsert(detail).execute()

        _bounded(write, FINISH_TIMEOUT_S, "finish", backup={"summary": summary, "detail": detail})


# ── Writing ───────────────────────────────────────────────────────────────

def _supabase():
    from llm_logger import _get_supabase   # same lazy client as llm_logs
    return _get_supabase()


def _record_failure(what, err, backup):
    msg = f"{what}: {str(err)[:200]}"
    with _failures_lock:
        _failures["count"] += 1
        _failures["last_error"] = msg
    if backup is None:   # the "running" row: the final write will carry everything
        print(f"  [run_record] write failed ({msg})")
        return
    print(f"  [run_record] write failed ({msg}) — saved to {BACKUP_FILE}")
    try:
        os.makedirs(os.path.dirname(BACKUP_FILE), exist_ok=True)
        with open(BACKUP_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"failed": what, "error": msg, **backup},
                               ensure_ascii=False, default=str) + "\n")
    except Exception as e:
        print(f"  [run_record] backup file failed too: {e}")


def _bounded(fn, timeout_s, what, backup=None):
    """Run fn in a thread; wait at most timeout_s. A failure or a timeout is
    counted and the record goes to the backup file. Never raises."""
    box = {}

    def target():
        try:
            fn()
        except Exception as e:
            box["error"] = e

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout_s)
    if t.is_alive():
        _record_failure(what, f"no answer from Supabase after {timeout_s}s", backup)
    elif "error" in box:
        _record_failure(what, box["error"], backup)
    return t


# ── Public helpers ────────────────────────────────────────────────────────

def start(question, equip_tag, plant_site="", line="", run_tag="", source="script",
          run_id=None):
    """Create the record and write the "running" row without waiting for it
    (finish() waits for it, at most START_TIMEOUT_S). The caller makes it
    current with use(), step by step."""
    rec = RunRecord(question, equip_tag, plant_site, line, run_tag, source, run_id)
    row = dict(rec.summary)

    def write():
        _supabase().table("investigation_runs").insert(row).execute()

    def runner():
        _bounded(write, START_TIMEOUT_S, "start")
    rec._start_thread = threading.Thread(target=runner, daemon=True)
    rec._start_thread.start()
    return rec


def current():
    """The record of the investigation running in this context, or None."""
    return _current.get()


@contextmanager
def use(rec, step=None):
    """Make rec current (and name the step) for the code inside the block.
    Used around each pipeline step and inside each specialist thread."""
    t1 = _current.set(rec)
    t2 = _step.set(step) if step is not None else None
    try:
        yield rec
    finally:
        if t2 is not None:
            _step.reset(t2)
        _current.reset(t1)


def in_thread(rec, step, fn):
    """Wrap a specialist function so it runs with rec current and its step named."""
    def run(*args, **kwargs):
        with use(rec, step):
            return fn(*args, **kwargs)
    return run


def sources_cited(report):
    """The lines of the report's SOURCE DATA section, read by code."""
    m = re.search(r"SOURCE DATA:\s*\n(.*?)(?:\n\s*\n|\n[A-Z][A-Z /]+:)", report or "", re.S)
    if not m:
        return []
    return [ln.strip()[1:].strip() for ln in m.group(1).splitlines()
            if ln.strip().startswith("-")]


def criticality(report):
    m = re.search(r"HOW CRITICAL IS IT:\s*\n\s*-?\s*(CRITICAL|HIGH|MEDIUM|LOW)", report or "")
    return m.group(1) if m else None
