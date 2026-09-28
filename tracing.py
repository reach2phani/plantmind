"""
tracing.py — LangSmith tracing for the investigation pipeline, in one place.

WHAT IT GIVES YOU
    Every investigation becomes a trace at smith.langchain.com: a timeline tree
    of graph lookup -> supervisor -> specialists (each with its search) ->
    orchestrator, with the exact input and output of every step and the tokens
    of every Groq call. Use it to answer "was the fact missing from what the AI
    was given, or did the AI ignore it?" by clicking, not by writing a script.

    It shows what each step received and produced. It does NOT show the
    model's private reasoning — PlantMind turns that off on purpose.

OFF UNLESS SWITCHED ON
    Nothing is sent anywhere unless .env has:
        LANGSMITH_TRACING=true
        LANGSMITH_API_KEY=<your key>
        LANGSMITH_PROJECT=plantmind
    Without them, @traceable does nothing and the pipeline behaves exactly as
    before. If the langsmith package is missing, the decorator is a no-op.

    Traces go to LangChain's cloud (question, retrieved chunks, report). Fine
    for PlantMind's demo data; a real plant would need approval or the
    self-hosted option.
"""

try:
    from langsmith import traceable  # noqa: F401
except ImportError:  # tracing must never be able to break the app
    def traceable(*args, **kwargs):
        if args and callable(args[0]) and len(args) == 1 and not kwargs:
            return args[0]
        return lambda fn: fn


def llm_inputs(inputs):
    """Show which call this was, not the lambda that makes it."""
    return {"call_type": inputs.get("call_type"), "model": inputs.get("model"),
            "equip_tag": inputs.get("equip_tag")}


def llm_outputs(response):
    """The answer text plus token usage, in the shape LangSmith displays."""
    try:
        text = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        out = {"content": text,
               "finish_reason": getattr(response.choices[0], "finish_reason", None)}
        if usage is not None:
            out["usage_metadata"] = {
                "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
                "total_tokens": getattr(usage, "total_tokens", 0) or 0,
            }
        return out
    except Exception:
        return {"output": str(response)[:2000]}


def fault_chain_outputs(result):
    """The graph hand-over, summarised: exactly the text the orchestrator gets."""
    if not isinstance(result, dict):
        return {"output": str(result)[:2000]}
    return {
        "has_data": result.get("has_data"),
        "degraded": result.get("degraded", False),
        "source": result.get("source", "neo4j"),
        "nodes": len(result.get("chain_nodes", []) or []),
        "chain_text": result.get("chain_text", ""),
        "warnings": result.get("warnings", []),
        "downtime": result.get("downtime", ""),
    }


def join_stream(chunks):
    """investigate_incident streams text; show the whole thing as one output."""
    return "".join(str(c) for c in chunks)
