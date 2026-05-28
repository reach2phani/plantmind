# PlantMind — Full Project Context for Claude

> This is the complete handoff document. Paste this entire file at the start of any new Claude conversation.
> Last updated: Session 11 complete.

---

## Project summary

PlantMind is an AI assistant for manufacturing plant operators built from scratch as a learning project by a Technical Product Manager on a career break. The goal was to learn AI engineering by building something real, not reading about it.

An operator describes an equipment incident — "WR-401 welding robot wire feed stuttering, third time this week" — and gets a structured investigation report drawn from uploaded SOPs, maintenance records, shift logs, and NCR reports. The report shows criticality first, immediate action highlighted, root cause, and sources used.

Session 11 added real-time MQTT integration — the system now monitors live equipment data, detects alarm patterns automatically, and surfaces enriched alert cards to operators.

---

## Stack

| Component | Technology | Details |
|-----------|-----------|---------|
| LLM inference | Groq free tier | API compatible with OpenAI SDK |
| Specialist agents | llama-3.1-8b-instant | 14,400 RPD, 6,000 TPM, 500K TPD |
| Orchestrator + reflection | llama-3.3-70b-versatile | 1,000 RPD, 12,000 TPM, 100K TPD |
| Vector DB | Pinecone free tier | Serverless, metadata filtering |
| Embedding model | multilingual-e5-large | Via Pinecone inference API |
| Database + storage | Supabase free tier | Pauses after 7 days inactivity |
| MQTT broker | HiveMQ Cloud free tier | cloud broker, TLS port 8883 |
| API framework | Flask | Streaming responses via stream_with_context |
| Hosting | Render free tier | Spins down after inactivity |
| Frontend | Vanilla JS + HTML | No framework |

---

## Repository structure

```
C:\PlantMind\                     (Windows, VS Code)
├── app.py                        — Flask API, all routes
├── multi_agent.py                — Full agent pipeline
├── llm_logger.py                 — LLM observability
├── embedder.py                   — Document chunking and Pinecone upsert
├── reembed.py                    — Re-index all documents
├── simulator.py                  — SimPy wear-state plant simulator (NEW Session 11)
├── mqtt_subscriber.py            — MQTT listener + pattern detection (NEW Session 11)
├── test_pattern.py               — Manual test script to insert fake alerts
├── nav_context.js                — Plant site context (also in static/)
├── templates/
│   ├── chat.html                 — Ask + Investigate + Shift UI
│   ├── library.html              — Document library
│   ├── alerts.html               — Live feed + Pattern alerts (NEW Session 11)
│   ├── plant_setup.html          — Plant CRUD
│   └── index.html                — Upload interface (fallback)
├── static/
│   └── nav_context.js
├── evals/
│   ├── test_cases.json           — 10 test cases
│   ├── eval_runner.py            — Test runner
│   ├── baseline_session6.json    — 90% baseline locked
│   └── baseline_session8.json    — 90% baseline locked
├── ragas_test.py                 — Ragas evaluation script
├── requirements.txt              — Includes paho-mqtt, simpy (added Session 11)
├── CONTEXT.md                    — This file
├── LEARNING.md                   — AI concepts reference
├── README.md                     — GitHub README
├── PlantMind-Presentation.pptx   — 10-slide deck
└── PlantMind-WriteUp.docx        — Detailed write-up
```

---

## Supabase schema (all tables)

```sql
documents (
  id uuid, name text, file_type text, doc_type text,
  plant_site text, line text, equip_tag text,
  revision text, file_path text, status text default 'uploaded',
  embed_status text default 'pending',
  last_embedded_at timestamptz, created_at timestamptz
)

chat_history (
  id uuid, mode text, question text, answer text,
  sources text, plant_site text, line text,
  equip_tag text, read boolean default true,   -- 'read' column added Session 11
  created_at timestamptz
)
-- mode='proactive' used for MQTT pattern alerts, read=false means unread

llm_logs (
  id uuid, model text, call_type text,
  input_tokens int, output_tokens int, latency_ms int,
  error text, plant_site text, equip_tag text,
  created_at timestamptz
)

plant_sites (
  id uuid, name text, created_at timestamptz
)

lines (
  id uuid, name text, plant_site text,
  active bool default true, created_at timestamptz
)

equipment (
  id uuid, equip_tag text unique, name text,
  type text, plant_site text, line text,
  manufacturer text, active bool default true,
  created_at timestamptz
)

live_events (
  id uuid, plant_site text, line text, equip_tag text,
  event_type text, value float, unit text,
  severity text, message text,
  created_at timestamptz
)
-- event_type = 'alarm' or 'sensor'
-- only alarms are saved here (sensor readings held in subscriber memory only)
```

