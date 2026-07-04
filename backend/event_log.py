"""
Append-only event log writer (trust stack Phase 1b) with provenance
built into the schema from day one (Phase 1c).

Every agent input/output, schema-gate decision, risk-gate decision, and nurse
edit is one immutable row in the `events` table. The `provenance` column is
NOT optional decoration — it is the foundation the Phase 4 "Linked Evidence"
surface reads from: every logged output carries a pointer back to what
produced it (source update IDs and/or a transcript excerpt).

⚠️ NEEDS LIVE VERIFICATION — the `events` table is created by
backend/migrations/create_events_table.sql, which has NOT been applied to a
live Supabase project (this machine has no database connection). Until it is
applied, every write degrades to a local warning (see below) — by design the
request is never crashed by event logging.

Degradation policy:
  - No Supabase client configured  → warn once, no-op.
  - Insert fails (table missing, network, RLS) → warn per event type, no-op.
  - The local warning logs event_type/agent/stage only — NEVER payload or
    provenance content, which can contain transcript text (PHI).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

log = logging.getLogger("cascadeai.event_log")

# Canonical event types — keep in sync with the CHECK constraint in
# backend/migrations/create_events_table.sql.
EVENT_TYPES = (
    "update_received",       # raw nurse input accepted by the API
    "extraction_completed",  # UpdateAgent LLM extraction output
    "schema_gate",           # a schema-gate decision (pass / pass_after_retry / flagged)
    "verification_completed",  # EMR cross-check output
    "protocol_check",        # ProtocolAgent output
    "risk_gate",             # risk score + needs-attention decision
    "draft_generated",       # DraftGenerator output saved
    "nurse_edit",            # nurse changed content during HITL review
)

_TRANSCRIPT_EXCERPT_CHARS = 240

# Warn-once latch so a machine with no DB doesn't emit one warning per event.
_warned_no_client = False


def make_provenance(
    source_update_ids: Optional[List[str]] = None,
    transcript_excerpt: Optional[str] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """
    Build the standard provenance pointer carried by every event.

    source_update_ids: the patient_updates rows this content was derived from.
    transcript_excerpt: the first N chars of the raw transcript that produced
    it (enough to trace, not the whole recording).
    """
    prov: Dict[str, Any] = {}
    if source_update_ids:
        prov["source_update_ids"] = list(source_update_ids)
    if transcript_excerpt:
        prov["transcript_excerpt"] = str(transcript_excerpt)[:_TRANSCRIPT_EXCERPT_CHARS]
    prov.update(extra)
    return prov


def log_event(
    event_type: str,
    agent: str,
    payload: Optional[Dict[str, Any]] = None,
    *,
    shift_id: Optional[str] = None,
    patient_id: Optional[str] = None,
    update_id: Optional[str] = None,
    nurse_id: Optional[str] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Append one immutable event. Returns the event id, or None when degraded.

    NEVER raises — a failure to record an event must not fail the clinical
    request it describes. (The inverse is also deliberate: this is a log,
    not a transactional outbox; do not gate request success on it.)
    """
    global _warned_no_client

    if event_type not in EVENT_TYPES:
        # Unknown types are still logged (schema allows text) but called out,
        # so a typo shows up in review instead of vanishing.
        log.warning("event_log: unknown event_type %r (logging anyway)", event_type)

    event_id = str(uuid.uuid4())
    row = {
        "id": event_id,
        "created_at": datetime.now().astimezone().isoformat(),
        "event_type": event_type,
        "agent": agent,
        "shift_id": shift_id,
        "patient_id": patient_id,
        "update_id": update_id,
        "nurse_id": nurse_id,
        "payload": payload or {},
        "provenance": provenance or {},
    }

    try:
        # Imported lazily so a missing Supabase config degrades instead of
        # breaking module import for callers.
        from database import supabase
    except Exception:
        supabase = None

    if supabase is None:
        if not _warned_no_client:
            log.warning(
                "event_log DEGRADED: no Supabase client — events are not being "
                "persisted (they are dropped after this warning)."
            )
            _warned_no_client = True
        return None

    try:
        result = supabase.table("events").insert(row).execute()
        if result.data:
            return event_id
        log.warning("event_log: insert returned no data (type=%s agent=%s)", event_type, agent)
        return None
    except Exception as exc:
        # Deliberately terse: no payload/provenance in local logs (PHI).
        log.warning(
            "event_log DEGRADED: failed to persist event (type=%s agent=%s): %s",
            event_type, agent, type(exc).__name__,
        )
        return None
