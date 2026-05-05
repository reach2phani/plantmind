"""
llm_logger.py — PM-039
LLM call observability for PlantMind.

Wraps every Groq API call and logs to Supabase llm_logs table:
  - model, call_type, latency_ms, input_tokens, output_tokens, error

Teaching concept: AI observability.
Without this, you are flying blind — you discover rate limits by hitting them,
you discover slow calls by waiting, and you have no idea which call types
cost the most tokens. With this, every call is visible and queryable.

Usage:
    from llm_logger import log_llm_call

    # Non-streaming call
    response, usage = log_llm_call(
        fn          = lambda: groq_client.chat.completions.create(...),
        call_type   = "orchestrator",
        model       = "llama-3.3-70b-versatile",
        plant_site  = plant_site,
        equip_tag   = equip_tag
    )

    # Streaming call — log after collecting all chunks
    log_llm_call_streaming(
        call_type  = "qa",
        model      = "llama-3.1-8b-instant",
        input_text = system_prompt + user_prompt,
        output_text= full_answer,
        latency_ms = elapsed,
        error      = None
    )
"""

import os
import time
import threading
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

# ── Supabase client — lazy init ────────────────────────────────────────
# Created on first use rather than at import time.
# Avoids conflicts when imported after Flask initialisation.
_supabase = None

def _get_supabase():
    global _supabase
    if _supabase is None:
        _supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    return _supabase

# ── Token estimation ───────────────────────────────────────────────────
# Groq returns exact token counts for non-streaming calls.
# For streaming calls we estimate: 1 token ≈ 4 characters (conservative).
def _estimate_tokens(text):
    return max(1, len(text) // 4)


# ── Core log function ──────────────────────────────────────────────────
def _write_log(model, call_type, input_tokens, output_tokens,
               latency_ms, error=None, plant_site="", equip_tag=""):
    """Write one log entry to Supabase. Runs in background thread — never blocks."""
    try:
        _get_supabase().table("llm_logs").insert({
            "model":          model,
            "call_type":      call_type,
            "input_tokens":   input_tokens,
            "output_tokens":  output_tokens,
            "latency_ms":     latency_ms,
            "error":          str(error)[:500] if error else None,
            "plant_site":     plant_site or "",
            "equip_tag":      equip_tag or "",
        }).execute()
    except Exception as e:
        # Logging must never crash the main request
        print(f"  [llm_logger] write failed: {e}")


def _log_async(model, call_type, input_tokens, output_tokens,
               latency_ms, error=None, plant_site="", equip_tag=""):
    """Fire-and-forget background log write."""
    t = threading.Thread(
        target=_write_log,
        args=(model, call_type, input_tokens, output_tokens,
              latency_ms, error, plant_site, equip_tag),
        daemon=True
    )
    t.start()


# ── Public API ─────────────────────────────────────────────────────────

def log_llm_call(fn, call_type, model, plant_site="", equip_tag=""):
    """
    Wrap a non-streaming Groq call with timing and logging.

    Args:
        fn:         lambda that calls groq_client.chat.completions.create(...)
        call_type:  label for this call e.g. "orchestrator", "specialist_alarm"
        model:      model name string
        plant_site: optional context for filtering logs
        equip_tag:  optional context for filtering logs

    Returns:
        The Groq response object (same as calling fn() directly)

    Teaching note: we wrap the call in try/except so logging never swallows
    real errors — if Groq throws, we log the error and re-raise.
    """
    start = time.time()
    error = None
    response = None

    try:
        response = fn()
    except Exception as e:
        error = e
        latency_ms = int((time.time() - start) * 1000)
        _log_async(
            model=model, call_type=call_type,
            input_tokens=0, output_tokens=0,
            latency_ms=latency_ms, error=error,
            plant_site=plant_site, equip_tag=equip_tag
        )
        raise  # re-raise so caller handles it normally

    latency_ms = int((time.time() - start) * 1000)

    # Extract exact token counts from Groq response
    usage = getattr(response, "usage", None)
    input_tokens  = usage.prompt_tokens     if usage else 0
    output_tokens = usage.completion_tokens if usage else 0

    _log_async(
        model=model, call_type=call_type,
        input_tokens=input_tokens, output_tokens=output_tokens,
        latency_ms=latency_ms, error=None,
        plant_site=plant_site, equip_tag=equip_tag
    )

    return response


def log_streaming_call(call_type, model, input_text, output_text,
                       latency_ms, error=None, plant_site="", equip_tag=""):
    """
    Log a streaming Groq call after all chunks have been collected.

    Streaming responses don't return token counts — we estimate from text length.

    Teaching note: streaming is harder to observe than non-streaming because
    the response arrives in pieces. The pattern here is to collect the full
    output first, then log. The latency is wall-clock time from first chunk
    request to last chunk received.
    """
    input_tokens  = _estimate_tokens(input_text)
    output_tokens = _estimate_tokens(output_text)

    _log_async(
        model=model, call_type=call_type,
        input_tokens=input_tokens, output_tokens=output_tokens,
        latency_ms=latency_ms, error=error,
        plant_site=plant_site, equip_tag=equip_tag
    )


# ── Stats query (for /api/llm-stats endpoint) ─────────────────────────

def get_today_stats():
    """
    Return token usage and call counts for today.
    Used by /api/llm-stats endpoint.

    Teaching note: this is the "closing the loop" step — once you have logs,
    you can answer "how much did I use today?" before hitting the limit.
    """
    try:
        result = _supabase.rpc("llm_stats_today").execute()
        if result.data:
            return result.data[0]
    except Exception:
        pass

    # Fallback: manual aggregation if RPC not available
    try:
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rows = _get_supabase().table("llm_logs")\
            .select("model,call_type,input_tokens,output_tokens,latency_ms,error,created_at")\
            .gte("created_at", f"{today}T00:00:00Z")\
            .execute()

        logs = rows.data or []
        by_model = {}
        total_input = 0
        total_output = 0
        errors = 0

        for log in logs:
            m = log.get("model", "unknown")
            if m not in by_model:
                by_model[m] = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
            by_model[m]["calls"]         += 1
            by_model[m]["input_tokens"]  += log.get("input_tokens", 0) or 0
            by_model[m]["output_tokens"] += log.get("output_tokens", 0) or 0
            total_input  += log.get("input_tokens", 0) or 0
            total_output += log.get("output_tokens", 0) or 0
            if log.get("error"):
                errors += 1

        return {
            "total_calls":    len(logs),
            "total_input":    total_input,
            "total_output":   total_output,
            "total_tokens":   total_input + total_output,
            "errors":         errors,
            "by_model":       by_model,
            "date":           today
        }
    except Exception as e:
        return {"error": str(e)}
