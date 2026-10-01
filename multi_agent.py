"""
multi_agent.py — PlantMind Multi-Agent Investigation System

Architecture:
  4 specialist agents run in parallel, each with one tool and one focused job.
  When all four finish, the Orchestrator synthesizes their findings into a
  two-part report: technical (for the maintenance engineer) and plain language
  (for the plant manager).

Agents:
  AlarmAgent       — shift log search, alarm pattern analysis
  ExpertFixAgent   — senior-operator field captures (PM-IK-001), searched
                     right after shift logs since a prior expert fix on the
                     exact fault pattern is the highest-value lead available
  MaintenanceAgent — maintenance record search, repair history
  SOPAgent         — procedure search, specification lookup
  NCRAgent         — non-conformance history, corrective action patterns
  Orchestrator     — receives all specialist findings, synthesizes final report
"""

from groq import Groq
from pinecone import Pinecone
from concurrent.futures import ThreadPoolExecutor, as_completed
from models import MODEL_FAST, MODEL_DEEP, extract_json, completion_kwargs
from token_budget import acquire, settle, estimate_tokens, usage_from_response
import os
import re
import json
from dotenv import load_dotenv

load_dotenv()

from llm_logger import log_llm_call
from tracing import traceable, llm_inputs, llm_outputs, join_stream
import contextvars

import time as _time

def _retry_after_seconds(err_text, default=3.0):
    """Pull 'try again in 1.07s' (or '6m 11s') out of a Groq 429 message.
    Returns seconds to wait; falls back to `default` if not found. Capped at 60s
    since TPM windows reset within a minute."""
    import re as _re2
    m = _re2.search(r'try again in\s+(?:(\d+)m\s*)?([\d.]+)s', err_text or "", _re2.IGNORECASE)
    if m:
        mins = float(m.group(1)) if m.group(1) else 0.0
        secs = float(m.group(2))
        return min(60.0, mins * 60 + secs + 0.5)   # +0.5s cushion
    return float(default)


def _completion_cap(model, call_type, content_tokens):
    """Total output tokens a call may use (content + reasoning headroom)."""
    kw = completion_kwargs(model, call_type, content_tokens)
    return kw.get("max_completion_tokens") or kw.get("max_tokens") or content_tokens


@traceable(run_type="llm", name="groq_call", process_inputs=llm_inputs, process_outputs=llm_outputs)
def _groq_call_with_retry(fn, max_retries=3, call_type="specialist",
                          model=MODEL_FAST,
                          plant_site="", equip_tag="",
                          estimate=1500, graph_source=None):
    """
    Every investigation LLM call goes through here, and gets three behaviours:
      1. TOKEN BUDGET (Batch C2): wait for room in this model's per-minute
         budget BEFORE calling, instead of failing with a 429 and retrying.
      2. LOGGING: every call, success or failure, lands in llm_logs, now with
         finish_reason and (for reports) where graph context came from.
      3. RETRY: still here as the backstop if the estimate was too low.

    Teaching note: wrapping budget + logging + retry in one function means
    every call site gets all three for free.
    """
    for attempt in range(max_retries):
        reservation = acquire(model, estimate)
        try:
            response = log_llm_call(
                fn=fn, call_type=call_type, model=model,
                plant_site=plant_site, equip_tag=equip_tag,
                graph_source=graph_source
            )
            settle(reservation, usage_from_response(response))
            return response
        except Exception as e:
            settle(reservation, None)   # keep the estimate: a rejected call may still count
            if "rate_limit" in str(e).lower() or "429" in str(e):
                # TPM windows reset within ~60s, and Groq tells us exactly how
                # long to wait ("try again in 1.07s"). Honour that hint instead
                # of a flat 55s wait, with a short backoff as the fallback.
                wait = _retry_after_seconds(str(e), default=[3, 8, 15][attempt])
                print(f"  Rate limit hit — waiting {wait:.1f}s before retry {attempt+1}/{max_retries}")
                _time.sleep(wait)
            else:
                raise
    raise Exception("Max retries exceeded on Groq rate limit")

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ── Feature flag — disable for eval runs to avoid rate limits ─────────────────
# Set to True for production/manual testing, False for automated eval runs.
# Reflection adds 1 LLM call per investigation — on free tier this reliably
# hits the 6,000 TPM limit when running multiple investigations back to back.
ENABLE_REFLECTION = os.getenv("ENABLE_REFLECTION", "false").lower() == "true"
pc          = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
pine_index  = pc.Index(os.getenv("PINECONE_INDEX"))

# ── Citation tracking for expert fixes (PM-IK-001) ─────────────────────────
# A lightweight Supabase client just for the one write this file needs:
# incrementing expert_fixes.times_cited when a fix is retrieved as a strong
# match during a live investigation. Kept separate from app.py's client so
# multi_agent.py has no import-time dependency on app.py (it's already run
# standalone via the __main__ block at the bottom of this file).
try:
    from supabase import create_client as _create_supabase_client
    _supabase = _create_supabase_client(
        os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")
    )
except Exception as _e:
    print(f"  [expert_fix] Supabase client unavailable: {_e} — citation tracking disabled")
    _supabase = None


def _increment_expert_fix_citations(expert_fix_ids):
    """
    Mark each expert fix as cited. Silent-fail — citation tracking is a
    nice-to-have counter for the operator, never something that should be
    able to break or slow down an investigation.
    """
    if not _supabase or not expert_fix_ids:
        return
    for fid in expert_fix_ids:
        try:
            _supabase.rpc("increment_expert_fix_cited", {"fix_id": fid}).execute()
        except Exception as e:
            print(f"  [expert_fix] citation increment failed for {fid}: {e}")


# ── Shared Pinecone search ─────────────────────────────────────────────────────

@traceable(run_type="retriever", name="search_documents")
def search_plantmind(query, doc_type_filter=None, equipment_filter=None, top_k=4):
    """
    Search Pinecone for relevant document chunks.
    Returns formatted string of strong matches, or a clear no-data message.
    """
    embedding = pc.inference.embed(
        model="multilingual-e5-large",
        inputs=[query],
        parameters={"input_type": "query", "truncate": "END"}
    )
    query_vec = embedding[0].values

    filter_dict = {}
    if equipment_filter:
        filter_dict["equip_tag"] = {"$eq": equipment_filter}
    if doc_type_filter:
        filter_dict["doc_type"] = {"$eq": doc_type_filter}

    results = pine_index.query(
        vector=query_vec,
        top_k=top_k,
        include_metadata=True,
        filter=filter_dict if filter_dict else None
    )

    if not results.matches:
        return "NO_DATA: No documents found in PlantMind for this query."

    strong_matches = [m for m in results.matches if m.score >= 0.4]

    if not strong_matches:
        return "LOW_CONFIDENCE: Documents found but similarity score below threshold. Do not cite — state insufficient data."

    output = []
    for match in strong_matches:
        meta = match.metadata
        output.append(
            f"[Source: {meta.get('name', 'unknown')} | "
            f"Type: {meta.get('doc_type', 'unknown')} | "
            f"Revision: {meta.get('revision', '?')} | "
            f"Score: {round(match.score, 2)}]\n"
            f"{meta.get('text', '')[:300]}"
        )

    return "\n\n---\n\n".join(output)


# ── Expert Fix search (PM-IK-001) ──────────────────────────────────────────
# A dedicated search function rather than reusing search_plantmind(), because
# this one needs to return the matched expert_fix_ids too — search_plantmind()
# only returns formatted text, which is all every other doc_type needs, but
# citation tracking here requires knowing exactly WHICH rows were used.

def _drop_disputed(matches):
    """
    Remove operator captures a reviewer has REJECTED.

    Why this exists (found by hand-testing in Phase 1B): a reviewer marked an
    operator's arc-voltage note as disputed IN THE GRAPH — it claimed 15-16 V
    was normal when the SOP says 18-22 V. But the note also lives in Pinecone,
    where the Expert Fix agent found it with no idea it had been rejected. The
    report then flagged the contradiction AND still told the operator to set
    the machine to 15.5 V. A rejection in one system that the other never hears
    about is worse than no rejection at all.

    Reads expert_fixes.status (added by sql/06_expert_fix_status.sql). If that
    column does not exist yet, nothing is dropped and behaviour is unchanged.
    """
    ids = [m.metadata.get("expert_fix_id") for m in matches if m.metadata.get("expert_fix_id")]
    if not ids:
        return matches
    try:
        from llm_logger import _get_supabase
        rows = (_get_supabase().table("expert_fixes")
                .select("id,status").in_("id", ids).execute().data or [])
    except Exception as e:
        print(f"[expert-fix] status check skipped ({str(e)[:80]})")
        return matches

    rejected = {r["id"] for r in rows if (r.get("status") or "active") != "active"}
    if rejected:
        print(f"[expert-fix] dropped {len(rejected)} disputed capture(s) from retrieval")
    return [m for m in matches if m.metadata.get("expert_fix_id") not in rejected]


REVIEW_APPROVED = "TIER 3 APPROVED — reviewed and approved in the Review queue"
REVIEW_UNREVIEWED = ("TIER 4 UNREVIEWED — nobody has checked this yet: a lead to check, "
                     "never a setting or an instruction")


