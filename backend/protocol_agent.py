"""Check clinical protocol compliance for patient care."""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()  # Load .env file

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from llm_client import ask_llm


__all__ = [
    "ProtocolAgentError",
    "ProtocolFinding",
    "ProtocolResult",
    "ProtocolAgent",
]


class ProtocolAgentError(RuntimeError):
    """Raised when the protocol agent cannot complete a request."""


@dataclass(slots=True)
class ProtocolFinding:
    """A protocol compliance finding or violation."""

    protocol_name: str  # e.g., "ACS Protocol", "Fall Risk Protocol"
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    confidence: float  # 0.0-1.0
    requirement: str  # what should be done
    status: str  # "MISSING", "INCOMPLETE", "COMPLIANT"
    reasoning: str  # AI-generated clinical explanation
    recommendation: str  # actionable next step

    def as_dict(self) -> Dict[str, Any]:
        return {
            "protocol_name": self.protocol_name,
            "severity": self.severity,
            "confidence": self.confidence,
            "requirement": self.requirement,
            "status": self.status,
            "reasoning": self.reasoning,
            "recommendation": self.recommendation,
        }


@dataclass(slots=True)
class ProtocolResult:
    """Results from checking clinical protocol compliance."""

    findings: List[ProtocolFinding] = field(default_factory=list)
    protocols_checked: List[str] = field(default_factory=list)
    overall_compliance_score: float = 0.0  # 0.0-1.0 (higher = better compliance)
    summary: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "findings": [f.as_dict() for f in self.findings],
            "protocols_checked": self.protocols_checked,
            "overall_compliance_score": self.overall_compliance_score,
            "summary": self.summary,
        }


def _env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ProtocolAgentError(f"Environment variable '{name}' must be set.")
    return value


def _require_module(module: str, package_hint: str):
    try:
        return __import__(module, fromlist=["*"])
    except ImportError as exc:  # pragma: no cover - defensive branch
        raise ProtocolAgentError(
            f"Missing dependency '{module}'. Install it with 'pip install {package_hint}'."
        ) from exc


