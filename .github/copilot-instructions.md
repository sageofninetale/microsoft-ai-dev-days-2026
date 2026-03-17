# Copilot Instructions - CascadeAI

## System Overview
**CascadeAI**: Multi-agent clinical handoff intelligence system preventing medical errors during nurse shift changes (Microsoft AI Dev Days 2026 hackathon).

**Tech Stack**: Python FastAPI backend with 6 specialized AI agents (Azure OpenAI + Azure Speech) + React frontend + Supabase Postgres EMR database.

**Status**: ✅ Full production system (all agents + UI working end-to-end)

---

## Architecture: Multi-Agent Clinical Workflow

# Copilot instructions — CascadeAI (concise)

This repo is a multi-agent clinical handoff system. The guidance below highlights repo-specific patterns, essential commands, and where to look for details.

Quick start (dev):
- Install backend deps: `pip install -r backend/requirements.txt`
- Start backend: `cd backend && python main.py` (or run `./start.sh` from repo root)
- Start frontend: `cd frontend && npm install && npm start`
- Run E2E tests (backend must be running): `python test_full_workflow.py`

Important conventions:
- Agent singletons: Use getters in `backend/api.py` (e.g. `get_update_agent()`) — do NOT instantiate agents inside request handlers.
- Structured LLM output: Agents use `response_format={"type":"json_object"}`. Keep prompts strict and return exactly the JSON schema expected (see `backend/intake_agent.py`).
- Clinical confidence: The intake confidence scale is safety-first (missing `patient_name` → UNUSABLE 0.15–0.30). See `backend/intake_agent.py` for the exact scoring rules and wording.
- Audio pipeline: Browser MediaRecorder (WebM) → base64 → `POST /api/transcribe` → backend converts to WAV (ffmpeg/PyAV) → Azure Speech SDK → Whisper fallback. Ensure `ffmpeg` is available for reliable transcription.
- Supabase ordering: Always apply `.order("patient_id")` when fetching patient lists; otherwise UI order may be nondeterministic.

Key files to consult when making changes:
- `backend/api.py` — startup, CORS, agent getter singletons, endpoints
- `backend/intake_agent.py` — intake prompt, confidence rules, transcription fallback
- `backend/update_agent.py` — update extraction prompts, verification, EMR checks
- `backend/coordinator_agent.py` — orchestration and weighted risk calculation
- `backend/database.py` — Supabase client usage and query examples
- `frontend/src/App.js` — audio capture and UI integration

Adding features checklist (safe, minimal steps):
1. Create agent module with `@dataclass(slots=True)` models and a custom error class.
2. Add module-level `None` + getter in `backend/api.py` to preserve singleton client reuse.
3. Use strict JSON response_format for Azure OpenAI when extracting structured data.
4. Persist via `backend/database.py` and keep `.order("patient_id")` for lists.
5. Add tests: `backend/test_*` (unit) and root `test_*` (integration/E2E) and run them with the server running.

Troubleshooting quick hits:
- Module import errors: run scripts from repo root so package imports resolve (e.g., `python backend/test_*.py`).
- Transcription issues: install `ffmpeg` (`brew install ffmpeg`) or inspect logs (`/tmp/cascade-backend.log` when using `start.sh`).
- Bad JSON from LLM: run the agent locally with a known transcript and dump the raw `response.choices[0].message.content` to debug.

For deeper domain rules (color mapping, detailed prompt text, and confidence table) see `COLOR_CODED_HANDOFF_GUIDE.md`, `WORKFLOW_EXPLAINED.md`, and `backend/intake_agent.py`. If you'd like, I can merge specific prompt fragments or the full confidence table back into this file — tell me which sections to preserve.
