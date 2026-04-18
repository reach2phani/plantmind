"""
multi_agent.py — PlantMind Multi-Agent Investigation System

Architecture:
  4 specialist agents run in parallel, each with one tool and one focused job.
  When all four finish, the Orchestrator synthesizes their findings into a
  two-part report: technical (for the maintenance engineer) and plain language
  (for the plant manager).

Agents:
  AlarmAgent       — shift log search, alarm pattern analysis
  MaintenanceAgent — maintenance record search, repair history
  SOPAgent         — procedure search, specification lookup
  NCRAgent         — non-conformance history, corrective action patterns
  Orchestrator     — receives all four findings, synthesizes final report
"""

from groq import Groq
from pinecone import Pinecone
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import json
from dotenv import load_dotenv

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
pc          = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
pine_index  = pc.Index(os.getenv("PINECONE_INDEX"))


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

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt}
        ],
        max_tokens=600,
        temperature=0.1
    )

    return {
        "agent":    "Alarm Agent",
        "icon":     "🚨",
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

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt}
        ],
        max_tokens=600,
        temperature=0.1
    )

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

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt}
        ],
        max_tokens=600,
        temperature=0.1
    )

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

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt}
        ],
        max_tokens=600,
        temperature=0.1
    )

    return {
        "agent":    "NCR Agent",
        "icon":     "📊",
        "findings": response.choices[0].message.content,
        "raw_data": search_result
    }


# ── Orchestrator ───────────────────────────────────────────────────────────────

def run_orchestrator(incident, specialist_results):
    """
    Receives all four specialist findings and synthesizes the final investigation report.
    Produces two reports: technical (maintenance engineer) + plain language (plant manager).
    Never touches Pinecone — reasons only over specialist findings.
    """
    SYSTEM_PROMPT = """You are the Investigation Orchestrator for PlantMind, a manufacturing plant AI system.

You receive structured findings from four specialist agents and synthesize them into a final investigation report.

Your rules:
1. Only use evidence the specialists found. Never add information they did not surface.
2. When specialists contradict each other — note the contradiction, do not resolve it by guessing.
3. When a specialist returned NO DATA — that absence is itself a finding (e.g. no SOP = procedure gap).
4. Weight findings by data confidence: HIGH > MEDIUM > LOW > NO DATA.
5. The report has TWO sections — technical and plain language. Both are required.

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
- Immediate action (do this now)
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

    user_prompt = f"""Incident: {incident}

Specialist agent findings:
{findings_block}

Synthesize the final investigation report from these findings."""

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt}
        ],
        max_tokens=1500,
        temperature=0.1
    )

    return response.choices[0].message.content


# ── Parallel Coordinator + Streaming Generator ─────────────────────────────────

def investigate_incident(incident):
    """
    Generator — runs 4 specialist agents in parallel, then orchestrates.
    Yields progress updates and the final report for streaming to the UI.

    This is the function called by app.py's /investigate route.
    It replaces the single-agent investigate_incident() from agent_v2.py.
    """

    # Extract equipment ID from incident text if present (e.g. P-201, WR-401)
    import re
    equipment_match = re.search(r'\b([A-Z]{1,3}-\d{2,4})\b', incident)
    equipment_id    = equipment_match.group(1) if equipment_match else None

    yield "🔍 Multi-agent investigation started...\n\n"
    if equipment_id:
        yield f"📍 Equipment identified: {equipment_id}\n\n"

    yield "⚡ Dispatching 4 specialist agents in parallel...\n\n"

    # ── Run all four specialists simultaneously ────────────────────────────────
    specialist_functions = [
        ("🚨 Alarm Agent",       run_alarm_agent),
        ("🔧 Maintenance Agent", run_maintenance_agent),
        ("📋 SOP Agent",         run_sop_agent),
        ("📊 NCR Agent",         run_ncr_agent),
    ]

    specialist_results = []
    completed_names    = []

    with ThreadPoolExecutor(max_workers=4) as executor:
        # Submit all four jobs at once
        future_to_name = {
            executor.submit(fn, incident, equipment_id): label
            for label, fn in specialist_functions
        }

        # Collect results as they finish (whichever finishes first)
        for future in as_completed(future_to_name):
            label = future_to_name[future]
            try:
                result = future.result()
                specialist_results.append(result)
                completed_names.append(label)
                yield f"   ✅ {label} complete\n"
            except Exception as e:
                # If a specialist fails, record the failure — don't crash the whole investigation
                agent_name = label.split(" ", 1)[1]  # strip the emoji
                specialist_results.append({
                    "agent":    agent_name,
                    "icon":     "⚠️",
                    "findings": f"Agent failed: {str(e)}",
                    "raw_data": ""
                })
                yield f"   ⚠️ {label} encountered an error — continuing\n"

    yield "\n📝 All specialists complete. Orchestrator synthesizing report...\n\n"

    # ── Run orchestrator ───────────────────────────────────────────────────────
    final_report = run_orchestrator(incident, specialist_results)

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
