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
import os
import json
from dotenv import load_dotenv

load_dotenv()

from llm_logger import log_llm_call

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


def _groq_call_with_retry(fn, max_retries=3, call_type="specialist",
                          model=MODEL_FAST,
                          plant_site="", equip_tag=""):
    """
    Retry Groq calls on rate limit errors with exponential backoff.
    Also logs every call (success or failure) to Supabase via llm_logger.

    Teaching note: wrapping retries + logging in one function means
    every call site gets both behaviours for free.
    """
    for attempt in range(max_retries):
        try:
            return log_llm_call(
                fn=fn, call_type=call_type, model=model,
                plant_site=plant_site, equip_tag=equip_tag
            )
        except Exception as e:
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
    if not strong_matches:
        return "LOW_CONFIDENCE: Expert fixes found but similarity too low — do not cite.", []

    output   = []
    fix_ids  = []
    for match in strong_matches:
        meta = match.metadata
        name = meta.get("captured_by_name", "an operator")
        role = meta.get("captured_by_role", "") or "Operator"
        date = meta.get("captured_at", "")[:10]  # YYYY-MM-DD prefix only
        output.append(
            f"[Expert Fix — {name}, {role}"
            f"{', ' + date if date else ''} | Score: {round(match.score, 2)}]\n"
            f"{meta.get('text', '')[:400]}"
        )
        fid = meta.get("expert_fix_id")
        if fid:
            fix_ids.append(fid)

    return "\n\n---\n\n".join(output), fix_ids


# ── Specialist Agent: Alarm Agent ──────────────────────────────────────────────

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
        equip_tag=equipment_id)

    return {
        "agent":    "Alarm Agent",
        "icon":     "🚨",
        "findings": response.choices[0].message.content,
        "raw_data": search_result
    }


# ── Specialist Agent: Expert Fix Agent (PM-IK-001) ────────────────────────────

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
- Expert fixes are cited by the OPERATOR'S NAME AND ROLE — never call them "unverified".
  The name and role ARE the trust signal; do not add hedging language on top of it.
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
- Found: [YES, attributed to <name, role> | NO — no prior expert fix on record]
- What was different: [from the fix, or N/A]
- What fixed it: [from the fix, or N/A]
- When it applies: [any stated conditions, or N/A]
- SOP gap flagged by operator: [YES/NO — did they say the SOP misses this]
- Data confidence: HIGH / MEDIUM / LOW / NO DATA