def _approved_fix_ids(fix_ids):
    """
    Which of these operator captures a reviewer has APPROVED (they are part of
    an approved candidate in the Review queue). Anything else is unreviewed.

    Fails safe: if the lookup fails, every fix counts as unreviewed, so a
    database hiccup can only make PlantMind MORE cautious, never less.
    """
    ids = [i for i in fix_ids if i]
    if not ids:
        return set()
    try:
        from llm_logger import _get_supabase
        rows = (_get_supabase().table("graph_candidates")
                .select("fix_ids").eq("status", "approved").execute().data or [])
    except Exception as e:
        print(f"[expert-fix] review status check skipped ({str(e)[:80]}) — treating as unreviewed")
        return set()
    approved = {i for r in rows for i in (r.get("fix_ids") or [])}
    return {i for i in ids if i in approved}


@traceable(run_type="retriever", name="search_expert_fixes")
def search_expert_fixes(query, equipment_filter=None, top_k=3):
    """
    Search Pinecone for Expert Fix documents on this equipment.
    Returns (formatted_text, list_of_expert_fix_ids_for_strong_matches).

    A "strong match" (score >= 0.4) is treated as "the agent used this" for
    citation-counting purposes — see increment_expert_fix_cited in the SQL
    schema and the comment on expert_fixes.times_cited for why this simpler
    definition (found + used as context) was chosen over trying to parse
    the orchestrator's final report text for exact citations.
    """
    embedding = pc.inference.embed(
        model="multilingual-e5-large",
        inputs=[query],
        parameters={"input_type": "query", "truncate": "END"}
    )
    query_vec = embedding[0].values

    filter_dict = {"doc_type": {"$eq": "Expert Fix"}}
    if equipment_filter:
        filter_dict["equip_tag"] = {"$eq": equipment_filter}

    results = pine_index.query(
        vector=query_vec,
        top_k=top_k,
        include_metadata=True,
        filter=filter_dict
    )

    if not results.matches:
        return "NO_DATA: No expert fixes found in PlantMind for this equipment.", []

    strong_matches = [m for m in results.matches if m.score >= 0.4]
    strong_matches = _drop_disputed(strong_matches)
    if not strong_matches:
        return "LOW_CONFIDENCE: Expert fixes found but similarity too low — do not cite.", []

    approved = _approved_fix_ids([m.metadata.get("expert_fix_id") for m in strong_matches])

    output   = []
    fix_ids  = []
    for match in strong_matches:
        meta = match.metadata
        name = meta.get("captured_by_name", "an operator")
        # Role is blank in this deployment. Do NOT substitute a default job
        # title: whatever appears in this header gets copied into the final
        # report as if it were recorded fact (it was, as "Senior Operator").
        role = (meta.get("captured_by_role", "") or "").strip()
        date = meta.get("captured_at", "")[:10]  # YYYY-MM-DD prefix only
        # Phase 2a trust order: say whether a person has reviewed this fix.
        # Search results cannot tell an approved fix from one nobody checked,
        # and an unchecked "reset tension 18 to 22" was beating the SOP.
        status = (REVIEW_APPROVED if meta.get("expert_fix_id") in approved
                  else REVIEW_UNREVIEWED)
        output.append(
            f"[Expert Fix — {name}"
            f"{', ' + role if role else ''}"
            f"{', ' + date if date else ''} | {status} | Score: {round(match.score, 2)}]\n"
            f"{meta.get('text', '')[:400]}"
        )
        fid = meta.get("expert_fix_id")
        if fid:
            fix_ids.append(fid)

    return "\n\n---\n\n".join(output), fix_ids


# ── Specialist Agent: Alarm Agent ──────────────────────────────────────────────

def _finish_reason(response):
    """Groq/OpenAI-style responses say WHY generation stopped. "length" means the
    model hit its token cap mid-sentence -- the answer is incomplete."""
    try:
        return getattr(response.choices[0], "finish_reason", "") or ""
    except Exception:
        return ""


def _flag_if_truncated(response, what):
    """Return the response text, with a visible marker if it was cut off.

    Silent truncation is why a specialist can hand the orchestrator half a
    finding, or a report can end mid-section, and nothing anywhere says so.
    Both were happening: orchestrator output landed on exactly its cap
    (1400 content + 1024 reasoning headroom) and no one could tell.
    """
    text = response.choices[0].message.content or ""
    if _finish_reason(response) == "length":
        print(f"  [truncated] {what} hit the output token cap")
        text += f"\n\n[TRUNCATED: {what} hit the output token limit and is incomplete.]"
    return text


@traceable(name="alarm_agent")
def run_alarm_agent(incident, equipment_id=None):
    """
    Specialist: searches shift logs for alarm history and event patterns.
    Returns a structured findings dict.
    """
    SYSTEM_PROMPT = """You are the Alarm Analyst agent for PlantMind, a manufacturing plant AI system.

Your single job: analyse shift log data to identify alarm patterns for the reported incident.

Rules:
- You have been given ONE tool result from a shift log search. Analyse it fully.
- Identify: how many times this alarm has occurred, when, what preceded it, what resolved it.
- Crucially — note what is DIFFERENT about this occurrence vs previous ones.
- If the data shows NO previous occurrences, state that explicitly — it is significant.
- Never invent data. If the search returned no results, say so clearly.

Return your findings in this exact structure:

ALARM PATTERN FINDINGS:
- Frequency: [how many occurrences in the data]
- Most recent prior event: [date/time if available]
- Pattern: [what the data shows about this alarm's history]
- What is different this time: [compare current incident to historical pattern]
- Data confidence: HIGH / MEDIUM / LOW / NO DATA

SOURCES USED:
- [list each source document name and timestamp cited]"""

    query = f"alarm history incidents for {equipment_id or 'equipment'} {incident[:100]}"
    search_result = search_plantmind(query, doc_type_filter="Shift Log", equipment_filter=equipment_id)

    user_prompt = f"""Incident reported: {incident}

Shift log search results:
{search_result}

Analyse the alarm pattern from this data."""

    response = _groq_call_with_retry(
        lambda: groq_client.chat.completions.create(
            model=MODEL_FAST,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt}
            ],
            temperature=0.1, **completion_kwargs(MODEL_FAST, "specialist", 400)),
        call_type="specialist", model=MODEL_FAST,
        equip_tag=equipment_id,
        estimate=estimate_tokens([SYSTEM_PROMPT, user_prompt],
                                 _completion_cap(MODEL_FAST, "specialist", 400)))

    return {
        "agent":    "Alarm Agent",
        "icon":     "🚨",
        "findings": _flag_if_truncated(response, "specialist findings"),
        "raw_data": search_result
    }


# ── Specialist Agent: Expert Fix Agent (PM-IK-001) ────────────────────────────

@traceable(name="expert_fix_agent")
def run_expert_fix_agent(incident, equipment_id=None):
    """
    Specialist: searches senior-operator field captures for this equipment.
    These are unverified-by-committee but highly credible — the trust signal
    is the named operator, not a formal sign-off. If a prior expert fix
    directly conflicts with what the SOP agent later reports, the orchestrator
    is instructed to surface that conflict explicitly, never resolve it here.
    """
    SYSTEM_PROMPT = """You are the Expert Fix agent for PlantMind, a manufacturing plant AI system.

Your single job: check whether a senior operator has already captured a fix for this exact
fault pattern on this equipment, from a real incident they personally resolved.

Rules:
- You have been given ONE tool result from an expert-fix search. Analyse it fully.
- Expert fixes are cited by the OPERATOR'S NAME. Include a job title only if the
  search result actually shows one; never invent one.
- Each result carries a review status: TIER 3 APPROVED (a reviewer checked it) or
  TIER 4 UNREVIEWED (nobody has checked it yet). Copy that status into your findings
  for every fix. Never upgrade an UNREVIEWED fix, and never describe it as proven.
- If a fix is found, state exactly what the operator found different and what fixed it,
  in your own words, attributed to them by name.
- CRITICAL — if the search result contains reproducible numbered steps, preserve them
  as numbered steps in your findings, in the same order, with the same specific values.
  Do NOT compress them into a single summary sentence — the orchestrator downstream
  needs the literal steps to build an actionable report, not a paraphrase of them.
- If the search result is flagged as insufficient detail to reproduce, say so plainly —
  present it as a lead worth investigating, not as a proven procedure.
- If no expert fix exists for this equipment or fault pattern, say so plainly — that is
  itself a useful finding (it means this is a genuine knowledge gap, not just a missed search).
- Never invent or embellish an expert fix. Report only what the search actually returned.

Return your findings in this exact structure:

EXPERT FIX FINDINGS:
- Found: [YES, attributed to <name> | NO — no prior expert fix on record]
- Review status: [TIER 3 APPROVED | TIER 4 UNREVIEWED | N/A]
- What was different: [from the fix, or N/A]
- What fixed it: [from the fix, or N/A]
- When it applies: [any stated conditions, or N/A]
- SOP gap flagged by operator: [YES/NO — did they say the SOP misses this]
- Data confidence: HIGH / MEDIUM / LOW / NO DATA

SOURCES USED:
- [operator name and date cited]"""

    query = f"fix for {equipment_id or 'equipment'} {incident[:100]}"
    search_result, fix_ids = search_expert_fixes(query, equipment_filter=equipment_id)

    # Citation tracking happens here, at retrieval time — not after the
    # orchestrator writes its report. See search_expert_fixes() docstring.
    _increment_expert_fix_citations(fix_ids)

    user_prompt = f"""Incident reported: {incident}

Expert fix search results:
{search_result}

Analyse whether a prior expert fix applies to this incident."""

    response = _groq_call_with_retry(
        lambda: groq_client.chat.completions.create(
            model=MODEL_FAST,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt}
            ],
            temperature=0.1, **completion_kwargs(MODEL_FAST, "specialist", 400)),
        call_type="specialist", model=MODEL_FAST,
        equip_tag=equipment_id,
        estimate=estimate_tokens([SYSTEM_PROMPT, user_prompt],
                                 _completion_cap(MODEL_FAST, "specialist", 400)))

    return {
        "agent":    "Expert Fix Agent",
        "icon":     "🎙",
        "findings": _flag_if_truncated(response, "specialist findings"),
        "raw_data": search_result,
        # The report guardrail (check_report) needs the raw text of any
        # unreviewed fix, to spot its values being turned into instructions.
        "unreviewed": [block for block in search_result.split("\n\n---\n\n")
                       if REVIEW_UNREVIEWED in block],
    }