**SQL run in Session 11:**
```sql
-- Add read column to chat_history (run once)
ALTER TABLE chat_history ADD COLUMN read boolean DEFAULT true;

-- live_events table (run once)
create table live_events (
  id uuid primary key default gen_random_uuid(),
  plant_site text, line text, equip_tag text,
  event_type text, value float, unit text,
  severity text, message text,
  created_at timestamptz default now()
);
create policy "Allow all" on live_events for all using (true) with check (true);
```

---

## Full architecture

```
Operator query (chat.html)
      │
      ▼
Flask /ask or /investigate route (app.py)
      │
      ├── /ask (Q&A + Shift Intel)
      │     extract_equipment_id() — regex detects equip tag from question
      │     get_embedding() — multilingual-e5-large via Pinecone inference
      │     Pinecone query — equip_tag + doc_type + line filters
      │     confidence threshold — 0.30 (with equip filter), 0.35 (without)
      │     top_k=12 — spec chunks rank lower, need more results
      │     llama-3.1-8b — answer generation (streaming)
      │     log_streaming_call() — background thread to llm_logs
      │
      └── /investigate (Agent Investigation)
            extract_equipment_id() — auto-detect from incident text
            get_previous_investigations() — last 3 from chat_history
                  │
                  ▼
            supervisor_route() — llama-3.1-8b, temp=0.0, max_tokens=100
              → returns JSON: {"agents": ["alarm","maintenance"], "reason": "..."}
              → fallback: all 4 agents if JSON invalid
                  │
                  ▼
            ThreadPoolExecutor(max_workers=4) — parallel specialist calls
              run_alarm_agent()       — searches Shift Log doc_type
              run_maintenance_agent() — searches Work Instruction doc_type
              run_sop_agent()         — searches SOP doc_type
              run_ncr_agent()         — searches NCR doc_type
              each: llama-3.1-8b, max_tokens=400, logged to llm_logs
                  │
                  ▼
            run_orchestrator(incident, specialist_results, memory_context)
              llama-3.3-70b, max_tokens=800
              memory_context prepended from get_previous_investigations()
              produces: INVESTIGATION REPORT (technical + plant manager summary)
                  │
                  ▼ (if ENABLE_REFLECTION=true)
            reflection pass — llama-3.3-70b, max_tokens=600
              critiques and improves report
              NEVER changes criticality rating
                  │
                  ▼
            saveToHistory() — saves to chat_history with equip_tag

MQTT pipeline (runs as separate process — Terminal 2):
      │
      ▼
simulator.py (Terminal 3 — demo only)
  SimPy wear-state model
  3 machines: WR-401 (primary), CV-401, PC-701, AT-301, P-201
  Publishes to HiveMQ: plant/northgate/{line}/{equip_tag}/sensor|alarm
      │
      ▼
HiveMQ Cloud (cloud MQTT broker — always running)
  Host: 2949bf9e63b84fac924639d39df6ab3a.s1.eu.hivemq.cloud
  Port: 8883 (TLS)
  Username: pmmessages
      │
      ▼
mqtt_subscriber.py (Terminal 2 — run locally)
  Subscribes to: plant/#  (all topics)
  On sensor event: holds in memory (last 50), does NOT save to Supabase
  On alarm event:
    1. Saves to live_events (Supabase)
    2. Counts alarms for that equip_tag in last PATTERN_WINDOW_DAYS days
    3. If count >= PATTERN_THRESHOLD and cooldown clear:
       - Calls Flask /ask for RAG snippet (SOP guidance)
       - Saves enriched alert to chat_history (mode='proactive', read=False)
       - Sets cooldown for that equip_tag (PROACTIVE_COOLDOWN_MINUTES)
      │
      ▼
Flask routes serve Alerts page
  GET /alerts             → alerts.html
  GET /api/alerts         → unread rows from chat_history where mode='proactive'
  GET /api/alerts/count   → badge count
  POST /api/alerts/<id>/dismiss → marks read=true
  GET /api/live-events    → recent rows from live_events table
      │
      ▼
alerts.html
  Live Equipment Feed — polls /api/live-events every 10s
  Pattern Alert cards — polls /api/alerts every 30s
  Filter pills: All / HIGH / MEDIUM / LOW
  Dismiss All button (filtered or all)
  Investigate button → /chat?equip=...&incident=... (pre-fills Ask tab)
```

