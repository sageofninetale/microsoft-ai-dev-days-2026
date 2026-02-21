# **CascadeAI System - Complete Workflow Explained Simply** 💧

This document explains how the ENTIRE CascadeAI system works from start to finish in simple terms.

---

## **📋 STEP 1: SHIFT STARTS**

**What happens:**
- A nurse (e.g., Neymar) logs in
- Selects which patients they'll monitor (e.g., P026, P046)
- Clicks "Start Shift"

**Behind the scenes:**
- Creates a new record in `nurse_shifts` table
- Generates a unique Shift ID
- Status: "active"

**Database:**
```
nurse_shifts table:
- shift_id: abc-123-xyz
- nurse: NURSE_NEYMAR
- patients: [P026, P046]
- start_time: 2026-02-19 21:00:00
```

---

## **🎤 STEP 2: NURSE RECORDS PATIENT UPDATE**

**What happens:**
- Nurse clicks "Record Audio"
- Speaks into microphone: *"Patient has been prescribed paracetamol 500mg every 6 hours"*
- Clicks "Stop Recording"

**Behind the scenes:**
1. **Browser records audio** → Creates WebM audio file
2. **Converts to Base64** → Sends to backend API
3. **Backend receives audio** → `/api/transcribe` endpoint
4. **Converts WebM → WAV** → Uses ffmpeg (audio format conversion)
5. **Sends to Azure Speech API** → Microsoft's AI transcription service
6. **Gets back text:** "Patient has been prescribed paracetamol 500mg every 6 hours"
7. **Returns to frontend** → Shows transcription

**What you see:**
- Green checkmarks showing progress
- "✅ Transcribed by Azure Speech API"
- The text appears on screen

---

## **💾 STEP 3: SUBMIT UPDATE (Save to Database)**

**What happens:**
- Nurse clicks **"Submit Audio Update"** button
- Frontend sends the transcribed text to backend

**Behind the scenes:**

### **3a. Backend Processing (`/api/patient/P026/update`)**

1. **Receives the text update:**
   ```json
   {
     "patient_id": "P026",
     "shift_id": "abc-123-xyz",
     "nurse_id": "NURSE_NEYMAR",
     "update_type": "medication",
     "text": "Patient prescribed paracetamol 500mg every 6 hours"
   }
   ```

2. **Calls UpdateAgent** (AI processing)

### **3b. UpdateAgent Extracts Structured Data**

**Uses Azure OpenAI (GPT model)** to analyze the text:

**Input:** "Patient prescribed paracetamol 500mg every 6 hours"

**AI Extraction:**
```json
{
  "event_type": "medication",
  "medications": [
    {
      "name": "paracetamol",
      "dose": "500mg",
      "frequency": "every 6 hours"
    }
  ],
  "vitals": {},
  "events": ["Prescribed paracetamol"]
}
```

### **3c. Verification Against Patient EMR**

**Fetches patient P026's medical record from database:**
```json
{
  "name": "Timothy Wilson",
  "age": 68,
  "current_medications": ["aspirin", "metformin"],
  "allergies": ["penicillin"],
  "conditions": ["diabetes", "hypertension"]
}
```

**AI Compares:**
- ✅ Is paracetamol in the patient's current med list? **NO**
- ❌ **ALERT:** New medication not in EMR
- ✅ Is patient allergic to paracetamol? **NO** (safe)

**Verification Result:**
```json
{
  "emr_verified": false,
  "issues": [
    {
      "type": "MEDICATION_NOT_IN_EMR",
      "severity": "HIGH",
      "finding": "Paracetamol not in current medication list"
    }
  ]
}
```

### **3d. Save to Database**

**Creates record in `patient_updates` table:**
```
patient_updates:
- id: xyz-789
- patient_id: P026
- shift_id: abc-123-xyz
- nurse_id: NURSE_NEYMAR
- timestamp: 2026-02-19 21:15:00
- update_type: medication
- transcription: "Patient prescribed paracetamol..."
- extracted_data: { medications: [...] }
- emr_verified: false
- verification_notes: { issues: [...] }
```

**Frontend shows:** ✅ "Update submitted successfully!"

---

## **👁️ STEP 4: VIEW ALL UPDATES**

**What happens:**
- Nurse clicks "Show All Updates"

**Behind the scenes:**
- Queries database: `SELECT * FROM patient_updates WHERE patient_id = P026 AND shift_id = abc-123-xyz`
- Returns all updates for this patient during this shift
- Shows chronologically (oldest → newest)

**What you see:**
```
1. 21:05 - Vital Signs: BP 130/85, HR 78
2. 21:10 - Medication: Prescribed paracetamol 500mg
3. 21:15 - General: Patient reports reduced pain
```

---

## **📄 STEP 5: GENERATE DRAFT HANDOFF**

**What happens:**
- Nurse clicks "Generate Draft Handoff"
- System creates a summary for the next nurse

**Behind the scenes:**

### **5a. Collect All Updates**
```sql
SELECT * FROM patient_updates 
WHERE patient_id = P026 
  AND shift_id = abc-123-xyz
ORDER BY timestamp
```

