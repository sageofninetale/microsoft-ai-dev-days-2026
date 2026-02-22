-- ============================================================
-- PERMANENT FIX: Set default ordering for patients table
-- Run this in Supabase SQL Editor
-- ============================================================

-- Step 1: Create an index on patient_id for faster sorting
-- This makes ORDER BY patient_id very fast
CREATE INDEX IF NOT EXISTS idx_patients_patient_id 
ON patients(patient_id);

-- Step 2: Add a comment to document the intended sort order
COMMENT ON TABLE patients IS 'Patient records - default view should ORDER BY patient_id';

-- Step 3: Create a function to get patients in proper order
-- This is what the API should use
CREATE OR REPLACE FUNCTION get_patients_ordered()
RETURNS TABLE (
    id uuid,
    patient_id text,
    name text,
    age int,
    date_of_birth date,
    gender text,
    room_number text,
    admission_date date,
    primary_diagnosis text,
    medications jsonb,
    allergies text[],
    vitals_history jsonb,
    past_medical_history text[],
    fall_risk_score int,
    code_status text,
    created_at timestamptz
) AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM patients
    ORDER BY patients.patient_id;
END;
$$ LANGUAGE plpgsql;

-- Step 4: Create a view for Supabase Table Editor
-- This makes the UI always show patients in order
CREATE OR REPLACE VIEW patients_ordered AS
SELECT 
    patient_id,
    name,
    age,
    gender,
    room_number,
    primary_diagnosis,
    admission_date,
    medications,
    allergies,
    vitals_history,
    past_medical_history,
    fall_risk_score,
    code_status,
    id,
    date_of_birth,
    created_at
FROM patients
ORDER BY patient_id;

-- Step 5: Grant permissions on the view
GRANT SELECT ON patients_ordered TO anon, authenticated;

-- ============================================================
-- VERIFICATION QUERY
-- Run this to confirm it works:
-- ============================================================
SELECT patient_id, name, room_number 
FROM patients_ordered 
LIMIT 10;

-- Expected output: P001, P002, P003... in order
