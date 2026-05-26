# PlantMind — Full Project Context for Claude

> This is the complete handoff document. Paste this entire file at the start of any new Claude conversation.
> Last updated: Session 9 complete.

---

## Project summary

PlantMind is an AI assistant for manufacturing plant operators built from scratch as a learning project by a Technical Product Manager on a career break. The goal was to learn AI engineering by building something real, not reading about it.

An operator describes an equipment incident — "WR-401 welding robot wire feed stuttering, third time this week" — and gets a structured investigation report drawn from uploaded SOPs, maintenance records, shift logs, and NCR reports. The report shows criticality first, immediate action highlighted, root cause, and sources used.

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
| API framework | Flask | Streaming responses via stream_with_context |
| Hosting | Render free tier | Spins down after inactivity |
| Frontend | Vanilla JS + HTML | No framework, chat.html is main UI |

---

## Repository structure

```
C:\PlantMind\                     (Windows, VS Code)
├── app.py                        — Flask API, all routes
├── multi_agent.py                — Full agent pipeline
├── llm_logger.py                 — LLM observability
├── embedder.py                   — Document chunking and Pinecone upsert
├── reembed.py                    — Re-index all documents
├── nav_context.js                — Plant site context (also in static/)
├── templates/
│   ├── chat.html                 — Main UI (3 modes)
│   ├── library.html              — Document library
│   └── index.html                — Upload interface
├── static/
│   └── nav_context.js
├── evals/
│   ├── test_cases.json           — 10 test cases
│   ├── eval_runner.py            — Test runner
│   ├── baseline_session6.json    — 90% baseline locked
│   └── baseline_session8.json    — 90% baseline locked
├── ragas_test.py                 — Ragas evaluation script
├── requirements.txt              — Locked after clean venv reinstall
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
  equip_tag text, created_at timestamptz
)

llm_logs (
  id uuid, model text, call_type text,
  input_tokens int, output_tokens int, latency_ms int,
  error text, plant_site text, equip_tag text,
  created_at timestamptz
)

plant_sites (
  id uuid, name text, created_at timestamptz
)
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
            _groq_call_with_retry() — 55s/70s/90s backoff on 429
```

---

## Key functions and where they live

### app.py
- `extract_equipment_id(text)` — regex extracts WR-401 style tags, normalises to uppercase-hyphenated
- `get_embedding(text)` — calls Pinecone inference API
- `_init_connections()` — lazy init for Supabase, Pinecone, Groq (avoids Windows httpx conflict)
- `/ask` route — Q&A and shift intel, streaming response
- `/investigate` route — triggers investigation pipeline
- `/api/recent-equipment` — returns last 4 investigated equipment tags from chat_history
- `/api/llm-stats` — today's token usage from llm_logs
- `/api/history` POST — saves chat to chat_history with equip_tag
- `/api/plant-sites` — dynamic plant site list from Supabase

### multi_agent.py
- `get_previous_investigations(equip_tag, limit=3)` — queries chat_history, returns memory context string
- `supervisor_route(incident, equipment_id)` — classifies incident, returns agent list + reason
- `run_alarm_agent(incident, equipment_id)` — shift log specialist
- `run_maintenance_agent(incident, equipment_id)` — work instruction specialist
- `run_sop_agent(incident, equipment_id)` — SOP specialist
- `run_ncr_agent(incident, equipment_id)` — NCR specialist
- `run_orchestrator(incident, specialist_results, memory_context)` — synthesis
- `investigate_incident(incident, equipment_id)` — main generator function, yields streaming output
- `_groq_call_with_retry(fn, call_type, model)` — wraps all Groq calls with retry + logging
- `ENABLE_REFLECTION` — reads from env var, default false

### llm_logger.py
- `_get_supabase()` — lazy init, creates client on first call not at import
- `log_llm_call(fn, call_type, model, plant_site, equip_tag)` — wraps non-streaming calls
- `log_streaming_call(call_type, model, input_text, output_text, latency_ms)` — for /ask
- `get_today_stats()` — aggregates llm_logs for /api/llm-stats endpoint

### embedder.py
- `_normalise_equip_tag(tag)` — WR401 → WR-401, wr-401 → WR-401
- `embed_document(doc_id, storage_path, metadata)` — chunks and upserts to Pinecone
- Chunk size: 1000 chars, overlap: 200 chars
- CSV shift logs: custom chunker groups 5 rows into natural language batches