---

## MQTT topic structure

```
plant/{plant_site}/{line}/{equip_tag}/{event_type}

Examples:
  plant/northgate/line4/WR-401/alarm
  plant/northgate/line4/WR-401/sensor
  plant/northgate/line3/AT-301/alarm

Subscriber wildcard: plant/#
Payload (alarm):  {value, unit, severity, message}
Payload (sensor): {metric_name: value, ...}
```

## SimPy simulator — equipment modelled

| Equipment | Line | Sensor | Alarm condition |
|-----------|------|--------|----------------|
| WR-401 | line4 | spatter_index | > 3.5 threshold |
| CV-401 | line4 | belt_speed_ms | > 15% deviation |
| PC-701 | line4 | booth_temp_c | outside 18-25°C |
| AT-301 | line3 | torque_nm | outside spec range |
| P-201 | line2 | pressure_bar | pressure drop |

WR-401 starts at wear=0.35, degrades fastest. Reaches HIGH alarm territory in ~4 real minutes. Pattern detection fires (3 alarms) in ~6-8 real minutes.

## Pattern detection config (.env)

```bash
MQTT_HOST=2949bf9e63b84fac924639d39df6ab3a.s1.eu.hivemq.cloud
MQTT_PORT=8883
MQTT_USERNAME=pmmessages
MQTT_PASSWORD=<in .env>
PATTERN_THRESHOLD=3
PATTERN_WINDOW_DAYS=7
PROACTIVE_COOLDOWN_MINUTES=60
```

---

## Key functions and where they live

### app.py
- `extract_equipment_id(text)` — regex extracts WR-401 style tags
- `get_embedding(text)` — calls Pinecone inference API
- `/ask` route — Q&A and shift intel, streaming response
- `/investigate` route — triggers investigation pipeline
- `/alerts` route — serves alerts.html (NEW Session 11)
- `/api/alerts` GET — unread proactive alerts from chat_history (NEW)
- `/api/alerts/count` GET — badge count (NEW)
- `/api/alerts/<id>/dismiss` POST — mark read=true (NEW)
- `/api/live-events` GET — recent alarm rows from live_events (NEW)
- `/api/recent-equipment` — last 4 investigated equipment tags
- `/api/llm-stats` — today's token usage
- `/api/history` POST — saves chat to chat_history

### mqtt_subscriber.py (NEW Session 11)
- `get_supabase()` — lazy init (avoids Windows httpx conflict)
- `on_message()` — routes sensor vs alarm events
- `check_pattern()` — counts alarms, checks cooldown, saves alert
- `get_rag_snippet()` — calls Flask /ask for SOP guidance
- `get_live_feed()` — returns in-memory deque of last 50 events
- `_cooldowns` — dict tracking last alert time per equip_tag

### simulator.py (NEW Session 11)
- SimPy discrete-event simulation
- `get_mqtt_client()` — single shared MQTT connection
- Each machine runs as a SimPy process
- Wear-state model: 0.0-1.0, resets at 1.0 (maintenance done)
- Real sleep 0.3s per sim_minute

