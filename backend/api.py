"""
FastAPI REST API server for CascadeAI - Intelligent Clinical Handoff System
Provides endpoints for shift management, patient updates, and draft generation.
"""

from __future__ import annotations
import asyncio
import logging
import os
import sys
from pathlib import Path
from datetime import date, datetime
from typing import Optional, List, Dict, Any, Literal
from dotenv import load_dotenv

# Ensure 'backend' package is importable whether we run from repo root or from backend/ dir.
# On Azure App Service, the app root is the backend/ folder itself, so we add its parent to
# sys.path so that `from xxx import ...` still works throughout the codebase.
_this_dir = Path(__file__).resolve().parent
if _this_dir.name == "backend":
    # Running from inside the backend directory (Azure) - add the parent so `backend` is a package
    sys.path.insert(0, str(_this_dir.parent))
# Also ensure the backend dir itself is on the path (for direct imports)
if str(_this_dir) not in sys.path:
    sys.path.insert(0, str(_this_dir))

# FastAPI imports
from fastapi import FastAPI, HTTPException, Body, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# Local imports - Config
from config import ALLOWED_ORIGINS, DOCS_ENABLED, MAX_AUDIO_B64_CHARS, MAX_AUDIO_DECODED_BYTES

# Local imports - Agents
from update_agent import UpdateAgent
from draft_generator import DraftGenerator

# Local imports - Risk pipeline (trust stack Phase 2): wires the previously
# orphaned ProtocolAgent + the 20/40/40 risk scorer into this live path.
import risk_pipeline
from database import update_draft

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("cascadeai.api")


def _rate_limit_key(request: Request) -> str:
    """
    Rate-limit key: the bearer token (which identifies the authenticated nurse)
    when present, else the client IP. Because auth runs first, this is effectively
    per-nurse for authenticated traffic.
    """
    auth_header = request.headers.get("authorization")
    if auth_header:
        return auth_header
    return get_remote_address(request)


limiter = Limiter(key_func=_rate_limit_key)

# Local imports - Auth & object-level authorization
from auth import (
    AuthedNurse,
    get_current_nurse,
    require_active_shift,
    require_owned_shift,
    require_patient_in_shift,
    require_patient_assigned,
    filter_to_assigned,
)

# Local imports - Models (shared enums for input validation)
from models import ShiftType, UpdateType

# Local imports - Database
from database import (
    create_shift,
    get_active_shift,
    get_shift_by_id,
    get_patient,
    get_multiple_patients,
    get_patient_updates,
    get_draft,
    get_client_for_token,
)
from supabase import Client

# Load environment variables
load_dotenv()


async def get_db(nurse: AuthedNurse = Depends(get_current_nurse)) -> Client:
    """Per-request Supabase client scoped to the calling nurse's own JWT, so
    RLS policies (current_nurse_id()) see the real caller instead of anon."""
    client = get_client_for_token(nurse.token)
    if client is None:
        raise HTTPException(status_code=503, detail="Database is not configured on the server.")
    return client


# ============================================================================
# LIFESPAN EVENTS
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    print("\n" + "="*60)
    print("💧 CascadeAI API - Starting Up")
    print("="*60)
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🌐 CORS enabled for: http://localhost:3000, http://localhost:8888")
    print(f"✅ API ready at: http://localhost:8000")
    print(f"📚 Docs available at: http://localhost:8000/docs")
    print("="*60 + "\n")

    yield

    # Shutdown
    print("\n" + "="*60)
    print("💧 CascadeAI API - Shutting Down")
    print("="*60 + "\n")


# Initialize FastAPI app.
# The global dependency on get_current_nurse means EVERY route requires a valid
# Supabase JWT (401 before any handler logic). Handlers that need the caller's
# identity re-declare `nurse: AuthedNurse = Depends(get_current_nurse)`; FastAPI
# resolves the dependency once per request, so this is not a double check.
app = FastAPI(
    title="CascadeAI API",
    description="Intelligent clinical handoff system with AI-powered patient updates and draft generation",
    version="1.0.0",
    lifespan=lifespan,
    dependencies=[Depends(get_current_nurse)],
    # Interactive docs are off unless ENABLE_DOCS is set (keep the endpoint map
    # unadvertised in production).
    docs_url="/docs" if DOCS_ENABLED else None,
    redoc_url="/redoc" if DOCS_ENABLED else None,
)

