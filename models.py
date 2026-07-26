"""
models.py — Central model configuration for PlantMind.

WHY THIS EXISTS
    Model names used to be hardcoded as string literals in ~19 places across
    app.py, multi_agent.py and work_order_agent.py. When Groq deprecated the
    Llama models (decommission 2026-08-16), that meant a 19-site edit under
    time pressure with no rollback switch. This module makes the model choice
    a single source of truth, so a migration is a one-line env change.

THE TWO TIERS  (mirroring the original architecture's cost/latency design)
    MODEL_FAST — high-volume / lower-stakes calls:
                 supervisor router, the 4 parallel specialist agents, streaming QA.
    MODEL_DEEP — low-volume / quality-critical calls:
                 orchestrator, reflection, work-order tool calling.

DEFAULTS ARE THE CURRENT LLAMA MODELS, so importing this module changes no
behaviour. Migrating is done purely through environment variables — no code edit:

    # Stay on Llama (default — valid until 2026-08-16):
    PM_MODEL_FAST=llama-3.1-8b-instant
    PM_MODEL_DEEP=llama-3.3-70b-versatile

    # Migrate to GPT-OSS (Groq's recommended replacements):
    PM_MODEL_FAST=openai/gpt-oss-20b
    PM_MODEL_DEEP=openai/gpt-oss-120b

Because it is env-switchable, rollback is instant: change the var back and
restart. No redeploy of code.
"""

import os
import json as _json


def extract_json(raw):
    """
    Pull a JSON object out of a model response, tolerating what reasoning
    models (GPT-OSS) add around it: chain-of-thought text before the JSON,
    and/or ```json fences. Returns the parsed dict, or raises ValueError.

    Order: try clean parse -> strip fences -> grab the outermost {...} span.
    """
    if raw is None:
        raise ValueError("empty response")
    s = raw.strip()

    # 1) clean parse
    try:
        return _json.loads(s)
    except Exception:
        pass

    # 2) strip a ```json ... ``` fence if present
    if "```" in s:
        parts = s.split("```")
        if len(parts) >= 2:
            body = parts[1]
            if body.lower().startswith("json"):
                body = body[4:]
            try:
                return _json.loads(body.strip())
            except Exception:
                pass

    # 3) last resort: outermost braces (skips any reasoning text around it)
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end != -1 and end > start:
        return _json.loads(s[start:end + 1])

    raise ValueError("no JSON object found in response")

# ── Tier → model string ────────────────────────────────────────────────
# Read once at import. Override via environment; defaults preserve today's
# behaviour exactly.
MODEL_FAST = os.getenv("PM_MODEL_FAST", "llama-3.1-8b-instant")
MODEL_DEEP = os.getenv("PM_MODEL_DEEP", "llama-3.3-70b-versatile")


# ── Reasoning effort per call type ─────────────────────────────────────
# Only meaningful for GPT-OSS reasoning models; Llama ignores it. Defined
# here so Phase 2 can wire `reasoning_effort` into the API calls without
# hunting through call sites again.
#
# Free-tier tuning rationale (8K TPM / 200K TPD on GPT-OSS):
#   - The high-volume and burst-prone calls (supervisor, the parallel
#     specialists, QA) are kept at "low" so chain-of-thought tokens don't
#     eat the per-minute token budget during the specialist fan-out.
#   - The single, low-frequency quality calls (orchestrator, work order)
#     get "medium" where reasoning actually earns its token cost.
REASONING_EFFORT = {
    "supervisor":   "low",
    "specialist":   "low",
    "qa":           "low",
    "orchestrator": "medium",
    "reflection":   "low",
    "work_order":   "medium",
}


def is_reasoning_model(model):
    """True if `model` is a GPT-OSS reasoning model (supports reasoning_effort)."""
    return "gpt-oss" in (model or "")


def reasoning_effort_for(call_type, model):
    """
    Return the reasoning-effort string for a call type, or None when it does
    not apply (i.e. the active model is not a reasoning model). Phase 2 call
    sites can do:

        kw = {}
        eff = reasoning_effort_for("specialist", MODEL_FAST)
        if eff:
            kw["reasoning_effort"] = eff
        groq_client.chat.completions.create(model=MODEL_FAST, **kw, ...)
    """
    if not is_reasoning_model(model):
        return None
    return REASONING_EFFORT.get(call_type)


# Extra completion-token budget for reasoning models, so chain-of-thought
# tokens don't eat into the actual answer (reasoning counts toward the cap).
_REASONING_HEADROOM = {"low": 512, "medium": 1024, "high": 2048}


def completion_kwargs(model, call_type, content_tokens):
    """
    Build the token-cap + reasoning kwargs for a chat.completions.create call.
    Splat the result into the call: create(..., **completion_kwargs(m, ct, 400)).

    Llama (non-reasoning):
        {"max_tokens": content_tokens}                 # unchanged behaviour

    GPT-OSS (reasoning):
        {"max_completion_tokens": content_tokens + headroom,
         "reasoning_effort": <low|medium|high>,
         "include_reasoning": False}
      - headroom is added so reasoning tokens don't starve the answer.
      - include_reasoning=False keeps raw reasoning out of content / JSON / tools.

    Because the reasoning kwargs are returned ONLY for GPT-OSS, this is a no-op
    on Llama — passing reasoning params to Llama would error, so we never do.
    """
    if not is_reasoning_model(model):
        return {"max_tokens": content_tokens}
    effort   = REASONING_EFFORT.get(call_type, "low")
    headroom = _REASONING_HEADROOM.get(effort, 512)
    return {
        "max_completion_tokens": content_tokens + headroom,
        "reasoning_effort":      effort,
        "include_reasoning":     False,
    }
