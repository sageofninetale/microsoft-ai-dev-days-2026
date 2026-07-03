"""
Database operations for the continuous handoff update workflow.
Handles all Supabase interactions for shifts, updates, drafts, and final handoffs.
"""

from __future__ import annotations
import logging
import os
import uuid
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from supabase import create_client, Client

from models import NurseShift, PatientUpdate, DraftHandoff, FinalHandoff

log = logging.getLogger("cascadeai.db")

# Load environment variables
load_dotenv()

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("⚠️  WARNING: SUPABASE_URL or SUPABASE_KEY not found in environment variables")
    supabase: Optional[Client] = None
else:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_client_for_token(token: Optional[str]) -> Optional[Client]:
    """
    Build a request-scoped Supabase client authenticated as the calling nurse.

    Deliberately creates a NEW client rather than mutating the shared module-level
    `supabase` client: postgrest-py's .auth(token) mutates client state in place,
    and FastAPI can interleave concurrent requests on one event loop, so sharing a
    client across requests would let one nurse's query run under another nurse's
    identity if two requests overlap.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    if token:
        client.postgrest.auth(token)
    return client


# ============================================================================
# NURSE SHIFTS
# ============================================================================

def create_shift(
    nurse_id: str,
    nurse_name: str,
    shift_type: str,
    shift_date: date,
    patient_ids: List[str]
) -> Optional[NurseShift]:
    """
    Create a new nurse shift.
    
    Args:
        nurse_id: ID of the nurse
        nurse_name: Name of the nurse
        shift_type: Type of shift (day/night/evening)
        shift_date: Date of the shift
        patient_ids: List of patient IDs assigned to this shift
    
    Returns:
        NurseShift object if successful, None otherwise
    """
    if not supabase:
        print("❌ Supabase client not initialized")
        return None
    
    try:
        shift_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        # Create NurseShift object
        shift = NurseShift(
            id=shift_id,
            nurse_id=nurse_id,
            nurse_name=nurse_name,
            shift_type=shift_type,
            shift_date=shift_date,
            start_time=start_time,
            patient_ids=patient_ids,
            status="active"
        )
        
        # Insert into database
        result = supabase.table("nurse_shifts").insert(shift.to_dict()).execute()
        
        if result.data:
            # Log the opaque shift id only — never the nurse name (PHI/staff identity).
            log.info("Created shift %s", shift_id)
            return shift
        else:
            log.warning("Failed to create shift %s", shift_id)
            return None
            
    except Exception as e:
        print(f"❌ Error creating shift: {e}")
        return None


def get_active_shift(nurse_id: str, client: Optional[Client] = None) -> Optional[NurseShift]:
    """
    Get the currently active shift for a nurse.

    Args:
        nurse_id: ID of the nurse

    Returns:
        NurseShift object if found, None otherwise
    """
    db = client or supabase
    if not db:
        print("❌ Supabase client not initialized")
        return None

    try:
        result = db.table("nurse_shifts")\
            .select("*")\
            .eq("nurse_id", nurse_id)\
            .eq("status", "active")\
            .order("start_time", desc=True)\
            .limit(1)\
            .execute()
        
        if result.data and len(result.data) > 0:
            return NurseShift.from_dict(result.data[0])
        else:
            return None
            
    except Exception as e:
        print(f"❌ Error getting active shift for nurse {nurse_id}: {e}")
        return None


def end_shift(shift_id: str) -> bool:
    """
    End a shift by setting end_time and status to completed.
    
    Args:
        shift_id: ID of the shift to end
    
    Returns:
        True if successful, False otherwise
    """
    if not supabase:
        print("❌ Supabase client not initialized")
        return False
    
    try:
        result = supabase.table("nurse_shifts")\
            .update({
                "end_time": datetime.now().isoformat(),
                "status": "completed"
            })\
            .eq("id", shift_id)\
            .execute()
        
        if result.data:
            print(f"✅ Ended shift {shift_id}")
            return True
        else:
            print(f"❌ Failed to end shift {shift_id}")
            return False
            
    except Exception as e:
        print(f"❌ Error ending shift {shift_id}: {e}")
        return False


def get_shift_by_id(shift_id: str, client: Optional[Client] = None) -> Optional[NurseShift]:
    """
    Get a shift by its ID.

    Args:
        shift_id: ID of the shift

    Returns:
        NurseShift object if found, None otherwise
    """
    db = client or supabase
    if not db:
        print("❌ Supabase client not initialized")
        return None

    try:
        result = db.table("nurse_shifts")\
            .select("*")\
            .eq("id", shift_id)\
            .execute()
        
        if result.data and len(result.data) > 0:
            return NurseShift.from_dict(result.data[0])
        else:
            return None
            
    except Exception as e:
        print(f"❌ Error getting shift {shift_id}: {e}")
        return None


# ============================================================================
# PATIENT UPDATES
# ============================================================================

def save_update(update: PatientUpdate) -> Optional[str]:
    """
    Save a patient update to the database.
    
    Args:
        update: PatientUpdate object to save
    
    Returns:
        Update ID if successful, None otherwise
    """
    if not supabase:
        print("❌ Supabase client not initialized")
        return None
    
    try:
        result = supabase.table("patient_updates").insert(update.to_dict()).execute()
        
        if result.data:
            print(f"✅ Saved update {update.id} for patient {update.patient_id}")
            return update.id
        else:
            print(f"❌ Failed to save update for patient {update.patient_id}")
            return None
            
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error saving update: {e}")
        
        # Check for foreign key violations (invalid shift_id)
        if 'foreign key constraint' in error_msg.lower() and 'shift_id' in error_msg:
            print(f"⚠️  INVALID SHIFT ID: {update.shift_id}")
            print("   This shift does not exist in the database.")
            print("   User needs to start a new shift!")
        
        return None


def get_patient_updates(patient_id: str, shift_id: str) -> List[PatientUpdate]:
    """
    Get all updates for a specific patient during a specific shift.
    
    Args:
        patient_id: ID of the patient
        shift_id: ID of the shift
    
    Returns:
        List of PatientUpdate objects
    """
    if not supabase:
        print("❌ Supabase client not initialized")
        return []
    
    try:
        result = supabase.table("patient_updates")\
            .select("*")\
            .eq("patient_id", patient_id)\
            .eq("shift_id", shift_id)\
            .order("timestamp", desc=False)\
            .execute()
        
        if result.data:
            return [PatientUpdate.from_dict(update) for update in result.data]
        else:
            return []
            
    except Exception as e:
        print(f"❌ Error getting updates for patient {patient_id}: {e}")
        return []


def get_update_by_id(update_id: str) -> Optional[PatientUpdate]:
    """
    Get a specific update by its ID.
    
    Args:
        update_id: ID of the update
    
    Returns:
        PatientUpdate object if found, None otherwise
    """
    if not supabase:
        print("❌ Supabase client not initialized")
        return None
    
    try:
        result = supabase.table("patient_updates")\
            .select("*")\
            .eq("id", update_id)\
            .execute()
        
        if result.data and len(result.data) > 0:
            return PatientUpdate.from_dict(result.data[0])
        else:
            return None
            
    except Exception as e:
        print(f"❌ Error getting update {update_id}: {e}")
        return None


def get_all_shift_updates(shift_id: str) -> List[PatientUpdate]:
    """
    Get all updates for all patients during a specific shift.
    
    Args:
        shift_id: ID of the shift
    
    Returns:
        List of PatientUpdate objects
    """
    if not supabase:
        print("❌ Supabase client not initialized")
        return []
    
    try:
        result = supabase.table("patient_updates")\
            .select("*")\
            .eq("shift_id", shift_id)\
            .order("timestamp", desc=False)\
            .execute()
        
        if result.data:
            return [PatientUpdate.from_dict(update) for update in result.data]
        else:
            return []
            
    except Exception as e:
        print(f"❌ Error getting updates for shift {shift_id}: {e}")
        return []


# ============================================================================
# DRAFT HANDOFFS
# ============================================================================

def save_draft(draft: DraftHandoff) -> Optional[str]:
    """
    Save a draft handoff to the database.
    
    Args:
        draft: DraftHandoff object to save
    
    Returns:
        Draft ID if successful, None otherwise
    """
    if not supabase:
        print("❌ Supabase client not initialized")
        return None
    
    try:
        result = supabase.table("draft_handoffs").insert(draft.to_dict()).execute()
        
        if result.data:
            print(f"✅ Saved draft {draft.id} for patient {draft.patient_id}")
            return draft.id
        else:
            print(f"❌ Failed to save draft for patient {draft.patient_id}")
            return None
            
    except Exception as e:
        print(f"❌ Error saving draft: {e}")
        return None


def get_draft(patient_id: str, shift_id: str) -> Optional[DraftHandoff]:
    """
    Get the draft handoff for a specific patient during a specific shift.
    
    Args:
        patient_id: ID of the patient
        shift_id: ID of the shift
    
    Returns:
        DraftHandoff object if found, None otherwise
    """
    if not supabase:
        print("❌ Supabase client not initialized")
        return None
    
    try:
        result = supabase.table("draft_handoffs")\
            .select("*")\
            .eq("patient_id", patient_id)\
            .eq("shift_id", shift_id)\
            .order("last_updated", desc=True)\
            .limit(1)\
            .execute()
        
        if result.data and len(result.data) > 0:
            return DraftHandoff.from_dict(result.data[0])
        else:
            return None
            
    except Exception as e:
        print(f"❌ Error getting draft for patient {patient_id}: {e}")
        return None


def update_draft(draft_id: str, draft_content: dict, update_count: int) -> bool:
    """
    Update an existing draft handoff with new content.
    
    Args:
        draft_id: ID of the draft to update
        draft_content: New draft content
        update_count: New update count
    
    Returns:
        True if successful, False otherwise
    """
    if not supabase:
        print("❌ Supabase client not initialized")
        return False
    
    try:
        result = supabase.table("draft_handoffs")\
            .update({
                "draft_content": draft_content,
                "update_count": update_count,
                "last_updated": datetime.now().isoformat()
            })\
            .eq("id", draft_id)\
            .execute()
        
        if result.data:
            print(f"✅ Updated draft {draft_id}")
            return True
        else:
            print(f"❌ Failed to update draft {draft_id}")
            return False
            
    except Exception as e:
        print(f"❌ Error updating draft {draft_id}: {e}")
        return False


def get_all_shift_drafts(shift_id: str) -> List[DraftHandoff]:
    """
    Get all draft handoffs for a specific shift.
    
    Args:
        shift_id: ID of the shift
    
    Returns:
        List of DraftHandoff objects
    """
    if not supabase:
        print("❌ Supabase client not initialized")
        return []
    
    try:
        result = supabase.table("draft_handoffs")\
            .select("*")\
            .eq("shift_id", shift_id)\
            .order("last_updated", desc=True)\
            .execute()
        
        if result.data:
            return [DraftHandoff.from_dict(draft) for draft in result.data]
        else:
            return []
            
    except Exception as e:
        print(f"❌ Error getting drafts for shift {shift_id}: {e}")
        return []


# ============================================================================
# FINAL HANDOFFS
# ============================================================================

def save_handoff(handoff: FinalHandoff) -> Optional[str]:
    """
    Save a final handoff to the database.
    
    Args:
        handoff: FinalHandoff object to save
    
    Returns:
        Handoff ID if successful, None otherwise
    """
    if not supabase:
        print("❌ Supabase client not initialized")
        return None
    
    try:
        result = supabase.table("sent_handoffs").insert(handoff.to_dict()).execute()
        
        if result.data:
            print(f"✅ Saved handoff {handoff.id} for patient {handoff.patient_id}")
            return handoff.id
        else:
            print(f"❌ Failed to save handoff for patient {handoff.patient_id}")
            return None
            
    except Exception as e:
        print(f"❌ Error saving handoff: {e}")
        return None


def get_incoming_handoffs(nurse_id: str) -> List[FinalHandoff]:
    """
    Get all incoming handoffs for a specific nurse.
    
    Args:
        nurse_id: ID of the nurse receiving handoffs
    
    Returns:
        List of FinalHandoff objects
    """
    if not supabase:
        print("❌ Supabase client not initialized")
        return []
    
    try:
        result = supabase.table("sent_handoffs")\
            .select("*")\
            .eq("to_nurse_id", nurse_id)\
            .order("sent_at", desc=True)\
            .execute()
        
        if result.data:
            return [FinalHandoff.from_dict(handoff) for handoff in result.data]
        else:
            return []
            
    except Exception as e:
        print(f"❌ Error getting incoming handoffs for nurse {nurse_id}: {e}")
        return []


def mark_handoff_received(handoff_id: str) -> bool:
    """
    Mark a handoff as received by the incoming nurse.
    
    Args:
        handoff_id: ID of the handoff
    
    Returns:
        True if successful, False otherwise
    """
    if not supabase:
        print("❌ Supabase client not initialized")
        return False
    
    try:
        result = supabase.table("sent_handoffs")\
            .update({"status": "received"})\
            .eq("id", handoff_id)\
            .execute()
        
        if result.data:
            print(f"✅ Marked handoff {handoff_id} as received")
            return True
        else:
            print(f"❌ Failed to mark handoff {handoff_id} as received")
            return False
            
    except Exception as e:
        print(f"❌ Error marking handoff {handoff_id} as received: {e}")
        return False


def get_handoff_by_id(handoff_id: str) -> Optional[FinalHandoff]:
    """
    Get a specific handoff by its ID.
    
    Args:
        handoff_id: ID of the handoff
    
    Returns:
        FinalHandoff object if found, None otherwise
    """
    if not supabase:
        print("❌ Supabase client not initialized")
        return None
    
    try:
        result = supabase.table("sent_handoffs")\
            .select("*")\
            .eq("id", handoff_id)\
            .execute()
        
        if result.data and len(result.data) > 0:
            return FinalHandoff.from_dict(result.data[0])
        else:
            return None
            
    except Exception as e:
        print(f"❌ Error getting handoff {handoff_id}: {e}")
        return None


# ============================================================================
# PATIENTS (existing table queries)
# ============================================================================

def get_patient(patient_id: str) -> Optional[dict]:
    """
    Get patient information from the existing patients table.
    
    Args:
        patient_id: ID of the patient
    
    Returns:
        Patient data as dictionary if found, None otherwise
    """
    if not supabase:
        print("❌ Supabase client not initialized")
        return None
    
    try:
        result = supabase.table("patients")\
            .select("*")\
            .eq("patient_id", patient_id)\
            .execute()
        
        if result.data and len(result.data) > 0:
            return result.data[0]
        else:
            return None
            
    except Exception as e:
        print(f"❌ Error getting patient {patient_id}: {e}")
        return None


def get_nurse_assignments(nurse_id: str) -> List[str]:
    """
    Return the list of patient_ids assigned to a nurse, read from the `assignments`
    table (nurse_id, patient_id).

    NOTE: the `assignments` table is created by
    backend/migrations/enable_rls_and_ownership_policy.sql, which must be run against
    the live Supabase project. Until it exists and is seeded, this returns [] and
    assignment checks fail closed (deny), which is the intended secure default.
    """
    if not supabase:
        print("❌ Supabase client not initialized")
        return []

    try:
        result = supabase.table("assignments")\
            .select("patient_id")\
            .eq("nurse_id", nurse_id)\
            .execute()

        if result.data:
            return [row["patient_id"] for row in result.data if row.get("patient_id")]
        return []

    except Exception as e:
        print(f"❌ Error getting assignments for nurse {nurse_id}: {e}")
        return []


def get_multiple_patients(patient_ids: List[str], client: Optional[Client] = None) -> List[dict]:
    """
    Get multiple patients from the existing patients table.

    Args:
        patient_ids: List of patient IDs

    Returns:
        List of patient data dictionaries
    """
    db = client or supabase
    if not db:
        print("❌ Supabase client not initialized")
        return []

    try:
        result = db.table("patients")\
            .select("*")\
            .in_("patient_id", patient_ids)\
            .order("patient_id")\
            .execute()
        
        if result.data:
            return result.data
        else:
            return []
            
    except Exception as e:
        print(f"❌ Error getting multiple patients: {e}")
        return []