### **5b. Fetch Patient EMR Data**
```sql
SELECT * FROM patients WHERE patient_id = P026
```

### **5c. Call DraftGenerator (AI)**

**Sends to Azure OpenAI:**
```
PROMPT:
"Generate a clinical handoff report for Patient P026 (Timothy Wilson).

Patient Info:
- Age: 68
- Room: 544
- Diagnosis: Diabetes, Hypertension
- Current Meds: Aspirin, Metformin

Updates during shift:
1. 21:05 - Vital Signs: BP 130/85, HR 78
2. 21:10 - Medication: Prescribed paracetamol 500mg q6h
3. 21:15 - Patient reports reduced pain

Create a structured handoff following SBAR format."
```

**AI Generates:**
```
PATIENT HANDOFF - P026 Timothy Wilson

SITUATION:
68-year-old male in Room 544 with diabetes and hypertension.
New medication added during shift.

BACKGROUND:
- Known conditions: Diabetes, Hypertension
- Current medications: Aspirin, Metformin, Paracetamol (NEW)
- Allergies: Penicillin

ASSESSMENT:
- Vital signs stable (BP 130/85, HR 78)
- Pain management improved with paracetamol
- Blood sugar monitoring needed

RECOMMENDATIONS:
1. Continue paracetamol 500mg q6h for pain
2. Monitor blood glucose levels
3. Next vital signs check in 4 hours
```

### **5d. Save Draft to Database**

**Creates record in `draft_handoffs` table:**
```
draft_handoffs:
- id: draft-456
- patient_id: P026
- shift_id: abc-123-xyz
- nurse_id: NURSE_NEYMAR
- created_at: 2026-02-19 21:30:00
- draft_content: { ... AI-generated report ... }
- status: draft
```

**Frontend shows:** The formatted handoff report

---

## **✅ STEP 6: APPROVE & SEND (Future Feature)**

**What WOULD happen:**
- Nurse reviews the AI-generated handoff
- Edits if needed
- Clicks "Approve and Send"
- Moves from `draft_handoffs` → `sent_handoffs`
- Next nurse receives the handoff

---

## **🔄 SUMMARY - The Complete Flow:**

```
1. START SHIFT
   ↓
2. RECORD AUDIO → Azure Speech → Get Text
   ↓
3. SUBMIT UPDATE
   ↓
   → Azure OpenAI → Extract structured data
   ↓
   → Fetch patient EMR
   ↓
   → AI Verification (compare new vs EMR)
   ↓
   → Save to database (patient_updates)
   ↓
4. VIEW UPDATES (query database)
   ↓
5. GENERATE HANDOFF
   ↓
   → Collect all updates
   ↓
   → Fetch patient EMR
   ↓
   → Azure OpenAI → Generate narrative
   ↓
   → Save to database (draft_handoffs)
   ↓
6. DISPLAY HANDOFF (show AI summary)
```

---

## **🧠 KEY AI COMPONENTS:**

### **1. Azure Speech API**
- **Purpose:** Converts voice → text
- **When used:** Step 2 (Audio Recording)
- **Input:** WebM audio file (converted to WAV)
- **Output:** Transcribed text
- **Example:** Audio "patient prescribed paracetamol" → Text "Patient prescribed paracetamol"

### **2. Azure OpenAI - Data Extraction**
- **Purpose:** Text → Structured data
- **When used:** Step 3 (Submit Update)
- **Input:** Raw text from nurse
- **Output:** JSON with medications, vitals, events
- **Example:** 
  - Input: "BP is 130/85, gave aspirin 81mg"
  - Output: `{"vitals": {"bp": "130/85"}, "medications": [{"name": "aspirin", "dose": "81mg"}]}`

### **3. Azure OpenAI - EMR Verification**
- **Purpose:** Compare new data vs existing patient records
- **When used:** Step 3 (Submit Update)
- **Input:** Extracted data + Patient EMR
- **Output:** Verification results with safety alerts
- **Example:** Flags if new medication conflicts with allergies

### **4. Azure OpenAI - Draft Generator**
- **Purpose:** All updates → Clinical narrative
- **When used:** Step 5 (Generate Handoff)
- **Input:** All shift updates + Patient EMR
- **Output:** Structured SBAR handoff report
- **Example:** Creates a professional clinical summary for next nurse

---

## **📊 DATABASE TABLES:**

### **1. `patients` (Patient Medical Records - EMR)**
**Purpose:** Store complete patient medical history

**Columns:**
- `id` (UUID) - Internal database key
- `patient_id` (P001, P002...) - Human-readable patient code
- `name` - Patient full name
- `age` - Patient age
- `gender` - Male/Female
- `room_number` - Hospital room
- `primary_diagnosis` - Main condition
- `medications` (JSON) - Current medication list
- `allergies` (Array) - Known allergies
- `vitals_history` (JSON) - Recent vital signs
- `past_medical_history` (Array) - Previous conditions

