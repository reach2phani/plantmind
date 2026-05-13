# PlantMind — AI Engineering Concepts

> A plain-language reference built from 9 sessions of building PlantMind from scratch.
> Every concept has a real example, a real failure, and a real fix.
> Written so anyone can understand it — no AI background needed.

---

## Quick reference — key numbers

| Number | What it means |
|--------|--------------|
| 90% | Eval baseline — 9 of 10 test cases passing. Up from 65% in Session 5. |
| 65% → 90% | +25 point improvement across 4 sessions. Each had before/after measurement. |
| 1.00 | Ragas faithfulness score. Zero hallucinations across golden dataset. |
| 0.88 | Ragas context recall. Above the 0.85 manufacturing industry benchmark. |
| top_k = 12 | Chunks retrieved per query. Increased from 8 when spec chunks ranked 9th. |
| 0.30 / 0.35 | Confidence thresholds. Lower when equipment filter active, higher otherwise. |
| 8b / 70b split | 8b for specialists (14,400 RPD), 70b for orchestrator (1,000 RPD). Separate pools. |
| 1,000 chars | Chunk size with 200 char overlap. Balances context and specificity. |
| ~500/day | Investigations possible on free tier. Limited by 70b RPD limit. |
| 100K TPD | Daily token limit on 70b. Exhausted in one debugging session — why observability matters. |

---

## Concept 1 — RAG (Retrieval Augmented Generation)

**Used in:** `/ask` route, all specialist agents  
**Eval impact:** +25 points when retrieval bugs fixed

### What it is

> **Analogy:** Imagine a new employee asked a question about company policy. A bad employee makes up an answer from memory. A good employee walks to the filing cabinet, finds the relevant document, reads it, and answers based on what is actually written. RAG makes the AI do the second thing — find the document first, then answer.

Instead of relying on what the AI learned during training, RAG retrieves relevant document chunks from a database first, then passes those chunks as context. The AI answers from what it retrieved, not what it remembers.

### How I used it in PlantMind

```
Operator asks: "What is the spatter index alarm threshold for WR-401?"
Step 1: Question converted into a vector (embedding)
Step 2: Pinecone searches for most similar document chunks
Step 3: Top 12 chunks retrieved from SOP and maintenance log
Step 4: Chunks passed to LLM as context
Step 5: LLM answers "3.5" because it read it from the retrieved document
```

### Real failure I hit

The system was returning **5.0** (auto-quarantine threshold) instead of **3.5** (initial alarm threshold). The 3.5 chunk existed in the index but was ranked 9th. The system was only retrieving top 8, so the correct chunk was never seen. The LLM answered 5.0 because that was in the chunks it received.

### How I fixed it

Increased `top_k` from 8 to 12. The 3.5 chunk was now included. Ragas faithfulness jumped from **0.0 to 1.00** — confirming the answer was now grounded in the retrieved document, not guessed from training data.

### Tradeoff

Higher `top_k` = more text passed to LLM = higher cost and slower responses. 12 was the minimum that reliably included specification chunks while staying within the token budget.

### Interview question to practise

> *"Why did you choose RAG over fine-tuning?"*

Plant documents change frequently. Fine-tuning bakes knowledge into model weights at training time — a revised SOP would require retraining. RAG retrieves from a live index so new documents are immediately searchable after upload. No retraining required.

---

## Concept 2 — Vector Embeddings

**Used in:** All document uploads, all search queries  
**Model used:** multilingual-e5-large via Pinecone inference API

### What it is

> **Analogy:** Every document in your filing cabinet is given a GPS coordinate based on its meaning. Documents about welding robots cluster near each other. Documents about pump maintenance cluster elsewhere. When you ask a question, the system converts your question into a GPS coordinate and finds the nearest documents. That is what embeddings do — they convert text into coordinates so you can find similar text by measuring distance.

An embedding is a list of numbers (a vector) that represents the meaning of a piece of text. Similar meanings produce similar vectors. Pinecone finds which document vectors are closest to the question vector.