### multi_agent.py
- `get_previous_investigations(equip_tag, limit=3)` — memory context
- `supervisor_route(incident, equipment_id)` — dynamic agent routing
- `run_alarm_agent()`, `run_maintenance_agent()`, `run_sop_agent()`, `run_ncr_agent()`
- `run_orchestrator()` — 70b synthesis
- `investigate_incident()` — main generator, yields streaming output
- `_groq_call_with_retry()` — 55s/70s/90s backoff on 429

### llm_logger.py
- `_get_supabase()` — lazy init
- `log_llm_call()` — wraps non-streaming calls
- `log_streaming_call()` — for /ask
- `get_today_stats()` — aggregates llm_logs

### embedder.py
- `_normalise_equip_tag(tag)` — WR401 → WR-401
- `embed_document(doc_id, storage_path, metadata)` — chunks and upserts
- Chunk size: 1000 chars, overlap: 200 chars
- CSV shift logs: custom chunker, 5 rows per batch

---

## UI — what exists and where

### chat.html (Ask tab)
- 3 mode pills: Docs, Shift, Investigate
- Context breadcrumb: Site › Line › Equipment (loads from Supabase)
- History sidebar (toggle)
- Structured report rendering with criticality badge
- Elapsed timer during investigation
- Copy report button
- Query param handler: `/chat?equip=WR-401&incident=...` pre-fills from Alerts

### library.html
- Filter by plant, line, doc type, equipment, text search
- Pagination, embed status badges
- Inline edit form — edit tags and re-index
- Alert badge on Alerts tab (polls every 30s)

### alerts.html (NEW Session 11)
- Live Equipment Feed: last 15 alarm rows, colour-coded by severity, auto-refreshes 10s
- Pattern Alerts section:
  - Filter pills: All / HIGH / MEDIUM / LOW
  - Alert count shown next to section header
  - Dismiss All button (confirms before acting, only dismisses filtered set)
  - Each card: severity badge, equipment, line, summary, SOP guidance box, timestamp
  - Investigate button → `/chat?equip=...&incident=...`
  - Individual Dismiss button
- Refresh button (top right)

### Badge on Ask and Library tabs
- Both pages poll `/api/alerts/count` every 30s
- Alerts tab shows red badge with count when unread alerts exist
- Badge disappears when count = 0

### nav — consistent across all pages
- PlantMind brand, Plant Setup button, GP G. Phani user badge
- Tabs: Ask → /chat | Library → /library | Alerts → /alerts
- 50px nav height on all pages

---

## How to run locally (Session 11 — 3 terminals needed)

```bash
# Terminal 1 — Flask
cd C:\PlantMind
python app.py

# Terminal 2 — MQTT subscriber (always on while demoing)
cd C:\PlantMind
python mqtt_subscriber.py

# Terminal 3 — Simulator (run to generate test data)
cd C:\PlantMind
python simulator.py

# To force a pattern alert immediately (for testing):
python test_pattern.py
```

Render deployment: Flask only. MQTT subscriber runs locally. HiveMQ is the cloud broker. Supabase is the shared bridge — subscriber writes from laptop, Flask reads from Render.

---

## Critical bugs fixed — never revert these

### 1. equip_tag fallback — NEVER drop equipment filter
**File:** app.py
If no results with equip filter → return NOANSWER. Never search without equipment scope.

### 2. load_dotenv() must be FIRST import
**File:** app.py
`load_dotenv()` before any other import. llm_logger.py uses lazy `_get_supabase()`.

### 3. Reflection must not change criticality
**File:** multi_agent.py REFLECTION_PROMPT
Reflection prompt explicitly: never change the criticality rating.

### 4. Ragas requires OpenAI-compatible client
**File:** ragas_test.py
`openai.OpenAI(api_key=GROQ_KEY, base_url="https://api.groq.com/openai/v1")`

### 5. equipment_id_used must be defined at function top
**File:** chat.html — `submitInvestigation()`
Equipment ID extraction at very top before any async code.

