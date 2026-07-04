"""
Live-path risk pipeline (trust stack Phase 2).

Wires the previously-orphaned ProtocolAgent into the real update-processing
flow and ports the 20/40/40 risk-scoring + priority-actions logic OUT of
coordinator_agent.py (which is now marked for retirement — see its header).

Design constraints honoured here:
- ProtocolAgent's hybrid structure is preserved EXACTLY: its finding
  detection stays deterministic rule logic on structured fields; its
  _generate_reasoning/_generate_recommendation LLM calls remain presentation
  text on findings already made. This module only ADAPTS the live data shapes
  onto the handoff_summary shape check_protocols() already expects.
- All clinical scoring (NEWS2, isolated diastolic, risk weights) is
  deterministic code reading the rule tables in clinical_rules.py — never
  LLM judgment.
- Risk gate (Phase 2d): a draft whose overall risk >= RISK_ATTENTION_THRESHOLD
  is presented as "⚠ NEEDS ATTENTION" with the priority-action list, never as
  a clean report.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import clinical_rules
import schemas
from event_log import log_event, make_provenance
from protocol_agent import ProtocolAgent

log = logging.getLogger("cascadeai.risk_pipeline")

_protocol_agent: Optional[ProtocolAgent] = None


def _get_protocol_agent() -> ProtocolAgent:
    global _protocol_agent
    if _protocol_agent is None:
        _protocol_agent = ProtocolAgent()
    return _protocol_agent


# ============================================================================
# Shape adapters — live pipeline dicts → the handoff_summary shape
# ProtocolAgent.check_protocols() was built against (see intake_agent.HandoffSummary).
# ============================================================================

def _med_to_str(med: Any) -> str:
    if isinstance(med, dict):
        parts = [str(med.get(k, "")).strip() for k in ("name", "dose", "route", "frequency")]
        return " ".join(p for p in parts if p)
    return str(med)


def adapt_update_for_protocols(
    extracted_data: Dict[str, Any],
    patient_record: Dict[str, Any],
    verification_results: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Map one UpdateAgent extraction onto the ProtocolAgent input shape."""
    extracted_data = extracted_data or {}
    vitals = extracted_data.get("mentioned_vitals") or {}
    bp = vitals.get("bp") or vitals.get("blood_pressure") or ""
    issues = (verification_results or {}).get("issues") or []
    return {
        # ProtocolAgent keys ACS applicability off chief_complaint/diagnosis;
        # in the live flow the closest stable signal is the EMR diagnosis.
        "chief_complaint": str(
            patient_record.get("primary_diagnosis")
            or patient_record.get("diagnosis")
            or ""
        ),
        "medications": [_med_to_str(m) for m in extracted_data.get("mentioned_medications") or []],
        "pending_tasks": [str(e) for e in extracted_data.get("mentioned_events") or []],
        "vitals": {"blood_pressure": str(bp)} if bp else {},
        "safety_alerts": [str(i.get("finding", "")) for i in issues if isinstance(i, dict)],
    }


def adapt_draft_for_protocols(
    draft_content: Dict[str, Any],
    patient_record: Dict[str, Any],
) -> Dict[str, Any]:
    """Map a generated draft onto the ProtocolAgent input shape (draft-time gate)."""
    draft_content = draft_content or {}
    status = draft_content.get("current_status") or {}
    latest_vitals = status.get("latest_vitals") or {}
    bp_entry = latest_vitals.get("bp") or {}
    bp_value = bp_entry.get("value", "") if isinstance(bp_entry, dict) else str(bp_entry)
    alerts = draft_content.get("safety_alerts") or []
    actions = draft_content.get("pending_actions") or []
    return {
        "chief_complaint": str(
            patient_record.get("primary_diagnosis")
            or patient_record.get("diagnosis")
            or ""
        ),
        "medications": [_med_to_str(m) for m in status.get("medications") or []],
        "pending_tasks": [
            str(a.get("action", a)) if isinstance(a, dict) else str(a) for a in actions
        ],
        "vitals": {"blood_pressure": str(bp_value)} if bp_value else {},
        "safety_alerts": [
            str(a.get("message", a)) if isinstance(a, dict) else str(a) for a in alerts
        ],
    }


# ============================================================================
# Protocol check (schema-gated, event-logged)
# ============================================================================