---

## Eval test cases

| ID | Mode | What it tests | Current status |
|----|------|--------------|----------------|
| QA-001 | doc | Basic SOP lookup — AT-301 torque spec | PASS |
| QA-004 | doc | No-data handling — CM-201 unknown equipment, must not hallucinate | PASS |
| QA-006 | doc | Spatter threshold 3.5 vs 5.0 — must return initial alarm not auto-quarantine | PASS |
| SI-001 | shift | Alarm frequency — how many WR-401 alarms night shift | PASS |
| SI-005 | shift | No events in window — honest no-data response | PASS |
| SI-006 | shift | Pattern detection across days — WR-401 recurring | PASS |
| INV-002 | investigation | No history — must state insufficient data, not hallucinate | PASS |
| INV-003 | investigation | Safety critical — PC-701 exhaust fan, must assign CRITICAL | PASS |
| INV-004 | investigation | Recent maintenance — connect liner replacement to burn-in SOP | FAIL (known) |
| INV-006 | investigation | Conflicting signals — sensor residue after clean, false high reading | PASS |

**INV-004 failure reason:** 8b specialist agents find liner replacement in maintenance log but do not connect it to the burn-in requirement in the SOP. Requires cross-document reasoning that 8b model cannot reliably do. Would improve with reflection enabled or 70b specialist agents (not viable on free tier).

---

## Ragas results

```
Run date: Session 9
Judge: llama-3.1-8b via Groq OpenAI-compatible endpoint
Context source: Pinecone direct query (not API response)

RQ-001 (spatter threshold 3.5 vs 5.0):
  Faithfulness:     1.00  ✓
  Context recall:   1.00  ✓

RQ-002 (burn-in SOP procedure after liner replacement):
  Faithfulness:     1.00  ✓
  Context recall:   0.75  (ground truth has LOW criticality claim not in SOP)

Overall:
  Faithfulness:     1.00  (target 1.00) ✓
  Context recall:   0.88  (target 0.85) ✓
```

---

## Critical bugs fixed — never revert these

### 1. equip_tag fallback — NEVER drop equipment filter
**File:** app.py  
**What happened:** Original fallback dropped all Pinecone filters when no results found. Returned Fanuc robot manual for CM-201 query at 0.82 confidence.  
**Fix:** If no results with equip filter, return NOANSWER response. Never search without equipment scope.

### 2. load_dotenv() must be FIRST import
**File:** app.py  
**What happened:** Flask crashed silently on Windows when llm_logger.py created Supabase connection at import time before env vars loaded. httpx connection pooling conflict.  
**Fix:** `load_dotenv()` is called before any other import in app.py. llm_logger.py uses lazy `_get_supabase()` function.

### 3. Reflection must not change criticality
**File:** multi_agent.py REFLECTION_PROMPT  
**What happened:** Reflection agent was adding "safety risk manageable" text, causing CRITICAL keyword to appear in wrong context.  
**Fix:** Reflection prompt explicitly states: never change the criticality rating.

### 4. Ragas requires OpenAI-compatible client
**File:** ragas_test.py  
**What happened:** Native `groq.Groq()` client fails with Ragas — it expects OpenAI interface.  
**Fix:** `openai.OpenAI(api_key=GROQ_KEY, base_url="https://api.groq.com/openai/v1")`

### 5. equipment_id_used must be defined at function top
**File:** templates/chat.html — `submitInvestigation()`  
**What happened:** Variable was defined inside streaming block, undefined when saveToHistory called. Memory feature showed "no previous investigations" on second run.  
**Fix:** Equipment ID extraction at very top of submitInvestigation() before any async code.

### 6. Supabase lazy init in llm_logger
**File:** llm_logger.py  
**What happened:** Creating Supabase client at module level in llm_logger.py conflicted with app.py doing the same — Windows httpx crash.  
**Fix:** `_get_supabase()` function creates client on first call only.

---

## UI features — what exists and where