class ProtocolAgent:
    """Checks clinical protocol compliance for patient care."""

    def __init__(self) -> None:
        pass

    def _generate_reasoning(self, protocol_context: Dict[str, Any]) -> str:
        """Use LLM to generate intelligent clinical reasoning for a protocol finding."""
        system_prompt = (
            "You are a clinical protocol compliance assistant. "
            "Generate a concise, evidence-based explanation for why this protocol requirement matters. "
            "Focus on patient safety and clinical best practices. Keep it under 80 words. "
            'Respond as a JSON object of the form {"reasoning": "<your explanation>"}.'
        )
        user_prompt = json.dumps(protocol_context, indent=2)

        # ask_llm() raises on failure (rate limit, API error, malformed JSON).
        # We deliberately catch it HERE, not inside the adapter — this is a
        # per-finding explanation, not the finding itself (that's computed by
        # local rule logic above). A failure here shouldn't blow up the whole
        # protocol check; it produces an explicit, visible degraded string
        # rather than a value that could be mistaken for a real explanation.
        try:
            result = ask_llm(system_prompt, user_prompt)
            reasoning = result.get("reasoning")
            return reasoning.strip() if reasoning else "No reasoning available."
        except Exception as exc:
            return f"Unable to generate reasoning: {str(exc)}"

    def _generate_recommendation(self, protocol_context: Dict[str, Any]) -> str:
        """Use LLM to generate actionable recommendation."""
        system_prompt = (
            "You are a clinical protocol compliance assistant. "
            "Generate a specific, actionable recommendation to address this protocol gap. "
            "Be direct and concise. Keep it under 50 words. "
            'Respond as a JSON object of the form {"recommendation": "<your recommendation>"}.'
        )
        user_prompt = json.dumps(protocol_context, indent=2)

        try:
            result = ask_llm(system_prompt, user_prompt)
            recommendation = result.get("recommendation")
            return recommendation.strip() if recommendation else "No recommendation available."
        except Exception as exc:
            return f"Unable to generate recommendation: {str(exc)}"

    def _check_acs_protocol(
        self, patient_record: Dict[str, Any], handoff_summary: Dict[str, Any]
    ) -> List[ProtocolFinding]:
        """Check Acute Coronary Syndrome (ACS) Protocol compliance."""
        findings = []

        # Check if ACS protocol applies
        chief_complaint = handoff_summary.get("chief_complaint", "").lower()
        diagnosis = patient_record.get("diagnosis", "").lower()
        
        acs_triggers = ["chest pain", "acute coronary syndrome", "acs", "myocardial infarction", "mi", "stemi", "nstemi"]
        protocol_applies = any(trigger in chief_complaint or trigger in diagnosis for trigger in acs_triggers)

        if not protocol_applies:
            return findings  # Protocol doesn't apply to this patient

        # Protocol applies - check requirements
        medications = handoff_summary.get("medications") or []
        pending_tasks = handoff_summary.get("pending_tasks") or []
        
        # Requirement 1: Aspirin administered
        aspirin_given = any("aspirin" in med.lower() for med in medications)
        if not aspirin_given:
            context = {
                "protocol": "ACS Protocol",
                "requirement": "Aspirin administration",
                "status": "MISSING",
                "patient_condition": chief_complaint or diagnosis,
                "safety_impact": "Delayed antiplatelet therapy increases risk of myocardial damage",
            }
            reasoning = self._generate_reasoning(context)
            recommendation = self._generate_recommendation(context)
            
            findings.append(
                ProtocolFinding(
                    protocol_name="ACS Protocol",
                    severity="CRITICAL",
                    confidence=0.95,
                    requirement="Aspirin administered (162-325mg chewed)",
                    status="MISSING",
                    reasoning=reasoning,
                    recommendation=recommendation,
                )
            )

        # Requirement 2: Cardiac enzymes ordered
        cardiac_enzymes_ordered = any(
            "troponin" in task.lower() or "cardiac enzyme" in task.lower()
            for task in pending_tasks
        )
        if not cardiac_enzymes_ordered:
            context = {
                "protocol": "ACS Protocol",
                "requirement": "Cardiac enzyme labs (troponin)",
                "status": "MISSING",
                "patient_condition": chief_complaint or diagnosis,
                "safety_impact": "Cannot confirm myocardial injury without troponin levels",
            }
            reasoning = self._generate_reasoning(context)
            recommendation = self._generate_recommendation(context)
            
            findings.append(
                ProtocolFinding(
                    protocol_name="ACS Protocol",
                    severity="CRITICAL",
                    confidence=0.90,
                    requirement="Cardiac enzyme labs ordered (troponin)",
                    status="MISSING",
                    reasoning=reasoning,
                    recommendation=recommendation,
                )
            )

        # Requirement 3: Cardiology consult requested
        cardiology_consult = any(
            "cardiology" in task.lower() or "cardiologist" in task.lower()
            for task in pending_tasks
        )
        if not cardiology_consult:
            context = {
                "protocol": "ACS Protocol",
                "requirement": "Cardiology consult",
                "status": "MISSING",
                "patient_condition": chief_complaint or diagnosis,
                "safety_impact": "Specialist evaluation needed for treatment plan",
            }
            reasoning = self._generate_reasoning(context)
            recommendation = self._generate_recommendation(context)
            
            findings.append(
                ProtocolFinding(
                    protocol_name="ACS Protocol",
                    severity="HIGH",
                    confidence=0.85,
                    requirement="Cardiology consult requested",
                    status="MISSING",
                    reasoning=reasoning,
                    recommendation=recommendation,
                )
            )

        return findings

    def _check_fall_risk_protocol(
        self, patient_record: Dict[str, Any], handoff_summary: Dict[str, Any]
    ) -> List[ProtocolFinding]:
        """Check Fall Risk Protocol compliance."""
        findings = []

        # Check if fall risk protocol applies
        fall_risk_score = patient_record.get("fall_risk_score", 0)
        
        if fall_risk_score < 5:
            return findings  # Protocol doesn't apply

        # Protocol applies - check requirements
        safety_alerts = handoff_summary.get("safety_alerts") or []
        
        # Requirement 1: Bed alarm activated
        bed_alarm_active = any(
            "bed alarm" in alert.lower() or "alarm activated" in alert.lower()
            for alert in safety_alerts
        )
        if not bed_alarm_active:
            context = {
                "protocol": "Fall Risk Protocol",
                "requirement": "Bed alarm activation",
                "status": "MISSING",
                "fall_risk_score": fall_risk_score,
                "safety_impact": "High-risk patient not protected from unassisted mobility",
            }
            reasoning = self._generate_reasoning(context)
            recommendation = self._generate_recommendation(context)
            
            findings.append(
                ProtocolFinding(
                    protocol_name="Fall Risk Protocol",
                    severity="HIGH",
                    confidence=0.90,
                    requirement="Bed alarm activated for high fall risk",
                    status="MISSING",
                    reasoning=reasoning,
                    recommendation=recommendation,
                )
            )

        # Requirement 2: Fall risk assessment documented
        fall_risk_documented = any(
            "fall risk" in alert.lower() for alert in safety_alerts
        )
        if not fall_risk_documented:
            context = {
                "protocol": "Fall Risk Protocol",
                "requirement": "Fall risk assessment documentation",
                "status": "MISSING",
                "fall_risk_score": fall_risk_score,
                "safety_impact": "Receiving team unaware of fall risk level",
            }
            reasoning = self._generate_reasoning(context)
            recommendation = self._generate_recommendation(context)
            
            findings.append(
                ProtocolFinding(
                    protocol_name="Fall Risk Protocol",
                    severity="MEDIUM",
                    confidence=0.80,
                    requirement="Fall risk assessment documented in handoff",
                    status="MISSING",
                    reasoning=reasoning,
                    recommendation=recommendation,
                )
            )

        return findings

    def _check_hypertension_protocol(
        self, patient_record: Dict[str, Any], handoff_summary: Dict[str, Any]
    ) -> List[ProtocolFinding]:
        """Check Hypertension Protocol compliance."""
        findings = []

        # Check if hypertension protocol applies
        vitals = handoff_summary.get("vitals") or {}
        
        # Extract blood pressure
        bp_str = vitals.get("blood_pressure", "")
        if not bp_str or "/" not in bp_str:
            return findings  # No BP data available

        try:
            # Parse BP (format: "145/92" or "145/92 mmHg")
            bp_parts = bp_str.split("/")
            systolic = int(''.join(c for c in bp_parts[0] if c.isdigit()))
            diastolic = int(''.join(c for c in bp_parts[1].split()[0] if c.isdigit()))
        except (ValueError, IndexError):
            return findings  # Unable to parse BP

        # Check if protocol applies (BP >= 140/90)
        if systolic < 140 and diastolic < 90:
            return findings  # Normal BP, protocol doesn't apply

        # Protocol applies - check requirements
        medications = handoff_summary.get("medications") or []
        
        # Requirement 1: Anti-hypertensive medication prescribed
        antihypertensive_meds = [
            "metoprolol", "lisinopril", "amlodipine", "losartan", "hydrochlorothiazide",
            "atenolol", "carvedilol", "enalapril", "valsartan", "diltiazem"
        ]
        
        has_antihypertensive = any(
            any(med_name in medication.lower() for med_name in antihypertensive_meds)
            for medication in medications
        )
        
        if not has_antihypertensive:
            severity = "CRITICAL" if systolic >= 180 or diastolic >= 110 else "HIGH"
            context = {
                "protocol": "Hypertension Protocol",
                "requirement": "Anti-hypertensive medication",
                "status": "MISSING",
                "blood_pressure": f"{systolic}/{diastolic}",
                "safety_impact": "Uncontrolled hypertension increases stroke and cardiac event risk",
            }
            reasoning = self._generate_reasoning(context)
            recommendation = self._generate_recommendation(context)
            
            findings.append(
                ProtocolFinding(
                    protocol_name="Hypertension Protocol",
                    severity=severity,
                    confidence=0.85,
                    requirement="Anti-hypertensive medication prescribed",
                    status="MISSING",
                    reasoning=reasoning,
                    recommendation=recommendation,
                )
            )

        # Requirement 2: Immediate physician notification for hypertensive crisis (BP >= 180/110)
        if systolic >= 180 or diastolic >= 110:
            pending_tasks = handoff_summary.get("pending_tasks") or []
            physician_notified = any(
                "physician" in task.lower() or "doctor" in task.lower() or "md notified" in task.lower()
                for task in pending_tasks
            )
            
            if not physician_notified:
                context = {
                    "protocol": "Hypertension Protocol - Crisis",
                    "requirement": "Immediate physician notification",
                    "status": "MISSING",
                    "blood_pressure": f"{systolic}/{diastolic}",
                    "safety_impact": "Hypertensive crisis requires immediate intervention to prevent end-organ damage",
                }
                reasoning = self._generate_reasoning(context)
                recommendation = self._generate_recommendation(context)
                
                findings.append(
                    ProtocolFinding(
                        protocol_name="Hypertension Protocol",
                        severity="CRITICAL",
                        confidence=0.95,
                        requirement=f"Immediate physician notification for hypertensive crisis (BP {systolic}/{diastolic})",
                        status="MISSING",
                        reasoning=reasoning,
                        recommendation=recommendation,
                    )
                )

        return findings

    def _calculate_compliance_score(self, findings: List[ProtocolFinding]) -> float:
        """Calculate overall protocol compliance score (0.0-1.0, higher is better)."""
        if not findings:
            return 1.0  # Perfect compliance if no violations found

        # Weight violations by severity
        severity_weights = {
            "CRITICAL": 1.0,
            "HIGH": 0.7,
            "MEDIUM": 0.4,
            "LOW": 0.2,
        }

        total_deduction = 0.0
        for finding in findings:
            if finding.status in ["MISSING", "INCOMPLETE"]:
                weight = severity_weights.get(finding.severity, 0.5)
                total_deduction += weight * finding.confidence

        # Normalize and invert (more deductions = lower score)
        compliance_score = max(0.0, 1.0 - (total_deduction / len(findings)))
        return round(compliance_score, 2)

    def _generate_summary(
        self, findings: List[ProtocolFinding], protocols_checked: List[str], compliance_score: float
    ) -> str:
        """Generate a summary of protocol check results."""
        if not findings:
            return f"✅ All {len(protocols_checked)} protocol(s) fully compliant. Compliance score: {compliance_score:.2f}"

        critical = sum(1 for f in findings if f.severity == "CRITICAL")
        high = sum(1 for f in findings if f.severity == "HIGH")
        medium = sum(1 for f in findings if f.severity == "MEDIUM")
        low = sum(1 for f in findings if f.severity == "LOW")

        summary_parts = [
            f"⚠️ {len(findings)} protocol violation(s) found (Compliance score: {compliance_score:.2f}):"
        ]

        if critical:
            summary_parts.append(f"  • {critical} CRITICAL violations requiring immediate action")
        if high:
            summary_parts.append(f"  • {high} HIGH priority violations")
        if medium:
            summary_parts.append(f"  • {medium} MEDIUM priority violations")
        if low:
            summary_parts.append(f"  • {low} LOW priority violations")

        summary_parts.append(f"\n📋 Protocols checked: {', '.join(protocols_checked)}")

        return "\n".join(summary_parts)

    def check_protocols(
        self, patient_record: Dict[str, Any], handoff_summary: Dict[str, Any]
    ) -> ProtocolResult:
        """
        Check clinical protocol compliance for a patient.
        
        Args:
            patient_record: Patient EMR data from database
            handoff_summary: HandoffSummary as dict (from intake agent)
            
        Returns:
            ProtocolResult with findings, protocols checked, compliance score, and summary
        """
        findings: List[ProtocolFinding] = []
        protocols_checked: List[str] = []

        # Check ACS Protocol
        acs_findings = self._check_acs_protocol(patient_record, handoff_summary)
        if acs_findings or any(
            trigger in str(handoff_summary.get("chief_complaint", "")).lower() or 
            trigger in str(patient_record.get("diagnosis", "")).lower()
            for trigger in ["chest pain", "acs", "myocardial"]
        ):
            protocols_checked.append("ACS Protocol")
            findings.extend(acs_findings)

        # Check Fall Risk Protocol
        fall_findings = self._check_fall_risk_protocol(patient_record, handoff_summary)
        if fall_findings or patient_record.get("fall_risk_score", 0) >= 5:
            protocols_checked.append("Fall Risk Protocol")
            findings.extend(fall_findings)

        # Check Hypertension Protocol
        hypertension_findings = self._check_hypertension_protocol(patient_record, handoff_summary)
        vitals = handoff_summary.get("vitals") or {}
        bp_str = vitals.get("blood_pressure", "")
        if hypertension_findings or (bp_str and "/" in bp_str):
            protocols_checked.append("Hypertension Protocol")
            findings.extend(hypertension_findings)

        # Calculate compliance score
        compliance_score = self._calculate_compliance_score(findings)

        # Generate summary
        summary = self._generate_summary(findings, protocols_checked, compliance_score)

        return ProtocolResult(
            findings=findings,
            protocols_checked=protocols_checked,
            overall_compliance_score=compliance_score,
            summary=summary,
        )