SOURCES USED:
- [operator name, role, and date cited]"""

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
        equip_tag=equipment_id)

    return {
        "agent":    "Expert Fix Agent",
        "icon":     "🎙",
        "findings": response.choices[0].message.content,
        "raw_data": search_result
    }


# ── Specialist Agent: Maintenance Agent ───────────────────────────────────────

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
        equip_tag=equipment_id)

    return {
        "agent":    "Maintenance Agent",
        "icon":     "🔧",
        "findings": response.choices[0].message.content,
        "raw_data": search_result
    }


# ── Specialist Agent: SOP Agent ────────────────────────────────────────────────

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
        equip_tag=equipment_id)

    return {
        "agent":    "SOP Agent",
        "icon":     "📋",
        "findings": response.choices[0].message.content,
        "raw_data": search_result
    }


# ── Specialist Agent: NCR Agent ────────────────────────────────────────────────

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
        equip_tag=equipment_id)

    return {
        "agent":    "NCR Agent",
        "icon":     "📊",
        "findings": response.choices[0].message.content,
        "raw_data": search_result
    }


# ── Orchestrator ───────────────────────────────────────────────────────────────

def run_orchestrator(incident, specialist_results, graph_context=None):
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
1. Only use evidence the specialists found. Never add information they did not surface.
2. When specialists contradict each other — note the contradiction, do not resolve it by guessing.
3. When a specialist returned NO DATA — that absence is itself a finding (e.g. no SOP = procedure gap).
4. Weight findings by data confidence: HIGH > MEDIUM > LOW > NO DATA.
5. The report has TWO sections — technical and plain language. Both are required.
6. EXPERT FIX RULES — follow strictly:
   - Cite expert fixes by the operator's NAME AND ROLE, e.g. "Dave (Senior Operator)
     found on 14 Jul 2026 that..." — never label an expert fix "unverified". The name
     and role are the trust signal; do not add hedging qualifiers on top of that.
   - If the Expert Fix agent found a match, it should normally be the FIRST thing named
     under IMMEDIATE ACTION — a prior operator's proven fix is the fastest path to
     resolving the current incident.
   - When the expert fix contains reproducible numbered steps (the source text says
     "reproducible steps"), REPRODUCE THOSE STEPS VERBATIM, in order, under IMMEDIATE
     ACTION — do not summarise or paraphrase them into a single sentence. The goal is
     that someone unfamiliar with this incident can follow the report like a checklist
     and resolve it without contacting the operator who captured it.
   - When the expert fix is flagged as insufficient detail ("treat as a lead, not a
     procedure"), present it as a starting lead, not as a step-by-step fix — and say so
     plainly rather than inventing steps that were never given.
   - If an expert fix CONTRADICTS what the SOP agent reports (e.g. different tension,
     temperature, or timing values), do NOT decide which one is correct. Surface BOTH
     explicitly, label it a contradiction, and recommend engineering review before
     acting on either one. Never silently prefer the SOP over the expert fix or vice versa.
7. CRITICALITY RULES — follow strictly:
   - Three or more alarms of same type in one shift = HIGH minimum (recurring fault indicator)
   - Any fault requiring LOTO or production stop = HIGH minimum
   - Worn components with documented NCR history = HIGH
   - Safety events (electrical, fire, fumes) = CRITICAL
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
  Step 4: Verify — post-fix checks, burn-in if required
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
KNOWLEDGE GRAPH CONTEXT — VERIFIED FROM SOP AND NCR DATA
─────────────────────────────────────────────────────
{graph_context["chain_text"]}
─────────────────────────────────────────────────────{mandatory_warnings}

STRICT GRAPH RULES — VIOLATION IS AN ERROR:
1. The graph shows burn-in is MANDATORY after liner replacement.
   You MUST include this in immediate action: "Complete burn-in procedure after replacement.
   Run wire at 5.0 m/min for 30 seconds. Wire instability during burn-in is EXPECTED — not a new fault."
2. The graph shows the WRONG RESPONSE is adjusting tension.
   You MUST include this warning: "Do NOT keep adjusting tension — this will not fix worn drive rolls
   and risks motor burnout. This is the documented operator trap from NCR-2024-047."
3. LOTO is required before any maintenance — include in immediate action.
4. Parts welded during fault must be quarantined — include in impact section.
─────────────────────────────────────────────────────"""

    user_prompt = f"""Incident: {incident}

Specialist agent findings:
{findings_block}{graph_block}

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
        call_type="orchestrator", model=MODEL_DEEP)

    initial_report = response.choices[0].message.content

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
        call_type="reflection", model=MODEL_DEEP)

    return reflection_response.choices[0].message.content


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
  maintenance — searches maintenance records and service history
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

Valid agent names: alarm, expert_fix, maintenance, sop, ncr"""


def supervisor_route(incident, equipment_id=None):
    """
    Classify the incident and return which agents to dispatch.
    Returns a list of agent names and a routing reason.

    Falls back to all 4 agents if classification fails — safe default.
    """
    user_msg = f"Incident: {incident}"
    if equipment_id:
        user_msg += "\nEquipment: " + str(equipment_id)

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
            model=MODEL_FAST
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
        if len(agents) < 1:
            agents = ["alarm", "expert_fix", "maintenance", "sop", "ncr"]
            reason = "fallback — routing returned empty list"

        return agents, reason

    except Exception as e:
        print(f"  Supervisor routing failed: {e} — using all agents")
        return ["alarm", "expert_fix", "maintenance", "sop", "ncr"], "fallback — routing error"


# ── Parallel Coordinator + Streaming Generator ─────────────────────────────────

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

    yield "🔍 Multi-agent investigation started...\n\n"
    if equipment_id:
        yield f"📍 Equipment identified: {equipment_id}\n\n"

    # ── Fetch knowledge graph context ────────────────────────────────────────
    # Silent fail — graph enrichment is optional, never blocks investigation
    graph_context = None
    if equipment_id:
        try:
            from knowledge_graph import get_fault_chain
            graph_context = get_fault_chain(equipment_id)
            if graph_context and graph_context.get("has_data"):
                node_count = len(graph_context.get("chain_nodes", []))
                warn_count = len(graph_context.get("warnings", []))
                yield f"🔗 Knowledge graph context loaded — {node_count} nodes, {warn_count} warnings\n\n"
            else:
                graph_context = None  # No data — do not pass empty context
        except Exception as e:
            print(f"  [graph] context fetch failed: {e} — proceeding without graph")
            graph_context = None

    # ── Supervisor routing — decide which agents to call ─────────────────────
    # Teaching note: this is the key change from fixed fan-out to dynamic routing.
    # The supervisor reads the incident and returns only the agents needed.
    routed_agents, routing_reason = supervisor_route(incident, equipment_id)

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
            executor.submit(fn, incident, equipment_id): label
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
        final_report = run_orchestrator(incident, specialist_results, graph_context=graph_context)
    except Exception as e:
        yield f"\n❌ Orchestrator error: {str(e)}\n"
        yield "\nNote: Rate limit hit. Please wait a minute and try again.\n"
        return

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