# ── Specialist Agent: Maintenance Agent ───────────────────────────────────────

@traceable(name="maintenance_agent")
def run_maintenance_agent(incident, equipment_id=None):
    """
    Specialist: searches maintenance records for repair history and service patterns.
    Returns a structured findings dict.
    """
    SYSTEM_PROMPT = """You are the Maintenance History agent for PlantMind, a manufacturing plant AI system.

Your single job: analyse maintenance records to identify repair history and service patterns for the reported incident.

Rules:
- You have been given ONE tool result from a maintenance record search. Analyse it fully.
- Identify: what maintenance has been done on this equipment, when, by whom, and what was found.
- Look for: recurring failures, parts replaced, last service date, any known wear issues.
- If recent maintenance was done — note whether it was completed correctly or if issues were flagged.
- Never invent data. If the search returned no results, say so clearly.

Return your findings in this exact structure:

MAINTENANCE HISTORY FINDINGS:
- Last service: [date and what was done, or NOT FOUND]
- Recurring issues: [any repeat failures in the records]
- Recent work: [any maintenance in the last 30 days]
- Relevant findings: [anything in the records that relates to this incident]
- Data confidence: HIGH / MEDIUM / LOW / NO DATA

SOURCES USED:
- [list each source document name cited]"""

    query = f"maintenance service repair history for {equipment_id or 'equipment'} {incident[:100]}"
    search_result = search_plantmind(query, doc_type_filter="Work Instruction", equipment_filter=equipment_id)

    user_prompt = f"""Incident reported: {incident}

Maintenance record search results:
{search_result}

Analyse the maintenance history from this data."""

    response = _groq_call_with_retry(
        lambda: groq_client.chat.completions.create(
            model=MODEL_FAST,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt}
            ],
            temperature=0.1, **completion_kwargs(MODEL_FAST, "specialist", 400)),
        call_type="specialist", model=MODEL_FAST,
        equip_tag=equipment_id,
        estimate=estimate_tokens([SYSTEM_PROMPT, user_prompt],
                                 _completion_cap(MODEL_FAST, "specialist", 400)))

    return {
        "agent":    "Maintenance Agent",
        "icon":     "🔧",
        "findings": _flag_if_truncated(response, "specialist findings"),
        "raw_data": search_result
    }


# ── Specialist Agent: SOP Agent ────────────────────────────────────────────────

@traceable(name="sop_agent")
def run_sop_agent(incident, equipment_id=None):
    """
    Specialist: searches SOPs for correct response procedures and specifications.
    Returns a structured findings dict.
    """
    SYSTEM_PROMPT = """You are the Procedures agent for PlantMind, a manufacturing plant AI system.

Your single job: find the correct standard operating procedure and specifications for responding to the reported incident.

Rules:
- You have been given ONE tool result from an SOP search. Analyse it fully.
- Identify: the correct response procedure, any safety steps, shutdown sequence, and restart criteria.
- Extract specific values where present: temperature limits, pressure specs, torque values, clearance tolerances.
- Note: if the current incident deviates from what the SOP defines as normal operating range.
- Never invent procedures. If no SOP was found, state that clearly — it is a gap finding.

Return your findings in this exact structure:

SOP / PROCEDURE FINDINGS:
- Correct response procedure: [steps from the SOP, or NOT FOUND]
- Key specifications: [any values, limits, or tolerances from the documents]
- Safety requirements: [any safety steps or PPE requirements]
- SOP gap: [YES — no procedure found | NO — procedure exists]
- Data confidence: HIGH / MEDIUM / LOW / NO DATA

SOURCES USED:
- [list each source document name and revision cited]"""

    query = f"procedure response steps specification for {equipment_id or 'equipment'} alarm {incident[:100]}"
    search_result = search_plantmind(query, doc_type_filter="SOP", equipment_filter=equipment_id)

    user_prompt = f"""Incident reported: {incident}

SOP search results:
{search_result}

Extract the relevant procedures and specifications from this data."""

    response = _groq_call_with_retry(
        lambda: groq_client.chat.completions.create(
            model=MODEL_FAST,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt}
            ],
            temperature=0.1, **completion_kwargs(MODEL_FAST, "specialist", 400)),
        call_type="specialist", model=MODEL_FAST,
        equip_tag=equipment_id,
        estimate=estimate_tokens([SYSTEM_PROMPT, user_prompt],
                                 _completion_cap(MODEL_FAST, "specialist", 400)))

    return {
        "agent":    "SOP Agent",
        "icon":     "📋",
        "findings": _flag_if_truncated(response, "specialist findings"),
        "raw_data": search_result
    }


# ── Specialist Agent: NCR Agent ────────────────────────────────────────────────

@traceable(name="ncr_agent")
def run_ncr_agent(incident, equipment_id=None):
    """
    Specialist: searches NCR history for past quality incidents and corrective actions.
    Returns a structured findings dict.
    """
    SYSTEM_PROMPT = """You are the Quality & NCR agent for PlantMind, a manufacturing plant AI system.

Your single job: analyse non-conformance reports to identify past quality incidents and whether corrective actions were completed for the reported equipment.

Rules:
- You have been given ONE tool result from an NCR search. Analyse it fully.
- Identify: past NCRs on this equipment, what the non-conformance was, and what corrective action was taken.
- Look for: open NCRs (corrective action not completed), repeat NCRs on the same failure mode.
- An open NCR on this equipment related to this failure mode is a HIGH PRIORITY finding.
- Never invent NCR data. If no NCRs were found, state that clearly.

Return your findings in this exact structure:

NCR / QUALITY FINDINGS:
- Past NCRs found: [count and summary, or NONE FOUND]
- Open NCRs: [any NCRs without completed corrective action — HIGH PRIORITY if yes]
- Repeat failure mode: [YES with details | NO]
- Corrective actions completed: [summary of what was done]
- Data confidence: HIGH / MEDIUM / LOW / NO DATA

SOURCES USED:
- [list each source document name cited]"""

    query = f"non-conformance quality incident corrective action for {equipment_id or 'equipment'} {incident[:100]}"
    search_result = search_plantmind(query, doc_type_filter="NCR", equipment_filter=equipment_id)

    user_prompt = f"""Incident reported: {incident}

NCR search results:
{search_result}

Analyse the quality and non-conformance history from this data."""

    response = _groq_call_with_retry(
        lambda: groq_client.chat.completions.create(
            model=MODEL_FAST,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt}
            ],
            temperature=0.1, **completion_kwargs(MODEL_FAST, "specialist", 400)),
        call_type="specialist", model=MODEL_FAST,
        equip_tag=equipment_id,
        estimate=estimate_tokens([SYSTEM_PROMPT, user_prompt],
                                 _completion_cap(MODEL_FAST, "specialist", 400)))

    return {
        "agent":    "NCR Agent",
        "icon":     "📊",
        "findings": _flag_if_truncated(response, "specialist findings"),
        "raw_data": search_result
    }


# ── Orchestrator ───────────────────────────────────────────────────────────────

# -- Graph rules: derived from what the graph actually returned ---------------
# These were four rules hard-coded for WM-101 (burn-in, the tension trap, LOTO,
# quarantine) appended to EVERY investigation that had any graph data at all --
# so an HC-401 report was told it "MUST" include WM-101's burn-in instructions.
# A rule now appears only when the node it describes is in THIS equipment's
# retrieved chain.