### chat.html
- **3 mode tabs:** Documents, Shift log, Investigate — clears answers on switch
- **Context banner:** Yellow warning when plant site not set, wired to nav_context.js
- **Context pill:** Nav bar, plant site + line, persists to localStorage
- **LLM stats widget:** Nav bar, click to see token usage per model with progress bars
- **Shift time picker:** Night/Day/Afternoon presets + custom inputs, auto-selects current shift
- **Quick investigate panel:** Equipment chips (from recent history or documents), incident type cards, collapsible with minimize button, state persists to localStorage
- **Structured report rendering:** parseReportSections() parses investigation output, criticality badge first, immediate action in blue box, sources collapsed
- **Elapsed timer:** Shows Xs during investigation, "Done in Xs" on completion
- **Copy report button:** Copies full report to clipboard via addEventListener (not inline onclick)
- **No-answer cards:** Show gaps link when equip tag detected (currently points to /gaps — BROKEN, needs fix)

### library.html
- Filter by plant site, line, doc type, equipment tag, text search
- Filter state persists to localStorage (pm_lib_search, pm_lib_plant, pm_lib_line)
- Pagination with keepPage flag (goPage passes {keepPage:true} to filterDocs)
- Embed status badges: green=indexed, amber=indexing, red=failed
- embedStatusBadge() function, positioned below equip tag on card

### nav_context.js
- PlantMindContext.get() / PlantMindContext.set()
- Loads plant sites from /api/plant-sites dynamically
- updateHeader() shows context banner when plant not set
- Persists to localStorage

---

## Known broken things (fix when time permits)

1. **Knowledge gaps tab in library.html** — still shows "Knowledge gaps" link pointing to /gaps which no longer exists. Remove the tab from library.html.
2. **No-answer card gaps link** — chat.html no-answer cards show "Check document coverage" link pointing to /gaps. Remove or update.
3. **INV-004** — known 8b model limitation, not a bug.

---

## Rate limit reference

| Model | RPM | RPD | TPM | TPD |
|-------|-----|-----|-----|-----|
| llama-3.1-8b-instant | 30 | 14,400 | 6,000 | 500,000 |
| llama-3.3-70b-versatile | 30 | 1,000 | 12,000 | 100,000 |

**Practical limits for testing:**
- ~500 investigations/day before hitting 70b RPD
- Check `/api/llm-stats` before running evals to see remaining daily budget
- Supabase free tier pauses after 7 days inactivity — always check first

---

## Demo checklist (run before any demo)

```bash
# 1. Check Supabase is active — supabase.com dashboard
# 2. Start Flask
python app.py
# 3. Run eval suite to confirm 90%
python eval_runner.py
# 4. Safe demo investigation query:
# "WR-401 welding robot on Line 4 has triggered a spatter index alarm.
#  Third time this week. Investigate root cause."
```

---

## Next planned work (in priority order)

1. **Fix broken things** — remove Knowledge gaps tab from library.html, fix no-answer card gaps link
2. **New laptop setup** — install Python 3.11, Git, VS Code, clone repo, pip install -r requirements.txt, create .env
3. **MQTT real-time integration** — Mosquitto broker + Simpy plant simulator + PlantMind MQTT subscriber. Topic structure: `plant/northgate/line4/WR-401/alarm`. Writes to Supabase live_events table. Replaces manual CSV upload for shift intelligence.
4. **PM-040 proactive pattern detection** — scans live_events for recurring alarms (3+ in 7 days), auto-triggers investigation, saves to chat_history with mode="proactive", surfaces in alerts tab
5. **LangGraph migration** — refactor multi_agent.py linear pipeline to StateGraph with conditional edges, loops, and retries
6. **Safety critic agent** — mandatory audit node checks every response against LOTO/PPE document index before output
7. **Expand Ragas golden dataset** — 10-15 cases for statistical significance

---

## Session history summary

| Session | Key change | Eval score |
|---------|-----------|------------|
| 1-4 | RAG pipeline, basic Q&A, document upload | Not measured |
| 5 | Eval suite built, equip_tag fallback bug fixed | 65% baseline |
| 6 | Reflection pattern, model split, retry handler | 90% |
| 7 | LLM observability, embed status, equipment auto-detect | 90% |
| 8 | Supervisor agent, dynamic routing | 90% |
| 9 | Agent memory, one-tap templates, Ragas, UX hardening, LEARNING.md, CONTEXT.md | 90% |

---

## How to continue in a new chat

Paste this entire file as your first message, then add:
```
This session I want to: [describe what to build]
```

Claude will have full context to continue without any gaps.

---

## Market research findings — gaps vs industry

Research date: Session 9. Sources: YC S22-S26 companies, IBM, Deloitte, IDC, Siemens.