### Real failure I hit

Specification chunks (short text with just numbers like "3.5") produced **lower similarity scores** than procedure chunks (longer descriptive text). A question about "alarm threshold" matched a paragraph describing the alarm response procedure better than a line saying "alarm threshold: 3.5". The number was ranked lower even though it was the direct answer.

### How I fixed it

Two fixes. Increased `top_k` so lower-ranked chunks were still included. Lowered the confidence threshold from 0.35 to 0.30 when equipment filter was active — we already know we are looking at the right machine so slightly lower similarity is still valid.

### Interview question to practise

> *"What is an embedding and why does it matter for RAG?"*

An embedding converts text into a list of numbers representing meaning. Similar meanings produce similar numbers. RAG uses embeddings to find relevant chunks by measuring distance between the question vector and document vectors. The quality of the embedding model directly determines retrieval quality.

---

## Concept 3 — Multi-Agent Systems

**Used in:** Investigation mode — 4 specialist agents + orchestrator  
**Architecture:** Parallel fan-out → synthesis

### What it is

> **Analogy:** When a patient goes to hospital with an unusual symptom, a single GP might struggle. Better to call in specialists — a cardiologist, a neurologist, a blood specialist — and then have a senior doctor read all their reports and make a diagnosis. PlantMind does the same. Four specialist agents each search a specific document type, and an orchestrator synthesises their findings.

### How I used it in PlantMind

```
WR-401 wire feed stuttering investigation:
Alarm agent     → found 4 spatter alarms in 7 days (shift logs)
Maintenance agent → found liner replacement on Apr 19 (work instructions)
SOP agent       → found burn-in procedure requirement (SOP)
NCR agent       → found previous spatter recurrence report (NCRs)
Orchestrator    → synthesised: burn-in incomplete after liner replacement,
                  MEDIUM criticality, immediate action: complete burn-in
```

### Real failure I hit

Originally all 4 agents always ran regardless of incident type. A safety event (exhaust fan failure, fumes in the building) does not need alarm history or NCR reports — it needs the SOP procedure immediately. Running all 4 agents wasted tokens, took longer, and produced empty findings that added noise to the report.

### How I fixed it

Added a **supervisor agent** that reads the incident description first and decides which specialists to call. Safety events → SOP agent only. Recurring alarms → alarm + maintenance + NCR. Wire feed issues → maintenance + SOP. Reduced from always 4 calls to typically 2-3 calls.

### Tradeoff

More agents = more LLM calls = higher cost and slower response. On free tier with 1,000 quality model requests per day, this matters significantly. Model split (cheap 8b for specialists, quality 70b for orchestrator) was the key budget decision.

### Interview question to practise

> *"Why specialist agents instead of one general agent?"*

A general agent with all documents produces unfocused queries. Specialist agents each have one narrow task with a specific document type filter — cleaner findings per source. The orchestrator synthesis is a different cognitive task from searching — separating them produces better results than combining them.

---

## Concept 4 — Evals (Evaluation Framework)

**Used in:** `eval_runner.py` — 10 test cases across all 3 modes  
**Baseline:** 65% → 90% over 4 sessions

### What it is

> **Analogy:** Imagine training a new employee to answer customer questions. Without tests, you just hope they are getting better. With tests, you give them 10 sample questions with known correct answers and score their responses. If their score goes from 65% to 90% after training, you have evidence of improvement. Evals are the same — a set of test cases with known correct answers that you run after every change.

### Real failure I hit

In Sessions 1-4, I was changing prompts based on manual testing with cherry-picked examples. An "improvement" in one example often made things worse on edge cases I was not testing. Four sessions of unmeasured iteration — essentially wasted time.

### How I fixed it

Built the eval suite in Session 5. From that point every architectural decision had a before/after score. The equip_tag fallback bug — returning a Fanuc robot manual with **0.82 confidence** for unknown equipment — was only discovered by running evals. Without evals it would never have been found.