_GRAPH_NODE_RULES = [
    ("burn_in_procedure",
     'The graph shows burn-in is MANDATORY after liner replacement. You MUST include this in '
     'immediate action: "Complete burn-in procedure after replacement. Run wire at 5.0 m/min '
     'for 30 seconds. Wire instability during burn-in is EXPECTED - not a new fault."'),
    ("operator_trap_pattern",
     'The graph documents an operator trap: the WRONG RESPONSE is to keep adjusting tension. '
     'You MUST include this warning: "Do NOT keep adjusting tension - this will not fix worn '
     'drive rolls and risks motor burnout." Cite the NCR named in the graph context.'),
    ("loto_procedure",
     "LOTO is required before any maintenance on this equipment - include it in immediate action."),
    ("quality_flag",
     "Parts welded during the fault event must be quarantined for inspection - include this "
     "in the impact section."),
]

_OPERATOR_PATTERN_RULE = (
    "OPERATOR-CONFIRMED PATTERNS - this graph contains patterns that came from an operator's "
    "field capture, reviewed and approved by a supervisor (NOT from formal SOP/NCR documents). "
    'They are introduced with "X operators confirmed" or "<name> found".\n'
    "   - Cite them by contributor name(s)/count exactly as given. Never call them "
    '"unverified" - the name/count IS the trust signal.\n'
    "   - Weight them BELOW a formal SOP/NCR fact, but above an unpromoted single expert-fix "
    "match.\n"
    "   - If one CONTRADICTS a formal SOP fact, do not decide which is correct: surface both, "
    "label it a contradiction, and recommend engineering review."
)

# Added Phase 1B after a live test. The report correctly flagged that an
# operator note ("normal arc voltage is 15-16 V, reset to 15.5 V") contradicted
# the SOP's 18-22 V — and then put "set arc voltage to 15.5 V" in the repair
# steps. Surfacing a contradiction and then acting on the losing side is worse
# than not noticing it: the operator follows the steps, not the discussion.
_DISPUTED_VALUE_RULE = (
    "NUMBERS IN INSTRUCTIONS - when a documented specification (SOP/NCR/work instruction, "
    "or a graph SPECIFICATION line) and an operator's note give DIFFERENT values for the same "
    "setting, threshold or range:\n"
    "   - The documented specification is the one to follow. Use ONLY its value in the steps.\n"
    "   - Never write an instruction that sets, resets or targets the operator's value. It may "
    "be mentioned in the findings as a contradiction to review - never in HOW TO ADDRESS IT.\n"
    "   - If the graph marks a claim DISPUTED or REJECTED, treat it as wrong: state that it was "
    "reviewed and rejected, give the documented value instead, and do not act on it."
)


def _build_graph_rules(graph_context):
    """Build the STRICT GRAPH RULES block from the nodes actually retrieved."""
    nodes    = graph_context.get("chain_nodes", []) or []
    # Phase 2a: only the matched fault's path. Built from every node, the
    # burn-in rule fired whenever the burn-in NODE existed, so gas-alarm and
    # hot-tip reports were ordered to include burn-in. Older contexts (the
    # backup file) have no relevant_node_ids and keep the old behaviour.
    relevant = graph_context.get("relevant_node_ids")
    node_ids = set(relevant) if relevant is not None else {n.get("id") for n in nodes}
    nodes    = [n for n in nodes if n.get("id") in node_ids]
    rules    = [text for node_id, text in _GRAPH_NODE_RULES if node_id in node_ids]

    if any((n.get("properties") or {}).get("operator_summary") for n in nodes):
        rules.append(_OPERATOR_PATTERN_RULE)

    # Always included: the Expert Fix agent can surface an operator's numbers
    # from Pinecone even when the graph holds no operator note at all, and
    # those numbers must never end up in the instructions.
    rules.append(_DISPUTED_VALUE_RULE)

    # True for every machine, so it is always included.
    # Phase 2a: this used to say "Use ONLY facts present in the knowledge graph
    # context", which contradicted the main rule "only use evidence the
    # specialists found". The trust order in the system prompt replaces both.
    rules.append("Do not import procedures, part numbers or thresholds from other equipment.")

    numbered = "\n".join("{}. {}".format(i + 1, r) for i, r in enumerate(rules))
    return "STRICT GRAPH RULES - VIOLATION IS AN ERROR:\n" + numbered


# ── Report guardrails (Phase 2a) ───────────────────────────────────────────────
# Defence in depth: the prompt ASKS for the trust order; this code CHECKS the
# finished report for the rules that must never break, and makes any breach
# visible. No extra AI call. Fixing a breach by re-asking the model is a
# Phase 4 validator node (at most one retry); here we warn and log.

_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
_TIP_STOPWORDS = {"after", "before", "which", "their", "there", "these", "those", "check",
                  "replace", "should", "would", "about", "using", "other", "first", "again",
                  "welding", "machine", "fixed", "operator", "found", "because", "while",
                  "where", "until", "every", "being", "steps", "reproducible"}


def _criticality_floor(graph_context):
    """A matched fault the graph marks CRITICAL sets a floor on the rating."""
    if not graph_context or not graph_context.get("has_data"):
        return None, ""
    # Never from a guess (Phase 2a step A): a close call between "pressure
    # dropped" and Glass Breakage must not push a pressure drop to CRITICAL.
    if graph_context.get("match_confidence") in ("unsure", "none"):
        return None, ""
    matched = set(graph_context.get("matched_faults") or [])
    for n in graph_context.get("chain_nodes", []) or []:
        p = n.get("properties") or {}
        crit = str(p.get("criticality", "")).strip()
        if n.get("type") == "Fault" and n.get("label") in matched and crit.upper().startswith("CRITICAL"):
            src = f" [source: {p['source']}]" if p.get("source") else ""
            return "CRITICAL", f"{crit}{src}"
    return None, ""


def _tips_to_guard(graph_context, specialist_results):
    """(who, text, kind) for every unreviewed tip found, and every rejected claim."""
    tips = []
    for r in specialist_results or []:
        for block in r.get("unreviewed", []) or []:
            m = re.search(r"\[Expert Fix — ([^,|\]]+)", block)
            body = block.split("]\n", 1)[-1]
            tips.append(((m.group(1).strip() if m else ""), body, "an UNREVIEWED operator tip"))
    relevant = set((graph_context or {}).get("relevant_node_ids") or [])
    for n in (graph_context or {}).get("chain_nodes", []) or []:
        p = n.get("properties") or {}
        if p.get("status") == "disputed" and (not relevant or n.get("id") in relevant):
            tips.append((p.get("contributors", ""), p.get("operator_summary", ""),
                         "a REJECTED operator claim"))
    return tips


def _flag_lines(section, who, body, kind):
    """Lines in HOW TO ADDRESS IT that repeat a tip's values or name its author."""
    body = re.sub(r"\b[A-Z]{1,3}-\d+\b|\d{4}-\d{2}-\d{2}", " ", body)   # tags, dates
    numbers, keywords = set(), set()
    for sentence in re.split(r"(?<=[.;:\n])\s+", body):
        nums = [n for n in re.findall(r"\d+(?:\.\d+)?", sentence) if len(n) >= 2 or "." in n]
        if nums:
            numbers.update(nums)
            keywords.update(w for w in re.findall(r"[a-z]{5,}", sentence.lower())
                            if w not in _TIP_STOPWORDS)
    surname = max(re.findall(r"[A-Za-z]{3,}", who or ""), key=len, default="").lower()
    flagged = []
    for line in section.splitlines():
        low = line.lower()
        by_name = bool(surname) and surname in low
        by_value = (any(re.search(rf"(?<![\d.]){re.escape(n)}(?![\d.])", line) for n in numbers)
                    and any(k in low for k in keywords))
        if line.strip() and (by_name or by_value):
            flagged.append(line)
    return flagged


@traceable(name="report_guardrails")
def check_report(report, graph_context, specialist_results):
    """
    Check a finished report against the rules that must never break.
    Returns (report, events): the report with any breach made visible, and a
    list of what fired (printed, traced in LangSmith, read by evals).

      1. Criticality floor: a matched fault the graph marks CRITICAL (e.g.
         shielding gas low) cannot be rated lower. The rating is raised and
         the report says so and why.
      2. Unreviewed tips: a step in HOW TO ADDRESS IT that repeats an
         unreviewed tip's values, or names its author, gets a visible warning.
         Same for a claim a reviewer rejected.
    """
    text, events = report or "", []

    floor, why = _criticality_floor(graph_context)
    at = text.find("HOW CRITICAL IS IT")
    if floor and at != -1:
        m = re.search(r"\b(CRITICAL|HIGH|MEDIUM|LOW)\b", text[at + len("HOW CRITICAL IS IT"):])
        if m and _RANK[m.group(1)] < _RANK[floor]:
            start = at + len("HOW CRITICAL IS IT") + m.start()
            end = start + len(m.group(1))
            rest = text[end:]
            nl = rest.find("\n")
            note = f"\n- Raised from {m.group(1)} to {floor} by a safety rule: {why}"
            rest = rest[:nl] + note + rest[nl:] if nl != -1 else rest + note
            text = text[:start] + floor + rest
            events.append(f"criticality raised {m.group(1)} -> {floor}")

    s = text.find("HOW TO ADDRESS IT")
    if s != -1:
        e = text.find("PLANT MANAGER SUMMARY", s)
        e = e if e != -1 else len(text)
        section = text[s:e]
        warned, done = section, set()
        for who, body, kind in _tips_to_guard(graph_context, specialist_results):
            for line in _flag_lines(section, who, body, kind):
                if line in done:   # one warning per line, whichever tip matched first
                    continue
                done.add(line)
                warning = (f"\n  ⚠ CHECK: this step comes from {kind}"
                           f"{' (' + who + ')' if who else ''}. It is not in any SOP or work "
                           f"instruction. Follow the documented procedure unless an engineer "
                           f"approves this change.")
                warned = warned.replace(line, line + warning, 1)
                events.append(f"{kind} in instructions: {line.strip()[:80]}")
        text = text[:s] + warned + text[e:]

    for ev in events:
        print(f"  [guardrail] {ev}")
    return text, events


