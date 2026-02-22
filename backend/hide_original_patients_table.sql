-- ============================================================
-- HIDE ORIGINAL PATIENTS TABLE FROM SUPABASE UI
-- This makes only patients_ordered visible in Table Editor
-- ============================================================

-- Option 1: Revoke SELECT permission for the UI role (but keep for backend)
-- This hides it from Supabase Table Editor while API still works
REVOKE SELECT ON patients FROM anon;
REVOKE SELECT ON patients FROM authenticated;

-- The view still works because it's owned by postgres user
-- Your Python backend still works because it uses service_role key

-- ============================================================
-- ALTERNATIVE: Add a comment to mark it as internal
-- ============================================================
COMMENT ON TABLE patients IS '[INTERNAL - DO NOT USE] Use patients_ordered view instead';

-- ============================================================
-- VERIFICATION
-- ============================================================
-- After running this, in Supabase Table Editor you should only see:
-- - patients_ordered (visible)
-- - patients (hidden from anon/authenticated, but backend still works)

-- To verify your Python code still works, run:
-- python3 -c "from backend.database import get_patient; print(get_patient('P001'))"
