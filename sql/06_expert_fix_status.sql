-- ============================================================================
-- 06_expert_fix_status.sql — Phase 1B
--
-- WHY
--   A reviewer can reject an operator's captured fix in the knowledge graph
--   (status = 'disputed' on the promoted note). That rejection had nowhere to
--   live on the capture itself, so search still returned it as good advice.
--   Found by hand-testing: a report flagged that an operator's "normal arc
--   voltage is 15-16 V" contradicted the SOP's 18-22 V, and then told the
--   operator to set the machine to 15.5 V anyway.
--
--   'active'   — normal, retrievable (default, so nothing changes for
--                existing rows)
--   'disputed' — a documented fact overrules it. Kept, never deleted: the
--                operator's words stay visible in their own library and in
--                the graph, but the investigation pipeline stops using it.
--
-- RUN
--   Supabase dashboard -> SQL editor -> paste -> Run. Safe to re-run.
-- ============================================================================

ALTER TABLE expert_fixes
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'active';

COMMENT ON COLUMN expert_fixes.status IS
  'active | disputed. Set to disputed when a reviewer marks the promoted graph '
  'note as overruled by a documented fact. multi_agent._drop_disputed() removes '
  'disputed captures from investigation retrieval. The row is never deleted.';

-- Optional: a note of WHY, for whoever reads the row later.
ALTER TABLE expert_fixes
  ADD COLUMN IF NOT EXISTS status_reason text;

CREATE INDEX IF NOT EXISTS expert_fixes_status_idx ON expert_fixes (status);
