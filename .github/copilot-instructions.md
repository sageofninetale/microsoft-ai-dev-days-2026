# Copilot Instructions - CascadeAI

## System Overview
**CascadeAI**: Multi-agent clinical handoff intelligence system preventing medical errors during nurse shift changes (Microsoft AI Dev Days 2026 hackathon).

**Tech Stack**: Python FastAPI backend with 6 specialized AI agents (Azure OpenAI + Azure Speech) + React frontend + Supabase Postgres EMR database.

**Status**: ✅ Full production system (all agents + UI working end-to-end)

---

## Architecture: Multi-Agent Clinical Workflow

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

# Terminal 3 - Run tests (server must be running for API tests)
python backend/test_update_agent.py       # Update processing + EMR verification
python backend/test_coordinator.py        # Multi-agent orchestration
python backend/test_draft_generator.py    # Color-coded handoff generation
python backend/test_edge_cases.py         # Clinical safety edge cases (offline)
python test_full_workflow.py              # End-to-end via API calls
```

### Key testing conventions
- Tests with `test_*.py` at project root call APIs (require running server)
- Tests in `backend/test_*.py` may be unit tests (check imports for API calls)
- `test_edge_cases.py` tests confidence scoring directly (no server needed)
- `test_speech.py` requires `test_handoff.m4a` audio file + ffmpeg for WAV conversion

### Database utilities
- `generate_patients.py`: Populate Supabase with 105 synthetic patients (P001-P105)
- `fix_patient_ordering.sql`: Create `patients_ordered` VIEW for sequential display
- See `ORDERING_FIX_GUIDE.md` for Supabase table ordering issues

**CRITICAL**: All Supabase queries fetching multiple patients MUST use `.order("patient_id")` to avoid random UUID ordering. The `patients_ordered` VIEW is available for Supabase UI but Python code uses the base table with explicit ordering.

---

## Conventions and patterns

### Python style
- **Type hints mandatory**: `from __future__ import annotations` in all files
- **Dataclasses with slots**: `@dataclass(slots=True)` for performance (all models in `intake_agent.py`, `verification_agent.py`, `protocol_agent.py`, `coordinator_agent.py`)
- **Custom exceptions**: Agent-specific errors (`IntakeAgentError`, `VerificationAgentError`, etc.) → HTTP 400
- **Import style**: Absolute imports `from backend.` when running from repo root
- **Async patterns**: Agent methods use `async def` with `asyncio.gather()` for parallel LLM calls (see `DraftGenerator._generate_handoff_summary_async()`)

### Agent initialization pattern
All agents are initialized as **module-level singletons** in `api.py` to reuse Azure OpenAI clients:
```python
# Singleton pattern in api.py
update_agent = None
def get_update_agent() -> UpdateAgent:
    global update_agent
    if update_agent is None:
        print("🔧 Initializing UpdateAgent...")
        update_agent = UpdateAgent()
    return update_agent
