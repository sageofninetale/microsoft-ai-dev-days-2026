-- ============================================================
-- URGENT FIX: Restore permissions for backend to work
-- ============================================================

-- Restore SELECT permission (we removed it by mistake)
GRANT SELECT ON patients TO anon;
GRANT SELECT ON patients TO authenticated;

-- The correct way to "hide" it is just to:
-- 1. Always use patients_ordered in Supabase UI
-- 2. Keep both visible but document which to use

-- ============================================================
-- VERIFICATION
-- ============================================================
-- Run this to confirm backend works again:
-- python3 -c "from backend.database import get_patient; print(get_patient('P001'))"
