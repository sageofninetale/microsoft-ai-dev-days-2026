# Copilot instructions

## Repository snapshot
**CascadeAI**: Multi-agent clinical handoff intelligence system for Microsoft AI Dev Days 2026 hackathon.
- **Backend**: Python FastAPI service (`backend/`) with 6 specialized AI agents + Supabase EMR database
- **Frontend**: React app (`frontend/`) with real-time audio recording, shift management, and color-coded handoff UI
- **Status**: Full system complete (5 agents + coordinator + UI working end-to-end)

---

## Big-picture architecture: Multi-Agent Workflow

**6 Specialized Agents** coordinate to verify clinical handoffs:

1. **IntakeAgent** (`intake_agent.py`): Transcribes audio → extracts structured patient data (Azure Speech + OpenAI JSON mode)
2. **VerificationAgent** (`verification_agent.py`): Cross-references handoff vs Supabase EMR → flags discrepancies with severity levels
3. **ProtocolAgent** (`protocol_agent.py`): Checks compliance with clinical protocols (ACS, Fall Risk, Hypertension)
4. **UpdateAgent** (`update_agent.py`): Real-time shift updates → auto-detects type (med/vital/procedure) → verifies vs EMR → saves to DB
5. **DraftGenerator** (`draft_generator.py`): Aggregates shift updates → generates AI color-coded handoff summary + narrative (150-250 words)
6. **CoordinatorAgent** (`coordinator_agent.py`): Orchestrates Intake+Verification+Protocol → calculates weighted risk scores → prioritizes actions

**Core Data Flow**:
```
Nurse Audio/Text → UpdateAgent → EMR Verification → Database
                                                    ↓
                  Shift End → DraftGenerator → Color-Coded Handoff
                                                    ↓
           Critical Case → CoordinatorAgent → Multi-Agent Safety Report
```

**Database Schema** (Supabase Postgres):
- `patients`: EMR master records (P001-P105)
- `nurse_shifts`: Shift tracking (nurse_id, patient_ids[], status)
- `patient_updates`: Real-time updates (shift_id, update_type, structured_data, verification_status)
- `draft_handoffs`: AI-generated handoff summaries with color-coded safety alerts
- `patients_ordered`: VIEW for P001→P105 sequential display (created via `fix_patient_ordering.sql`)

---

## Developer workflows

### Installation & Setup
```bash
# Backend
pip install -r backend/requirements.txt

# Frontend
cd frontend && npm install

# Environment variables (required)
# Create .env in repo root:
AZURE_OPENAI_ENDPOINT=<your-endpoint>
AZURE_OPENAI_KEY=<your-key>
AZURE_OPENAI_DEPLOYMENT=gpt-5-mini
AZURE_SPEECH_KEY=<your-key>
AZURE_SPEECH_REGION=<your-region>
SUPABASE_URL=<your-url>
SUPABASE_KEY=<your-key>
```

### Running the system
```bash
# Terminal 1 - Backend API (port 8000)
cd backend && python main.py

# Terminal 2 - Frontend (port 3000)
cd frontend && npm start

# Terminal 3 - Tests (server must be running)
python backend/test_update_agent.py
python backend/test_coordinator.py
python backend/test_draft_generator.py
```

### Key test files
- `test_update_agent.py`: Real-time update processing + EMR verification
- `test_coordinator.py`: Multi-agent orchestration + risk scoring
- `test_draft_generator.py`: Color-coded handoff generation
- `test_edge_cases.py`: Clinical safety edge cases (missing patient name = 0.20 confidence)
- `test_speech.py`: Azure Speech transcription (requires `test_handoff.m4a` + ffmpeg for WAV conversion)

### Database utilities
- `generate_patients.py`: Populate Supabase with 105 synthetic patients (P001-P105)
- `fix_patient_ordering.sql`: Create `patients_ordered` VIEW for sequential display
- See `ORDERING_FIX_GUIDE.md` for Supabase table ordering issues

---

## Conventions and patterns

### Python style
- **Type hints mandatory**: `from __future__ import annotations` in all files
- **Dataclasses with slots**: `@dataclass(slots=True)` for performance (all models)
- **Custom exceptions**: Agent-specific errors (`IntakeAgentError`, `VerificationAgentError`, etc.) → HTTP 400
- **Import style**: Absolute imports `from backend.` when running from repo root

