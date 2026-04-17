from groq import Groq
import os
import json
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# --- The tool definition ---
# This tells the LLM what tools exist and what they do
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_alarm_history",
            "description": "Search shift logs for alarm history of a specific equipment ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "equipment_id": {
                        "type": "string",
                        "description": "The equipment tag e.g. P-201"
                    },
                    "days": {
                        "type": "integer", 
                        "description": "How many days back to search"
                    }
                },
                "required": ["equipment_id", "days"]
            }
        }
    }
]

# --- The fake tool result ---
# Simulates what Pinecone would return
def search_alarm_history(equipment_id, days):
    return f"""
    Alarm history for {equipment_id} - last {days} days:
    - Apr 15 02:45 - Thermal overload trip - cooling fan cleaned - Resolved
    - Apr 12 14:20 - Thermal overload trip - cooling fan cleaned - Resolved  
    - Apr 08 09:15 - Thermal overload trip - motor windings checked OK - Resolved
    - Apr 03 22:30 - Bearing temperature high alert - cooling water increased - Resolved
    Note: 3 thermal overload trips in 12 days. Previous trips resolved by cleaning fan.
    This trip: bearing temperature also reading 79C - higher than previous occurrences.
    """

# --- The agent ---
messages = [
    {
        "role": "system",
        "content": """You are an expert maintenance investigation agent for a manufacturing plant.

        When investigating incidents always follow these rules:
        1. Always search for historical data before forming conclusions
        2. Look for what is DIFFERENT about this occurrence vs previous ones
        3. Never conclude from a single data point

        Always structure your investigation report in exactly this format:

        SOURCE DATA:
        - List every data point you used with exact timestamp, value, and where it came from

        WHAT IS THE ISSUE:
        - Plain language description of the root cause
        - What evidence proves this is the real issue not a symptom

        WHAT IS THE IMPACT:
        - Production impact - is the line down, degraded, or at risk
        - Safety risk level - High / Medium / Low
        - Financial impact - estimated cost of downtime if known

        HOW CRITICAL IS IT:
        - CRITICAL - immediate action required, line is down or unsafe
        - HIGH - action required within 2 hours, risk of failure imminent  
        - MEDIUM - action required this shift, degraded performance
        - LOW - schedule for next maintenance window

        HOW TO ADDRESS IT:
        - Immediate action - what to do right now
        - Root cause fix - what permanently solves this
        - Preventive action - what stops this happening again
        - Who needs to be notified"""
    },
    {
        "role": "user",
        "content": "P-201 just tripped on thermal overload. This is urgent - investigate."
    }
]

print("=== AGENT STARTING INVESTIGATION ===\n")
print(f"Incident: P-201 thermal overload trip\n")

# --- First LLM call - does it decide to use the tool? ---
response = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=messages,
    tools=tools,
    tool_choice="auto"
)

first_response = response.choices[0].message
print(f"AGENT REASONING: {first_response.content or 'Deciding to use a tool...'}")

# --- Did it call a tool? ---
if first_response.tool_calls:
    tool_call = first_response.tool_calls[0]
    args = json.loads(tool_call.function.arguments)
    
    print(f"\nAGENT ACTION: Calling {tool_call.function.name}")
    print(f"AGENT PARAMETERS: equipment_id={args['equipment_id']}, days={args['days']}")
    
    # Run the tool
    tool_result = search_alarm_history(args['equipment_id'], args['days'])
    print(f"\nTOOL RETURNED:\n{tool_result}")
    
    # Give the result back to the agent
    messages.append(first_response)
    messages.append({
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": tool_result
    })
    
    # Second LLM call - now form the conclusion
    final_response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages,
        tool_choice="none"
    )
    
    print(f"\n=== AGENT INVESTIGATION REPORT ===")
    print(final_response.choices[0].message.content)

else:
    print("\nAgent answered without using tools:")
    print(first_response.content)