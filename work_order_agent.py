"""
work_order_agent.py — M1 (Action Layer / Trend 1)

A SEPARATE agent from the investigation pipeline (multi_agent.py).
It does NOT diagnose — it turns a finished investigation report into a
DRAFT work order, using Groq NATIVE tool-calling against the seeded
Supabase tables + the knowledge graph.

Design guarantees:
  * Does not import from or modify multi_agent.py / the investigation path.
  * Tool results are AUTHORITATIVE — the model may only use parts, stock,
    technicians and downtime that a tool actually returned (system prompt
    enforces this; cost is computed in Python, never by the model).
  * Bounded loop — hard MAX_ITERATIONS cap.
  * Output is a validated draft work order dict, saved as 'pending_approval'.

Public entry point:
    draft_work_order(report_text, equip_tag, incident_ref=None) -> dict
"""

import os
import json
from groq import Groq
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
supabase    = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

MODEL          = "llama-3.3-70b-versatile"
MAX_ITERATIONS = 6          # bounded agentic loop (guardrail)

# ── Cost model (Python computes cost — the LLM never does) ────────────
LABOR_RATE_USD_PER_HR    = 120.0   # technician labor
DOWNTIME_RATE_USD_PER_HR = 355.0   # value of lost production while line is down
# drive-roll case: parts(85+45) + 1h labor(120) + 1h downtime(355) = ~605 -> Supervisor


# ═════════════════════════════════════════════════════════════════════
# TOOLS — each backed by a real query. Returned data is authoritative.
# ═════════════════════════════════════════════════════════════════════

def _tool_check_parts_inventory(skus):
    """Return live stock for the given part SKUs."""
    try:
        if isinstance(skus, str):
            skus = [skus]
        res = supabase.table("parts_inventory").select("*").in_("sku", skus).execute()
        rows = res.data or []
        out = []
        for r in rows:
            qty = r.get("qty_on_hand") or 0
            rop = r.get("reorder_point") or 0
            out.append({
                "sku":           r.get("sku"),
                "name":          r.get("name"),
                "qty_on_hand":   qty,
                "reorder_point": rop,
                "in_stock":      qty > 0,
                "needs_reorder": qty <= rop,
                "unit_cost_usd": float(r.get("unit_cost_usd") or 0),
                "lead_time_days": r.get("lead_time_days"),
            })
        found = {r["sku"] for r in out}
        for s in skus:
            if s not in found:
                out.append({"sku": s, "name": None, "qty_on_hand": 0,
                            "in_stock": False, "unit_cost_usd": 0,
                            "note": "SKU not found in inventory"})
        return {"parts": out}
    except Exception as e:
        return {"error": str(e), "parts": []}


def _tool_find_technician(required_skills, line=None):
    """Return active technicians whose skills include ALL required_skills."""
    try:
        if isinstance(required_skills, str):
            required_skills = [required_skills]
        q = supabase.table("technicians").select("*").eq("active", True)
        if line:
            q = q.eq("line", line)
        rows = q.execute().data or []
        matches = []
        for r in rows:
            skills = r.get("skills") or []
            if isinstance(skills, str):
                try: skills = json.loads(skills)
                except Exception: skills = []
            if all(s in skills for s in required_skills):
                matches.append({"id": r.get("id"), "name": r.get("name"),
                                "skills": skills, "shift_pattern": r.get("shift_pattern"),
                                "line": r.get("line")})
        return {"technicians": matches,
                "note": "No technician matched all required skills." if not matches else ""}
    except Exception as e:
        return {"error": str(e), "technicians": []}


def _tool_check_availability(technician_id=None, duration_min=60):
    """M1 stub — returns a simple next slot so the loop completes.
    Real scheduling (conflict checks, bookings) is M3."""
    return {
        "technician_id": technician_id,
        "available": True,
        "next_slot": "next available shift slot",
        "duration_min": duration_min,
        "note": "M1 stub — real availability/scheduling is added in M3."
    }


def _tool_get_equipment_fix_info(equip_tag):
    """Parts + procedures (incl. mandatory burn-in) + downtime from the
    knowledge graph. Reuses the same get_fault_chain the investigation used."""
    try:
        from knowledge_graph import get_fault_chain
        fc = get_fault_chain(equip_tag)
        if not fc or not fc.get("has_data"):
            return {"has_data": False,
                    "note": "No knowledge-graph data for this equipment."}
        return {
            "has_data":   True,
            "downtime":   fc.get("downtime", ""),
            "warnings":   fc.get("warnings", []),
            "chain_text": fc.get("chain_text", ""),
        }
    except Exception as e:
        return {"has_data": False, "error": str(e)}