### Interview question to practise

> *"How do you know PlantMind is working?"*

I built a 10-case eval suite with explicit pass/fail criteria. Current baseline is 90% with zero errors. I can tell you exactly which test case fails (INV-004) and why (8b model cannot connect liner replacement to burn-in requirement across two documents). That is the difference between AI engineering and AI prototyping.

---

## Concept 5 — Ragas (Scientific RAG Evaluation)

**Used in:** `ragas_test.py` — 2 golden cases  
**Results:** Faithfulness 1.00, Context recall 0.88

### What it is

> **Analogy:** Keyword evals check if the answer contains the word "3.5" — like checking if a student wrote the number on their exam. Ragas asks deeper questions: Did the student make up any facts not in the textbook? Did the student understand what the question was asking? Did the textbook contain the information needed to answer? These are fundamentally better questions.

### The three Ragas metrics

**Faithfulness** — did the answer make any claims not supported by retrieved documents? Score of 1.0 = zero hallucinations.

**Answer relevance** — did the answer actually address the question asked? High relevance with low faithfulness = understood the question, answered from memory instead of documents.

**Context recall** — did the retrieval find all the document chunks needed to answer correctly? Score of 0.75 = retrieved 3 of 4 needed facts.

### My Ragas results

```
RQ-001 (spatter threshold):  Faithfulness 1.00 | Context recall 1.00
RQ-002 (burn-in procedure):  Faithfulness 1.00 | Context recall 0.75
Overall:                     Faithfulness 1.00 | Context recall 0.88
Manufacturing benchmark:     Faithfulness 0.85 | Context recall 0.85
```

### Real failure I hit

First Ragas run showed **faithfulness 0.0** for RQ-001. The answer was correct (said 3.5) but Ragas scored it zero. Why? The retrieved contexts being passed to Ragas were just document filenames, not actual text. Ragas checked the answer against filenames and found no supporting evidence.

### How I fixed it

Changed the Ragas script to query Pinecone directly for actual chunk text rather than relying on the API response. With real chunk text as contexts, faithfulness jumped to 1.00.

### Interview question to practise

> *"How is Ragas different from your keyword evals?"*

Keyword evals check if specific words appear — fast but brittle. Ragas uses an LLM judge to measure faithfulness, answer relevance, and context recall. Ragas revealed that one answer was correct but unfaithful — the LLM knew the right answer from training data, not the retrieved document. That is a hallucination even when the answer is right.

---

## Concept 6 — Supervisor Pattern (Dynamic Routing)

**Used in:** `multi_agent.py` — `supervisor_route()` function  
**Model:** llama-3.1-8b at temperature 0.0, max 100 tokens

### What it is

> **Analogy:** When a 911 call comes in, the dispatcher does not send every emergency service simultaneously. They listen, classify, and route to the right responders. House fire: fire department. Medical emergency: ambulance. Crime in progress: police. The supervisor agent does the same — reads the incident and routes to the relevant specialists only.

### How I used it in PlantMind

```
Incident: "PC-701 paint booth exhaust fan stopped. Operators smell solvent fumes."
Supervisor classifies: safety event
Routes to: SOP agent only
Reason: safety procedure required immediately
Result: 1 agent call instead of 4. Faster, more focused, fewer tokens.
```

Routing logic lives in the supervisor system prompt — changing routing rules means editing a prompt, not deploying code.

### Real failure I hit

Supervisor classified "wire feed stuttering" as an alarm quality issue and routed to alarm + NCR agents. It **skipped the maintenance agent** that had the liner replacement history from April 19. Investigation missed the burn-in connection because the relevant document was never retrieved. INV-004 eval case started failing.

### How I fixed it

Updated the routing rules in the prompt: "wire feed, liner, arc, or stuttering → always include maintenance agent." The eval passed again. Lesson: routing logic in a prompt requires testing just like code.

### Interview question to practise

