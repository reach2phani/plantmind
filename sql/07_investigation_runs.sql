-- ─────────────────────────────────────────────────────────────────────────
-- 07_investigation_runs.sql — one record per investigation (observability)
--
-- Two tables, joined by run_id:
--   investigation_runs         SUMMARY: one row per investigation, plain
--                              columns a dashboard can chart directly.
--   investigation_run_details  DETAIL: the report, every retrieved piece
--                              (full text), specialist findings, and the
--                              event list (every AI call and search).
-- Plus llm_logs.run_id, so each logged AI call joins to its investigation.
--
-- status: running -> ok | error | rate_limited | cancelled
--   A row still "running" long after created_at = a run that never finished
--   (process stopped mid-run). It is kept on purpose, so lost runs are
--   visible instead of silently missing.
--
-- Safe to run more than once. Run in: Supabase dashboard → SQL Editor → Run.
-- The app keeps working before this is run; writes fail, are counted, and go
-- to logs/run_write_failures.jsonl.
-- ─────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS investigation_runs (
  id                   uuid PRIMARY KEY,
  created_at           timestamptz DEFAULT now(),
  finished_at          timestamptz,

  -- who / what
  run_tag              text,          -- e.g. 'baseline-d1-TC1'; null for normal use
  source               text,          -- 'ui' | 'eval' | 'script'
  question             text,
  plant_site           text,
  line                 text,
  equip_tag            text,

  -- outcome
  status               text,          -- running | ok | error | rate_limited | cancelled
  error                text,
  criticality          text,          -- CRITICAL | HIGH | MEDIUM | LOW, read from the report
  confidence           text,          -- HIGH | MEDIUM | LOW (assess_confidence)
  engineer_review      boolean,

  -- graph and routing
  fault_matched        text,
  match_confidence     text,          -- sure | unsure | none ...
  graph_source         text,          -- neo4j | local_file | unavailable | off | none
  agents_used          jsonb,
  pieces_count         int,
  warnings_count       int,
  sources_cited_count  int,
  guard_events_count   int,

  -- reliability
  llm_calls            int,
  llm_errors           int,
  retries              int,
  truncated_calls      int,
  rerank_fallbacks     int,

  -- cost
  tokens_in            int,
  tokens_out           int,
  tokens_total         int,
  cost_usd             numeric(12,6),
  price_version        text,

  -- time (milliseconds)
  total_ms             int,
  graph_ms             int,
  supervisor_ms        int,
  specialists_ms       int,
  writer_ms            int,
  budget_wait_ms       int,           -- time spent waiting for free-tier quota (token_budget.py)

  -- versions (for fair before/after comparisons)
  git_commit           text,          -- '+dirty' = uncommitted changes
  code_hash            text,          -- fingerprint of multi_agent / knowledge_graph / models
  model_fast           text,
  model_deep           text,
  switches             jsonb,         -- rerank, graph off, writer evidence, ...
  langsmith_trace_id   text
);

CREATE INDEX IF NOT EXISTS investigation_runs_created_idx ON investigation_runs (created_at DESC);
CREATE INDEX IF NOT EXISTS investigation_runs_tag_idx     ON investigation_runs (run_tag);
CREATE INDEX IF NOT EXISTS investigation_runs_status_idx  ON investigation_runs (status);

CREATE TABLE IF NOT EXISTS investigation_run_details (
  run_id           uuid PRIMARY KEY REFERENCES investigation_runs(id) ON DELETE CASCADE,
  created_at       timestamptz DEFAULT now(),
  report           text,
  sources_cited    jsonb,   -- lines of the report's SOURCE DATA section
  graph_warnings   jsonb,
  guard_events     jsonb,
  routing_reason   text,
  findings         jsonb,   -- [{agent, findings}]
  pieces           jsonb,   -- [{step, search, doc_type, rank, score, chunk_id, document, text, ...}]
  events           jsonb,   -- [{t_ms, kind, step, ...}] every AI call and search
  tokens_by_model  jsonb
);

-- Added after the first version of this file was run (2026-10-28):
ALTER TABLE investigation_runs ADD COLUMN IF NOT EXISTS budget_wait_ms int;

ALTER TABLE llm_logs ADD COLUMN IF NOT EXISTS run_id uuid;
CREATE INDEX IF NOT EXISTS llm_logs_run_id_idx ON llm_logs (run_id);

-- Same access pattern as expert_fixes: RLS on, one permissive backend policy
-- (no per-user Supabase Auth session exists yet).
ALTER TABLE investigation_runs        ENABLE ROW LEVEL SECURITY;
ALTER TABLE investigation_run_details ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "backend full access" ON investigation_runs;
DROP POLICY IF EXISTS "backend full access" ON investigation_run_details;
CREATE POLICY "backend full access" ON investigation_runs        FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "backend full access" ON investigation_run_details FOR ALL USING (true) WITH CHECK (true);

-- Useful queries once data exists:
--
-- Runs that never finished (process stopped mid-run):
--   SELECT id, created_at, question FROM investigation_runs
--   WHERE status = 'running' AND created_at < now() - interval '15 minutes';
--
-- One eval run, with its numbers:
--   SELECT run_tag, status, criticality, confidence, tokens_total, cost_usd, total_ms
--   FROM investigation_runs WHERE run_tag LIKE 'baseline-d1-%' ORDER BY run_tag;
--
-- Token totals agree with llm_logs?
--   SELECT r.id, r.tokens_total, sum(l.input_tokens + l.output_tokens) AS logged
--   FROM investigation_runs r JOIN llm_logs l ON l.run_id = r.id
--   GROUP BY r.id, r.tokens_total ORDER BY r.created_at DESC LIMIT 10;
