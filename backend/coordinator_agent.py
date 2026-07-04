"""Coordinate all agents into a unified clinical handoff workflow.

⚠️ MARKED FOR RETIREMENT (trust stack Phase 2b, 2026-07).
This module is NOT part of the live API path (backend/api.py has never
imported it). Its two load-bearing pieces of logic were ported to
backend/risk_pipeline.py, which the live path now uses:
  - _calculate_overall_risk  → risk_pipeline.calculate_overall_risk
    (identical 20/40/40 weighting; weights live in clinical_rules.py)
  - _prioritize_actions      → risk_pipeline.prioritize_actions
The only remaining importer is backend/test_coordinator.py (a legacy
standalone test), which is why the file is kept rather than deleted. Do not
add new callers; when test_coordinator.py is retired, delete this file with it.
"""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()  # Load .env file

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from intake_agent import PatientIntakeAgent, IntakeAgentError, HandoffSummary
from verification_agent import VerificationAgent, VerificationAgentError, VerificationResult
from protocol_agent import ProtocolAgent, ProtocolAgentError, ProtocolResult


__all__ = [
    "CoordinatorAgentError",
    "CoordinatorResult",
    "CoordinatorAgent",
]


class CoordinatorAgentError(RuntimeError):
    """Raised when the coordinator agent encounters a critical error."""


@dataclass(slots=True)
class CoordinatorResult:
    """Complete results from coordinated multi-agent workflow."""

    handoff_summary: HandoffSummary
    verification_findings: Optional[VerificationResult] = None
    protocol_findings: Optional[ProtocolResult] = None
    overall_risk_score: float = 0.0  # 0.0-1.0 (higher = more risk)
    priority_actions: List[str] = field(default_factory=list)
    executive_summary: str = ""
    timestamp: str = ""
    errors: List[str] = field(default_factory=list)  # Non-critical errors

    def as_dict(self) -> Dict[str, Any]:
        return {
            "handoff_summary": self.handoff_summary.as_dict(),
            "verification_findings": self.verification_findings.as_dict() if self.verification_findings else None,
            "protocol_findings": self.protocol_findings.as_dict() if self.protocol_findings else None,
            "overall_risk_score": self.overall_risk_score,
            "priority_actions": self.priority_actions,
            "executive_summary": self.executive_summary,
            "timestamp": self.timestamp,
            "errors": self.errors,
        }