> *"What happens if the supervisor routes incorrectly?"*

Safe fallback. If the supervisor returns empty or invalid JSON, the system falls back to running all 4 agents — the original fixed fan-out. A wrong routing produces a less focused report, not a broken investigation. The system degrades gracefully.

---

## Concept 7 — Agent Memory

**Used in:** `multi_agent.py` — `get_previous_investigations()` function  
**Storage:** Supabase `chat_history` table with `equip_tag` column

### What it is

> **Analogy:** Imagine a doctor with no memory of previous appointments. Every visit, you explain your entire medical history from scratch. Now imagine a doctor with your full patient record — they remember the prescription from last month that did not work, the allergy that caused a reaction, the recurring symptom that has appeared three times this year. Agent memory gives the AI the equivalent of a patient record.

### How I used it in PlantMind

Before each investigation, the system queries the last 3 investigation results for the same equipment from chat history. These summaries are prepended to the orchestrator prompt.

```
Thursday: WR-401 wire feed — root cause: burn-in incomplete — criticality: LOW
Saturday: WR-401 same symptom
Without memory: same report, same recommendation
With memory: "burn-in fix from Thursday did not hold — escalate to full
             wire feed system inspection, elevate to MEDIUM"
```

### Real failure I hit

Memory feature built but showed "no previous investigations" on second run. The `equipment_id_used` variable was defined inside the streaming reader block **after** the `saveToHistory` function had already been called. JavaScript scope issue — variable was undefined at save time.

### How I fixed it

Moved the equipment ID extraction to the very top of `submitInvestigation()`, before any async code runs. Confirmed by checking Supabase `chat_history` table — `equip_tag` column now populated correctly on every investigation.

### Interview question to practise

> *"How does agent memory work and what are its limitations?"*

Query last 3 investigations per equipment from database, summarise key facts, prepend as context to orchestrator. Limitations: recency-based not relevance-based. No cross-equipment memory — WR-401 history does not inform P-201 investigations even if they share a failure mode.

---

## Concept 8 — Confidence Thresholds and Fallback Logic

**Used in:** `/ask` route in `app.py`  
**Values:** 0.35 general, 0.30 when equipment filter active

### What it is

> **Analogy:** A search engine returns results ranked by relevance. Some results are so low in relevance that including them makes the answer worse, not better. A threshold is the minimum relevance score a result must achieve to be included. Below it, the system says "nothing relevant enough found" rather than including poor-quality results that might mislead.

### Real failure I hit

Original fallback: if equipment filter found no results above threshold, **drop all filters** and search everything. This caused the system to return a Fanuc robot manual for a query about unknown equipment CM-201. The Fanuc manual scored **0.82** — high confidence — because it contained general robot maintenance language. Completely wrong equipment. Returned as if it were the correct answer.

### How I fixed it

Changed the rule: **never drop the equipment tag filter.** If no documents exist for the requested equipment, return "no documents found" explicitly. An honest no-answer is always better than a confident wrong answer. A plant operator acting on a Fanuc robot procedure for a welding robot could cause equipment damage.

### Interview question to practise

> *"Why did you never drop the equipment tag filter?"*

The original fallback was returning a Fanuc robot manual with 0.82 confidence for unknown equipment. High confidence, completely wrong machine. In a safety-adjacent system, explicit uncertainty is always better than false confidence.

---

## Concept 9 — AI Observability

**Used in:** `llm_logger.py` — logs to Supabase `llm_logs` table  
**UI:** Stats widget in nav bar, auto-refreshes every 60 seconds

### What it is

> **Analogy:** Imagine driving a car with no dashboard. No speedometer, no fuel gauge, no warning lights. You only find out about problems when the car stops. Observability is the dashboard for your AI system. It tells you how many tokens you have used today, which calls are slow, which are failing, and how much budget you have left before hitting limits.

### How I used it in PlantMind

Every LLM call logs: model used, call type (specialist/orchestrator/Q&A), input tokens, output tokens, latency in milliseconds, errors. Written to Supabase in a background thread — never slows the main request.