# ── Report confidence (Phase 2a step B) ──────────────────────────────────────
# Every report used to SOUND equally sure, whether the fault was confirmed and
# the SOP found, or the system was guessing. This works out, in code, how much
# the report can be trusted and whether an engineer should look at it. Three
# levels with reasons, not a percentage: a number like "83%" would claim a
# precision nobody has. Separate from criticality (danger), which it never touches.

_DOC_AGENTS = {"Alarm Agent", "Maintenance Agent", "SOP Agent", "NCR Agent"}


def _found_evidence(result):
    raw = str(result.get("raw_data") or "")
    findings = str(result.get("findings") or "")
    return (bool(raw.strip()) and not raw.startswith("NO_DATA")
            and "Data confidence: NO DATA" not in findings
            and not findings.startswith("Agent failed"))


def assess_confidence(graph_context, specialist_results, guard_events=()):
    """
    Returns {"level": HIGH|MEDIUM|LOW, "reasons": [...], "review": bool,
             "review_reasons": [...]}.

      LOW     no known fault matched, or no documents found at all, or 2+
              reasons for doubt together
      MEDIUM  one reason for doubt (fault not confirmed, no graph for this
              machine, graph in backup mode, only one source, no SOP section...)
      HIGH    fault confirmed, graph available, documents found
    Engineer review is needed when the level is not HIGH, or a safety guard
    fired (an unreviewed tip reached the repair steps; the rating was raised).
    """
    low, medium, review_reasons = [], [], []
    ctx = graph_context or {}

    if not ctx.get("has_data"):
        medium.append("knowledge graph unavailable: documents only" if ctx.get("degraded")
                      else "no knowledge graph for this machine: documents only")
    else:
        if ctx.get("degraded"):
            medium.append("knowledge graph in backup mode (database unreachable)")
        conf = ctx.get("match_confidence")
        faults = " or ".join(ctx.get("matched_faults") or [])
        if conf == "unsure":
            medium.append(f"fault not confirmed (close call: {faults})")
        elif conf == "none":
            low.append("no known fault matched the description")
        elif conf == "words only":
            medium.append("fault matched by word count only (meaning check unavailable)")

    results = specialist_results or []
    searched = [r for r in results if r.get("agent") in _DOC_AGENTS]
    found = [r for r in searched if _found_evidence(r)]
    failed = [r["agent"] for r in results if str(r.get("findings", "")).startswith("Agent failed")]
    if searched and not found:
        low.append("no documents found for this incident")
    elif len(searched) > 1 and len(found) == 1:
        medium.append(f"only one source found evidence ({found[0]['agent'].replace(' Agent', '')})")
    if any(r["agent"] == "SOP Agent" for r in searched) and not any(r["agent"] == "SOP Agent" for r in found):
        medium.append("no SOP section found")
    for a in failed:
        medium.append(f"{a} failed")

    for ev in guard_events or ():
        if ev.startswith("criticality raised"):
            review_reasons.append("the rating was raised by a safety rule")
        elif "operator tip" in ev or "operator claim" in ev:
            review_reasons.append("an unreviewed or rejected operator tip reached the repair steps")

    level = "LOW" if low or len(medium) >= 2 else ("MEDIUM" if medium else "HIGH")
    review_reasons = list(dict.fromkeys(review_reasons))
    return {"level": level, "reasons": low + medium, "review": level != "HIGH" or bool(review_reasons),
            "review_reasons": review_reasons,
            "found": [r["agent"].replace(" Agent", "") for r in found]}


def add_confidence_block(report, assessment, graph_context=None):
    """A short REPORT CONFIDENCE section right under the report title."""
    a = assessment
    if a["reasons"]:
        why = "; ".join(a["reasons"])
    else:
        fault = ", ".join((graph_context or {}).get("matched_faults") or []) or "the fault"
        why = (f"fault identified ({fault}), knowledge graph available, evidence from "
               f"{', '.join(a['found']) or 'the documents'}")
    if a["review"]:
        need = "; ".join(a["review_reasons"]) or "confidence is not HIGH"
        review = f"NEEDED — {need}"
    else:
        review = "not needed"
    block = ("REPORT CONFIDENCE:\n"
             f"- Level: {a['level']} (worked out by code from the evidence, not by the AI)\n"
             f"- Why: {why}\n"
             f"- Engineer review: {review}\n")
    text = report or ""
    title = text.find("INVESTIGATION REPORT")
    if title == -1:
        return block + "\n" + text
    eol = text.find("\n", title)
    # Keep a divider line (═══) that follows the title attached to it.
    nxt = text.find("\n", eol + 1) if eol != -1 else -1
    if eol != -1 and nxt != -1 and re.fullmatch(r"[\s═=\-─]*", text[eol + 1:nxt]) and text[eol + 1:nxt].strip():
        eol = nxt
    if eol == -1:
        return text + "\n\n" + block
    return text[:eol + 1] + "\n" + block + "\n" + text[eol + 1:]


# Trust tier of each specialist's findings (Phase 2a trust order). Operator
# knowledge carries its own per-fix label: TIER 3 APPROVED or TIER 4 UNREVIEWED.
_TIER_BY_AGENT = {
    "Alarm Agent":       "TIER 2 · EVENTS — shift logs: what happened, not what to do",
    "Maintenance Agent": "TIER 2 · DOCUMENTS — work instructions",
    "SOP Agent":         "TIER 2 · DOCUMENTS — standard operating procedures",
    "NCR Agent":         "TIER 2 · DOCUMENTS — non-conformance reports",
    "Expert Fix Agent":  "OPERATOR KNOWLEDGE — each fix is labelled TIER 3 APPROVED or TIER 4 UNREVIEWED",
}