**Example:**
```json
{
  "patient_id": "P026",
  "name": "Timothy Wilson",
  "age": 68,
  "medications": [
    {"name": "aspirin", "dose": "81mg", "frequency": "daily"},
    {"name": "metformin", "dose": "500mg", "frequency": "twice daily"}
  ],
  "allergies": ["penicillin"]
}
```

---

### **2. `nurse_shifts` (Who's Working When)**
**Purpose:** Track nurse shifts and assigned patients

**Columns:**
- `id` (UUID) - Shift ID
- `nurse_id` - Which nurse (NURSE_NEYMAR, NURSE_MESSI...)
- `nurse_name` - Full name (Neymar Junior, Lionel Messi...)
- `shift_type` - Day/Night/Evening
- `shift_date` - Date of shift
- `patient_ids` (Array) - List of assigned patients
- `start_time` - When shift started
- `end_time` - When shift ended (NULL if active)
- `status` - active/completed

**Example:**
```json
{
  "id": "abc-123-xyz",
  "nurse_id": "NURSE_NEYMAR",
  "nurse_name": "Neymar Junior",
  "patient_ids": ["P026", "P046"],
  "start_time": "2026-02-19 21:00:00",
  "status": "active"
}
```

---

### **3. `patient_updates` (Individual Updates - Timestamped Events)**
**Purpose:** Store every patient update made by nurses

**Columns:**
- `id` (UUID) - Update ID
- `shift_id` - Which shift this belongs to
- `patient_id` - Which patient
- `nurse_id` - Who made the update
- `timestamp` - When it happened
- `update_type` - medication/vital_signs/procedure/general
- `transcription` - Original text (what nurse said/typed)
- `audio_url` - Link to audio file (if recorded)
- `extracted_data` (JSON) - AI-extracted structured data
- `emr_verified` (Boolean) - Did it pass verification?
- `verification_notes` (JSON) - Any issues/alerts found

**Example:**
```json
{
  "id": "xyz-789",
  "patient_id": "P026",
  "shift_id": "abc-123-xyz",
  "nurse_id": "NURSE_NEYMAR",
  "timestamp": "2026-02-19 21:15:00",
  "update_type": "medication",
  "transcription": "Patient prescribed paracetamol 500mg every 6 hours",
  "extracted_data": {
    "medications": [
      {"name": "paracetamol", "dose": "500mg", "frequency": "q6h"}
    ]
  },
  "emr_verified": false,
  "verification_notes": {
    "issues": [
      {
        "type": "MEDICATION_NOT_IN_EMR",
        "severity": "HIGH",
        "finding": "Paracetamol not in current medication list"
      }
    ]
  }
}
```

---

### **4. `draft_handoffs` (AI-Generated Handoff Reports)**
**Purpose:** Store AI-generated clinical summaries

**Columns:**
- `id` (UUID) - Draft ID
- `patient_id` - Which patient
- `shift_id` - Which shift
- `nurse_id` - Who generated it
- `created_at` - When generated
- `draft_content` (JSON) - The AI-generated report
- `status` - draft/approved/sent

**Example:**
```json
{
  "id": "draft-456",
  "patient_id": "P026",
  "shift_id": "abc-123-xyz",
  "created_at": "2026-02-19 21:30:00",
  "draft_content": {
    "patient_summary": "68-year-old male...",
    "key_events": [...],
    "medications": [...],
    "vital_trends": {...},
    "recommendations": [...]
  },
  "status": "draft"
}
```

---

### **5. `sent_handoffs` (Completed Handoffs - Future)**
**Purpose:** Archive of sent handoff reports

**Columns:**
- Same as `draft_handoffs` plus:
- `approved_at` - When nurse approved it
- `sent_to` - Receiving nurse ID
- `received_at` - When next nurse acknowledged

---

## **🔐 IMPORTANT NOTES:**

### **Patient Assignment is Flexible:**
- The `patient_ids` in `nurse_shifts` is **informational only**
- Nurses can create updates for ANY patient (P001-P105)
- Multiple nurses can work on the same patient
- No restrictions enforced by the system

### **Data Flow Direction:**
```
Frontend (Browser)
    ↓
Backend API (FastAPI)
    ↓
Azure Services (Speech, OpenAI)
    ↓
Supabase Database (PostgreSQL)
```

### **Security:**
- CORS enabled for `localhost:3000` (development only)
- Supabase uses service_role key (full access)
- Production would need: authentication, authorization, HIPAA compliance

---

## **💡 TIPS FOR UNDERSTANDING:**

1. **Think of updates as events** - Each button click creates a timestamped record
2. **AI is the translator** - Converts messy speech → clean structured data
3. **Database is the memory** - Everything is saved, nothing is lost
4. **Handoff is the summary** - AI reads all events and writes a report

---

## **📚 RELATED DOCUMENTATION:**

- `README.md` - Project overview and setup
- `SETUP_STATUS.md` - Azure services configuration
- `AUDIO_RECORDING_GUIDE.md` - How audio recording works
- `ORDERING_FIX_GUIDE.md` - Database sorting explanation

---

**Created:** 2026-02-21  
**Last Updated:** 2026-02-21  
**For Questions:** Refer to the code in `backend/` directory or check Azure OpenAI/Speech documentation