class CoordinatorAgent:
    """Orchestrates Intake, Verification, and Protocol agents into unified workflow."""

    def __init__(self) -> None:
        """Initialize the coordinator and all sub-agents."""
        try:
            self.intake_agent = PatientIntakeAgent()
            self.verification_agent = VerificationAgent()
            self.protocol_agent = ProtocolAgent()
        except Exception as exc:
            raise CoordinatorAgentError(
                f"Failed to initialize coordinator agents: {str(exc)}"
            ) from exc

    def _calculate_overall_risk(
        self,
        handoff_summary: HandoffSummary,
        verification_result: Optional[VerificationResult],
        protocol_result: Optional[ProtocolResult],
    ) -> float:
        """
        Calculate weighted overall risk score.
        
        Weights:
        - Handoff confidence: 20% (inverted: low confidence = high risk)
        - Verification findings: 40%
        - Protocol compliance: 40%
        """
        # Component 1: Handoff confidence (20% weight, inverted)
        # Low confidence (0.15) → high risk contribution (0.85)
        # High confidence (0.95) → low risk contribution (0.05)
        handoff_risk = (1.0 - handoff_summary.confidence) * 0.20

        # Component 2: Verification risk (40% weight)
        verification_risk = 0.0
        if verification_result:
            verification_risk = verification_result.overall_risk_score * 0.40

        # Component 3: Protocol compliance (40% weight, inverted)
        # Low compliance (0.0) → high risk (1.0)
        # High compliance (1.0) → low risk (0.0)
        protocol_risk = 0.0
        if protocol_result:
            protocol_risk = (1.0 - protocol_result.overall_compliance_score) * 0.40

        total_risk = handoff_risk + verification_risk + protocol_risk
        return round(min(total_risk, 1.0), 2)

    def _prioritize_actions(
        self,
        handoff_summary: HandoffSummary,
        verification_result: Optional[VerificationResult],
        protocol_result: Optional[ProtocolResult],
    ) -> List[str]:
        """
        Generate prioritized action list ordered by severity.
        
        Priority order: CRITICAL > HIGH > MEDIUM > LOW
        Returns top 5 actions.
        """
        actions = []

        # Add handoff confidence warning if low
        if handoff_summary.confidence < 0.50:
            actions.append(
                f"🚨 CRITICAL: Handoff confidence very low ({handoff_summary.confidence:.2f}). "
                f"Verify all information before proceeding. {handoff_summary.reasoning}"
            )

        # Add verification findings
        if verification_result:
            for finding in verification_result.findings:
                severity_emoji = {
                    "CRITICAL": "🚨",
                    "HIGH": "⚠️",
                    "MEDIUM": "⚡",
                    "LOW": "ℹ️",
                }.get(finding.severity, "•")
                
                actions.append(
                    f"{severity_emoji} {finding.severity}: {finding.type.replace('_', ' ').title()} - "
                    f"{finding.field}: {finding.reasoning[:100]}..."
                )

        # Add protocol violations
        if protocol_result:
            for finding in protocol_result.findings:
                severity_emoji = {
                    "CRITICAL": "🚨",
                    "HIGH": "⚠️",
                    "MEDIUM": "⚡",
                    "LOW": "ℹ️",
                }.get(finding.severity, "•")
                
                actions.append(
                    f"{severity_emoji} {finding.severity}: {finding.protocol_name} - "
                    f"{finding.requirement} ({finding.status}). {finding.recommendation[:100]}..."
                )

        # Sort by severity (CRITICAL first, then HIGH, MEDIUM, LOW)
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        
        def get_severity_order(action: str) -> int:
            for severity, order in severity_order.items():
                if severity in action:
                    return order
            return 99  # Unknown severity goes last

        actions.sort(key=get_severity_order)

        # Return top 5 actions
        return actions[:5]

    def _generate_executive_summary(
        self,
        handoff_summary: HandoffSummary,
        verification_result: Optional[VerificationResult],
        protocol_result: Optional[ProtocolResult],
        overall_risk: float,
    ) -> str:
        """Generate 2-3 sentence executive summary."""
        summary_parts = []

        # Sentence 1: Handoff quality
        if handoff_summary.confidence >= 0.85:
            summary_parts.append(
                f"Handoff received with HIGH confidence ({handoff_summary.confidence:.2f}). "
                f"Patient: {handoff_summary.patient_name or 'UNKNOWN'}, "
                f"Room {handoff_summary.room_number or 'UNKNOWN'}."
            )
        elif handoff_summary.confidence >= 0.50:
            summary_parts.append(
                f"Handoff received with MODERATE confidence ({handoff_summary.confidence:.2f}). "
                f"Patient: {handoff_summary.patient_name or 'UNKNOWN'}, "
                f"Room {handoff_summary.room_number or 'UNKNOWN'}. Proceed with caution."
            )
        else:
            summary_parts.append(
                f"⚠️ ALERT: Handoff has VERY LOW confidence ({handoff_summary.confidence:.2f}). "
                f"Critical information missing. Immediate verification required."
            )

        # Sentence 2: Verification status
        if verification_result:
            critical_count = sum(1 for f in verification_result.findings if f.severity == "CRITICAL")
            high_count = sum(1 for f in verification_result.findings if f.severity == "HIGH")
            
            if critical_count > 0:
                summary_parts.append(
                    f"EMR verification found {critical_count} CRITICAL and {high_count} HIGH severity "
                    f"discrepancies requiring immediate attention."
                )
            elif high_count > 0:
                summary_parts.append(
                    f"EMR verification found {high_count} HIGH priority discrepancies to address."
                )
            elif verification_result.findings:
                summary_parts.append(
                    f"EMR verification found {len(verification_result.findings)} minor discrepancies."
                )
            else:
                summary_parts.append("EMR verification: handoff data matches records.")
        else:
            summary_parts.append("EMR verification skipped (service unavailable).")

        # Sentence 3: Protocol compliance
        if protocol_result:
            if protocol_result.overall_compliance_score >= 0.90:
                summary_parts.append(
                    f"Protocol compliance: EXCELLENT ({protocol_result.overall_compliance_score:.0%}). "
                    f"All clinical protocols met."
                )
            elif protocol_result.overall_compliance_score >= 0.70:
                summary_parts.append(
                    f"Protocol compliance: GOOD ({protocol_result.overall_compliance_score:.0%}). "
                    f"Minor protocol gaps identified."
                )
            else:
                summary_parts.append(
                    f"⚠️ Protocol compliance: POOR ({protocol_result.overall_compliance_score:.0%}). "
                    f"Multiple protocol violations require immediate action."
                )
        else:
            summary_parts.append("Protocol validation skipped (service unavailable).")

        return " ".join(summary_parts)

    def process_handoff(
        self, 
        audio_or_text: str, 
        patient_id: str,
        is_audio_file: bool = False
    ) -> CoordinatorResult:
        """
        Process complete handoff through all agents.
        
        Args:
            audio_or_text: Either audio file path or text transcript
            patient_id: Patient ID for EMR lookup
            is_audio_file: True if audio_or_text is a file path, False if text
            
        Returns:
            CoordinatorResult with complete analysis and recommendations
        """
        errors: List[str] = []
        timestamp = datetime.utcnow().isoformat() + "Z"

        print("\n" + "=" * 80)
        print("  💧 CASCADEAI - MULTI-AGENT CLINICAL HANDOFF COORDINATOR")
        print("=" * 80)
        print(f"Timestamp: {timestamp}")
        print(f"Patient ID: {patient_id}")
        print(f"Input Type: {'Audio File' if is_audio_file else 'Text Transcript'}")
        print("=" * 80 + "\n")

        # ========================================
        # STEP 1: INTAKE AGENT
        # ========================================
        print("📥 STEP 1/4: Running Intake Agent...")
        try:
            if is_audio_file:
                print(f"   🎤 Transcribing audio file: {audio_or_text}")
                result_dict = self.intake_agent.process(audio_or_text)
                handoff_summary = result_dict["handoff_summary"]
            else:
                print(f"   📝 Processing text transcript ({len(audio_or_text)} chars)")
                handoff_summary = self.intake_agent.extract(audio_or_text)
            
            print(f"   ✅ Intake complete - Confidence: {handoff_summary.confidence:.2f}")
            
            # Flag low confidence but continue
            if handoff_summary.confidence < 0.50:
                warning = (
                    f"⚠️  WARNING: Handoff confidence below threshold ({handoff_summary.confidence:.2f}). "
                    f"Proceeding with HIGH RISK flag."
                )
                print(f"   {warning}")
                errors.append(warning)
            
            print(f"   Patient: {handoff_summary.patient_name or 'UNKNOWN'}")
            print(f"   Room: {handoff_summary.room_number or 'UNKNOWN'}")
            print()

        except IntakeAgentError as exc:
            # Critical failure - cannot proceed without handoff data
            raise CoordinatorAgentError(
                f"CRITICAL: Intake Agent failed. Cannot proceed without handoff data. Error: {str(exc)}"
            ) from exc
        except Exception as exc:
            raise CoordinatorAgentError(
                f"CRITICAL: Unexpected error in Intake Agent: {str(exc)}"
            ) from exc

        # ========================================
        # STEP 2: VERIFICATION AGENT
        # ========================================
        print("🔍 STEP 2/4: Running Verification Agent...")
        verification_result: Optional[VerificationResult] = None
        try:
            print(f"   📊 Fetching EMR data for patient {patient_id}")
            verification_result = self.verification_agent.verify(
                handoff_summary.as_dict(),
                patient_id
            )
            print(f"   ✅ Verification complete - Risk Score: {verification_result.overall_risk_score:.2f}")
            print(f"   Findings: {len(verification_result.findings)} discrepancies detected")
            print()

        except VerificationAgentError as exc:
            # Non-critical - log warning and continue
            warning = f"⚠️  Verification Agent failed: {str(exc)}. Continuing without EMR verification."
            print(f"   {warning}")
            errors.append(warning)
            print()
        except Exception as exc:
            warning = f"⚠️  Unexpected error in Verification Agent: {str(exc)}. Continuing anyway."
            print(f"   {warning}")
            errors.append(warning)
            print()

        # ========================================
        # STEP 3: PROTOCOL AGENT
        # ========================================
        print("📋 STEP 3/4: Running Protocol Agent...")
        protocol_result: Optional[ProtocolResult] = None
        try:
            # We need patient record for protocol checks - try to fetch it
            print(f"   🏥 Checking clinical protocol compliance")
            
            # Fetch patient record for protocol context
            try:
                patient_record = self.verification_agent._fetch_patient_record(patient_id)
                protocol_result = self.protocol_agent.check_protocols(
                    patient_record,
                    handoff_summary.as_dict()
                )
                print(f"   ✅ Protocol check complete - Compliance Score: {protocol_result.overall_compliance_score:.2f}")
                print(f"   Protocols checked: {', '.join(protocol_result.protocols_checked)}")
                print(f"   Violations: {len(protocol_result.findings)}")
                print()
            except Exception as fetch_exc:
                raise ProtocolAgentError(f"Failed to fetch patient record: {str(fetch_exc)}")

        except ProtocolAgentError as exc:
            # Non-critical - log warning and continue
            warning = f"⚠️  Protocol Agent failed: {str(exc)}. Continuing without protocol validation."
            print(f"   {warning}")
            errors.append(warning)
            print()
        except Exception as exc:
            warning = f"⚠️  Unexpected error in Protocol Agent: {str(exc)}. Continuing anyway."
            print(f"   {warning}")
            errors.append(warning)
            print()

        # ========================================
        # STEP 4: AGGREGATE AND PRIORITIZE
        # ========================================
        print("🎯 STEP 4/4: Aggregating Results and Prioritizing Actions...")
        try:
            # Calculate overall risk score
            overall_risk = self._calculate_overall_risk(
                handoff_summary,
                verification_result,
                protocol_result
            )
            print(f"   ✅ Overall Risk Score: {overall_risk:.2f}")

            # Generate priority actions
            priority_actions = self._prioritize_actions(
                handoff_summary,
                verification_result,
                protocol_result
            )
            print(f"   ✅ Priority Actions: {len(priority_actions)} identified")

            # Generate executive summary
            executive_summary = self._generate_executive_summary(
                handoff_summary,
                verification_result,
                protocol_result,
                overall_risk
            )
            print(f"   ✅ Executive Summary generated")
            print()

        except Exception as exc:
            warning = f"⚠️  Error during aggregation: {str(exc)}. Using partial results."
            print(f"   {warning}")
            errors.append(warning)
            
            # Provide fallback values
            overall_risk = handoff_summary.confidence if handoff_summary.confidence < 0.50 else 0.5
            priority_actions = [f"⚠️ Aggregation failed. Review handoff manually. Confidence: {handoff_summary.confidence:.2f}"]
            executive_summary = f"Handoff processed with errors. Confidence: {handoff_summary.confidence:.2f}. Manual review required."
            print()

        # ========================================
        # FINAL SUMMARY
        # ========================================
        print("=" * 80)
        print("  COORDINATION COMPLETE")
        print("=" * 80)
        print(f"✅ Intake Agent: SUCCESS")
        print(f"{'✅' if verification_result else '⚠️ '} Verification Agent: {'SUCCESS' if verification_result else 'FAILED'}")
        print(f"{'✅' if protocol_result else '⚠️ '} Protocol Agent: {'SUCCESS' if protocol_result else 'FAILED'}")
        print(f"\n📊 OVERALL RISK SCORE: {overall_risk:.2f}")
        print(f"🎯 PRIORITY ACTIONS: {len(priority_actions)}")
        print(f"⚠️  WARNINGS: {len(errors)}")
        print("=" * 80 + "\n")

        # Return complete result
        return CoordinatorResult(
            handoff_summary=handoff_summary,
            verification_findings=verification_result,
            protocol_findings=protocol_result,
            overall_risk_score=overall_risk,
            priority_actions=priority_actions,
            executive_summary=executive_summary,
            timestamp=timestamp,
            errors=errors,
        )