@traceable(name="orchestrator")
def run_orchestrator(incident, specialist_results, graph_context=None, equipment_id=None):
    """
    Receives all four specialist findings and synthesizes the final investigation report.
    Produces two reports: technical (maintenance engineer) + plain language (plant manager).
    Never touches Pinecone — reasons only over specialist findings.

    graph_context: optional plain-English fault chain from knowledge graph.
    When present, adds relationship context the RAG chunks cannot provide
    (e.g. liner replacement → requires → burn-in procedure).
    """
    SYSTEM_PROMPT = """You are the Investigation Orchestrator for PlantMind, a manufacturing plant AI system.

You receive structured findings from four specialist agents and synthesize them into a final investigation report.

Your rules:
1. Only use the evidence you are given: the knowledge graph context and the specialist
   findings, together. Never add information that neither of them contains.
2. Every piece of evidence is labelled with a TRUST TIER. When sources disagree, follow
   the TRUST ORDER below, state both, and say which one you followed and why. When two
   sources of the SAME tier disagree, do not pick one: recommend engineering review.
3. When a specialist returned NO DATA — that absence is itself a finding (e.g. no SOP = procedure gap).
4. Data confidence (HIGH > MEDIUM > LOW > NO DATA) ranks findings WITHIN a tier. It never
   lifts a finding above a higher tier.
5. The report has TWO sections — technical and plain language. Both are required.

TRUST ORDER — by kind of fact:
   - Specifications, settings, limits, part numbers and repair procedures:
     TIER 1 VERIFIED (knowledge graph) > TIER 2 DOCUMENTS (SOP, work instruction, NCR)
     > TIER 3 APPROVED operator knowledge. A TIER 4 UNREVIEWED operator tip NEVER sets a
     value, a setting or a step in HOW TO ADDRESS IT.
   - What is happening now (alarm counts, timing, recent changes): TIER 2 EVENTS (shift logs).
   - Safety steps: include every safety step from any tier. The most cautious one wins.
   Why: controlled documents are reviewed and approved; an unreviewed tip is one person's
   account that nobody has checked yet.

6. OPERATOR KNOWLEDGE RULES — follow strictly:
   - Cite operator knowledge by the operator's NAME. Use a job title ONLY if the source
     text actually carries one — never invent or assume one.
   - TIER 3 APPROVED knowledge (reviewed in the Review queue): may be the FIRST thing
     named under IMMEDIATE ACTION. When it contains reproducible numbered steps,
     REPRODUCE THEM VERBATIM, in order, so the report can be followed like a checklist.
   - TIER 4 UNREVIEWED tip: call it an "unreviewed operator tip (<name>)". Mention it only
     under diagnosis, as a lead to check. Never copy its values or steps into HOW TO
     ADDRESS IT. If it disagrees with TIER 1 or TIER 2, say so and follow TIER 1 or 2.
   - When operator knowledge is flagged as insufficient detail ("treat as a lead, not a
     procedure"), present it as a lead and say so plainly rather than inventing steps.
   - If APPROVED knowledge contradicts a TIER 1 or TIER 2 fact, surface BOTH, label it a
     contradiction, follow the documented fact in HOW TO ADDRESS IT, and recommend
     engineering review.
7. CRITICALITY RULES — follow strictly:
   - Three or more alarms of same type in one shift = HIGH minimum (recurring fault indicator)
   - Any fault requiring LOTO or production stop = HIGH minimum
   - Worn components with documented NCR history = HIGH
   - Safety events (electrical, fire, fumes, injury to a person, or foreign material such
     as glass or metal that could end up in the product) = CRITICAL
   - If a TIER 1 or TIER 2 document states a criticality for this kind of event, rate it
     at least that. Never rate below what the document says.
   Never downgrade below HIGH when evidence shows recurring fault or production stop required.

FORMATTING RULES (follow these EXACTLY — do not deviate):
- Output PLAIN TEXT only. Do NOT use Markdown: no ** for bold, no * for italics,
  no # headings, no backticks. The section headers below are the only headers.
- Use simple single-level "- " bullets. Do NOT nest bullets or create
  sub-sub-lists. One fact per bullet, kept to a single line where possible.
- Reproduce the section structure below verbatim, including the ═ divider lines.
- Be concise. Prefer short, direct bullets over long paragraphs.

Produce the report in exactly this format:

═══════════════════════════════════════
INVESTIGATION REPORT — TECHNICAL
═══════════════════════════════════════

SOURCE DATA:
- List every data point used with exact source document and timestamp

WHAT IS THE ISSUE:
- Root cause with evidence from specialist findings
- What is different about this occurrence vs historical pattern

WHAT IS THE IMPACT:
- Production impact (line down / degraded / at risk)
- Safety risk: HIGH / MEDIUM / LOW
- Financial impact if determinable from the data

HOW CRITICAL IS IT:
- CRITICAL / HIGH / MEDIUM / LOW
- One sentence justification

HOW TO ADDRESS IT:
- Immediate action (numbered steps in correct sequence — safety first, then fix, then verify)
  Step 1: Safety — LOTO, stop production, isolate
  Step 2: Diagnosis — what to inspect
  Step 3: Fix — what to replace or repair
  Step 4: Verify — post-fix checks, and any run-in or first-product check the procedure requires
  Step 5: Quality — parts to quarantine or inspect
- Root cause fix (permanent solution)
- Preventive action (stops recurrence)
- Who to notify

═══════════════════════════════════════
PLANT MANAGER SUMMARY
═══════════════════════════════════════

SITUATION: [One sentence — what happened]
ROOT CAUSE: [One sentence — why it happened, in plain language]
STATUS: [One sentence — is the line running, stopped, or at risk]
ACTION REQUIRED: [One sentence — the single most important thing to do right now]
RISK IF NOT ACTIONED: [One sentence — what happens if nothing is done]"""

    # Format all specialist findings into one block for the orchestrator
    findings_block = ""
    for result in specialist_results:
        findings_block += f"\n\n{'─'*50}\n"
        findings_block += f"{result['icon']} {result['agent'].upper()} FINDINGS\n"
        findings_block += f"[{_TIER_BY_AGENT.get(result['agent'], 'TIER 2 · DOCUMENTS')}]\n"
        findings_block += f"{'─'*50}\n"
        findings_block += result["findings"]

    # Build graph context block if available
    graph_block = ""
    if graph_context and graph_context.get("has_data") and graph_context.get("chain_text"):
        # Build mandatory warnings section from graph
        warnings = graph_context.get("warnings", [])
        downtime = graph_context.get("downtime", "")

        mandatory_warnings = ""
        if warnings:
            mandatory_warnings = "\n\nMANDATORY REQUIREMENTS FROM KNOWLEDGE GRAPH (you MUST include ALL of these):"
            for w in warnings:
                mandatory_warnings += f"\n  ⚠️  {w}"

        if downtime:
            mandatory_warnings += f"\n  ⏱  Estimated downtime: {downtime} — include this in the impact section."

        graph_block = f"""

─────────────────────────────────────────────────────
[TIER 1 · VERIFIED] KNOWLEDGE GRAPH CONTEXT — facts taken from the SOP, work
instruction and NCR and checked by a person, each with its source. Operator
patterns shown here were approved in the Review queue (TIER 3); a DISPUTED
claim was reviewed and rejected — never use it.
─────────────────────────────────────────────────────
{graph_context["chain_text"]}
─────────────────────────────────────────────────────{mandatory_warnings}

{_build_graph_rules(graph_context)}
─────────────────────────────────────────────────────"""

    # B1 - when the graph is missing, or came from the local fallback file, the
    # report must SAY so. A quietly thinner report is the failure mode we found:
    # the same WM-101 question produced different safety content depending on
    # whether the database happened to be awake.
    degraded_note = ""
    if graph_context and graph_context.get("degraded"):
        if graph_context.get("source") == "local_file":
            detail = ("knowledge graph database unavailable; equipment facts came from the local "
                      "backup copy and operator-confirmed patterns are NOT included")
        else:
            detail = ("knowledge graph unavailable; equipment-specific warnings are NOT included "
                      "in this report - check the SOP manually before acting")
        degraded_note = ("\n\nSYSTEM NOTE - DEGRADED MODE (you MUST reproduce this line verbatim "
                         "as the last bullet of SOURCE DATA):\n- DEGRADED: " + detail + ".")

    user_prompt = f"""Incident: {incident}

Specialist agent findings:
{findings_block}{graph_block}{degraded_note}

Synthesize the final investigation report from these findings."""

    # ── First pass — initial report ─────────────────────────────────
    # Teaching note: This is the same as before — one LLM call to
    # synthesise the specialist findings into a structured report.
    response = _groq_call_with_retry(
        lambda: groq_client.chat.completions.create(
            model=MODEL_DEEP,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt}
            ],
            temperature=0.1, **completion_kwargs(MODEL_DEEP, "orchestrator", 1400)),
        call_type="orchestrator", model=MODEL_DEEP,
        equip_tag=equipment_id or "",
        graph_source=(graph_context or {}).get("source", "none"),
        estimate=estimate_tokens([SYSTEM_PROMPT, user_prompt],
                                 _completion_cap(MODEL_DEEP, "orchestrator", 1400)))

    initial_report = _flag_if_truncated(response, "investigation report")

    # ── Reflection pass — second LLM critiques and improves ──────────
    # Only runs when ENABLE_REFLECTION=true (set in .env or environment)
    if not ENABLE_REFLECTION:
        return initial_report
    # Teaching note: This is the REFLECTION PATTERN.
    # A second LLM call reads the first report and asks:
    #   - What did I miss?
    #   - Did I correctly connect the maintenance history to the SOP?
    #   - Is the criticality rating justified by the evidence?
    #   - Are there contradictions I glossed over?
    # Then it rewrites the report with those gaps filled.
    #
    # Key insight: LLMs are better at *critiquing* than *generating*.
    # The first pass produces something plausible. The second pass
    # catches the logical gaps that a single-pass LLM skips over.

    REFLECTION_PROMPT = """You are a senior maintenance engineer reviewing an AI-generated investigation report.

Your job is to critique the report and rewrite it with improvements.

STRICT RULES:
- Do NOT downgrade a CRITICAL rating unless you have clear evidence it is wrong.
- Do NOT add safety risk labels that contradict the overall criticality rating.
- Do NOT invent new facts — only use evidence already in the specialist findings.
- If criticality is already correct, keep it exactly as is.

Check for these specific failure patterns:
1. MISSED CONNECTIONS — did the report fail to link a maintenance event to a SOP requirement?
   Example: liner was replaced + SOP says burn-in required after liner change = must be connected.
   Example: sensor reading high after cleaning + SOP says false readings possible post-clean = explain it.
2. WRONG CRITICALITY — only change if clearly wrong.
   Safety events (exhaust fan failure, solvent exposure, fire risk) = CRITICAL. Do not downgrade.
   Expected behaviour after maintenance (burn-in period, calibration drift) = LOW or MEDIUM.
3. IGNORED CONTRADICTIONS — if sensor reads high but visual inspection is normal,
   the report must explain why (e.g. sensor residue after cleaning), not treat it as a real fault.
4. INCOMPLETE ACTIONS — are immediate, root cause, and preventive actions all present?

Rewrite the full report with gaps corrected.
Keep the exact same format (INVESTIGATION REPORT — TECHNICAL + PLANT MANAGER SUMMARY)."""

    reflection_response = _groq_call_with_retry(
        lambda: groq_client.chat.completions.create(
            model=MODEL_DEEP,
            messages=[
                {"role": "system", "content": REFLECTION_PROMPT},
                {"role": "user",   "content": f"Original report to critique and improve:\n\n{initial_report}\n\nNote: The report above was synthesised from shift logs, maintenance records, SOPs, and NCR history for this equipment. Improve it using only what is already stated in the report."}
            ],
            temperature=0.1, **completion_kwargs(MODEL_DEEP, "reflection", 600)),
        call_type="reflection", model=MODEL_DEEP,
        estimate=estimate_tokens([REFLECTION_PROMPT, initial_report],
                                 _completion_cap(MODEL_DEEP, "reflection", 600)))

    return _flag_if_truncated(reflection_response, "reflection pass")


