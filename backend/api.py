"""
FastAPI REST API server for CascadeAI - Intelligent Clinical Handoff System
Provides endpoints for shift management, patient updates, and draft generation.
"""

from __future__ import annotations
import asyncio
import os
import sys
from pathlib import Path
from datetime import date, datetime
from typing import Optional, List, Dict, Any
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
from fastapi import FastAPI, HTTPException, Body, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager

# Local imports - Agents
from update_agent import UpdateAgent
from draft_generator import DraftGenerator

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

# Local imports - Database
from database import (
    create_shift,
    get_active_shift,
    get_shift_by_id,
    get_patient,
    get_multiple_patients,
    get_patient_updates,
    get_draft
)

# Load environment variables
load_dotenv()


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
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8888",
        "http://127.0.0.1:8888",
        "https://happy-sand-07c137903.6.azurestaticapps.net",
    ],
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
    shift_type: str  # day, night, evening
    patient_ids: List[str]


class PatientUpdateRequest(BaseModel):
    # nurse_id is intentionally NOT accepted from the client — see StartShiftRequest.
    shift_id: str
    update_type: str  # medication, vital_signs, procedure, general
    text: Optional[str] = None
    audio: Optional[str] = None  # base64 encoded audio


class GenerateDraftRequest(BaseModel):
    shift_id: str