### What PlantMind has that the market values
- RAG across maintenance documents ✓
- Multi-agent investigation ✓
- Measured quality baseline with Ragas ✓ — most competitors do not publicly document this

### What major companies are solving that PlantMind is missing

**Gap 1 — Remaining Useful Life (RUL) estimation**
Companies like Siemens and Praxis predict when a component will fail, not just investigate after it fails. "WR-401 wire liner has approximately 4 days of life remaining based on current wear pattern." PlantMind investigates after failure. RUL predicts before. Requires sensor data stream — not buildable at $0 without MQTT integration first.

**Gap 2 — Digital twins**
A digital twin mirrors real equipment state in software. Every sensor reading updates the model. Companies like Siemens are unlocking CAPEX savings in tens of millions by deferring asset replacements using physics-based AI twins. PlantMind searches documents — it has no live equipment model. Long-term goal.

**Gap 3 — ERP and work order integration**
PlantMind generates an investigation report. It does not create the work order in SAP, assign the technician, or order the spare part. Tiny (YC) and Lumari (YC) are building exactly this — AI agents that compress sourcing, RFQ, and PO workflows. Value stops at investigation not action. Buildable via n8n webhooks in Session 10+.

**Gap 4 — Computer vision quality control**
Inspecting 100% of parts in real time against spec at production speed. PlantMind has no vision layer. High ROI in manufacturing — catching defects the human eye misses. Requires camera hardware on the line. Future phase.

**Gap 5 — Supply chain and spare parts intelligence**
When PlantMind recommends "replace the wire liner," it does not know if one is in stock, lead time, or supplier. Lumari (YC) deploys AI agents that run sourcing workflows end-to-end. Requires ERP/inventory system integration.

**Gap 6 — Prescriptive shift handover**
PlantMind tells operators what happened and why. It does not tell the incoming shift supervisor "here are the 3 things that need attention today, ranked by risk, with recommended action for each." This is the step from reactive investigation to prescriptive intelligence. Buildable with current architecture — no new integrations needed. Highest near-term value.

### Market context
- By 2028, 33% of enterprise applications will include agentic AI capable of making semi-autonomous decisions — including adjusting machine parameters before a human operator notices a problem
- 71% of organisations use AIoT for predictive maintenance, making it the primary strategy for increasing competitiveness
- GenAI and RAG solve alert fatigue by analysing unstructured data such as 6,000-page OEM manuals, reducing root cause identification from 6-10 hours to nearly instantaneous — this is exactly what PlantMind does

---

## Full backlog (all stories, prioritised)

### Immediate fixes (do first)
| ID | Story | Effort | Notes |
|----|-------|--------|-------|
| FIX-001 | Remove Knowledge gaps tab from library.html | 15 min | Tab still points to /gaps which was deleted |
| FIX-002 | Remove gaps link from no-answer cards in chat.html | 15 min | Same broken /gaps route |

### Session 10 — Real-time integration
| ID | Story | Effort | Notes |
|----|-------|--------|-------|
| MQTT-001 | Install Mosquitto broker locally | 30 min | mosquitto.org/download |
| MQTT-002 | Build Simpy plant simulator | 2 hrs | Publishes alarm events to MQTT topics |
| MQTT-003 | PlantMind MQTT subscriber | 2 hrs | Listens to topics, writes to live_events table |
| MQTT-004 | Supabase live_events table | 30 min | Schema: plant_site, line, equip_tag, event_type, value, timestamp |
| PM-040 | Proactive pattern detection | 3 hrs | Scans live_events for 3+ alarms in 7 days, auto-investigates |
| PM-040-UI | Alerts tab in chat.html | 2 hrs | Badge count on tab, alert cards with severity, dismiss button |

### Session 11 — Agent architecture upgrade
| ID | Story | Effort | Notes |
|----|-------|--------|-------|
| PM-LG-001 | LangGraph migration | 4 hrs | Refactor multi_agent.py to StateGraph |
| PM-LG-002 | Safety critic agent node | 2 hrs | Mandatory LOTO/PPE audit before every response |
| PM-LG-003 | Retry and loop handling | 1 hr | LangGraph conditional edges replace manual retry logic |