# ── Supervisor Agent ──────────────────────────────────────────────────────────
#
# Teaching concept: dynamic agent orchestration.
# The supervisor reads the incident and decides which specialists to call.
# This replaces the fixed fan-out (always run all 4) with intelligent routing.
#
# Benefits:
#   - Fewer tokens: a first-time failure needs 2 agents, not 4
#   - Better reports: orchestrator gets focused findings, not empty results
#   - More investigations per day on free tier
#
# Routing logic:
#   RECURRING / PATTERN  → Alarm + Maintenance + NCR  (history matters)
#   QUALITY / WELD       → Alarm + NCR + SOP          (spec + history)
#   SAFETY / URGENT      → SOP only                   (procedure first)
#   MAINTENANCE / REPAIR → Maintenance + SOP           (what was done + spec)
#   UNKNOWN / GENERAL    → all 4                      (safe default)

SUPERVISOR_PROMPT = """You are a maintenance investigation supervisor at a manufacturing plant.

Read the incident description and decide which specialist agents to dispatch.
Choose the MINIMUM set needed — do not dispatch agents that will find nothing.

Available agents:
  alarm       — searches shift logs for alarm history and patterns
  expert_fix  — searches senior-operator field captures (PM-IK-001) for a
                prior fix on this exact fault pattern — check this whenever
                a specific equipment tag is known, it's often the fastest
                path to resolution and costs nothing to check
  maintenance — searches work instructions: repair and replacement procedures
  sop         — searches SOPs for procedures and specifications
  ncr         — searches non-conformance reports for quality incidents

Routing rules:
  - Whenever equipment is identified, include expert_fix alongside alarm —
    a prior operator fix, if one exists, is the single highest-value lead
  - Recurring alarm or "third time this week" → alarm + expert_fix + maintenance + ncr
  - Weld quality or spatter issue → alarm + expert_fix + ncr + sop
  - Safety event (exhaust fan, fumes, fire risk) → sop (urgent procedure first)
  - Wire feed, liner, arc, or stuttering → alarm + expert_fix + maintenance + sop
  - Any issue where recent maintenance could be relevant → always include maintenance
  - First-time failure, no history → expert_fix + maintenance + sop
  - Conflicting sensor readings → sop + maintenance (spec + recent work)
  - Unknown or general → all five agents

Think first, then choose. Write the "reason" BEFORE the "agents" list, and make
the list follow directly from your reason — every agent you name in the reason
must appear in the list, and vice versa. Choose 1-5 agents based purely on what
THIS incident needs; do not default to a fixed number.

Respond with ONLY a JSON object, nothing else, with "reason" first:
{"reason": "one sentence explanation", "agents": ["alarm", "expert_fix", "maintenance"]}

Examples (study how the agent list matches the reasoning):

Incident: "P-201 tripped again — that's the third overload this week and parts are piling up."
{"reason": "Recurring overload ('third this week') with quality impact — check for a prior expert fix, alarm history, recent maintenance, and any non-conformances.", "agents": ["alarm", "expert_fix", "maintenance", "ncr"]}

Incident: "Getting heavy spatter on the welds from WR-401 this shift, welds look out of spec."
{"reason": "Weld-quality/spatter issue — need alarm log for onset, a prior expert fix if one exists, NCRs for quality history, and the SOP spec.", "agents": ["alarm", "expert_fix", "ncr", "sop"]}

Incident: "Exhaust fan on the booth stopped and fumes are building up — what do we do right now?"
{"reason": "Safety event needing the correct urgent procedure first, not history.", "agents": ["sop"]}

Incident: "Wire feed on WM-101 is stuttering, started right after yesterday's service."
{"reason": "Wire-feed fault tied to recent work — check for a prior expert fix, then maintenance history and the feed-setup spec.", "agents": ["alarm", "expert_fix", "maintenance", "sop"]}

Incident: "New robot CV-410 threw an error on first run, no prior history."
{"reason": "First-time failure with no history — check for any expert fix on record, maintenance done, and the setup procedure.", "agents": ["expert_fix", "maintenance", "sop"]}

Incident: "Something seems off on Line 3 but I can't tell what."
{"reason": "Vague/general report with no clear signal — cast wide with all specialists.", "agents": ["alarm", "expert_fix", "maintenance", "sop", "ncr"]}

When the message lists agents as ALREADY REQUIRED, they will run whatever you
choose. Decide only whether this incident needs any OTHER agent as well.

Valid agent names: alarm, expert_fix, maintenance, sop, ncr"""

ALL_AGENTS = ["alarm", "expert_fix", "maintenance", "sop", "ncr"]
# Which search holds the facts of each kind of document on the graph.
_DOC_TYPE_TO_AGENT = {"SOP": "sop", "Work Instruction": "maintenance", "NCR": "ncr"}


def required_agents(graph_context, equipment_id=None):
    """
    The searches that MUST run, decided in code (Phase 2a step 4).

    Hybrid routing: rules decide what must happen, the supervisor AI may only
    add to it. The routing check found the supervisor sent every search the
    graph pointed to in only 1 of 6 cases, and never searched the SOP for a
    gas alarm, although the gas rules live in the SOP.

      - machine known          -> alarm + expert_fix (was a prompt rule)
      - graph matched a fault  -> the search for each document type its facts
                                  come from: SOP -> sop, Work Instruction ->
                                  maintenance, NCR -> ncr
    Returns (agents, documents) so the routing line can say why.
    """
    need, docs = set(), []
    if equipment_id:
        need.update({"alarm", "expert_fix"})
    ctx = graph_context or {}
    if ctx.get("has_data") and ctx.get("matched_faults"):
        by_id = {n["id"]: n for n in ctx.get("chain_nodes", []) or []}
        for nid in ctx.get("relevant_node_ids", []) or []:
            n = by_id.get(nid)
            if n and n.get("type") == "Document":
                dtype = (n.get("properties") or {}).get("type", "")
                if dtype in _DOC_TYPE_TO_AGENT:
                    need.add(_DOC_TYPE_TO_AGENT[dtype])
                    docs.append(dtype)
    return [a for a in ALL_AGENTS if a in need], sorted(set(docs))


@traceable(name="supervisor")
def supervisor_route(incident, equipment_id=None, graph_context=None):
    """
    Decide which specialist searches run. Returns (agents, reason).

    The graph sets a minimum (required_agents); the supervisor AI can only ADD
    to it, never drop from it. Without a graph match this behaves as before.
    Falls back to all five agents if the AI's answer is unusable.
    """
    required, docs = required_agents(graph_context, equipment_id)
    user_msg = f"Incident: {incident}"
    if equipment_id:
        user_msg += "\nEquipment: " + str(equipment_id)
    matched = (graph_context or {}).get("matched_faults") or []
    if matched:
        user_msg += (f"\nKnowledge graph matched: {', '.join(matched)}. "
                     f"Its facts come from: {', '.join(docs) or 'no linked documents'}.")
    if required:
        user_msg += f"\nALREADY REQUIRED (will run): {', '.join(required)}"

    def combine(ai_agents, ai_reason):
        added = [a for a in ai_agents if a not in required]
        agents = [a for a in ALL_AGENTS if a in required or a in ai_agents]
        why = []
        if required:
            why.append(f"required by {'the graph' if matched else 'the machine'}: {', '.join(required)}")
        if added:
            why.append(f"added by supervisor: {', '.join(added)}")
        return agents, (" · ".join(why) + (f" — {ai_reason}" if ai_reason else ""))

    try:
        response = _groq_call_with_retry(
            lambda: groq_client.chat.completions.create(
                model=MODEL_FAST,   # fast tier is fine for classification
                messages=[
                    {"role": "system", "content": SUPERVISOR_PROMPT},
                    {"role": "user",   "content": user_msg}
                ],
                temperature=0.0,   # deterministic routing
                **completion_kwargs(MODEL_FAST, "supervisor", 100)
            ),
            call_type="supervisor",
            model=MODEL_FAST,
            equip_tag=equipment_id or "",
            estimate=estimate_tokens([SUPERVISOR_PROMPT, user_msg],
                                     _completion_cap(MODEL_FAST, "supervisor", 100))
        )

        raw = response.choices[0].message.content or ""

        # Robustly extract the JSON, tolerating reasoning text / fences that
        # GPT-OSS models can wrap around it (see models.extract_json).
        data = extract_json(raw)
        agents = data.get("agents", [])
        reason = data.get("reason", "")

        # Validate — only accept known agent names
        valid = {"alarm", "expert_fix", "maintenance", "sop", "ncr"}
        agents = [a for a in agents if a in valid]

        # Always need at least 1 agent — fall back to all 5 if routing fails
        if len(agents) < 1 and not required:
            return list(ALL_AGENTS), "fallback — routing returned empty list"

        return combine(agents, reason)

    except Exception as e:
        print(f"  Supervisor routing failed: {e} — using all agents")
        return list(ALL_AGENTS), "fallback — routing error"


