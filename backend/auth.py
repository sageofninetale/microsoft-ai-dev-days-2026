"""
Authentication and object-level authorization for the CascadeAI API.

Every data route in api.py depends (globally) on get_current_nurse(), which verifies
a Supabase-issued JWT passed as `Authorization: Bearer <token>`. The verified nurse
identity — never a client-supplied nurse_id — is what all downstream ownership checks
key off, which is what closes the IDOR / broken-object-level-authorization holes.

Design notes / what needs live verification:
- Supabase signs access tokens with HS256 using the project's JWT secret. Set
  SUPABASE_JWT_SECRET in the backend environment (Supabase dashboard →
  Project Settings → API → JWT Secret). Without it the API fails closed (503).
- The per-nurse patient assignment check (require_patient_assigned / start_shift)
  reads an `assignments` table that must exist and be populated in Supabase. See
  backend/migrations/enable_rls_and_ownership_policy.sql. Until that table exists and
  is seeded, assignment checks fail closed (deny) — this is intentional but means the
  workflow cannot be exercised end-to-end from a machine with no live database.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import jwt
from fastapi import Header, HTTPException, status
from supabase import Client

from database import get_active_shift, get_shift_by_id, get_nurse_assignments
from models import NurseShift

# Supabase access tokens: HS256, signed with the project JWT secret, aud="authenticated".
_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
_JWT_AUDIENCE = os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated")
_JWT_ALGORITHMS = ["HS256"]


@dataclass(frozen=True)
class AuthedNurse:
    """The authenticated principal derived from a verified JWT. Trusted; not client-supplied."""

    nurse_id: str
    name: Optional[str] = None
    subject: Optional[str] = None  # the JWT `sub` claim (Supabase user id)
    token: str = ""  # the raw bearer token, forwarded to the DB client so RLS sees this nurse


def _credentials_error(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_nurse(authorization: Optional[str] = Header(default=None)) -> AuthedNurse:
    """
    FastAPI dependency: verify the bearer token and return the authenticated nurse.

    Applied globally in api.py, so this runs (and can reject with 401) before any
    handler logic on every route.
    """
    if not _JWT_SECRET:
        # Fail closed: with no configured secret we cannot verify anything, so we must
        # not silently treat requests as authenticated.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured on the server.",
        )

    if not authorization or not authorization.lower().startswith("bearer "):
        raise _credentials_error("Missing or malformed Authorization header.")

    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = jwt.decode(
            token,
            _JWT_SECRET,
            algorithms=_JWT_ALGORITHMS,
            audience=_JWT_AUDIENCE,
        )
    except jwt.PyJWTError as exc:
        raise _credentials_error("Invalid or expired token.") from exc

    # Nurse identifier: prefer an explicit custom claim, else Supabase app_metadata,
    # else fall back to the token subject (Supabase user id).
    app_metadata = claims.get("app_metadata") or {}
    user_metadata = claims.get("user_metadata") or {}
    nurse_id = claims.get("nurse_id") or app_metadata.get("nurse_id") or claims.get("sub")
    if not nurse_id:
        raise _credentials_error("Token does not identify a nurse.")

    name = user_metadata.get("name") or app_metadata.get("nurse_name")
    return AuthedNurse(nurse_id=str(nurse_id), name=name, subject=claims.get("sub"), token=token)


# ---------------------------------------------------------------------------
# Object-level authorization helpers. Each raises 404 (never leaks existence)
# when the authenticated nurse is not entitled to the requested object.
# ---------------------------------------------------------------------------

def require_active_shift(nurse: AuthedNurse) -> NurseShift:
    """Return the nurse's own active shift, or 404 if they have none."""
    shift = get_active_shift(nurse.nurse_id)
    if not shift:
        raise HTTPException(status_code=404, detail="No active shift for this nurse.")
    return shift


def require_owned_shift(nurse: AuthedNurse, shift_id: str, client: Optional[Client] = None) -> NurseShift:
    """
    Return the shift only if it belongs to the authenticated nurse.

    Returns 404 for both "does not exist" and "not yours" so callers cannot enumerate
    other nurses' shift IDs by distinguishing the responses.
    """
    shift = get_shift_by_id(shift_id, client=client)
    if not shift or shift.nurse_id != nurse.nurse_id:
        raise HTTPException(status_code=404, detail="Shift not found.")
    return shift


def require_patient_in_shift(patient_id: str, shift: NurseShift) -> None:
    """Reject access to a patient not assigned to the given shift."""
    if patient_id not in shift.patient_ids:
        raise HTTPException(status_code=404, detail="Patient not found in this shift.")


def require_patient_assigned(nurse: AuthedNurse, patient_id: str) -> NurseShift:
    """
    For patient-scoped reads that only carry a patient_id: resolve the nurse's active
    shift and confirm the patient is assigned to it. Returns the active shift.
    """
    shift = require_active_shift(nurse)
    require_patient_in_shift(patient_id, shift)
    return shift


def filter_to_assigned(nurse: AuthedNurse, patient_ids: list[str]) -> list[str]:
    """Return the subset of patient_ids actually assigned to the nurse (per the DB)."""
    assigned = set(get_nurse_assignments(nurse.nurse_id))
    return [pid for pid in patient_ids if pid in assigned]
