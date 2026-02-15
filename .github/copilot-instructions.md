# Copilot instructions

## Repository snapshot
- Patient handoff intake system for Microsoft AI Dev Days 2026.
- **Backend**: Python FastAPI service (`backend/`) that processes medical handoff transcripts using Azure OpenAI + Azure Speech Services.
- **Frontend**: Placeholder (`frontend/`) - not yet implemented.

## Big-picture architecture
- **Entry point**: `backend/main.py` runs a FastAPI server with a `POST /handoff/intake` endpoint.
- **Core logic**: `backend/intake_agent.py` contains `PatientIntakeAgent` class that:
  - Transcribes audio via Azure Speech SDK (not yet wired to the API)
  - Extracts structured patient data (name, room, age, chief complaint, meds, tasks, vitals, safety alerts) via Azure OpenAI with JSON mode.
- **Data flow**: Text transcript → Azure OpenAI → structured JSON → FastAPI response.

## Developer workflows
- **Install**: `pip install -r backend/requirements.txt`
- **Run server**: `cd backend && python main.py` (starts on `http://localhost:8000`)
- **Test**: `python backend/test_intake_api.py` (requires server running)
- **Environment**: Requires `.env` at repo root with `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_KEY`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`.

## Conventions and patterns
- Python backend uses type hints (`from __future__ import annotations`) and Pydantic models for request/response validation.
- CORS is wide-open (`allow_origins=["*"]`) for hackathon use; tighten for production.
- Error handling: `IntakeAgentError` for known failures → HTTP 400; unexpected exceptions → HTTP 500.
- Import style: Use absolute imports from `backend.` package when running from repo root.

## Integrations
- **Azure OpenAI**: `gpt-5-mini` deployment with JSON response mode for structured extraction.
- **Azure Speech**: Configured but not yet exposed via API endpoint (text-only for now).
- See `SETUP_STATUS.md` for confirmation that Azure services are provisioned and working.