### 6. Supabase lazy init everywhere
**Files:** llm_logger.py, mqtt_subscriber.py
All Supabase clients created on first call only — never at module import.

### 7. chat_history read column required for MQTT alerts
**Schema:** chat_history must have `read boolean DEFAULT true` column
Run: `ALTER TABLE chat_history ADD COLUMN read boolean DEFAULT true;`
Without this, all MQTT alert inserts will fail with PGRST204.

---

## Eval test cases

| ID | Mode | What it tests | Status |
|----|------|--------------|--------|
| QA-001 | doc | Basic SOP lookup — AT-301 torque spec | PASS |
| QA-004 | doc | No-data handling — CM-201 unknown equipment | PASS |
| QA-006 | doc | Spatter threshold 3.5 vs 5.0 | PASS |
| SI-001 | shift | Alarm frequency — WR-401 night shift | PASS |
| SI-005 | shift | No events in window — honest no-data | PASS |
| SI-006 | shift | Pattern detection across days | PASS |
| INV-002 | investigation | No history — must not hallucinate | PASS |
| INV-003 | investigation | Safety critical — PC-701 exhaust fan CRITICAL | PASS |
| INV-004 | investigation | Cross-document reasoning liner→burn-in | FAIL (known 8b limit) |
| INV-006 | investigation | Conflicting signals — false high reading | PASS |

**Baseline: 90% (9/10). INV-004 is known 8b limitation, not a bug.**

---

## Ragas results

```
Run date: Session 9
Faithfulness:   1.00  (target 1.00) ✓
Context recall: 0.88  (target 0.85) ✓
```

---

## Rate limit reference

| Model | RPD | TPM | TPD |
|-------|-----|-----|-----|
| llama-3.1-8b-instant | 14,400 | 6,000 | 500,000 |
| llama-3.3-70b-versatile | 1,000 | 12,000 | 100,000 |

MQTT pattern detection calls /ask (8b only) — cheap. Does NOT call /investigate pipeline.
Check `/api/llm-stats` before running evals.

---

## Demo checklist

```bash
# 1. Check Supabase is active — supabase.com dashboard
# 2. Start Flask
python app.py
# 3. Start subscriber
python mqtt_subscriber.py
# 4. Start simulator (generates live data)
python simulator.py
# 5. Visit http://localhost:5000/chat — Ask tab working
# 6. Visit http://localhost:5000/alerts — Live feed populating
# 7. Wait 6-8 min or run test_pattern.py — alert card appears
# 8. Click Investigate on alert card — pre-fills Ask tab
```

---

## Known issues

1. **INV-004** — known 8b model limitation, not a bug
2. **Render deployment** — MQTT subscriber cannot run on Render free tier (no background workers). Runs locally. All Flask routes work on Render.
3. **Simulator is demo-only** — in production, real equipment sends MQTT messages. Delete simulator.py for production.

---

## Session history summary

| Session | Key change | Eval score |
|---------|-----------|------------|
| 1-4 | RAG pipeline, basic Q&A, document upload | Not measured |
| 5 | Eval suite, equip_tag fallback bug fixed | 65% |
| 6 | Reflection, model split, retry handler | 90% |
| 7 | LLM observability, embed status, equipment auto-detect | 90% |
| 8 | Supervisor agent, dynamic routing | 90% |
| 9 | Agent memory, one-tap templates, Ragas, UX hardening | 90% |
| 10 | Plant setup CRUD, dynamic dropdowns, unified input, library fix | 90% |
| 11 | MQTT real-time integration, HiveMQ, SimPy simulator, alerts page | 90% |

---

## Full backlog (updated after Session 11)