### Session 12 — Quality and validation
| ID | Story | Effort | Notes |
|----|-------|--------|-------|
| PM-RAGAS-02 | Expand Ragas golden dataset to 15 cases | 2 hrs | Statistical significance |
| PM-RAGAS-03 | Ragas with reflection on vs off | 1 hr | Measure if reflection actually improves faithfulness |
| PM-RAGAS-04 | Shift intel Ragas cases | 2 hrs | Add faithfulness measurement for shift log queries |

### Session 13 — High-value product features
| ID | Story | Effort | Notes |
|----|-------|--------|-------|
| PM-SH-001 | Prescriptive shift handover | 3 hrs | "3 things needing attention today, ranked by risk" — buildable now |
| PM-VISION-001 | Multimodal vision — photo to investigation | 4 hrs | Operator points camera at error screen, AI reads and investigates |
| PM-IK-001 | Institutional knowledge capture | 2 hrs | Structured form for veteran engineer notes |

### Future (requires live data or integrations)
| ID | Story | Notes |
|----|-------|-------|
| PM-RUL-001 | Remaining Useful Life estimation | Requires sensor data stream via MQTT |
| PM-ERP-001 | Work order creation via n8n | Closes the investigation→action gap |
| PM-SPARE-001 | Spare parts intelligence | Requires inventory system integration |
| PM-TWIN-001 | Digital twin foundation | Long-term — requires live sensor data model |
| PM-VISION-002 | Computer vision quality control | Requires camera hardware on production line |
| PM-N8N-001 | Slack/email alerts via n8n | Trigger on CRITICAL investigations |

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
| PM-RAGAS-01 | Ragas baseline — faithfulness 1.00, context recall 0.88 | 9 |


## New laptop setup — completed
- Python 3.11.9 installed (not 3.14 — packages like ragas/scikit-network need 3.11)
- Clean venv created with Python 3.11
- requirements.txt cleaned — removed pyiceberg and scikit-network (ragas transitive deps that require C++ Build Tools)
- Git configured with user name and email
- 90% eval baseline confirmed on new laptop
- .env file transferred from old laptop

## Requirements files
- `requirements.txt` — single file covering core app + evals + ragas. No pyiceberg, no scikit-network.
- If pip install fails with C++ build error, it means Python version is too new. Use Python 3.11.9.
- Do NOT run pip freeze to regenerate requirements.txt — it will pull in pyiceberg again from ragas dependencies

## Knowledge gaps dashboard — removed
- /gaps and /api/gaps routes deleted from app.py
- Knowledge gaps nav tab removed from chat.html
- library.html still has a broken gaps tab — FIX-001 still pending
- No-answer card gaps link in chat.html — FIX-002 still pending

## Additional backlog items added this session
- Hybrid RAG — combine keyword + semantic search, Pinecone supports natively, improves context recall from 0.88 toward 0.95+
- Prescriptive shift handover — "3 things needing attention today ranked by risk", buildable now
- Graph RAG — knowledge graph layer for multi-hop reasoning, frontier 2026 architecture
- Self-RAG — agent decides when to retrieve vs answer from memory
- n8n workflows — Slack alerts, auto document ingestion, shift handover email, work order creation

## Next session starts with
MQTT integration (Session 10):
1. Install Mosquitto from mosquitto.org
2. pip install paho-mqtt simpy (add to requirements.txt after)
3. Build Simpy plant simulator
4. Build PlantMind MQTT subscriber
5. Create Supabase live_events table
6. PM-040 proactive pattern detection on top of live events

*PlantMind · Session 9 complete · Update this file at end of each session*

---

## Session 10 — UX Rebuild + Plant Setup

### New Supabase tables
```sql
-- Lines table
create table lines (
  id uuid primary key default gen_random_uuid(),
  name text not null, plant_site text not null,
  active bool default true, created_at timestamptz default now()
);
-- Equipment table
create table equipment (
  id uuid primary key default gen_random_uuid(),
  equip_tag text not null unique, name text not null,
  type text, plant_site text not null, line text not null,
  manufacturer text, active bool default true,
  created_at timestamptz default now()
);
-- RLS policies needed:
create policy "Allow all" on lines for all using (true) with check (true);
create policy "Allow all" on equipment for all using (true) with check (true);
-- Seed data already inserted for Northgate Automotive
```