```
This prevents reinitializing OpenAI clients on every request. FastAPI lifespan events (`@asynccontextmanager`) handle startup/shutdown logging.

### Clinical confidence scoring (CRITICAL)
The `IntakeAgent` applies **strict clinical safety standards** to assess handoff quality. Confidence scores are **NOT percentages** - they're clinical risk assessments:

- **0.20-0.30**: 🔴 HARD STOP - Missing `patient_name` → UNUSABLE
- **0.40-0.50**: 🟠 CRITICAL GAPS - Missing `room_number` OR `chief_complaint` → UNUSABLE
- **0.55-0.65**: 🟡 IMPORTANT GAPS - Missing 2+ of: age, vitals, meds → Usable with caution
- **0.70-0.80**: 🟢 MINOR GAPS - Missing only 1 field → Usable
- **0.85-0.95**: 🟢 COMPLETE - All critical fields present
- **Rule**: Apply LOWEST applicable level (see `backend/README.md` table)

Example: Handoff with all fields BUT missing `patient_name` gets 0.20-0.30, not 0.90. Patient identity is non-negotiable.

Test with `test_edge_cases.py` to see AI reasoning for various confidence scores.

### Color-coded severity system
Used in `DraftGenerator` for visual handoff summaries (see `COLOR_CODED_HANDOFF_GUIDE.md`):
- 🔴 RED (CRITICAL): SpO2 <90%, active bleeding, severe vitals → Immediate action
- 🟠 ORANGE (HIGH RISK): Dual anticoagulation, abnormal vitals trending worse → Within 1 hour
- 🟡 YELLOW (CAUTION): New meds not in EMR, mild abnormalities → Monitor closely
- 🟢 GREEN (VERIFIED): Meds in EMR, vitals normal → Good to go
- 🔵 BLUE (INFO): Comfort measures, family updates → Informational only
- ⚪ GRAY (ADMIN): Shift changes, room transfers → Administrative

The `DraftGenerator` automatically assigns colors based on clinical thresholds. See `_generate_clinical_status_async()` for color assignment logic.

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
- **Parallel calls**: `DraftGenerator` uses `asyncio.gather()` to generate timeline, clinical status, and narrative simultaneously (3x speedup)

### Azure Speech
- **Audio flow**: WebM (browser) → Base64 → Backend → WAV (ffmpeg) → Azure Speech API → Text
- **Transcription endpoint**: `POST /api/transcribe` (base64 audio) → returns text
- **API version**: Using `azure-cognitiveservices-speech==1.35.0`
- **WAV conversion**: Backend uses `ffmpeg` subprocess to convert WebM → WAV before sending to Azure

### Supabase
- **Client init**: `database.py` module-level singleton (`supabase: Client`)
- **Query pattern**: `.table("patients").select("*").eq("patient_id", id).execute()`
- **Ordering**: Always use `.order("patient_id")` for patient lists (see `ORDERING_FIX_GUIDE.md`)
- **EMR verification**: `VerificationAgent` fetches patient records for cross-referencing

### Frontend-Backend API
- **CORS**: Allows `http://localhost:3000` and `127.0.0.1:3000`
- **Key endpoints**:
  - `POST /api/shift/start`: Create nurse shift → returns `shift_id`
  - `POST /api/transcribe`: Audio → text (Azure Speech)
  - `POST /api/patient/{id}/update`: Process update (UpdateAgent) → returns verification status
  - `POST /api/patient/{id}/draft`: Generate handoff (DraftGenerator) → returns color-coded summary
  - `POST /api/handoff/intake`: Full multi-agent workflow (CoordinatorAgent) → returns risk scores

---

## Critical files to understand

- `backend/api.py`: FastAPI endpoints, lifespan events, agent singletons
- `backend/models.py`: Dataclass definitions (NurseShift, PatientUpdate, DraftHandoff, etc.)
- `backend/coordinator_agent.py`: Multi-agent orchestration + weighted risk formula (20% handoff + 40% verification + 40% protocol)
- `backend/database.py`: All Supabase CRUD operations
- `WORKFLOW_EXPLAINED.md`: Step-by-step system flow (nurse shift → update → handoff)
- `COLOR_CODED_HANDOFF_GUIDE.md`: Visual severity classification rules
- `frontend/src/App.js`: React UI state management, audio recording logic (MediaRecorder API)

---

## Common workflows

### Adding a new agent
1. Create `backend/new_agent.py` with `@dataclass(slots=True)` result class
2. Define custom exception class (e.g., `NewAgentError(RuntimeError)`)
3. Implement agent class with `__init__` and main processing method
4. Add to `api.py` singleton pattern: `new_agent = None` + `get_new_agent()`
5. Import in `coordinator_agent.py` if needed for multi-agent workflows

### Adding a new API endpoint
1. Define Pydantic request model in `api.py` (inherits `BaseModel`)
2. Create async route function with `@app.post()` or `@app.get()`
3. Use agent singletons via `get_update_agent()` pattern
4. Call database functions from `database.py` for persistence
5. Return structured JSON (FastAPI auto-converts dataclasses)

### Testing a new feature
1. Write standalone test in `backend/test_feature.py` for unit tests
2. Write API test in `test_feature.py` (repo root) for integration tests
3. Run backend server: `cd backend && python main.py`
4. Run test: `python test_feature.py` (or `python backend/test_feature.py` for unit tests)
5. Check `test_full_workflow.py` for E2E test patterns
