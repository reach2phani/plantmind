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

*PlantMind · Session 9 complete · Update this file at end of each session*