TOOL_IMPL = {
    "check_parts_inventory":  lambda a: _tool_check_parts_inventory(a.get("skus", [])),
    "find_technician":        lambda a: _tool_find_technician(a.get("required_skills", []), a.get("line")),
    "check_availability":     lambda a: _tool_check_availability(a.get("technician_id"), a.get("duration_min", 60)),
    "get_equipment_fix_info": lambda a: _tool_get_equipment_fix_info(a.get("equip_tag", "")),
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_equipment_fix_info",
            "description": "Get the verified parts, mandatory procedures (e.g. burn-in) and estimated downtime for an equipment's fault, from the knowledge graph. Call this FIRST.",
            "parameters": {
                "type": "object",
                "properties": {
                    "equip_tag": {"type": "string", "description": "Equipment tag, e.g. WM-101"}
                },
                "required": ["equip_tag"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_parts_inventory",
            "description": "Check live stock levels, cost and availability for one or more part SKUs. Only parts confirmed by this tool may go on the work order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skus": {"type": "array", "items": {"type": "string"},
                             "description": "Part SKUs to check, e.g. ['GSW-DROLL-08']"}
                },
                "required": ["skus"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_technician",
            "description": "Find active technicians who have ALL the required skills (e.g. LOTO, MIG) on a given line.",
            "parameters": {
                "type": "object",
                "properties": {
                    "required_skills": {"type": "array", "items": {"type": "string"},
                                        "description": "Skills required, e.g. ['LOTO','MIG']"},
                    "line": {"type": "string", "description": "Line name, e.g. 'Fabrication Line 1'"}
                },
                "required": ["required_skills"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check when a technician is next available for a job of a given duration.",
            "parameters": {
                "type": "object",
                "properties": {
                    "technician_id": {"type": "string"},
                    "duration_min": {"type": "integer"}
                },
                "required": ["technician_id"]
            }
        }
    },
]

SYSTEM_PROMPT = """You are a maintenance work-order drafting agent for a manufacturing plant.

You are given a completed INVESTIGATION REPORT. Your job is to turn its recommended fix into a DRAFT work order by calling tools. You do NOT diagnose — the diagnosis is already done.

STRICT RULES (these are guardrails — follow them exactly):
1. Use ONLY information that a tool returned. Never invent a part SKU, a stock level, a technician, a cost, or a downtime figure. If a tool did not return it, you do not know it.
2. Call get_equipment_fix_info FIRST to get the verified parts, mandatory procedures and downtime from the knowledge graph.
3. Then call check_parts_inventory for the parts you intend to use — only parts confirmed in stock (or explicitly flagged for reorder) may be listed.
4. Find a technician with the required skills (drive roll / liner / electrical work on a MIG welder requires LOTO and MIG), then check their availability.
5. Do NOT compute or state a total cost — the system computes cost from the unit costs the inventory tool returned. Leave cost out of your reasoning.
6. Include any mandatory procedure (e.g. burn-in after liner replacement) returned by the graph.

When you have gathered everything, STOP calling tools and reply with ONLY a JSON object (no prose, no markdown fences) in exactly this shape:
{
  "title": "short human-readable name, e.g. 'Drive roll & liner replacement'",
  "summary": "one-paragraph plain-language description of the work to be done",
  "parts": [{"sku": "GSW-DROLL-08", "qty": 1}],
  "procedures": [{"name": "Mandatory burn-in after liner replacement", "mandatory": true}],
  "technician_id": "<id returned by find_technician, or null>",
  "technician_name": "<name returned by find_technician, or null>",
  "est_downtime_min": 60
}
Only these fields. Use the exact SKUs and technician id/name the tools returned."""


# ═════════════════════════════════════════════════════════════════════
# AGENT LOOP
# ═════════════════════════════════════════════════════════════════════

def _run_tool_loop(report_text, equip_tag, line_hint=""):
    """Run the bounded native tool-calling loop. Returns (draft_json, tool_log)."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content":
            f"Equipment: {equip_tag}\nLine: {line_hint or 'unknown'}\n\n"
            f"INVESTIGATION REPORT:\n{report_text}\n\n"
            f"Draft the work order. Remember: call get_equipment_fix_info first."}
    ]
    tool_log = []

    for _ in range(MAX_ITERATIONS):
        resp = groq_client.chat.completions.create(
            model=MODEL, messages=messages,
            tools=TOOLS, tool_choice="auto", max_tokens=1200,
        )
        msg = resp.choices[0].message

        if not msg.tool_calls:
            # Final answer — parse JSON (tolerate accidental fences)
            content = (msg.content or "").strip()
            if content.startswith("```"):
                content = content.strip("`")
                if content.lower().startswith("json"):
                    content = content[4:]
            try:
                return json.loads(content), tool_log
            except Exception:
                start, end = content.find("{"), content.rfind("}")
                if start != -1 and end != -1:
                    return json.loads(content[start:end + 1]), tool_log
                raise ValueError("Agent did not return valid JSON: " + content[:300])

        messages.append(msg)
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}
            result = TOOL_IMPL.get(name, lambda a: {"error": "unknown tool"})(args)
            tool_log.append({"tool": name, "args": args})
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result)})

    raise ValueError("Work-order agent exceeded max iterations without a draft.")


# ═════════════════════════════════════════════════════════════════════
# COST + TIER (computed in Python, never by the model)
# ═════════════════════════════════════════════════════════════════════

def _price_parts(parts):
    """Attach unit_cost from inventory and return (priced_parts, parts_total)."""
    priced, total = [], 0.0
    skus = [p.get("sku") for p in parts if p.get("sku")]
    cost_by_sku = {}
    if skus:
        inv = _tool_check_parts_inventory(skus).get("parts", [])
        cost_by_sku = {r["sku"]: r.get("unit_cost_usd", 0) for r in inv}
    for p in parts:
        sku = p.get("sku")
        qty = int(p.get("qty") or 1)
        unit = float(cost_by_sku.get(sku, 0) or 0)
        line_total = unit * qty
        total += line_total
        priced.append({"sku": sku, "qty": qty, "unit_cost_usd": unit})
    return priced, round(total, 2)


def _compute_cost(parts_total, downtime_min):
    hrs = (downtime_min or 0) / 60.0
    labor    = hrs * LABOR_RATE_USD_PER_HR
    downtime = hrs * DOWNTIME_RATE_USD_PER_HR
    return round(parts_total + labor + downtime, 2)


def _match_tier(est_cost_usd):
    """Match cost to a cost_thresholds tier. min inclusive, max exclusive."""
    try:
        tiers = supabase.table("cost_thresholds").select("*").order("min_usd").execute().data or []
        for t in tiers:
            lo = float(t.get("min_usd") or 0)
            hi = t.get("max_usd")
            if est_cost_usd >= lo and (hi is None or est_cost_usd < float(hi)):
                return t.get("tier"), t.get("required_approver_role")
    except Exception:
        pass
    return "supervisor", "Shift Supervisor"   # safe default: require a human


def price_and_cost(parts, downtime_min):
    """Public helper used by drafting AND editing.
    Returns (priced_parts, est_cost_usd, tier, approver_role).
    Cost is ALWAYS computed here in Python — never taken from the model
    or from a human edit — so it can't be gamed into a lower tier."""
    priced_parts, parts_total = _price_parts(parts)
    est_cost = _compute_cost(parts_total, downtime_min)
    tier, approver_role = _match_tier(est_cost)
    return priced_parts, est_cost, tier, approver_role


# ═════════════════════════════════════════════════════════════════════
# PUBLIC ENTRY POINT
# ═════════════════════════════════════════════════════════════════════

def draft_work_order(report_text, equip_tag, incident_ref=None, line_hint=""):
    """Draft a work order from a finished investigation report and save it
    as 'pending_approval'. Returns the saved work_order row (dict)."""
    draft, tool_log = _run_tool_loop(report_text, equip_tag, line_hint)

    parts = draft.get("parts") or []
    downtime_min = int(draft.get("est_downtime_min") or 60)
    priced_parts, est_cost, tier, approver_role = price_and_cost(parts, downtime_min)

    # Date-based WO number (atomic, per-day sequence) via DB function.
    wo_number = None
    try:
        r = supabase.rpc("next_wo_number").execute()
        wo_number = r.data if isinstance(r.data, str) else (r.data or None)
    except Exception:
        pass

    title = (draft.get("title") or "").strip() or f"Work order — {equip_tag}"

    row = {
        "equip_tag":           equip_tag,
        "incident_ref":        incident_ref,
        "status":              "pending_approval",
        "wo_number":           wo_number,
        "title":               title,
        "summary":             draft.get("summary", ""),
        "parts":               priced_parts,
        "procedures":          draft.get("procedures") or [],
        "assigned_technician": draft.get("technician_id"),
        "est_downtime_min":    downtime_min,
        "est_cost_usd":        est_cost,
        "approval_tier":       tier,
    }

    saved = supabase.table("work_orders").insert(row).execute()
    wo = (saved.data or [row])[0]

    # Audit trail (guardrail: every action is logged)
    try:
        supabase.table("wo_audit").insert({
            "work_order_id": wo.get("id"),
            "event_type":    "drafted",
            "actor":         "work_order_agent",
            "detail":        {"tool_log": tool_log,
                              "approver_role": approver_role,
                              "wo_number": wo_number},
        }).execute()
    except Exception:
        pass

    wo["technician_name"] = draft.get("technician_name")
    wo["approver_role"]   = approver_role
    return wo
