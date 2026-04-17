from groq import Groq
from pinecone import Pinecone
import os
import json
from dotenv import load_dotenv

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
pc          = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
pine_index  = pc.Index(os.getenv("PINECONE_INDEX"))

# ── Real Pinecone search ──────────────────────────────────────────────

def search_plantmind(query, doc_type_filter=None, equipment_filter=None, top_k=3):
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
        return "No relevant documents found in PlantMind."

    strong_matches = [m for m in results.matches if m.score >= 0.4]

    if not strong_matches:
        return "Documents found but confidence too low to cite. Do not guess — state insufficient data."

    output = []
    for match in strong_matches:
        meta = match.metadata
        output.append(
            f"[Source: {meta.get('name','unknown')} | "
            f"Type: {meta.get('doc_type','unknown')} | "
            f"Revision: {meta.get('revision','?')} | "
            f"Score: {round(match.score, 2)}]\n"
            f"{meta.get('text','')[:200]}"
        )

    return "\n\n---\n\n".join(output)


# ── Tool definitions ──────────────────────────────────────────────────

tools = [
    {
        "type": "function",
        "function": {
            "name": "search_shift_logs",
            "description": "Search shift logs for alarm history and events for a specific equipment",
            "parameters": {
                "type": "object",
                "properties": {
                    "equipment_id": {"type": "string", "description": "Equipment tag e.g. WR-401"},
                    "query": {"type": "string", "description": "What to search for in the shift logs"}
                },
                "required": ["equipment_id", "query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_maintenance_records",
            "description": "Search maintenance history and service records for a specific equipment",
            "parameters": {
                "type": "object",
                "properties": {
                    "equipment_id": {"type": "string", "description": "Equipment tag e.g. WR-401"},
                    "query": {"type": "string", "description": "What to search for in maintenance records"}
                },
                "required": ["equipment_id", "query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_sop",
            "description": "Search standard operating procedures for alarm response steps and specifications",
            "parameters": {
                "type": "object",
                "properties": {
                    "equipment_id": {"type": "string", "description": "Equipment tag e.g. WR-401"},
                    "query": {"type": "string", "description": "What procedure or specification to find"}
                },
                "required": ["equipment_id", "query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_ncr",
            "description": "Search non-conformance reports for past quality incidents on specific equipment",
            "parameters": {
                "type": "object",
                "properties": {
                    "equipment_id": {"type": "string", "description": "Equipment tag e.g. WR-401"},
                    "query": {"type": "string", "description": "What type of incident or deviation to find"}
                },
                "required": ["equipment_id", "query"]
            }
        }
    }
]

# ── Tool execution ────────────────────────────────────────────────────

def execute_tool(tool_name, args):
    equipment = args.get("equipment_id", "")
    query     = args.get("query", "")

    if tool_name == "search_shift_logs":
        return search_plantmind(query, doc_type_filter="Shift Log", equipment_filter=equipment)
    elif tool_name == "search_maintenance_records":
        return search_plantmind(query, doc_type_filter="Work Instruction", equipment_filter=equipment)
    elif tool_name == "search_sop":
        return search_plantmind(query, doc_type_filter="SOP", equipment_filter=equipment)
    elif tool_name == "search_ncr":
        return search_plantmind(query, doc_type_filter="NCR", equipment_filter=equipment)
    else:
        return "Unknown tool."

# ── System prompt ─────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert maintenance investigation agent for a manufacturing plant.

When investigating incidents always follow these rules:
1. Use ONE tool at a time. Call a tool, read the result, then decide what to search next.
2. Search shift logs first, then maintenance records, then SOP, then NCR.
3. Look for what is DIFFERENT about this occurrence vs previous ones.
4. Never conclude from a single data point.
5. Only write the final report when you have searched all four sources.
6. If any search returns insufficient data — say so explicitly. Never invent findings.

Always structure your investigation report in exactly this format:

SOURCE DATA:
- List every data point used with exact source document and timestamp

WHAT IS THE ISSUE:
- Plain language root cause with evidence

WHAT IS THE IMPACT:
- Production impact and safety risk level (High/Medium/Low)
- Financial impact if known

HOW CRITICAL IS IT:
- CRITICAL / HIGH / MEDIUM / LOW with justification

HOW TO ADDRESS IT:
- Immediate action
- Root cause fix
- Preventive action
- Who needs to be notified"""

# ── CLI version (for testing) ─────────────────────────────────────────

def investigate(incident):
    print(f"\n{'='*60}")
    print(f"INCIDENT: {incident}")
    print(f"{'='*60}")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": incident}
    ]

    max_iterations = 6
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        print(f"\n[Agent thinking — round {iteration}]")

        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            tools=tools,
            tool_choice="auto",
            max_tokens=2000
        )

        message = response.choices[0].message

        if not message.tool_calls:
            print(f"\n{'='*60}")
            print("INVESTIGATION REPORT")
            print(f"{'='*60}\n")
            print(message.content)
            break

        messages.append(message)

        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
            args      = json.loads(tool_call.function.arguments)
            equipment = args.get("equipment_id", "")

            print(f"  -> Searching: {tool_name}(equipment={equipment})")
            result = execute_tool(tool_name, args)
            print(f"  OK: {result[:100]}...")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result
            })

# ── Streaming version (for PlantMind UI) ─────────────────────────────

def investigate_incident(incident):
    """Generator — yields investigation progress and final report for streaming to UI."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": incident}
    ]

    tool_labels = {
        "search_shift_logs":          "Searching shift logs",
        "search_maintenance_records": "Searching maintenance records",
        "search_sop":                 "Searching SOPs",
        "search_ncr":                 "Searching NCR history"
    }

    yield "Investigation started...\n\n"

    max_iterations = 6
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            tools=tools,
            tool_choice="auto",
            max_tokens=2000
        )

        message = response.choices[0].message

        if not message.tool_calls:
            yield "\n" + "="*50 + "\n"
            yield "INVESTIGATION REPORT\n"
            yield "="*50 + "\n\n"
            yield message.content
            break

        messages.append(message)

        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
            args      = json.loads(tool_call.function.arguments)
            equipment = args.get("equipment_id", "")
            label     = tool_labels.get(tool_name, tool_name)

            yield f"-> {label} for {equipment}...\n"

            result = execute_tool(tool_name, args)

            # Show brief summary of what was found
            if "No relevant" in result or "confidence too low" in result:
                yield f"   No strong matches found\n"
            else:
                lines = result.split("\n")
                for line in lines[:2]:
                    if line.strip():
                        yield f"   Found: {line[:80]}...\n"
                        break

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result
            })

        yield "\n"


if __name__ == "__main__":
    investigate(
        "WR-401 welding robot on Line 4 has triggered a weld quality alarm again. "
        "This is the third time this week. Spatter index reading 4.8. "
        "Some panels already quarantined. Investigate the root cause."
    )
