-- ─────────────────────────────────────────────────────────────────────────
-- 06_llm_logs_observability.sql — Phase 0, Batch C1
--
-- Adds three columns to llm_logs so every logged AI call can answer:
--   finish_reason  WHY did the model stop?  "stop" = finished normally,
--                  "length" = hit the output token cap (answer is incomplete),
--                  "tool_calls" = the work-order agent is calling a tool.
--   truncated      convenience flag: finish_reason = 'length'
--   graph_source   for investigation reports: where graph context came from.
--                  "neo4j" = live graph, "local_file" = degraded fallback,
--                  "unavailable" = no graph, "none" = equipment has no graph.
--
-- Safe to run more than once (IF NOT EXISTS). Existing rows get NULLs.
-- Run in: Supabase dashboard → SQL Editor → paste → Run.
-- The app keeps working before this is run; it just logs without these fields.
-- ─────────────────────────────────────────────────────────────────────────

ALTER TABLE llm_logs ADD COLUMN IF NOT EXISTS finish_reason text;
ALTER TABLE llm_logs ADD COLUMN IF NOT EXISTS truncated     boolean;
ALTER TABLE llm_logs ADD COLUMN IF NOT EXISTS graph_source  text;

-- Useful query once data exists: how often are reports cut off?
-- SELECT call_type, model,
--        count(*)                              AS calls,
--        count(*) FILTER (WHERE truncated)     AS truncated_calls,
--        round(100.0 * count(*) FILTER (WHERE truncated) / count(*), 1) AS pct_truncated
-- FROM llm_logs
-- WHERE finish_reason IS NOT NULL
-- GROUP BY call_type, model
-- ORDER BY pct_truncated DESC;
