"""FastAPI backend for patient handoff intake.

NOTE: backend/api.py is the CANONICAL application (full handoff workflow). This
module is a minimal legacy intake-only endpoint retained for the hackathon demos.
It shares the same locked-down CORS allowlist as api.py — see backend/config.py.
"""

from __future__ import annotations

import logging
import os
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.intake_agent import PatientIntakeAgent, IntakeAgentError
from backend.config import ALLOWED_ORIGINS

log = logging.getLogger("cascadeai.intake")

app = FastAPI(
    title="Patient Handoff Intake API",
    description="Process patient handoff data via text or audio transcription",
    version="1.0.0",
)

# CORS: explicit allowlist. Never "*" with allow_credentials=True (that lets any
# origin make credentialed cross-site requests).
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HandoffTextRequest(BaseModel):
    """Request body for text-based handoff intake."""

    transcript: str = Field(
        ...,
        description="Text transcript of the patient handoff",
        min_length=1,
    )


class HandoffResponse(BaseModel):
    """Response structure for handoff intake."""

    confidence: float = 0.0
    reasoning: str | None = None
    patient_name: str | None = None
    room_number: str | None = None
    age: str | None = None
    chief_complaint: str | None = None
    medications: list[str] | None = None
    pending_tasks: list[str] | None = None
    vitals: Dict[str, str] | None = None
    safety_alerts: list[str] | None = None


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "Patient Handoff Intake API",
        "version": "1.0.0",
    }


@app.post("/handoff/intake", response_model=HandoffResponse)
async def process_handoff(request: HandoffTextRequest):
    """
    Process a patient handoff transcript and extract structured data.

    Accepts a text transcript and uses Azure OpenAI to extract:
    - Patient demographics (name, room, age)
    - Chief complaint
    - Medications
    - Pending tasks
    - Vitals
    - Safety alerts
    """
    try:
        agent = PatientIntakeAgent()
        summary = agent.extract(request.transcript)
        return HandoffResponse(**summary.as_dict())
    except IntakeAgentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        # Log the real error server-side; return a generic message to the caller so
        # internal details / stack context are not leaked.
        log.exception("Unexpected error processing handoff intake")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.") from exc


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "backend.api:app",
        host="0.0.0.0",
        port=port,
        reload=True,
    )