### Real failure I hit

Multiple sessions where the entire 100K daily token budget was exhausted without warning. Flask crashed mid-investigation with rate limit errors. The eval runner reported connection errors. Took hours to diagnose — the problem was daily token exhaustion, not a code bug.

### How I fixed it

Logged every LLM call. Added a nav bar stats widget showing live token usage with progress bars against daily limits. Added retry handler with 55/70/90 second waits. Now I check remaining budget before running evals.

### Interview question to practise

> *"How do you monitor your AI system?"*

Every LLM call logs model, call type, tokens, latency, and errors to Supabase via background thread. A real-time stats widget shows daily consumption per model with progress bars. This is the difference between reactive debugging and proactive management.

---

## Concept 10 — Model Selection and Rate Limit Architecture

**Used in:** All LLM calls across `app.py` and `multi_agent.py`

### What it is

> **Analogy:** A construction company has apprentices and master craftspeople. Routine work goes to apprentices — cheaper and faster. Complex decisions go to master craftspeople — quality matters. Using masters for bricklaying wastes money. Using apprentices for structural decisions is dangerous. Model selection in AI works the same way.

### My model split

| Call type | Model | Daily limit | Why |
|-----------|-------|-------------|-----|
| Q&A route | llama-3.1-8b | 14,400 RPD | Simple retrieval, high volume |
| 4 specialist agents | llama-3.1-8b | 14,400 RPD | Summarising docs, not reasoning |
| Supervisor routing | llama-3.1-8b | 14,400 RPD | Classification only, 100 tokens |
| Orchestrator | llama-3.3-70b | 1,000 RPD | Cross-document reasoning required |
| Reflection (optional) | llama-3.3-70b | 1,000 RPD | Quality critique requires nuance |

### Real failure I hit

Putting all 6 calls on llama-3.3-70b to maximise quality. **Exhausted the 100K daily token limit in a single testing session.** Also tried everything on 8b — investigation quality dropped noticeably on cross-document reasoning. Neither extreme worked.

### Interview question to practise

> *"How did you decide which model to use for each call?"*

Three factors: what cognitive task is being performed (summarisation vs reasoning), what the rate limit profiles are (8b has 14x more daily requests), and what the eval score shows (if 8b passes all relevant test cases, there is no justification for the higher cost of 70b).

---

## Concept 11 — Document Chunking Strategy

**Used in:** `embedder.py` — 1,000 char chunks with 200 char overlap  
**CSV chunker:** Groups 5 rows into natural language batches

### What it is

> **Analogy:** Finding a recipe in a cookbook. If the entire cookbook is one chunk, you get too much noise. If each sentence is a chunk, you lose context — "3.5" means nothing without "spatter index alarm threshold" next to it. The right chunk size is a paragraph or procedure step — enough context to be meaningful, small enough to be specific.

### Real failure I hit

Early chunking at 500 characters was splitting specification tables in the middle. A chunk would end with "spatter index alarm threshold:" and the next chunk would start with "3.5". The number was separated from its label. Semantic search would find the label chunk but not the value, or vice versa.

### How I fixed it

Increased chunk size to 1,000 characters with 200 character overlap. Specification tables now fit within single chunks. The overlap ensures cross-boundary content appears in both adjacent chunks. For CSV shift logs, the custom chunker groups 5 rows into one natural language paragraph — preserving the context that alarm event X was followed by maintenance action Y.

### Interview question to practise

> *"How would you improve chunking further?"*

Semantic chunking — split on meaning boundaries (end of a procedure step, end of a specification section) rather than character count. Create dedicated spec value chunks that always keep numerical values with their labels.

---

## Concept 12 — Reflection Pattern

**Used in:** `multi_agent.py` — `ENABLE_REFLECTION` feature flag  
**Default:** Disabled for evals, enabled for production testing

### What it is

