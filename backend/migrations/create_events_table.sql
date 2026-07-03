-- ============================================================================
-- Migration: Append-only `events` table (trust stack Phase 1b + 1c)
-- ============================================================================
--
-- ⚠️  NEEDS LIVE VERIFICATION — NOT APPLIED BY THIS REPO.
-- This file was written by reading the code; it has NOT been run against a live
-- Supabase project (this machine has no database connection). Run it manually in
-- the Supabase SQL Editor, then verify immutability and RLS actually behave as
-- intended (see the verification queries at the bottom) BEFORE relying on it.
--
-- DEPENDS ON: backend/migrations/enable_rls_and_ownership_policy.sql — the
-- current_nurse_id() helper and the `assignments` table are defined there and
-- used by the RLS policies below. Apply that migration first.
--
-- WHY: The trust stack requires an immutable audit trail. Every agent
-- input/output, schema-gate decision, risk-gate decision, and nurse edit is
-- one append-only row. Provenance (which update IDs / transcript excerpt
-- produced a given piece of content) is a first-class column from day one,
-- not a retrofit — the Phase 4 "Linked Evidence" UI reads it.
--
-- WHAT THIS DOES:
--   1. Creates the `events` table (writer: backend/event_log.py).
--   2. Makes it append-only for EVERYONE, including service_role, via a
--      BEFORE UPDATE OR DELETE trigger that unconditionally raises. (REVOKE
--      alone is not enough: service_role bypasses grants and RLS.)
--   3. Enables RLS: nurses may INSERT events attributed to themselves and
--      SELECT only events for patients assigned to them.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Table
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at  timestamptz NOT NULL DEFAULT now(),
    event_type  text NOT NULL,
    agent       text NOT NULL,          -- which agent/component produced it
    shift_id    text,                   -- nullable: not every event is shift-scoped
    patient_id  text,
    update_id   text,                   -- the patient_updates row this event concerns
    nurse_id    text,                   -- acting nurse (from the verified JWT)
    payload     jsonb NOT NULL DEFAULT '{}'::jsonb,
    -- Provenance is foundational (Phase 1c): a pointer back to what produced
    -- this content — {"source_update_ids": [...], "transcript_excerpt": "..."}.
    provenance  jsonb NOT NULL DEFAULT '{}'::jsonb,

    -- Keep in sync with EVENT_TYPES in backend/event_log.py. A CHECK (not an
    -- enum type) so adding a type later is one ALTER, not a type migration.
    CONSTRAINT events_type_known CHECK (event_type IN (
        'update_received', 'extraction_completed', 'schema_gate',
        'verification_completed', 'protocol_check', 'risk_gate',
        'draft_generated', 'nurse_edit'
    ))
);

CREATE INDEX IF NOT EXISTS idx_events_patient  ON events(patient_id, created_at);
CREATE INDEX IF NOT EXISTS idx_events_shift    ON events(shift_id, created_at);
CREATE INDEX IF NOT EXISTS idx_events_update   ON events(update_id);
CREATE INDEX IF NOT EXISTS idx_events_type     ON events(event_type, created_at);

-- ----------------------------------------------------------------------------
-- 2. Append-only enforcement (applies to service_role too)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION prevent_event_mutation() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_temp AS $$
BEGIN
    RAISE EXCEPTION 'events is append-only: % is not allowed', TG_OP;
END;
$$;

DROP TRIGGER IF EXISTS events_immutable ON events;
CREATE TRIGGER events_immutable
    BEFORE UPDATE OR DELETE ON events
    FOR EACH ROW EXECUTE FUNCTION prevent_event_mutation();

-- Belt-and-braces for non-service roles as well. anon gets ALL revoked (not
-- just UPDATE/DELETE/TRUNCATE) because this project auto-grants ALL to anon
-- on every new table via default ACLs (confirmed via pg_default_acl) -- the
-- same mechanism that produced the original anon_full_access exposure.
-- RLS already blocks anon (no policy targets it) but should not be the only
-- thing standing between anon and this table.
REVOKE ALL ON events FROM anon;
REVOKE UPDATE, DELETE, TRUNCATE ON events FROM authenticated;

-- ----------------------------------------------------------------------------
-- 3. RLS
-- ----------------------------------------------------------------------------
ALTER TABLE events ENABLE ROW LEVEL SECURITY;

-- A nurse may append events attributed to themselves (or system events with
-- no nurse attribution, e.g. gate decisions made mid-pipeline).
DROP POLICY IF EXISTS nurse_appends_own_events ON events;
CREATE POLICY nurse_appends_own_events ON events
    FOR INSERT TO authenticated
    WITH CHECK (nurse_id = current_nurse_id() OR nurse_id IS NULL);

-- A nurse may read events only for patients assigned to them.
DROP POLICY IF EXISTS nurse_reads_assigned_events ON events;
CREATE POLICY nurse_reads_assigned_events ON events
    FOR SELECT TO authenticated
    USING (
        patient_id IN (
            SELECT a.patient_id FROM assignments a
            WHERE a.nurse_id = current_nurse_id()
        )
    );

-- ============================================================================
-- VERIFICATION (run manually after applying; confirm results by hand)
-- ============================================================================
-- 1. INSERT a row, then:
--      UPDATE events SET agent = 'x' WHERE id = '<that id>';   -- expect ERROR
--      DELETE FROM events WHERE id = '<that id>';              -- expect ERROR
--    Repeat both with the service_role key — expect the SAME errors (the
--    trigger, unlike RLS/grants, is not bypassed by service_role).
-- 2. As nurse A (assigned P001 only):
--      SELECT count(*) FROM events WHERE patient_id = 'P002';  -- expect 0
-- 3. INSERT with nurse_id = '<some other nurse>' — expect RLS denial.
-- 4. Confirm backend/event_log.py writes succeed end-to-end and that a machine
--    with no SUPABASE_KEY logs the single "event_log DEGRADED" warning instead
--    of crashing a request.
-- ============================================================================
