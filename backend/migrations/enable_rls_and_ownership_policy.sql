-- ============================================================================
-- Migration: Enable Row-Level Security + per-nurse ownership policies
-- ============================================================================
--
-- ⚠️  NEEDS LIVE VERIFICATION — NOT APPLIED BY THIS REPO.
-- This file was written by reading the code; it has NOT been run against a live
-- Supabase project (this machine has no database connection). Run it manually in
-- the Supabase SQL Editor, then verify each policy actually behaves as intended
-- (see the verification queries at the bottom) BEFORE relying on it.
--
-- WHY: Previously the backend used the Supabase service_role key, which BYPASSES
-- RLS entirely, and hide_original_patients_table.sql granted broad SELECT to the
-- `anon` / `authenticated` roles. With no application auth (now added in api.py),
-- the database itself was the last line of defence and it was wide open.
--
-- WHAT THIS DOES:
--   1. Creates an `assignments` table (nurse_id, patient_id) — the source of truth
--      for which nurse may see which patient. The API's start_shift and read paths
--      now depend on this table (backend/auth.py, backend/database.py
--      get_nurse_assignments). Until it exists and is seeded, assignment checks
--      fail closed (deny) and shifts cannot be started.
--   2. Enables RLS on `patients`, `patient_updates`, `draft_handoffs`,
--      `nurse_shifts`, and `assignments`.
--   3. Adds policies scoping access to the authenticated nurse's assigned patients.
--   4. REVOKES the over-broad grants that hide_original_patients_table.sql added.
--
-- IMPORTANT DEPLOYMENT CHANGE (do this alongside running the migration):
--   Switch the backend's SUPABASE_KEY from the service_role key to the ANON key so
--   that RLS is actually enforced on request-path queries. Reserve the service_role
--   key for trusted admin/batch jobs only (e.g. generate_patients.py). If the
--   backend keeps using service_role, these policies will NOT be enforced.
--
-- ASSUMPTION TO VERIFY: these policies assume the JWT's `sub` (or a custom
-- `nurse_id` claim) equals assignments.nurse_id. Confirm how your nurse identities
-- map to Supabase auth users and adjust `auth.uid()` / the claim extraction below
-- to match before trusting this in production.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Assignment table: which nurse is responsible for which patient.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS assignments (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nurse_id    text NOT NULL,
    patient_id  text NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (nurse_id, patient_id)
);

CREATE INDEX IF NOT EXISTS idx_assignments_nurse ON assignments(nurse_id);

-- Helper: the nurse_id of the current request, taken from the JWT.
-- Adjust this to match how your tokens carry the nurse identity. This default
-- reads a top-level `nurse_id` claim and falls back to the auth user id.
CREATE OR REPLACE FUNCTION current_nurse_id() RETURNS text
LANGUAGE sql STABLE AS $$
    SELECT COALESCE(
        current_setting('request.jwt.claims', true)::jsonb ->> 'nurse_id',
        auth.uid()::text
    );
$$;

-- ----------------------------------------------------------------------------
-- 2. Undo the over-broad grants from hide_original_patients_table.sql
-- ----------------------------------------------------------------------------
REVOKE SELECT ON patients FROM anon;
REVOKE SELECT ON patients FROM authenticated;
-- (The patients_ordered view, if present, inherits access from the underlying
--  table under RLS; revoke direct grants on it too if it was granted.)
-- REVOKE SELECT ON patients_ordered FROM anon;
-- REVOKE SELECT ON patients_ordered FROM authenticated;

-- ----------------------------------------------------------------------------
-- 3. Enable RLS on every table holding patient data
-- ----------------------------------------------------------------------------
ALTER TABLE patients        ENABLE ROW LEVEL SECURITY;
ALTER TABLE patient_updates ENABLE ROW LEVEL SECURITY;
ALTER TABLE draft_handoffs  ENABLE ROW LEVEL SECURITY;
ALTER TABLE nurse_shifts    ENABLE ROW LEVEL SECURITY;
ALTER TABLE assignments     ENABLE ROW LEVEL SECURITY;

-- ----------------------------------------------------------------------------
-- 4. Policies — a nurse may only touch patients assigned to them
-- ----------------------------------------------------------------------------

-- patients: SELECT only rows for assigned patients.
DROP POLICY IF EXISTS nurse_reads_assigned_patients ON patients;
CREATE POLICY nurse_reads_assigned_patients ON patients
    FOR SELECT TO authenticated
    USING (
        patient_id IN (
            SELECT a.patient_id FROM assignments a
            WHERE a.nurse_id = current_nurse_id()
        )
    );

-- assignments: a nurse may read only their own assignment rows.
DROP POLICY IF EXISTS nurse_reads_own_assignments ON assignments;
CREATE POLICY nurse_reads_own_assignments ON assignments
    FOR SELECT TO authenticated
    USING (nurse_id = current_nurse_id());

-- nurse_shifts: a nurse may read/write only their own shifts.
DROP POLICY IF EXISTS nurse_rw_own_shifts ON nurse_shifts;
CREATE POLICY nurse_rw_own_shifts ON nurse_shifts
    FOR ALL TO authenticated
    USING (nurse_id = current_nurse_id())
    WITH CHECK (nurse_id = current_nurse_id());

-- patient_updates: a nurse may read/write updates only for assigned patients.
DROP POLICY IF EXISTS nurse_rw_assigned_updates ON patient_updates;
CREATE POLICY nurse_rw_assigned_updates ON patient_updates
    FOR ALL TO authenticated
    USING (
        patient_id IN (
            SELECT a.patient_id FROM assignments a
            WHERE a.nurse_id = current_nurse_id()
        )
    )
    WITH CHECK (
        nurse_id = current_nurse_id()
        AND patient_id IN (
            SELECT a.patient_id FROM assignments a
            WHERE a.nurse_id = current_nurse_id()
        )
    );

-- draft_handoffs: a nurse may read/write drafts only for assigned patients.
DROP POLICY IF EXISTS nurse_rw_assigned_drafts ON draft_handoffs;
CREATE POLICY nurse_rw_assigned_drafts ON draft_handoffs
    FOR ALL TO authenticated
    USING (
        patient_id IN (
            SELECT a.patient_id FROM assignments a
            WHERE a.nurse_id = current_nurse_id()
        )
    )
    WITH CHECK (
        patient_id IN (
            SELECT a.patient_id FROM assignments a
            WHERE a.nurse_id = current_nurse_id()
        )
    );

-- ============================================================================
-- VERIFICATION (run manually after applying; confirm results by hand)
-- ============================================================================
-- 1. As an authenticated nurse token whose nurse_id has one assignment (P001):
--      SELECT patient_id FROM patients;              -- expect ONLY P001
--      SELECT patient_id FROM patients WHERE patient_id = 'P002';  -- expect 0 rows
-- 2. Attempt to insert an update for an unassigned patient — expect RLS denial.
-- 3. Confirm the backend is using the ANON key (not service_role); with service_role
--    all of the above returns everything because RLS is bypassed.
-- ============================================================================