### New Flask routes added to app.py
```
GET  /plant-setup              → plant_setup.html template
GET  /api/lines                → all lines, ?plant_site=X to filter
POST /api/lines                → create line {name, plant_site}
PATCH /api/lines/<id>          → update line
DELETE /api/lines/<id>         → delete line
GET  /api/equipment            → all equipment, ?plant_site=X&line=Y
POST /api/equipment            → create equipment {equip_tag, name, type, plant_site, line, manufacturer}
PATCH /api/equipment/<id>      → update equipment / toggle active
DELETE /api/equipment/<id>     → delete equipment
PATCH /api/plant-sites/<id>    → update site name
DELETE /api/plant-sites/<id>   → delete site
```

### New templates
- `templates/plant_setup.html` — full CRUD for sites, lines, equipment
  - Hierarchy tree sidebar (site → line → equipment)
  - Detail panel with stats, fields, edit forms
  - Confirmation dialog for all deletes
  - Inline add/edit forms — no modals
  - Full CRUD: Create, Read, Update, Delete, Activate/Deactivate

### Nav changes (all pages)
- Upload tab removed from nav — upload now lives inside Library as inline panel
- Plant setup button added top right on all pages
- GP G. Phani user badge replaces context pill
- chat.html: Ask tab is now a `<span>` not an `<a>` — prevents page reload on click
- library.html: nav height fixed to 50px (was 54px), matching chat.html

### Chat page — unified input component
- Mode tabs bar removed — replaced with mode pills inside input box
- Context selectors (site/line/equipment) moved inside input box as breadcrumb
- Breadcrumb format: Northgate Automotive › Line 4 › WR-401 ▾
- Site, Line, Equipment now load dynamically from Supabase via API
- Lines filter by selected plant, Equipment filters by selected line
- Input area has grey background (#f8fafc) to visually separate from answers
- Input wrap has purple-tinted border (#ddd6fe) at rest, stronger on focus

### Known remaining issues
- FIX-001: library.html knowledge gaps tab — already removed in nav but check
- FIX-002: no-answer card gaps link in chat.html — may still reference /gaps
- Library upload inline panel — context bar added but needs testing end-to-end
- eval_runner.py — confirm 90% baseline after laptop setup before MQTT

### Next session — MQTT integration (Session 11)
Priority order:
1. Run eval_runner.py — confirm 90% baseline
2. Install Mosquitto: mosquitto.org/download
3. pip install paho-mqtt simpy (add to requirements.txt after)
4. Build Simpy plant simulator — publishes to plant/northgate/line4/WR-401/alarm
5. Build PlantMind MQTT subscriber — writes to Supabase live_events table
6. Create live_events table in Supabase
7. PM-040 proactive pattern detection on top of live events

### live_events table SQL (run before Session 11)
```sql
create table live_events (
  id uuid primary key default gen_random_uuid(),
  plant_site text, line text, equip_tag text,
  event_type text, value float, unit text,
  severity text, message text,
  created_at timestamptz default now()
);
create policy "Allow all" on live_events for all using (true) with check (true);
```

*PlantMind · Session 10 complete · Update this file at end of each session*

---

## Session 10 additions — dynamic dropdowns and library fix

### Library page — now fully dynamic
- Plant, Line, Equipment filters load from Supabase via API — not from document metadata
- Changing plant reloads lines, changing line reloads equipment
- Equipment shown as "WR-401 — Welding Robot" format
- Filter state syncs from localStorage (set context on Ask → Library picks it up)
- Functions added: populateLibLines(), populateLibEquip(), onLibPlantChange(), onLibLineChange()

### Chat page — dynamic dropdowns
- Line dropdown loads from /api/lines filtered by selected plant
- Equipment dropdown loads from /api/equipment filtered by plant and line
- Only active equipment shown
- loadLineOpts() and loadEquipmentOpts() called on every site/line change
- window._allLines and window._allEquipment cached globally

### Full audit — all 23 checks passing
- No /gaps references anywhere
- All nav consistent — GP G. Phani badge, Plant setup button, 50px height
- All dropdowns load from API dynamically
- Plant Setup CRUD complete — sites, lines, equipment
- FAB removed from plant setup
- Mode pills working — Docs, Shift, Investigate
- Breadcrumb context working — Site › Line › Equipment

### Pending before MQTT (nothing blocking)
- Run eval_runner.py to confirm 90% baseline still holds
- Upload inline panel in library — built but needs end-to-end test
- index.html (standalone upload page) — kept as fallback, has ← Back to Library link

*PlantMind · Session 10 complete · Ready for MQTT (Session 11)*