> **Analogy:** A junior doctor writes a diagnosis. A senior doctor reviews it, identifies what was missed, and writes a better version. The junior doctor did nothing wrong — the senior review catches things a single pass misses. Reflection does the same: a second LLM call reviews the first output and improves it.

### Real failure I hit

Reflection was **downgrading CRITICAL safety ratings**. The orchestrator correctly assigned CRITICAL to a safety event. The reflection agent added "safety risk is manageable with standard PPE" in the impact section. Keyword eval `must_not_contain:CRITICAL` started failing because CRITICAL appeared in the reflection agent's amended text.

### How I fixed it

Two fixes. Changed the keyword eval to anchor on the section header: `must_not_contain "HOW CRITICAL IS IT: CRITICAL"` rather than just "CRITICAL" anywhere. Added explicit instruction to the reflection prompt: never change the criticality rating, only improve the supporting reasoning. Also set `ENABLE_REFLECTION=false` as default for eval runs.

### Interview question to practise

> *"Did you measure whether reflection actually improved quality?"*

Honest answer — not with Ragas yet. I observed quality improvement in manual testing and keyword evals stayed at 90% with reflection enabled. The proper measurement would be running Ragas with reflection on versus off and comparing faithfulness and answer relevance scores. That is the next step.

---

## Concept 13 — Framework Selection and Scaling (Flask)

**Used in:** Entire API layer — all routes in `app.py`
**Alternative:** FastAPI for production

### What it is

> **Analogy:** A food truck is perfect for serving 20 customers at a lunch spot. It is fast to set up, easy to operate, and does the job well. A restaurant kitchen is needed when you have 200 covers a night, multiple chefs, and orders coming in simultaneously. Flask is the food truck. FastAPI with async handlers is the restaurant kitchen. You start with the food truck — you only build the kitchen when you need it.

Flask is a lightweight Python web framework. Minimal boilerplate, easy streaming responses, fast to set up. For a single-user prototype or a demo with one person at a time, it is the right choice. For concurrent users running 40-second LLM investigations simultaneously, it breaks.

### Why I used Flask

Fastest path to a working API without fighting framework complexity. A Flask route is 3 lines. Streaming responses with `Response` and `stream_with_context` worked immediately. For a learning project where the goal was understanding RAG and agents — not web framework design — Flask was the right choice.

### What breaks at scale

**Problem 1 — One request at a time**

Flask's development server handles one request at a time. Two operators submitting investigations simultaneously means operator 2 waits 30-40 seconds before their request even starts.

**Problem 2 — Blocking LLM calls**

Each investigation makes 5-6 synchronous LLM calls. The Flask worker thread is blocked for the entire duration. No other requests can be served while waiting for Groq to respond.

**Problem 3 — No job queue**

Long-running investigations (40+ seconds) hold open HTTP connections. Reverse proxies have timeout limits. A slow Groq response mid-investigation can silently drop the connection.

**Problem 4 — Single process**

Flask runs as one Python process. Cannot horizontally scale without stateless redesign and a load balancer.


---

## Key failure modes and lessons

| Failure | Lesson |
|---------|--------|
| Fanuc robot manual at 0.82 confidence | A confident wrong answer is more dangerous than an honest no-answer. Never drop safety filters. |
| Reflection downgrading safety criticality | Tell the reflection pass what it cannot change, not just what to improve. |
| Supervisor misrouting INV-004 | Routing logic in a prompt still needs test cases. Prompts can be wrong too. |
| Ragas faithfulness 0.0 on correct answer | Ragas measures grounding, not correctness. Correct but ungrounded is still hallucination. |
| 100K daily tokens exhausted in one session | Rate limit profiles must be first-class architectural constraints, not afterthoughts. |
| Flask crashing silently on Windows | Never create network connections at module import time. Use lazy initialisation. |
| Supabase project pausing | Check Supabase first after any long break. Add startup health check. |

---


---

*PlantMind · Updated continuously as the project grows · Last updated: Session 9*
