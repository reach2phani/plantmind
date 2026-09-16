"""
token_budget.py — client-side per-model token rate limiter (Phase 0, Batch C2).

WHY THIS EXISTS
    Groq's free tier allows 8,000 tokens per minute PER MODEL. PlantMind used to
    fire calls, get a 429 "rate limit" error, sleep, and retry. That wastes a
    request, adds latency, and is invisible until it fails.

    This module keeps a sliding 60-second window of tokens spent per model and
    makes a call WAIT before it would push the window over budget. Reacting to
    a limit (retry after error) becomes designing within it (backpressure).

HOW IT WORKS
    1. acquire(model, estimate)  — reserve an estimate before the call.
                                   Blocks until the window has room.
    2. make the API call
    3. settle(reservation, actual) — replace the estimate with the real token
                                   count from the response, so the window stays
                                   accurate and waiting callers are woken up.

    Thread-safe: the investigation runs specialists in parallel threads.

TUNING (environment variables)
    PM_TPM_LIMIT   tokens per minute per model  (default 8000, Groq free tier)
    PM_TPM_SAFETY  fraction of the limit to use (default 0.95)
    PM_TPM_OUTPUT_FRACTION
                   share of the output cap to reserve up front (default 0.5).
                   Measured 16 Sep 2026: specialists used 130-630 of a 912 cap,
                   the orchestrator ~1,900 of 2,424. Reserving the full cap made
                   calls wait for budget that was never spent, and doubled eval
                   run time. settle() still corrects to the real count after.
"""

import os
import threading
import time
from collections import deque

TPM_LIMIT   = int(os.getenv("PM_TPM_LIMIT", "8000"))
TPM_SAFETY  = float(os.getenv("PM_TPM_SAFETY", "0.95"))
OUTPUT_FRACTION = float(os.getenv("PM_TPM_OUTPUT_FRACTION", "0.5"))
WINDOW_S    = 60.0
MAX_WAIT_S  = 90.0     # never block forever; the retry handler is the backstop

_cond    = threading.Condition()
_windows = {}          # model -> deque of [timestamp, tokens]
_stats   = {}          # model -> {"waits": n, "waited_s": x}


def _budget():
    return int(TPM_LIMIT * TPM_SAFETY)


def estimate_tokens(texts, completion_cap):
    """Pre-call estimate: ~4 characters per input token, plus a realistic share
    of the output cap (not the whole cap -- see OUTPUT_FRACTION above).
    settle() replaces this with the real count once the response arrives."""
    chars = sum(len(t or "") for t in texts)
    return chars // 4 + int((completion_cap or 0) * OUTPUT_FRACTION)


def _prune(window, now):
    while window and now - window[0][0] >= WINDOW_S:
        window.popleft()


def acquire(model, tokens):
    """Reserve `tokens` for `model`, waiting if the last 60s would overflow.
    Returns a reservation to pass to settle()."""
    budget = _budget()
    tokens = max(1, min(int(tokens), budget))   # one oversized call may still run alone
    started = time.time()
    announced = False
    with _cond:
        window = _windows.setdefault(model, deque())
        while True:
            now = time.time()
            _prune(window, now)
            used = sum(entry[1] for entry in window)
            if used + tokens <= budget or not window or now - started >= MAX_WAIT_S:
                entry = [now, tokens]
                window.append(entry)
                waited = now - started
                if waited > 0.05:
                    s = _stats.setdefault(model, {"waits": 0, "waited_s": 0.0})
                    s["waits"] += 1
                    s["waited_s"] += waited
                return {"model": model, "entry": entry}
            wait = max(0.2, WINDOW_S - (now - window[0][0]) + 0.1)
            if not announced:
                print(f"  [token budget] {model}: {used}+{tokens} > {budget} tokens/min "
                      f"— waiting up to {wait:.0f}s instead of hitting a rate limit")
                announced = True
            _cond.wait(timeout=min(wait, MAX_WAIT_S))


def settle(reservation, actual_tokens):
    """Replace the reserved estimate with the real token count (if known)."""
    if not reservation:
        return
    with _cond:
        if actual_tokens:
            reservation["entry"][1] = int(actual_tokens)
        _cond.notify_all()


def usage_from_response(response):
    """Total tokens from an OpenAI-style response, or 0 if unavailable."""
    usage = getattr(response, "usage", None)
    if not usage:
        return 0
    return (getattr(usage, "prompt_tokens", 0) or 0) + (getattr(usage, "completion_tokens", 0) or 0)


def snapshot():
    """Current window usage per model — used by /api/health."""
    out = {}
    with _cond:
        now = time.time()
        for model, window in _windows.items():
            _prune(window, now)
            s = _stats.get(model, {"waits": 0, "waited_s": 0.0})
            out[model] = {
                "tokens_last_60s": sum(e[1] for e in window),
                "budget_per_min":  _budget(),
                "waits_since_start": s["waits"],
                "seconds_waited_since_start": round(s["waited_s"], 1),
            }
    return out