# Rate limiting: register the limiter and a 429 handler for exceeded limits.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Enable CORS for frontend — explicit allowlist (see backend/config.py).
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize agents (singleton instances)
update_agent = None
draft_generator = None


def get_update_agent() -> UpdateAgent:
    """Get or create UpdateAgent instance"""
    global update_agent
    if update_agent is None:
        print("🔧 Initializing UpdateAgent...")
        update_agent = UpdateAgent()
    return update_agent


def get_draft_generator() -> DraftGenerator:
    """Get or create DraftGenerator instance"""
    global draft_generator
    if draft_generator is None:
        print("🔧 Initializing DraftGenerator...")
        draft_generator = DraftGenerator()
    return draft_generator


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class StartShiftRequest(BaseModel):
    # nurse_id / nurse_name are intentionally NOT accepted from the client — the acting
    # nurse is derived from the authenticated JWT. Accepting them from the body allowed
    # any caller to impersonate any nurse.
    shift_type: ShiftType  # constrained to the ShiftType enum (day/night/evening)
    patient_ids: List[str] = Field(..., min_length=1, max_length=50)


class PatientUpdateRequest(BaseModel):
    # nurse_id is intentionally NOT accepted from the client — see StartShiftRequest.
    shift_id: str = Field(..., min_length=1, max_length=64)
    update_type: UpdateType  # constrained to the UpdateType enum
    text: Optional[str] = Field(default=None, max_length=20000)
    audio: Optional[str] = Field(default=None, max_length=MAX_AUDIO_B64_CHARS)  # base64 encoded audio


class GenerateDraftRequest(BaseModel):
    shift_id: str = Field(..., min_length=1, max_length=64)


class TranscribeAudioRequest(BaseModel):
    # Cap the base64 payload at the model layer so an oversized body is rejected
    # (422) before it is ever read into memory / decoded — mitigates memory DoS.
    audio: str = Field(..., min_length=1, max_length=MAX_AUDIO_B64_CHARS)  # base64 encoded audio
    # Constrain the format to a known allowlist — it is used to build temp filenames.
    format: Literal["webm", "wav", "m4a", "mp3", "ogg"] = "webm"


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    print("✅ Health check requested")
    return {
        "status": "healthy",
        "service": "CascadeAI API",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }



@app.post("/api/transcribe")
@limiter.limit("10/minute")
async def transcribe_audio(request: Request, payload: TranscribeAudioRequest):
    """Transcribe audio using VibeVoice-ASR via Modal"""
    log.info("Transcribing audio (format=%s)", payload.format)

    try:
        import base64
        import binascii
        import tempfile
        import os
        import subprocess
        # UpdateAgent already imported at module level

        # Decode base64 audio — keep bytes in memory for Whisper fallback.
        try:
            audio_bytes = base64.b64decode(payload.audio, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(status_code=400, detail="Audio is not valid base64.")

        # Bound the DECODED size too (the base64 char cap is enforced on the model),
        # so a valid-but-huge payload cannot exhaust memory downstream.
        if len(audio_bytes) > MAX_AUDIO_DECODED_BYTES:
            raise HTTPException(status_code=413, detail="Audio payload too large.")

        # Write to an auto-cleaned temp directory so BOTH the source audio and any
        # converted WAV are removed on exit — including on exception — rather than
        # relying on a best-effort finally. No PHI audio is left on disk afterwards.
        # (Paths are fixed names inside the private dir, so the client-supplied
        # `format` can no longer influence the on-disk filename.)
        with tempfile.TemporaryDirectory(prefix="cascade_asr_") as tmpdir:
            temp_audio_path = os.path.join(tmpdir, f"input.{payload.format}")
            with open(temp_audio_path, "wb") as temp_audio:
                temp_audio.write(audio_bytes)

            wav_path = None
            transcription = None

            # Convert to WAV if not already WAV (needed for Azure Speech SDK)
            audio_path_to_use = None
            if payload.format.lower() != 'wav':
                wav_path = os.path.join(tmpdir, "input.wav")

                print(f"🔄 Converting {payload.format} to WAV...")

                try:
                    result = subprocess.run(
                        ['ffmpeg', '-i', temp_audio_path, '-ar', '16000', '-ac', '1', '-f', 'wav', wav_path],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )

                    if result.returncode != 0:
                        print(f"⚠️ ffmpeg error: {result.stderr}")
                    else:
                        print(f"✅ Converted to WAV: {wav_path}")
                        audio_path_to_use = wav_path

                except FileNotFoundError:
                    print("⚠️ ffmpeg not found, trying PyAV (built-in FFmpeg bindings)...")

                    try:
                        import av
                        import io as _io
                        import struct

                        input_buf = _io.BytesIO(audio_bytes)
                        pcm_chunks = []

                        with av.open(input_buf) as container:
                            if not container.streams.audio:
                                raise ValueError("No audio streams found in container")
                            audio_stream = container.streams.audio[0]
                            resampler = av.AudioResampler(format='s16', layout='mono', rate=16000)
                            for frame in container.decode(audio_stream):
                                for rf in resampler.resample(frame):
                                    pcm_chunks.append(bytes(rf.planes[0]))
                            for rf in resampler.resample(None):  # flush
                                pcm_chunks.append(bytes(rf.planes[0]))

                        pcm_data = b''.join(pcm_chunks)
                        sr, ch, bits = 16000, 1, 16
                        wav_header = struct.pack(
                            '<4sI4s4sIHHIIHH4sI',
                            b'RIFF', 36 + len(pcm_data), b'WAVE',
                            b'fmt ', 16, 1, ch, sr, sr * ch * bits // 8, ch * bits // 8, bits,
                            b'data', len(pcm_data)
                        )
                        with open(wav_path, 'wb') as f:
                            f.write(wav_header)
                            f.write(pcm_data)

                        audio_path_to_use = wav_path
                        print(f"✅ Converted to WAV using PyAV: {wav_path}")

                    except Exception as av_err:
                        print(f"⚠️ PyAV conversion failed: {av_err} — will try Whisper directly")
            else:
                audio_path_to_use = temp_audio_path

            if audio_path_to_use:
                agent = get_update_agent()
                transcription = await asyncio.get_event_loop().run_in_executor(
                    None, agent._transcribe_audio, audio_path_to_use
                )
                if not transcription:
                    print("⚠️ Deepgram returned no transcription")

            if not transcription or transcription.strip() == "":
                raise Exception("No speech detected in audio")

            return {
                "success": True,
                "transcription": transcription,
                "audio_duration": len(audio_bytes) / 16000  # Approximate duration
            }

    except HTTPException:
        raise
    except Exception:
        # Log full detail server-side; return a generic message to the caller.
        log.exception("Transcription error")
        raise HTTPException(status_code=500, detail="Transcription failed.")


@app.get("/api/nurses")
async def get_nurses():
    """Get list of available nurses for dropdown selection"""
    print("📋 Fetching nurse list...")
    
    nurses = [
        {"id": "NURSE_SARAH", "name": "Sarah Mitchell"},
        {"id": "NURSE_JAMES", "name": "James Okafor"},
        {"id": "NURSE_PRIYA", "name": "Priya Sharma"},
        {"id": "NURSE_EMMA", "name": "Emma Clarke"},
        {"id": "NURSE_DANIEL", "name": "Daniel Wong"}
    ]
    
    print(f"✅ Returning {len(nurses)} nurses")
    return nurses


@app.get("/api/patient/{patient_id}/info")
async def get_patient_info(
    patient_id: str,
    nurse: AuthedNurse = Depends(get_current_nurse),
    db: Client = Depends(get_db),
):
    """Get basic patient information (only for a patient assigned to the caller's active shift)"""
    print(f"🔍 Fetching info for patient {patient_id}...")

    # Object-level authorization: the patient must be assigned to the caller's active shift.
    require_patient_assigned(nurse, patient_id, client=db)

    try:
        patient = get_patient(patient_id, client=db)

        if not patient:
            raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

        log.info("Fetched patient %s", patient_id)

        return {
            "patient_id": patient.get('patient_id'),
            "name": patient.get('name'),
            "age": patient.get('age'),
            "room_number": patient.get('room_number'),
            "primary_diagnosis": patient.get('primary_diagnosis')
        }

    except HTTPException:
        raise
    except Exception:
        log.exception("Error fetching patient %s", patient_id)
        raise HTTPException(status_code=500, detail="Failed to fetch patient.")


@app.post("/api/shift/start", status_code=201)
async def start_shift(
    request: StartShiftRequest,
    nurse: AuthedNurse = Depends(get_current_nurse),
    db: Client = Depends(get_db),
):
    """Start a new shift for the authenticated nurse over their assigned patients only"""
    print(f"🏥 Starting shift...")
    print(f"   Type: {request.shift_type}")
    print(f"   Patients requested: {len(request.patient_ids)}")

    # Workflow / business-logic guard: a nurse may only open a shift over patients that
    # are actually assigned to them. Requested-but-unassigned patient_ids are dropped;
    # if that leaves nothing, refuse rather than creating an all-access shift.
    authorized_patient_ids = filter_to_assigned(nurse, request.patient_ids, client=db)
    if not authorized_patient_ids:
        raise HTTPException(
            status_code=403,
            detail="None of the requested patients are assigned to you.",
        )
    if len(authorized_patient_ids) != len(set(request.patient_ids)):
        print(f"   ⚠️  Dropped unassigned patients from shift request")

    try:
        # Create shift in database — identity comes from the token, never the request body.
        shift = create_shift(
            nurse_id=nurse.nurse_id,
            nurse_name=nurse.name or nurse.nurse_id,
            shift_type=request.shift_type.value,
            shift_date=date.today(),
            patient_ids=authorized_patient_ids,
            client=db,
        )

        if not shift:
            raise HTTPException(status_code=500, detail="Failed to create shift")
        
        print(f"✅ Shift created: {shift.id}")
        
        return {
            "shift_id": shift.id,
            "nurse_id": shift.nurse_id,
            "nurse_name": shift.nurse_name,
            "shift_type": shift.shift_type,
            "patient_ids": shift.patient_ids,
            "start_time": shift.start_time.isoformat(),
            "status": shift.status
        }
        
    except HTTPException:
        raise
    except Exception:
        log.exception("Error starting shift")
        raise HTTPException(status_code=500, detail="Failed to start shift.")


@app.get("/api/shift/active/{nurse_id}")
async def get_nurse_active_shift(
    nurse_id: str,
    nurse: AuthedNurse = Depends(get_current_nurse),
    db: Client = Depends(get_db),
):
    """Get the caller's own active shift (a nurse may only query their own)"""
    print(f"🔍 Fetching active shift...")

    # A nurse may only look up their own active shift, regardless of the path value.
    if nurse_id != nurse.nurse_id:
        raise HTTPException(status_code=403, detail="You may only query your own active shift.")

    try:
        shift = get_active_shift(nurse.nurse_id, client=db)
        
        if not shift:
            log.info("No active shift found")
            return None

        log.info("Found active shift %s", shift.id)

        return {
            "shift_id": shift.id,
            "nurse_id": shift.nurse_id,
            "nurse_name": shift.nurse_name,
            "shift_type": shift.shift_type,
            "patient_ids": shift.patient_ids,
            "start_time": shift.start_time.isoformat(),
            "status": shift.status
        }

    except HTTPException:
        raise
    except Exception:
        log.exception("Error fetching active shift")
        raise HTTPException(status_code=500, detail="Failed to fetch active shift.")


@app.get("/api/patients/{shift_id}")
async def get_shift_patients(
    shift_id: str,
    nurse: AuthedNurse = Depends(get_current_nurse),
    db: Client = Depends(get_db),
):
    """Get all patients assigned to a shift the caller owns"""
    print(f"🔍 Fetching patients for shift {shift_id}...")

    try:
        # Object-level authorization: the shift must belong to the caller (404 otherwise).
        shift = require_owned_shift(nurse, shift_id, client=db)

        # Fetch patient details
        patients = get_multiple_patients(shift.patient_ids, client=db)
        
        log.info("Found %d patients for shift %s", len(patients), shift_id)

        return patients

    except HTTPException:
        raise
    except Exception:
        log.exception("Error fetching patients for shift %s", shift_id)
        raise HTTPException(status_code=500, detail="Failed to fetch patients.")


@app.post("/api/patient/{patient_id}/update", status_code=201)
@limiter.limit("30/minute")
async def add_patient_update(
    request: Request,
    patient_id: str,
    payload: PatientUpdateRequest,
    nurse: AuthedNurse = Depends(get_current_nurse),
    db: Client = Depends(get_db),
):
    """Add a new update for a patient in the caller's own active shift"""
    log.info("Adding update for patient %s (type=%s, shift=%s)",
             patient_id, payload.update_type.value, payload.shift_id)

    # Object-level authorization before any processing:
    #  - the shift must belong to the authenticated nurse (404 otherwise),
    #  - it must still be active,
    #  - and the patient must be assigned to that shift.
    shift = require_owned_shift(nurse, payload.shift_id, client=db)
    if not shift.is_active():
        raise HTTPException(status_code=409, detail="Shift is not active.")
    require_patient_in_shift(patient_id, shift)

    try:
        agent = get_update_agent()

        # Determine if audio or text
        if payload.audio:
            # TODO: Decode base64 audio and save to temp file
            # For now, return error
            raise HTTPException(status_code=501, detail="Audio updates not yet implemented")

        if not payload.text:
            raise HTTPException(status_code=400, detail="Either 'text' or 'audio' must be provided")

        # Process the update — nurse identity comes from the verified token, not the body.
        result = agent.process_update(
            audio_or_text=payload.text,
            patient_id=patient_id,
            nurse_id=nurse.nurse_id,
            shift_id=payload.shift_id,
            update_type=payload.update_type.value,
            is_audio=False,
            client=db,
        )

        if not result.get("success"):
            error_msg = result.get("message", "Update processing failed")
            # Check if it's a shift ID issue
            if "database" in error_msg.lower() or "save" in error_msg.lower():
                raise HTTPException(
                    status_code=400,
                    detail="Invalid shift ID. Please refresh the page and start a new shift."
                )
            raise HTTPException(status_code=500, detail="Update processing failed.")

        log.info("Update processed: %s", result.get("update_id"))

        # Trust stack Phase 2a: ProtocolAgent + deterministic NEWS2 + the
        # ported 20/40/40 risk scorer now run on every live update. A failure
        # inside the assessment must not lose an already-saved update, so it
        # degrades to an explicit "unavailable" marker (never a fake score).
        try:
            risk_assessment = risk_pipeline.assess_update(
                result.get("extracted_data") or {},
                get_patient(patient_id, client=db) or {},
                {"issues": result.get("verification_issues", []),
                 "emr_verified": result.get("emr_verified")},
                shift_id=payload.shift_id, patient_id=patient_id,
                update_id=result.get("update_id"), nurse_id=nurse.nurse_id,
            )
        except Exception:
            log.exception("Risk assessment failed for update %s", result.get("update_id"))
            risk_assessment = {"available": False,
                               "message": "Risk assessment unavailable — review manually."}

        return {
            "success": True,
            "update_id": result.get("update_id"),
            "transcription": result.get("transcription"),
            "extracted_data": result.get("extracted_data"),
            "emr_verified": result.get("emr_verified"),
            "verification_issues": result.get("verification_issues", []),
            "risk_assessment": risk_assessment
        }
        
    except HTTPException:
        raise
    except Exception:
        log.exception("Error processing update for patient %s", patient_id)
        raise HTTPException(status_code=500, detail="Failed to process update.")


@app.get("/api/patient/{patient_id}/updates/{shift_id}")
async def get_patient_shift_updates(
    patient_id: str,
    shift_id: str,
    nurse: AuthedNurse = Depends(get_current_nurse),
    db: Client = Depends(get_db),
):
    """Get all updates for a patient during a shift the caller owns"""
    log.info("Fetching updates for patient %s in shift %s", patient_id, shift_id)

    # Object-level authorization: shift must be the caller's and patient must be in it.
    shift = require_owned_shift(nurse, shift_id, client=db)
    require_patient_in_shift(patient_id, shift)

    try:
        updates = get_patient_updates(patient_id, shift_id, client=db)

        log.info("Found %d updates", len(updates))
        
        # Convert to dict format
        updates_data = []
        for update in updates:
            updates_data.append({
                "id": update.id,
                "timestamp": update.timestamp.isoformat() if hasattr(update.timestamp, 'isoformat') else str(update.timestamp),
                "update_type": update.update_type,
                "transcription": update.transcription,
                "extracted_data": update.extracted_data,
                "emr_verified": update.emr_verified,
                "verification_notes": update.verification_notes
            })
        
        return updates_data

    except HTTPException:
        raise
    except Exception:
        log.exception("Error fetching updates for patient %s", patient_id)
        raise HTTPException(status_code=500, detail="Failed to fetch updates.")


@app.post("/api/patient/{patient_id}/draft", status_code=201)
@limiter.limit("6/minute")
async def generate_patient_draft(
    request: Request,
    patient_id: str,
    payload: GenerateDraftRequest,
    nurse: AuthedNurse = Depends(get_current_nurse),
    db: Client = Depends(get_db),
):
    """Generate draft handoff for a patient in the caller's own shift"""
    log.info("Generating draft for patient %s (shift=%s)", patient_id, payload.shift_id)

    # Object-level authorization before triggering (billable) LLM calls.
    shift = require_owned_shift(nurse, payload.shift_id, client=db)
    require_patient_in_shift(patient_id, shift)

    try:
        # Check if there are any updates first
        updates = get_patient_updates(patient_id, payload.shift_id, client=db)

        if not updates or len(updates) == 0:
            raise HTTPException(
                status_code=400,
                detail="No updates found for this patient. Please add at least one update before generating a draft."
            )

        generator = get_draft_generator()

        # Generate draft
        result = await generator.generate_draft(
            patient_id=patient_id,
            shift_id=payload.shift_id,
            client=db,
        )

        if not result.get("success"):
            raise HTTPException(status_code=500, detail="Draft generation failed.")

        log.info("Draft generated: %s", result.get("draft_id"))

        # Trust stack Phase 2d — risk gate. The final draft state is scored
        # (protocol compliance + aggregated verification issues + confidence,
        # 20/40/40) and a score at/above the threshold forces the draft to be
        # presented as "⚠ NEEDS ATTENTION" with its priority-action list —
        # never as a clean report. The annotation is persisted onto the saved
        # draft so the review UI reads the same thing this response returns.
        draft_content = result.get("draft_content") or {}
        try:
            attention = risk_pipeline.assess_draft(
                draft_content,
                get_patient(patient_id, client=db) or {},
                updates,
                shift_id=payload.shift_id, patient_id=patient_id,
                nurse_id=nurse.nurse_id, draft_id=result.get("draft_id"),
            )
        except Exception:
            log.exception("Risk gate failed for draft %s", result.get("draft_id"))
            # Fail SAFE for a clinical gate: an unscoreable draft is flagged
            # for attention, not waved through as clean.
            attention = {
                "needs_attention": True,
                "banner": "⚠ NEEDS ATTENTION",
                "risk_score": None,
                "risk_level": "UNSCORED",
                "priority_actions": ["Risk gate failed to run — review this draft manually."],
            }

        draft_content["attention"] = attention
        if result.get("draft_id"):
            # Persist the annotated content; failure to persist must not lose
            # the response annotation (update_draft already logs its own errors).
            update_draft(result["draft_id"], draft_content, result.get("update_count") or len(updates), client=db)

        return {
            "success": True,
            "draft_id": result.get("draft_id"),
            "patient_id": patient_id,
            "update_count": result.get("update_count"),
            "draft_content": draft_content,
            "attention": attention,
            # Linked Evidence (trust stack Phase 4): per-section pointers back
            # to the update IDs / transcript excerpts that produced the draft.
            "provenance": draft_content.get("provenance")
        }
        
    except HTTPException:
        raise
    except Exception:
        log.exception("Error generating draft for patient %s", patient_id)
        raise HTTPException(status_code=500, detail="Failed to generate draft.")


@app.get("/api/patient/{patient_id}/draft/{shift_id}")
async def get_patient_draft(
    patient_id: str,
    shift_id: str,
    nurse: AuthedNurse = Depends(get_current_nurse),
    db: Client = Depends(get_db),
):
    """Retrieve existing draft for a patient in a shift the caller owns"""
    log.info("Fetching draft for patient %s in shift %s", patient_id, shift_id)

    # Object-level authorization: shift must be the caller's and patient must be in it.
    shift = require_owned_shift(nurse, shift_id, client=db)
    require_patient_in_shift(patient_id, shift)

    try:
        draft = get_draft(patient_id, shift_id, client=db)

        if not draft:
            log.info("No draft found for patient %s", patient_id)
            return None

        log.info("Found draft %s", draft.id)

        return {
            "draft_id": draft.id,
            "patient_id": draft.patient_id,
            "shift_id": draft.shift_id,
            "update_count": draft.update_count,
            "draft_content": draft.draft_content,
            "last_updated": draft.last_updated.isoformat() if hasattr(draft.last_updated, 'isoformat') else str(draft.last_updated),
            "status": draft.status,
            # Linked Evidence (trust stack Phase 4) — surfaced from the stored
            # draft content so the review UI can render per-section pointers.
            "provenance": (draft.draft_content or {}).get("provenance")
        }

    except HTTPException:
        raise
    except Exception:
        log.exception("Error fetching draft for patient %s", patient_id)
        raise HTTPException(status_code=500, detail="Failed to fetch draft.")


# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.api:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