### Agent initialization pattern
```python
# Singleton pattern in api.py
update_agent = None
def get_update_agent() -> UpdateAgent:
    global update_agent
    if update_agent is None:
        update_agent = UpdateAgent()
    return update_agent
```

### Clinical confidence scoring (CRITICAL)
- **0.20-0.30**: 🔴 HARD STOP - Missing `patient_name` → UNUSABLE
- **0.40-0.50**: 🟠 CRITICAL GAPS - Missing `room_number` OR `chief_complaint` → UNUSABLE
- **0.55-0.65**: 🟡 IMPORTANT GAPS - Missing 2+ of: age, vitals, meds → Usable with caution
- **0.70-0.80**: 🟢 MINOR GAPS - Missing only 1 field → Usable
- **0.85-0.95**: 🟢 COMPLETE - All critical fields present
- **Rule**: Apply LOWEST applicable level (see `backend/README.md` table)

### Color-coded severity system
Used in `DraftGenerator` for visual handoff summaries (see `COLOR_CODED_HANDOFF_GUIDE.md`):
- 🔴 RED (CRITICAL): SpO2 <90%, active bleeding, severe vitals
- 🟠 ORANGE (HIGH RISK): Dual anticoagulation, abnormal vitals trending worse
- 🟡 YELLOW (CAUTION): New meds not in EMR, mild abnormalities
- 🟢 GREEN (VERIFIED): Meds in EMR, vitals normal
- 🔵 BLUE (INFO): Comfort measures, family updates
- ⚪ GRAY (ADMIN): Shift changes, room transfers

### Error handling
```python
# Known failures → HTTP 400
raise IntakeAgentError("Missing patient_name")

# Unexpected → HTTP 500 (handled by FastAPI)
# Non-critical errors → store in CoordinatorResult.errors list
```

---

## Integrations

### Azure OpenAI
- **Deployment**: `gpt-5-mini` (env: `AZURE_OPENAI_DEPLOYMENT`)
- **JSON mode**: All agents use `response_format={"type": "json_object"}` for structured extraction
- **System prompts**: Clinical context-aware (see agent `_extract_*` methods)

### Azure Speech
- **Audio flow**: WebM (browser) → Base64 → Backend → WAV (ffmpeg) → Azure Speech API → Text
- **Transcription endpoint**: `POST /api/transcribe` (base64 audio) → returns text
- **API version**: Using `azure-cognitiveservices-speech==1.35.0`

### Supabase
- **Client init**: `database.py` module-level singleton (`supabase: Client`)
- **Query pattern**: `.table("patients").select("*").eq("patient_id", id).execute()`
- **Ordering**: Always use `.order("patient_id")` for patient lists (see `ORDERING_FIX_GUIDE.md`)
- **EMR verification**: `VerificationAgent` fetches patient records for cross-referencing

### Frontend-Backend API
- **CORS**: Allows `http://localhost:3000` and `127.0.0.1:3000`
- **Key endpoints**:
  - `POST /api/shift/start`: Create nurse shift
  - `POST /api/transcribe`: Audio → text (Azure Speech)
  - `POST /api/patient/{id}/update`: Process update (UpdateAgent)
  - `GET /api/shift/{id}/draft`: Generate handoff (DraftGenerator)
  - `POST /api/handoff/intake`: Full multi-agent workflow (CoordinatorAgent)

---

## Critical files to understand

- `backend/api.py`: FastAPI endpoints, lifespan events, agent singletons
- `backend/models.py`: Dataclass definitions (NurseShift, PatientUpdate, DraftHandoff, etc.)
- `backend/coordinator_agent.py`: Multi-agent orchestration + weighted risk formula
- `backend/database.py`: All Supabase CRUD operations
- `WORKFLOW_EXPLAINED.md`: Step-by-step system flow (nurse shift → update → handoff)
- `COLOR_CODED_HANDOFF_GUIDE.md`: Visual severity classification rules
- `frontend/src/App.js`: React UI state management, audio recording logic