def run_protocol_check(
    handoff_shaped: Dict[str, Any],
    patient_record: Dict[str, Any],
    *,
    shift_id: Optional[str] = None,
    patient_id: Optional[str] = None,
    update_id: Optional[str] = None,
    nurse_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Run ProtocolAgent against an adapted summary. Returns the
    ProtocolOutput-shaped dict, or None if the check itself failed (the
    caller treats None as "protocol component unavailable", mirroring the
    coordinator's non-critical handling — it never fakes a compliant result).
    """
    try:
        result = _get_protocol_agent().check_protocols(
            patient_record or {}, handoff_shaped
        ).as_dict()
    except Exception:
        log.exception("Protocol check failed — continuing without protocol component")
        return None

    # Schema gate (Phase 1a schema, wired here in Phase 2): the producer's
    # finding detection is deterministic, so no retry — a failure is a code
    # bug, flagged immediately.
    result, gate = schemas.gate_sync("protocol_check", result, schemas.ProtocolOutput)

    log_event(
        "protocol_check", "protocol_agent",
        payload={
            "protocols_checked": result.get("protocols_checked", []),
            "finding_count": len(result.get("findings", [])),
            "overall_compliance_score": result.get("overall_compliance_score"),
            "schema_gate": gate["status"],
        },
        shift_id=shift_id, patient_id=patient_id,
        update_id=update_id, nurse_id=nurse_id,
        provenance=make_provenance(
            source_update_ids=[update_id] if update_id else None,
        ),
    )
    return result


# ============================================================================
# Risk scoring — PORTED from coordinator_agent.py (Phase 2b). The 20/40/40
# weighting is unchanged; only the input shapes are the live pipeline's.
# ============================================================================

def derive_confidence(extracted_data: Dict[str, Any], draft_content: Optional[Dict[str, Any]] = None) -> float:
    """
    The coordinator's 20% component was intake HandoffSummary.confidence; the
    live pipeline has no intake agent, so confidence is derived
    DETERMINISTICALLY from the trust signals Phase 1 produces:
      start at 1.0,
      -0.5 if the extraction failed its schema gate (still flagged),
      -0.5 if suppression/prompt-injection was suspected,
      -0.3 if any draft schema gate flagged (when a draft is in scope).
    Floor 0.0. This keeps the 20/40/40 formula intact without inventing an
    LLM-judged confidence number.
    """
    confidence = 1.0
    extracted_data = extracted_data or {}
    if extracted_data.get("_schema_flagged"):
        confidence -= 0.5
    if extracted_data.get("_injection_suspected"):
        confidence -= 0.5
    if draft_content:
        gates = draft_content.get("_schema_gates") or []
        flagged = draft_content.get("_schema_flagged") or any(
            g.get("status") == "flagged" for g in gates if isinstance(g, dict)
        )
        if flagged or draft_content.get("_review_flags"):
            confidence -= 0.3
    return round(max(confidence, 0.0), 2)


def verification_risk_from_issues(issues: List[Dict[str, Any]]) -> float:
    """
    Severity-weighted verification risk, same formula as
    verification_agent._calculate_overall_risk. Live-path issues carry no
    per-finding confidence, so confidence is taken as 1.0 (a flagged issue is
    a flagged issue).
    """
    if not issues:
        return 0.0
    total = sum(
        clinical_rules.SEVERITY_WEIGHTS.get(str(i.get("severity", "MEDIUM")).upper(), 0.5)
        for i in issues if isinstance(i, dict)
    )
    return round(min(total / len(issues), 1.0), 2)


def calculate_overall_risk(
    confidence: float,
    verification_risk: Optional[float],
    protocol_compliance: Optional[float],
) -> float:
    """
    PORTED VERBATIM in weighting from CoordinatorAgent._calculate_overall_risk:
      handoff confidence 20% (inverted) +
      verification findings 40% +
      protocol compliance 40% (inverted).
    A missing component contributes 0 (same as the coordinator's behavior
    when an agent failed) — it never fabricates a good score.
    """
    handoff_risk = (1.0 - confidence) * clinical_rules.RISK_WEIGHT_CONFIDENCE
    verification_component = (verification_risk or 0.0) * clinical_rules.RISK_WEIGHT_VERIFICATION
    protocol_component = 0.0
    if protocol_compliance is not None:
        protocol_component = (1.0 - protocol_compliance) * clinical_rules.RISK_WEIGHT_PROTOCOL
    total = handoff_risk + verification_component + protocol_component
    return round(min(total, 1.0), 2)


def prioritize_actions(
    confidence: float,
    verification_issues: List[Dict[str, Any]],
    protocol_findings: List[Dict[str, Any]],
) -> List[str]:
    """
    PORTED from CoordinatorAgent._prioritize_actions: severity-ordered
    (CRITICAL > HIGH > MEDIUM > LOW), top 5, adapted to the live dict shapes.
    """
    severity_emoji = {"CRITICAL": "🚨", "HIGH": "⚠️", "MEDIUM": "⚡", "LOW": "ℹ️"}
    actions: List[str] = []

    if confidence < 0.50:
        actions.append(
            f"🚨 CRITICAL: Pipeline confidence very low ({confidence:.2f}) — "
            f"extraction was schema-flagged or suppression was suspected. "
            f"Verify all information manually before handoff."
        )

    for issue in verification_issues or []:
        if not isinstance(issue, dict):
            continue
        sev = str(issue.get("severity", "MEDIUM")).upper()
        emoji = severity_emoji.get(sev, "•")
        finding = str(issue.get("finding", issue.get("type", "verification issue")))
        actions.append(f"{emoji} {sev}: {str(issue.get('type', 'issue')).replace('_', ' ').title()} - {finding[:120]}")

    for finding in protocol_findings or []:
        if not isinstance(finding, dict):
            continue
        sev = str(finding.get("severity", "MEDIUM")).upper()
        emoji = severity_emoji.get(sev, "•")
        actions.append(
            f"{emoji} {sev}: {finding.get('protocol_name', 'Protocol')} - "
            f"{finding.get('requirement', '')} ({finding.get('status', '')}). "
            f"{str(finding.get('recommendation', ''))[:100]}"
        )

    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

    def order(action: str) -> int:
        for sev, o in severity_order.items():
            if sev in action:
                return o
        return 99

    actions.sort(key=order)
    return actions[:5]


# ============================================================================
# Deterministic NEWS2 scoring of extracted vitals (Phase 2c)
# ============================================================================

def score_vitals(mentioned_vitals: Dict[str, Any]) -> Dict[str, Any]:
    """
    Classify extracted vitals against the clinical_rules NEWS2 table +
    isolated-diastolic trigger. Pure lookup — no LLM involvement. Vitals that
    are absent or unparseable are reported as unscored, never guessed.
    """
    vitals = mentioned_vitals or {}
    out: Dict[str, Any] = {"scores": {}, "isolated_diastolic": None, "worst": None}

    systolic = diastolic = None
    bp = vitals.get("bp") or vitals.get("blood_pressure")
    if bp is not None:
        systolic, diastolic = clinical_rules.parse_bp(bp)
        if systolic is not None:
            out["scores"]["bp_sys"] = {
                "value": systolic,
                "severity": clinical_rules.classify_vital("bp_sys", systolic),
            }

    for key, aliases in (("hr", ("hr", "heart_rate")),
                         ("temp_f", ("temp", "temperature")),
                         ("spo2", ("spo2", "oxygen_saturation", "o2_sat"))):
        raw = next((vitals[a] for a in aliases if vitals.get(a) is not None), None)
        if raw is None:
            continue
        value = clinical_rules.parse_number(raw)
        if value is None:
            continue
        out["scores"][key] = {
            "value": value,
            "severity": clinical_rules.classify_vital(key, value),
        }

    # Isolated elevated diastolic — the reading plain NEWS2 cannot see.
    # Thresholds are PLACEHOLDERS pending Sakshi's clinical sign-off
    # (see clinical_rules.py).
    out["isolated_diastolic"] = clinical_rules.classify_isolated_diastolic(systolic, diastolic)

    rank = {"RED": 0, "ORANGE": 1, "YELLOW": 2, "GREEN": 3}
    scored = [s["severity"] for s in out["scores"].values() if s.get("severity")]
    out["worst"] = min(scored, key=lambda s: rank.get(s, 9)) if scored else None
    return out


# ============================================================================
# Entry points used by api.py
# ============================================================================

def assess_update(
    extracted_data: Dict[str, Any],
    patient_record: Dict[str, Any],
    verification_results: Dict[str, Any],
    *,
    shift_id: Optional[str] = None,
    patient_id: Optional[str] = None,
    update_id: Optional[str] = None,
    nurse_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Protocol + NEWS2 + 20/40/40 risk assessment for ONE processed update."""
    protocol = run_protocol_check(
        adapt_update_for_protocols(extracted_data, patient_record or {}, verification_results),
        patient_record or {},
        shift_id=shift_id, patient_id=patient_id, update_id=update_id, nurse_id=nurse_id,
    )
    issues = (verification_results or {}).get("issues") or []
    confidence = derive_confidence(extracted_data)
    verification_risk = verification_risk_from_issues(issues)
    compliance = protocol.get("overall_compliance_score") if protocol else None
    risk = calculate_overall_risk(confidence, verification_risk, compliance)

    return {
        "risk_score": risk,
        "risk_level": clinical_rules.risk_level(risk),
        "components": {
            "confidence": confidence,
            "verification_risk": verification_risk,
            "protocol_compliance": compliance,
        },
        "news2": score_vitals((extracted_data or {}).get("mentioned_vitals") or {}),
        "protocol": protocol,
        "priority_actions": prioritize_actions(
            confidence, issues, (protocol or {}).get("findings") or []
        ),
    }


def assess_draft(
    draft_content: Dict[str, Any],
    patient_record: Dict[str, Any],
    updates: List[Any],
    *,
    shift_id: Optional[str] = None,
    patient_id: Optional[str] = None,
    nurse_id: Optional[str] = None,
    draft_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Draft-time risk gate (Phase 2d). Aggregates verification issues across the
    shift's updates, runs the protocol check against the FINAL draft state,
    and decides whether the draft must be presented as "⚠ NEEDS ATTENTION".
    """
    update_ids = [getattr(u, "id", None) for u in updates or []]
    all_issues: List[Dict[str, Any]] = []
    worst_extraction_confidence = 1.0
    for u in updates or []:
        notes = getattr(u, "verification_notes", None) or {}
        all_issues.extend(i for i in (notes.get("issues") or []) if isinstance(i, dict))
        worst_extraction_confidence = min(
            worst_extraction_confidence,
            derive_confidence(getattr(u, "extracted_data", None) or {}),
        )

    protocol = run_protocol_check(
        adapt_draft_for_protocols(draft_content, patient_record or {}),
        patient_record or {},
        shift_id=shift_id, patient_id=patient_id, nurse_id=nurse_id,
    )

    # Confidence combines the worst per-update extraction signal with any
    # draft-level schema/review flags.
    confidence = min(
        worst_extraction_confidence,
        derive_confidence({}, draft_content=draft_content),
    )
    verification_risk = verification_risk_from_issues(all_issues)
    compliance = protocol.get("overall_compliance_score") if protocol else None
    risk = calculate_overall_risk(confidence, verification_risk, compliance)

    needs_attention = risk >= clinical_rules.RISK_ATTENTION_THRESHOLD

    attention = {
        "needs_attention": needs_attention,
        "banner": "⚠ NEEDS ATTENTION" if needs_attention else "REVIEWED CLEAN BY RISK GATE",
        "risk_score": risk,
        "risk_level": clinical_rules.risk_level(risk),
        "risk_threshold": clinical_rules.RISK_ATTENTION_THRESHOLD,
        "components": {
            "confidence": confidence,
            "verification_risk": verification_risk,
            "protocol_compliance": compliance,
        },
        "priority_actions": prioritize_actions(
            confidence, all_issues, (protocol or {}).get("findings") or []
        ),
        "protocol": protocol,
    }

    log_event(
        "risk_gate", "risk_pipeline",
        payload={
            "draft_id": draft_id,
            "risk_score": risk,
            "risk_level": attention["risk_level"],
            "needs_attention": needs_attention,
            "components": attention["components"],
            "priority_action_count": len(attention["priority_actions"]),
        },
        shift_id=shift_id, patient_id=patient_id, nurse_id=nurse_id,
        provenance=make_provenance(
            source_update_ids=[uid for uid in update_ids if uid],
            draft_id=draft_id,
        ),
    )
    return attention