# ── Parallel Coordinator + Streaming Generator ─────────────────────────────────

@traceable(name="investigation", reduce_fn=join_stream)
def investigate_incident(incident, equipment_id=None):
    """
    Generator — supervisor routes to relevant agents, then orchestrates.
    Yields progress updates and the final report for streaming to the UI.

    Architecture change from PM-037:
      Before: always runs all 4 agents (fixed fan-out)
      After:  supervisor reads incident → selects 1-4 agents (dynamic routing)

    Benefits: fewer tokens, better focused reports, more investigations/day.
    Falls back to all 4 agents if supervisor classification fails.
    """

    # Use passed equipment_id or extract from incident text as fallback
    if not equipment_id:
        import re
        equipment_match = re.search(r'\b([A-Z]{1,3}-\d{2,4})\b', incident)
        equipment_id = equipment_match.group(1) if equipment_match else None

    # Never investigate across every machine (2026-10-01). The web page stops
    # with "No matching equipment manual found" before getting here; this
    # stops any other caller too.
    if not equipment_id:
        yield ("⚠️ No matching equipment manual found. Please select the machine selector "
               "below (e.g., WM-101) or upload the required documents to proceed.\n")
        return

    yield "🔍 Multi-agent investigation started...\n\n"
    yield f"📍 Equipment identified: {equipment_id}\n\n"

    # ── Fetch knowledge graph context ────────────────────────────────────────
    # Silent fail — graph enrichment is optional, never blocks investigation
    graph_context = None
    # EVAL ONLY — PM_EVAL_DISABLE_GRAPH=true skips the graph step entirely (no
    # Neo4j, no local backup file), so an ablation test can compare "documents
    # only" against "documents + graph" on the same questions. Read per call,
    # so evals/graph_value_test.py can flip it between runs. Never set it in
    # .env: app.py prints a warning at startup if it is on.
    graph_disabled = os.getenv("PM_EVAL_DISABLE_GRAPH", "").strip().lower() == "true"
    if graph_disabled:
        yield "🧪 Knowledge graph OFF (eval switch) — documents only.\n\n"
    if equipment_id and not graph_disabled:
        try:
            from knowledge_graph import get_fault_chain
            # Pass the operator's own words: the graph text then leads with the
            # fault that matches THIS incident, instead of dumping every fault
            # the machine can have into every report (Phase 1B usage fix).
            graph_context = get_fault_chain(equipment_id, incident_text=incident)
            if graph_context and graph_context.get("has_data"):
                node_count = len(graph_context.get("chain_nodes", []))
                warn_count = len(graph_context.get("warnings", []))
                if graph_context.get("degraded"):
                    # Fallback file: real SOP/NCR facts, but no operator patterns.
                    yield (f"⚠️ Knowledge graph DEGRADED — database unavailable, using local backup "
                           f"({node_count} nodes, {warn_count} warnings). Operator-confirmed "
                           f"patterns are not included.\n\n")
                else:
                    yield f"🔗 Knowledge graph context loaded — {node_count} nodes, {warn_count} warnings\n\n"
                # Which fault, and how sure (Phase 2a step A) — visible, not silent.
                conf = graph_context.get("match_confidence")
                faults = ", ".join(graph_context.get("matched_faults") or []) or "no single fault"
                if conf == "sure":
                    yield f"🎯 Fault: {faults} ({graph_context.get('match_method')})\n\n"
                elif conf == "unsure":
                    yield f"❓ Fault not confirmed — close call: {faults}\n\n"
                elif conf:
                    yield f"❓ No fault matched ({graph_context.get('match_method')}) — all faults considered\n\n"
            elif graph_context and graph_context.get("degraded"):
                # Graph unreachable AND no local data for this equipment: keep the
                # context object so the report still declares degraded mode.
                yield "⚠️ Knowledge graph unavailable — report will not include equipment-specific warnings.\n\n"
            else:
                graph_context = None  # genuinely no graph data for this equipment
        except Exception as e:
            print(f"  [graph] context fetch failed: {e} — proceeding without graph")
            yield "⚠️ Knowledge graph unavailable — report will not include equipment-specific warnings.\n\n"
            graph_context = {"has_data": False, "degraded": True, "source": "unavailable",
                             "degraded_reason": str(e)[:120], "chain_nodes": [], "warnings": []}

    # ── Supervisor routing — decide which agents to call ─────────────────────
    # Teaching note: this is the key change from fixed fan-out to dynamic routing.
    # The supervisor reads the incident and returns only the agents needed.
    # Phase 2a step 4: the graph ran first, so the supervisor gets what it
    # matched and which documents hold its facts (see required_agents).
    routed_agents, routing_reason = supervisor_route(incident, equipment_id,
                                                     graph_context=graph_context)

    agent_map = {
        "alarm":       ("🚨 Alarm Agent",       run_alarm_agent),
        "expert_fix":  ("🎙 Expert Fix Agent",  run_expert_fix_agent),
        "maintenance": ("🔧 Maintenance Agent", run_maintenance_agent),
        "sop":         ("📋 SOP Agent",         run_sop_agent),
        "ncr":         ("📊 NCR Agent",         run_ncr_agent),
    }

    specialist_functions = [agent_map[a] for a in routed_agents if a in agent_map]
    agent_count = len(specialist_functions)

    yield f"⚡ Dispatching {agent_count} specialist agent{'s' if agent_count != 1 else ''} in parallel...\n"
    yield f"   Routing: {routing_reason}\n\n"

    specialist_results = []
    completed_names    = []
    progress_lines     = []  # collect progress — yield AFTER executor closes

    # Run all routed specialists in parallel (now up to 5 with expert_fix).
    # IMPORTANT: do NOT yield inside the with-block — collect results first,
    # yield progress after the executor has cleanly closed.
    # Run specialists with max_workers=2 (waves of two), NOT all at once.
    # Simultaneous calls stack their tokens into the same 60s window and
    # trip the TPM limit (the 429 we saw). Two-at-a-time halves the burst while
    # staying nearly as fast. Matters more on GPT-OSS, which adds reasoning tokens.
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_to_name = {
            executor.submit(contextvars.copy_context().run, fn, incident, equipment_id): label
            for label, fn in specialist_functions
        }
        for future in as_completed(future_to_name):
            label = future_to_name[future]
            try:
                result = future.result()
                specialist_results.append(result)
                completed_names.append(label)
                progress_lines.append(f"   ✅ {label} complete\n")
            except Exception as e:
                agent_name = label.split(" ", 1)[1]
                specialist_results.append({
                    "agent":    agent_name,
                    "icon":     "⚠️",
                    "findings": f"Agent failed — error: {str(e)}",
                    "raw_data": ""
                })
                progress_lines.append(f"   ⚠️ {label} encountered an error — continuing\n")

    # Executor is fully closed — now safe to yield
    for line in progress_lines:
        yield line

    yield "\n📝 All specialists complete. Orchestrator synthesizing report...\n\n"

    # ── Run orchestrator ───────────────────────────────────────────────────────
    try:
        final_report = run_orchestrator(incident, specialist_results,
                                        graph_context=graph_context, equipment_id=equipment_id)
    except Exception as e:
        yield f"\n❌ Orchestrator error: {str(e)}\n"
        yield "\nNote: Rate limit hit. Please wait a minute and try again.\n"
        return

    # Phase 2a guardrails: code checks the finished report (see check_report).
    _guard_events = []
    try:
        final_report, _guard_events = check_report(final_report, graph_context, specialist_results)
    except Exception as e:  # a checker bug must never swallow the report
        print(f"  [guardrail] check skipped: {str(e)[:100]}")

    # Phase 2a step B: how far can this report be trusted? (code, not AI)
    try:
        _confidence = assess_confidence(graph_context, specialist_results, _guard_events)
        final_report = add_confidence_block(final_report, _confidence, graph_context)
        print(f"  [confidence] {_confidence['level']}; review "
              f"{'needed' if _confidence['review'] else 'not needed'}; {_confidence['reasons']}")
    except Exception as e:  # never lose a report over its confidence line
        print(f"  [confidence] skipped: {str(e)[:100]}")

    yield "\n" + "═" * 50 + "\n"
    yield "INVESTIGATION REPORT\n"
    yield "═" * 50 + "\n\n"
    yield final_report


# ── CLI test harness ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    for chunk in investigate_incident(
        "WR-401 welding robot on Line 4 has triggered a weld quality alarm again. "
        "This is the third time this week. Spatter index reading 4.8. "
        "Some panels already quarantined. Investigate the root cause."
    ):
        print(chunk, end="", flush=True)