### Completed stories
| ID | Story | Session |
|----|-------|---------|
| PM-001 | Document upload and embedding pipeline | 1-2 |
| PM-002 | Basic Q&A mode with RAG | 2-3 |
| PM-003 | Shift Intelligence mode | 3 |
| PM-004 | Multi-agent investigation pipeline | 4 |
| PM-005 | Eval suite 10 cases | 5 |
| PM-026 | Reflection pattern | 6 |
| PM-027 | Model split 8b/70b | 6 |
| PM-028 | Retry handler with backoff | 6 |
| PM-039 | LLM observability and stats widget | 7 |
| PM-INV01 | Embed status badges on library cards | 7 |
| PM-014 | Equipment auto-detect from operator input | 7 |
| PM-037 | Supervisor agent with dynamic routing | 8 |
| PM-038 | Agent memory across investigations | 9 |
| PM-041 | One-tap investigation templates | 9 |
| PM-RAGAS-01 | Ragas baseline — faithfulness 1.00 | 9 |
| MQTT-001 | HiveMQ cloud broker setup | 11 |
| MQTT-002 | SimPy wear-state plant simulator | 11 |
| MQTT-003 | PlantMind MQTT subscriber | 11 |
| MQTT-004 | live_events Supabase table | 11 |
| PM-040 | Proactive pattern detection | 11 |
| PM-040-UI | Alerts standalone page with filters + dismiss all | 11 |

### Next session — Session 12 options

**Option A — LangGraph agent architecture upgrade**
| ID | Story | Effort |
|----|-------|--------|
| PM-LG-001 | LangGraph migration — refactor multi_agent.py to StateGraph | 4 hrs |
| PM-LG-002 | Safety critic agent node — LOTO/PPE audit before every response | 2 hrs |
| PM-LG-003 | Retry and loop handling via conditional edges | 1 hr |

**Option B — Quality and eval expansion**
| ID | Story | Effort |
|----|-------|--------|
| PM-RAGAS-02 | Expand Ragas golden dataset to 15 cases | 2 hrs |
| PM-RAGAS-03 | Ragas with reflection on vs off | 1 hr |
| PM-RAGAS-04 | Shift intel Ragas cases | 2 hrs |

**Option C — High-value product features**
| ID | Story | Effort |
|----|-------|--------|
| PM-SH-001 | Prescriptive shift handover — "3 things needing attention, ranked by risk" | 3 hrs |
| PM-VISION-001 | Multimodal vision — photo to investigation | 4 hrs |
| PM-IK-001 | Institutional knowledge capture form | 2 hrs |

### Future (requires live data or integrations)
| ID | Story | Notes |
|----|-------|-------|
| PM-RUL-001 | Remaining Useful Life estimation | live_events now exists — buildable |
| PM-ERP-001 | Work order creation via n8n | Closes investigation→action gap |
| PM-SPARE-001 | Spare parts intelligence | Requires inventory integration |
| PM-TWIN-001 | Digital twin foundation | live_events is the seed — long-term |
| PM-N8N-001 | Slack/email alerts via n8n | Trigger on proactive alerts |

---

## New laptop setup

- Python 3.11.9 (not 3.14 — ragas/scikit-network need 3.11)
- Clean venv, requirements.txt covers core + evals + ragas
- No pyiceberg, no scikit-network
- Git configured
- .env transferred — includes MQTT vars from Session 11

## Requirements

```
flask, gunicorn, groq, pinecone, supabase, python-dotenv,
langchain-community, langchain-text-splitters, langchain-groq,
pypdf, requests, openai, ragas, datasets,
paho-mqtt, simpy
```

Do NOT run pip freeze — pulls in pyiceberg from ragas dependencies.

---

## Market research — gaps vs industry

- RAG across maintenance docs ✓ | Multi-agent investigation ✓ | Measured quality baseline ✓
- **Gap 1 — RUL:** live_events now exists — first data for this
- **Gap 2 — Digital twin:** live_events is the foundation
- **Gap 3 — ERP/work orders:** n8n integration, future
- **Gap 4 — Computer vision:** requires camera hardware
- **Gap 5 — Prescriptive shift handover:** buildable now with live_events

Key stat: GenAI and RAG reduce root cause identification from 6-10 hours to nearly instantaneous. PlantMind does this. MQTT adds proactive detection — system notices patterns before operators do.

---

## How to continue in a new chat

Paste this entire file as your first message, then add:
```
This session I want to: [describe what to build]
```

*PlantMind · Session 11 complete · Push to GitHub before next session*
