"""
Inter-agent handoff schema gates (trust stack Phase 1a).

Every hop between agents in the live pipeline now passes through an explicit
Pydantic validation gate:

    UpdateAgent extraction  → ExtractedUpdate
    EMR/verification check  → VerificationOutput
    ProtocolAgent output    → ProtocolOutput
    DraftGenerator output   → ClinicalStatusOutput / TimelineOutput /
                              NarrativeOutput, merged → DraftContent

Gate policy — "block, retry once, then flag":
  1. BLOCK: malformed output is never passed downstream as-if-valid.
  2. RETRY ONCE: for LLM-produced payloads the caller re-invokes the producing
     call exactly once (LLM output is non-deterministic enough that a clean
     second attempt is common; more than one retry just hides a broken prompt).
  3. FLAG: if still malformed, the payload is annotated (`_schema_flagged`,
     `_schema_errors`) and the gate decision is recorded — it proceeds only as
     visibly-suspect data that the risk gate and the nurse review UI surface.
     It must NEVER be silently normalized into something that looks clean.

These gates cover INTER-AGENT boundaries only. API request/response validation
is already handled by the FastAPI/Pydantic request models in api.py — do not
duplicate that here.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

log = logging.getLogger("cascadeai.schemas")


# ============================================================================
# 1. UpdateAgent extraction output
# ============================================================================

class ExtractedUpdate(BaseModel):
    """Shape of UpdateAgent._extract_update_data() output (LLM-produced)."""

    # extra="allow" keeps defence-in-depth annotations (_injection_suspected,
    # _review_reason) and any harmless extra keys the model returns.
    model_config = ConfigDict(extra="allow")

    event_type: Literal[
        "medication", "vital_signs", "procedure", "lab_result", "assessment", "general"
    ]
    description: str = Field(min_length=1)
    timestamp: Optional[str] = None
    mentioned_medications: List[Any] = Field(default_factory=list)
    mentioned_vitals: Dict[str, Any] = Field(default_factory=dict)
    mentioned_events: List[Any] = Field(default_factory=list)

    @field_validator("mentioned_medications", "mentioned_events", mode="before")
    @classmethod
    def _none_to_list(cls, v):
        return [] if v is None else v

    @field_validator("mentioned_vitals", mode="before")
    @classmethod
    def _none_to_dict(cls, v):
        return {} if v is None else v

    @field_validator("timestamp", mode="before")
    @classmethod
    def _timestamp_to_str(cls, v):
        return str(v) if v is not None else None


# ============================================================================
# 2. EMR / verification check output
# ============================================================================

class VerificationIssue(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    finding: str
    details: Optional[str] = None


class VerificationOutput(BaseModel):
    """Shape of UpdateAgent._verify_update() output (deterministic producer)."""

    model_config = ConfigDict(extra="allow")

    emr_verified: bool
    issues: List[VerificationIssue]
    checked_at: str


# ============================================================================
# 3. ProtocolAgent output
# ============================================================================

class ProtocolFindingSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    protocol_name: str
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    confidence: float = Field(ge=0.0, le=1.0)
    requirement: str
    status: Literal["MISSING", "INCOMPLETE", "COMPLIANT"]
    reasoning: str
    recommendation: str


class ProtocolOutput(BaseModel):
    """Shape of ProtocolAgent.check_protocols().as_dict()."""

    model_config = ConfigDict(extra="allow")

    findings: List[ProtocolFindingSchema]
    protocols_checked: List[str]
    overall_compliance_score: float = Field(ge=0.0, le=1.0)
    summary: str


# ============================================================================
# 4. DraftGenerator outputs (three LLM calls + merged draft)
# ============================================================================

class TimelineEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    time: str
    event: str = Field(min_length=1)
    severity: Literal["RED", "ORANGE", "YELLOW", "GREEN", "BLUE", "GRAY"]
    icon: Optional[str] = None


class TimelineOutput(BaseModel):
    timeline: List[TimelineEvent]


class SafetyAlert(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    severity: Literal["RED", "ORANGE", "YELLOW"]
    message: str = Field(min_length=1)


class PendingAction(BaseModel):
    model_config = ConfigDict(extra="allow")

    action: str = Field(min_length=1)
    category: Literal["CRITICAL", "HIGH", "ROUTINE"]


class CurrentStatus(BaseModel):
    """
    The keys whose silent absence caused the P045 bug: a truncated LLM response
    used to fall back to empty/placeholder Safety Alerts, Pending Actions and
    Vitals while Timeline/Narrative still rendered — an easy-to-miss failure.
    Requiring these keys structurally means a truncated response FAILS the gate
    (→ retry → flag) instead of quietly rendering as a clean-looking report.
    """

    model_config = ConfigDict(extra="allow")

    medications: List[Dict[str, Any]]
    latest_vitals: Dict[str, Any]
    overall_condition: str = Field(min_length=1)


class ClinicalStatusOutput(BaseModel):
    """Shape of DraftGenerator._generate_clinical_status_async() output."""

    model_config = ConfigDict(extra="allow")

    current_status: CurrentStatus
    safety_alerts: List[SafetyAlert]
    key_changes: List[Dict[str, Any]]
    pending_actions: List[PendingAction]

    @field_validator("safety_alerts", "key_changes", "pending_actions", mode="before")
    @classmethod
    def _none_to_list(cls, v):
        return [] if v is None else v


class NarrativeOutput(BaseModel):
    """Shape of DraftGenerator._generate_narrative_async() raw LLM output."""

    model_config = ConfigDict(extra="allow")

    narrative_summary: str = Field(min_length=1)


class DraftContent(BaseModel):
    """Final merged draft_content — the object saved and shown to the nurse."""

    model_config = ConfigDict(extra="allow")

    timeline: List[TimelineEvent]
    current_status: CurrentStatus
    safety_alerts: List[SafetyAlert]
    key_changes: List[Dict[str, Any]]
    pending_actions: List[PendingAction]
    narrative_summary: str = Field(min_length=1)


# ============================================================================
# Gate helpers
# ============================================================================

def check(stage: str, payload: Any, model: type[BaseModel]) -> Tuple[bool, List[str]]:
    """
    Validate a payload against a schema. Returns (ok, errors).
    Never raises — a gate must not crash the request it is guarding.
    """
    if not isinstance(payload, dict):
        return False, [f"{stage}: expected a JSON object, got {type(payload).__name__}"]
    try:
        model.model_validate(payload)
        return True, []
    except ValidationError as exc:
        errors = [
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
        ]
        return False, errors
    except Exception as exc:  # defensive: schema bug must not take down the pipeline
        return False, [f"{stage}: gate error: {exc}"]


def flag(payload: Any, stage: str, errors: List[str]) -> Dict[str, Any]:
    """
    Annotate a payload that failed its gate after the one allowed retry.
    Non-dict payloads are wrapped so the flag can be carried. The flags are
    load-bearing: the risk gate (risk_pipeline.py) and the eval graders key
    off `_schema_flagged` — do not strip them downstream.
    """
    if not isinstance(payload, dict):
        payload = {"_raw": payload}
    payload["_schema_flagged"] = True
    payload["_schema_stage"] = stage
    payload["_schema_errors"] = errors[:10]  # cap: enough to debug, no log flooding
    log.warning("Schema gate FLAGGED stage=%s (%d error(s))", stage, len(errors))
    return payload


def gate_sync(
    stage: str,
    payload: Any,
    model: type[BaseModel],
    retry: Optional[Callable[[], Any]] = None,
) -> Tuple[Any, Dict[str, Any]]:
    """
    Full block→retry-once→flag gate for synchronous producers.

    Returns (payload, gate_record). gate_record.status is one of
    "pass" | "pass_after_retry" | "flagged" and is what gets written to the
    event log as the gate decision. Async producers (draft_generator) drive
    check()/flag() directly because their retry needs an await.
    """
    ok, errors = check(stage, payload, model)
    if ok:
        return payload, {"stage": stage, "status": "pass", "attempts": 1, "errors": []}

    log.warning("Schema gate BLOCKED stage=%s, retrying once: %s", stage, errors[:3])
    if retry is not None:
        try:
            payload = retry()
        except Exception as exc:
            return (
                flag(payload, stage, errors + [f"retry raised: {exc}"]),
                {"stage": stage, "status": "flagged", "attempts": 2,
                 "errors": errors + [f"retry raised: {exc}"]},
            )
        ok, retry_errors = check(stage, payload, model)
        if ok:
            return payload, {
                "stage": stage, "status": "pass_after_retry", "attempts": 2,
                "errors": errors,
            }
        errors = retry_errors

    return (
        flag(payload, stage, errors),
        {"stage": stage, "status": "flagged", "attempts": 2 if retry else 1,
         "errors": errors},
    )