class TranscribeAudioRequest(BaseModel):
    audio: str  # base64 encoded audio
    format: str = "webm"  # audio format


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
async def transcribe_audio(request: TranscribeAudioRequest):
    """Transcribe audio using VibeVoice-ASR via Modal"""
    print(f"🎤 Transcribing audio (format: {request.format})...")

    try:
        import base64
        import tempfile
        import os
        import subprocess
        # UpdateAgent already imported at module level

        # Decode base64 audio — keep bytes in memory for Whisper fallback
        audio_bytes = base64.b64decode(request.audio)

        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{request.format}') as temp_audio:
            temp_audio.write(audio_bytes)
            temp_audio_path = temp_audio.name

        wav_path = None
        transcription = None
        try:
            # Convert to WAV if not already WAV (needed for Azure Speech SDK)
            audio_path_to_use = None
            if request.format.lower() != 'wav':
                wav_path = temp_audio_path.replace(f'.{request.format}', '.wav')

                print(f"🔄 Converting {request.format} to WAV...")

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
        finally:
            # Clean up temp files
            if os.path.exists(temp_audio_path):
                os.unlink(temp_audio_path)
            if wav_path and os.path.exists(wav_path):
                os.unlink(wav_path)

    except Exception as e:
        import traceback
        print(f"❌ Transcription error: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


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
async def get_patient_info(patient_id: str, nurse: AuthedNurse = Depends(get_current_nurse)):
    """Get basic patient information (only for a patient assigned to the caller's active shift)"""
    print(f"🔍 Fetching info for patient {patient_id}...")

    # Object-level authorization: the patient must be assigned to the caller's active shift.
    require_patient_assigned(nurse, patient_id)

    try:
        patient = get_patient(patient_id)

        if not patient:
            raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
        
        print(f"✅ Found patient: {patient.get('name')}")
        
        return {
            "patient_id": patient.get('patient_id'),
            "name": patient.get('name'),
            "age": patient.get('age'),
            "room_number": patient.get('room_number'),
            "primary_diagnosis": patient.get('primary_diagnosis')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error fetching patient: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch patient: {str(e)}")


@app.post("/api/shift/start", status_code=201)
async def start_shift(request: StartShiftRequest, nurse: AuthedNurse = Depends(get_current_nurse)):
    """Start a new shift for the authenticated nurse over their assigned patients only"""
    print(f"🏥 Starting shift...")
    print(f"   Type: {request.shift_type}")
    print(f"   Patients requested: {len(request.patient_ids)}")

    # Workflow / business-logic guard: a nurse may only open a shift over patients that
    # are actually assigned to them. Requested-but-unassigned patient_ids are dropped;
    # if that leaves nothing, refuse rather than creating an all-access shift.
    authorized_patient_ids = filter_to_assigned(nurse, request.patient_ids)
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
            shift_type=request.shift_type,
            shift_date=date.today(),
            patient_ids=authorized_patient_ids
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
        
    except Exception as e:
        print(f"❌ Error starting shift: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start shift: {str(e)}")


@app.get("/api/shift/active/{nurse_id}")
async def get_nurse_active_shift(nurse_id: str, nurse: AuthedNurse = Depends(get_current_nurse)):
    """Get the caller's own active shift (a nurse may only query their own)"""
    print(f"🔍 Fetching active shift...")

    # A nurse may only look up their own active shift, regardless of the path value.
    if nurse_id != nurse.nurse_id:
        raise HTTPException(status_code=403, detail="You may only query your own active shift.")

    try:
        shift = get_active_shift(nurse.nurse_id)
        
        if not shift:
            print(f"⚠️  No active shift found for {nurse_id}")
            return None
        
        print(f"✅ Found active shift: {shift.id}")
        
        return {
            "shift_id": shift.id,
            "nurse_id": shift.nurse_id,
            "nurse_name": shift.nurse_name,
            "shift_type": shift.shift_type,
            "patient_ids": shift.patient_ids,
            "start_time": shift.start_time.isoformat(),
            "status": shift.status
        }
        
    except Exception as e:
        print(f"❌ Error fetching active shift: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch active shift: {str(e)}")


@app.get("/api/patients/{shift_id}")
async def get_shift_patients(shift_id: str, nurse: AuthedNurse = Depends(get_current_nurse)):
    """Get all patients assigned to a shift the caller owns"""
    print(f"🔍 Fetching patients for shift {shift_id}...")

    try:
        # Object-level authorization: the shift must belong to the caller (404 otherwise).
        shift = require_owned_shift(nurse, shift_id)

        # Fetch patient details
        patients = get_multiple_patients(shift.patient_ids)
        
        print(f"✅ Found {len(patients)} patients")
        
        return patients
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error fetching patients: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch patients: {str(e)}")


@app.post("/api/patient/{patient_id}/update", status_code=201)
async def add_patient_update(
    patient_id: str,
    request: PatientUpdateRequest,
    nurse: AuthedNurse = Depends(get_current_nurse),
):
    """Add a new update for a patient in the caller's own active shift"""
    print(f"📝 Adding update for patient {patient_id}...")
    print(f"   Type: {request.update_type}")
    print(f"   Shift: {request.shift_id}")

    # Object-level authorization before any processing:
    #  - the shift must belong to the authenticated nurse (404 otherwise),
    #  - it must still be active,
    #  - and the patient must be assigned to that shift.
    shift = require_owned_shift(nurse, request.shift_id)
    if not shift.is_active():
        raise HTTPException(status_code=409, detail="Shift is not active.")
    require_patient_in_shift(patient_id, shift)

    try:
        agent = get_update_agent()

        # Determine if audio or text
        if request.audio:
            # TODO: Decode base64 audio and save to temp file
            # For now, return error
            raise HTTPException(status_code=501, detail="Audio updates not yet implemented")

        if not request.text:
            raise HTTPException(status_code=400, detail="Either 'text' or 'audio' must be provided")

        # Process the update — nurse identity comes from the verified token, not the body.
        result = agent.process_update(
            audio_or_text=request.text,
            patient_id=patient_id,
            nurse_id=nurse.nurse_id,
            shift_id=request.shift_id,
            update_type=request.update_type,
            is_audio=False
        )
        
        if not result.get("success"):
            error_msg = result.get("message", "Update processing failed")
            # Check if it's a shift ID issue
            if "database" in error_msg.lower() or "save" in error_msg.lower():
                raise HTTPException(
                    status_code=400, 
                    detail="Invalid shift ID. Please refresh the page and start a new shift."
                )
            raise HTTPException(status_code=500, detail=error_msg)
        
        print(f"✅ Update processed: {result.get('update_id')}")
        
        return {
            "success": True,
            "update_id": result.get("update_id"),
            "transcription": result.get("transcription"),
            "extracted_data": result.get("extracted_data"),
            "emr_verified": result.get("emr_verified"),
            "verification_issues": result.get("verification_issues", [])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error processing update: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process update: {str(e)}")


@app.get("/api/patient/{patient_id}/updates/{shift_id}")
async def get_patient_shift_updates(
    patient_id: str,
    shift_id: str,
    nurse: AuthedNurse = Depends(get_current_nurse),
):
    """Get all updates for a patient during a shift the caller owns"""
    print(f"🔍 Fetching updates for patient {patient_id} in shift {shift_id}...")

    # Object-level authorization: shift must be the caller's and patient must be in it.
    shift = require_owned_shift(nurse, shift_id)
    require_patient_in_shift(patient_id, shift)

    try:
        updates = get_patient_updates(patient_id, shift_id)
        
        print(f"✅ Found {len(updates)} updates")
        
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
        
    except Exception as e:
        print(f"❌ Error fetching updates: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch updates: {str(e)}")


@app.post("/api/patient/{patient_id}/draft", status_code=201)
async def generate_patient_draft(
    patient_id: str,
    request: GenerateDraftRequest,
    nurse: AuthedNurse = Depends(get_current_nurse),
):
    """Generate draft handoff for a patient in the caller's own shift"""
    print(f"📋 Generating draft for patient {patient_id}...")
    print(f"   Shift: {request.shift_id}")

    # Object-level authorization before triggering (billable) LLM calls.
    shift = require_owned_shift(nurse, request.shift_id)
    require_patient_in_shift(patient_id, shift)

    try:
        # Check if there are any updates first
        updates = get_patient_updates(patient_id, request.shift_id)
        
        if not updates or len(updates) == 0:
            raise HTTPException(
                status_code=400, 
                detail="No updates found for this patient. Please add at least one update before generating a draft."
            )
        
        generator = get_draft_generator()
        
        # Generate draft
        result = await generator.generate_draft(
            patient_id=patient_id,
            shift_id=request.shift_id
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("message", "Draft generation failed"))
        
        print(f"✅ Draft generated: {result.get('draft_id')}")
        
        return {
            "success": True,
            "draft_id": result.get("draft_id"),
            "patient_id": patient_id,
            "update_count": result.get("update_count"),
            "draft_content": result.get("draft_content")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"❌ Error generating draft: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to generate draft: {str(e)}")


@app.get("/api/patient/{patient_id}/draft/{shift_id}")
async def get_patient_draft(
    patient_id: str,
    shift_id: str,
    nurse: AuthedNurse = Depends(get_current_nurse),
):
    """Retrieve existing draft for a patient in a shift the caller owns"""
    print(f"🔍 Fetching draft for patient {patient_id} in shift {shift_id}...")

    # Object-level authorization: shift must be the caller's and patient must be in it.
    shift = require_owned_shift(nurse, shift_id)
    require_patient_in_shift(patient_id, shift)

    try:
        draft = get_draft(patient_id, shift_id)
        
        if not draft:
            print(f"⚠️  No draft found")
            return None
        
        print(f"✅ Found draft: {draft.id}")
        
        return {
            "draft_id": draft.id,
            "patient_id": draft.patient_id,
            "shift_id": draft.shift_id,
            "update_count": draft.update_count,
            "draft_content": draft.draft_content,
            "last_updated": draft.last_updated.isoformat() if hasattr(draft.last_updated, 'isoformat') else str(draft.last_updated),
            "status": draft.status
        }
        
    except Exception as e:
        print(f"❌ Error fetching draft: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch draft: {str(e)}")


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
