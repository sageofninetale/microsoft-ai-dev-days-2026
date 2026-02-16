"""Verify handoff summaries against EMR data in Supabase."""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()  # Load .env file

import json
import os
from dataclasses import dataclass, field, fields
from typing import Any, Dict, List, Optional


__all__ = [
    "VerificationAgentError",
    "Finding",
    "VerificationResult",
    "VerificationAgent",
]


class VerificationAgentError(RuntimeError):
    """Raised when the verification agent cannot complete a request."""


@dataclass(slots=True)
class Finding:
    """A discrepancy or issue found during verification."""

    type: str  # e.g., "medication_discrepancy", "missing_allergy", "name_mismatch"
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    confidence: float  # 0.0-1.0
    field: str  # which field has the issue
    handoff_value: Any  # what the handoff said
    emr_value: Any  # what the EMR says
    reasoning: str  # AI-generated explanation

    def as_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "severity": self.severity,
            "confidence": self.confidence,
            "field": self.field,
            "handoff_value": self.handoff_value,
            "emr_value": self.emr_value,
            "reasoning": self.reasoning,
        }


@dataclass(slots=True)
class VerificationResult:
    """Results from verifying a handoff against EMR data."""

    findings: List[Finding] = field(default_factory=list)
    overall_risk_score: float = 0.0  # 0.0-1.0 (higher = more risk)
    summary: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "findings": [f.as_dict() for f in self.findings],
            "overall_risk_score": self.overall_risk_score,
            "summary": self.summary,
        }


def _env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise VerificationAgentError(f"Environment variable '{name}' must be set.")
    return value


def _require_module(module: str, package_hint: str):
    try:
        return __import__(module, fromlist=["*"])
    except ImportError as exc:  # pragma: no cover - defensive branch
        raise VerificationAgentError(
            f"Missing dependency '{module}'. Install it with 'pip install {package_hint}'."
        ) from exc


class VerificationAgent:
    """Verifies handoff summaries against patient EMR data."""

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        azure_openai_endpoint: Optional[str] = None,
        azure_openai_key: Optional[str] = None,
        azure_openai_deployment: Optional[str] = None,
        azure_openai_api_version: Optional[str] = None,
    ) -> None:
        self._supabase_module = _require_module("supabase", "supabase")
        self._openai = _require_module("openai", "openai")

        # Supabase configuration
        self._supabase_url = supabase_url or _env("SUPABASE_URL")
        self._supabase_key = supabase_key or _env("SUPABASE_KEY")
        self._supabase_client = self._supabase_module.create_client(
            self._supabase_url,
            self._supabase_key
        )

        # Azure OpenAI configuration
        self._aoai_endpoint = azure_openai_endpoint or _env("AZURE_OPENAI_ENDPOINT")
        self._aoai_key = azure_openai_key or _env("AZURE_OPENAI_KEY")
        self._aoai_deployment = azure_openai_deployment or _env("AZURE_OPENAI_DEPLOYMENT")
        self._aoai_api_version = azure_openai_api_version or os.getenv(
            "AZURE_OPENAI_API_VERSION", "2024-02-15-preview"
        )

        self._aoai_client = self._openai.AzureOpenAI(
            api_key=self._aoai_key,
            azure_endpoint=self._aoai_endpoint,
            api_version=self._aoai_api_version,
        )

    def _fetch_patient_record(self, patient_id: str) -> Dict[str, Any]:
        """Fetch patient record from Supabase."""
        try:
            response = self._supabase_client.table("patients").select("*").eq("patient_id", patient_id).execute()
            
            if not response.data or len(response.data) == 0:
                raise VerificationAgentError(f"Patient record not found for ID: {patient_id}")
            
            return response.data[0]
        except Exception as exc:
            if isinstance(exc, VerificationAgentError):
                raise
            raise VerificationAgentError(f"Failed to fetch patient record: {str(exc)}") from exc

    def _generate_reasoning(self, finding_context: Dict[str, Any]) -> str:
        """Use Azure OpenAI to generate intelligent reasoning for a finding."""
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a clinical safety verification assistant. "
                    "Generate a concise, clinically-relevant explanation for the discrepancy found. "
                    "Focus on patient safety implications. Keep it under 100 words."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(finding_context, indent=2),
            },
        ]

        try:
            response = self._aoai_client.chat.completions.create(
                model=self._aoai_deployment,
                messages=messages,
                max_completion_tokens=150,
            )
            
            content = response.choices[0].message.content
            return content.strip() if content else "No reasoning available."
        except Exception as exc:
            return f"Unable to generate reasoning: {str(exc)}"

    def _check_name_match(self, handoff_name: Optional[str], emr_name: str) -> Optional[Finding]:
        """Check if patient names match."""
        if not handoff_name:
            context = {
                "issue": "Patient name missing in handoff",
                "handoff_value": None,
                "emr_value": emr_name,
                "safety_impact": "Wrong-patient risk - cannot verify identity",
            }
            reasoning = self._generate_reasoning(context)
            return Finding(
                type="name_missing",
                severity="CRITICAL",
                confidence=1.0,
                field="patient_name",
                handoff_value=None,
                emr_value=emr_name,
                reasoning=reasoning,
            )

        # Normalize names for comparison (case-insensitive, remove extra spaces)
        handoff_normalized = " ".join(handoff_name.strip().lower().split())
        emr_normalized = " ".join(emr_name.strip().lower().split())

        if handoff_normalized != emr_normalized:
            context = {
                "issue": "Patient name mismatch",
                "handoff_value": handoff_name,
                "emr_value": emr_name,
                "safety_impact": "Potential wrong-patient error",
            }
            reasoning = self._generate_reasoning(context)
            return Finding(
                type="name_mismatch",
                severity="CRITICAL",
                confidence=0.95,
                field="patient_name",
                handoff_value=handoff_name,
                emr_value=emr_name,
                reasoning=reasoning,
            )

        return None

    def _check_age_match(self, handoff_age: Optional[str], emr_age: int) -> Optional[Finding]:
        """Check if ages match (allow ±2 years tolerance)."""
        if not handoff_age:
            return None  # Missing age is handled by intake agent confidence scoring

        try:
            # Extract numeric age from handoff (handle formats like "67 years", "67", "67-year-old")
            handoff_age_str = handoff_age.strip().split()[0]
            handoff_age_num = int(handoff_age_str)

            age_diff = abs(handoff_age_num - emr_age)
            if age_diff > 2:
                context = {
                    "issue": "Age discrepancy exceeds tolerance",
                    "handoff_value": handoff_age,
                    "emr_value": emr_age,
                    "difference": age_diff,
                    "safety_impact": "May indicate wrong patient or outdated information",
                }
                reasoning = self._generate_reasoning(context)
                
                # Severity based on magnitude of difference
                if age_diff > 10:
                    severity = "CRITICAL"
                    confidence = 0.95
                elif age_diff > 5:
                    severity = "HIGH"
                    confidence = 0.85
                else:
                    severity = "MEDIUM"
                    confidence = 0.75

                return Finding(
                    type="age_discrepancy",
                    severity=severity,
                    confidence=confidence,
                    field="age",
                    handoff_value=handoff_age,
                    emr_value=emr_age,
                    reasoning=reasoning,
                )
        except (ValueError, IndexError):
            # Unable to parse age - report as uncertain
            context = {
                "issue": "Unable to parse age from handoff",
                "handoff_value": handoff_age,
                "emr_value": emr_age,
                "safety_impact": "Age verification failed",
            }
            reasoning = self._generate_reasoning(context)
            return Finding(
                type="age_parse_error",
                severity="MEDIUM",
                confidence=0.60,
                field="age",
                handoff_value=handoff_age,
                emr_value=emr_age,
                reasoning=reasoning,
            )

        return None

    def _check_room_match(self, handoff_room: Optional[str], emr_room: str) -> Optional[Finding]:
        """Check if room numbers match."""
        if not handoff_room:
            return None  # Missing room is handled by intake agent confidence scoring

        # Normalize room numbers (remove spaces, "Room", "rm", etc.)
        handoff_normalized = handoff_room.strip().lower().replace("room", "").replace("rm", "").strip()
        emr_normalized = emr_room.strip().lower().replace("room", "").replace("rm", "").strip()

        if handoff_normalized != emr_normalized:
            context = {
                "issue": "Room number mismatch",
                "handoff_value": handoff_room,
                "emr_value": emr_room,
                "safety_impact": "Staff may go to wrong location, delaying urgent care",
            }
            reasoning = self._generate_reasoning(context)
            return Finding(
                type="room_mismatch",
                severity="HIGH",
                confidence=0.90,
                field="room_number",
                handoff_value=handoff_room,
                emr_value=emr_room,
                reasoning=reasoning,
            )

        return None

    def _check_medications(
        self, handoff_meds: Optional[List[str]], emr_meds: List[Dict[str, str]]
    ) -> List[Finding]:
        """Check for medication discrepancies."""
        findings = []

        if not handoff_meds:
            # No medications mentioned in handoff - check if EMR has any
            if emr_meds:
                context = {
                    "issue": "Medications not mentioned in handoff",
                    "handoff_value": None,
                    "emr_value": [med["name"] for med in emr_meds],
                    "safety_impact": "Risk of medication errors or missed doses",
                }
                reasoning = self._generate_reasoning(context)
                findings.append(
                    Finding(
                        type="medications_missing_in_handoff",
                        severity="HIGH",
                        confidence=0.85,
                        field="medications",
                        handoff_value=None,
                        emr_value=[med["name"] for med in emr_meds],
                        reasoning=reasoning,
                    )
                )
            return findings

        # Build normalized med names from EMR
        emr_med_names = {med["name"].strip().lower() for med in emr_meds}
        handoff_med_names = {med.split()[0].strip().lower() for med in handoff_meds}  # Extract drug name

        # Check for medications in EMR not mentioned in handoff
        missing_in_handoff = emr_med_names - handoff_med_names
        if missing_in_handoff:
            context = {
                "issue": "EMR medications not mentioned in handoff",
                "missing_medications": list(missing_in_handoff),
                "handoff_value": handoff_meds,
                "emr_value": [med["name"] for med in emr_meds],
                "safety_impact": "Risk of missed doses or drug interactions",
            }
            reasoning = self._generate_reasoning(context)
            findings.append(
                Finding(
                    type="medication_discrepancy",
                    severity="HIGH",
                    confidence=0.80,
                    field="medications",
                    handoff_value=handoff_meds,
                    emr_value=[med["name"] for med in emr_meds if med["name"].strip().lower() in missing_in_handoff],
                    reasoning=reasoning,
                )
            )

        # Check for medications in handoff not in EMR (could be new orders or errors)
        extra_in_handoff = handoff_med_names - emr_med_names
        if extra_in_handoff:
            context = {
                "issue": "Handoff mentions medications not in EMR",
                "extra_medications": list(extra_in_handoff),
                "handoff_value": handoff_meds,
                "emr_value": [med["name"] for med in emr_meds],
                "safety_impact": "May be new orders not yet documented or incorrect medications",
            }
            reasoning = self._generate_reasoning(context)
            findings.append(
                Finding(
                    type="medication_not_in_emr",
                    severity="MEDIUM",
                    confidence=0.70,
                    field="medications",
                    handoff_value=[med for med in handoff_meds if med.split()[0].strip().lower() in extra_in_handoff],
                    emr_value=[med["name"] for med in emr_meds],
                    reasoning=reasoning,
                )
            )

        return findings

    def _check_allergies(
        self, handoff_summary: Dict[str, Any], emr_allergies: List[str]
    ) -> List[Finding]:
        """Check if allergies are missing from handoff (critical safety issue)."""
        findings = []

        if not emr_allergies:
            return findings  # No allergies in EMR to check

        # Handoff doesn't have an explicit allergies field - check safety_alerts
        safety_alerts = handoff_summary.get("safety_alerts") or []
        
        # Check if any EMR allergies are mentioned in safety alerts
        missing_allergies = []
        for allergy in emr_allergies:
            allergy_mentioned = any(
                allergy.lower() in alert.lower() 
                for alert in safety_alerts
            )
            if not allergy_mentioned:
                missing_allergies.append(allergy)

        if missing_allergies:
            context = {
                "issue": "Critical allergies not mentioned in handoff",
                "missing_allergies": missing_allergies,
                "emr_value": emr_allergies,
                "safety_impact": "Risk of administering allergen - potential anaphylaxis",
            }
            reasoning = self._generate_reasoning(context)
            findings.append(
                Finding(
                    type="missing_allergy",
                    severity="CRITICAL",
                    confidence=0.95,
                    field="safety_alerts",
                    handoff_value=safety_alerts,
                    emr_value=emr_allergies,
                    reasoning=reasoning,
                )
            )

        return findings

    def _check_vitals(
        self, handoff_vitals: Optional[Dict[str, str]], emr_vitals: Dict[str, Any]
    ) -> List[Finding]:
        """Check for vital signs abnormalities or discrepancies."""
        findings = []

        if not handoff_vitals:
            return findings  # Missing vitals handled by intake agent

        # Define normal ranges for adult vitals
        normal_ranges = {
            "systolic_bp": (90, 140),
            "diastolic_bp": (60, 90),
            "heart_rate": (60, 100),
            "respiratory_rate": (12, 20),
            "temperature_f": (97.0, 99.5),
            "oxygen_saturation": (95, 100),
        }

        # Check for abnormal values in handoff
        for vital_key, (low, high) in normal_ranges.items():
            if vital_key in handoff_vitals:
                try:
                    # Extract numeric value (handle formats like "160/95", "88 bpm", "98.6 F")
                    vital_str = str(handoff_vitals[vital_key])
                    
                    # Special handling for blood pressure
                    if "bp" in vital_key and "/" in vital_str:
                        systolic, diastolic = vital_str.split("/")
                        if "systolic" in vital_key:
                            value = float(systolic.strip().split()[0])
                        else:
                            value = float(diastolic.strip().split()[0])
                    else:
                        # Extract first numeric value
                        value = float(''.join(c for c in vital_str.split()[0] if c.isdigit() or c == '.'))

                    if value < low or value > high:
                        severity = "HIGH" if (value < low * 0.8 or value > high * 1.2) else "MEDIUM"
                        context = {
                            "issue": f"Abnormal {vital_key.replace('_', ' ')}",
                            "value": value,
                            "normal_range": f"{low}-{high}",
                            "handoff_value": vital_str,
                            "safety_impact": "May require immediate intervention",
                        }
                        reasoning = self._generate_reasoning(context)
                        findings.append(
                            Finding(
                                type="vital_abnormal",
                                severity=severity,
                                confidence=0.85,
                                field=f"vitals.{vital_key}",
                                handoff_value=vital_str,
                                emr_value=f"Normal range: {low}-{high}",
                                reasoning=reasoning,
                            )
                        )
                except (ValueError, IndexError):
                    continue  # Skip if unable to parse

        return findings

    def _calculate_overall_risk(self, findings: List[Finding]) -> float:
        """Calculate overall risk score based on findings."""
        if not findings:
            return 0.0

        # Weight findings by severity
        severity_weights = {
            "CRITICAL": 1.0,
            "HIGH": 0.7,
            "MEDIUM": 0.4,
            "LOW": 0.2,
        }

        total_risk = 0.0
        for finding in findings:
            weight = severity_weights.get(finding.severity, 0.5)
            total_risk += weight * finding.confidence

        # Normalize to 0.0-1.0 range (cap at 1.0)
        return min(total_risk / len(findings), 1.0)

    def _generate_summary(self, findings: List[Finding], overall_risk: float) -> str:
        """Generate a summary of verification results."""
        if not findings:
            return "✅ No discrepancies found. Handoff data matches EMR records."

        critical = sum(1 for f in findings if f.severity == "CRITICAL")
        high = sum(1 for f in findings if f.severity == "HIGH")
        medium = sum(1 for f in findings if f.severity == "MEDIUM")
        low = sum(1 for f in findings if f.severity == "LOW")

        summary_parts = [
            f"⚠️ {len(findings)} discrepancies found (Risk score: {overall_risk:.2f}):"
        ]

        if critical:
            summary_parts.append(f"  • {critical} CRITICAL issues requiring immediate attention")
        if high:
            summary_parts.append(f"  • {high} HIGH priority issues")
        if medium:
            summary_parts.append(f"  • {medium} MEDIUM priority issues")
        if low:
            summary_parts.append(f"  • {low} LOW priority issues")

        return "\n".join(summary_parts)

    def verify(self, handoff_summary: Dict[str, Any], patient_id: str) -> VerificationResult:
        """
        Verify handoff summary against EMR data.
        
        Args:
            handoff_summary: HandoffSummary as dict (from intake agent)
            patient_id: Patient ID to look up in Supabase
            
        Returns:
            VerificationResult with findings, risk score, and summary
        """
        # Fetch patient record from Supabase
        emr_record = self._fetch_patient_record(patient_id)

        findings: List[Finding] = []

        # 1. Check name match
        name_finding = self._check_name_match(
            handoff_summary.get("patient_name"),
            emr_record.get("name", "")
        )
        if name_finding:
            findings.append(name_finding)

        # 2. Check age match
        age_finding = self._check_age_match(
            handoff_summary.get("age"),
            emr_record.get("age", 0)
        )
        if age_finding:
            findings.append(age_finding)

        # 3. Check room match
        room_finding = self._check_room_match(
            handoff_summary.get("room_number"),
            emr_record.get("room_number", "")
        )
        if room_finding:
            findings.append(room_finding)

        # 4. Check medications
        med_findings = self._check_medications(
            handoff_summary.get("medications"),
            emr_record.get("medications", [])
        )
        findings.extend(med_findings)

        # 5. Check allergies
        allergy_findings = self._check_allergies(
            handoff_summary,
            emr_record.get("allergies", [])
        )
        findings.extend(allergy_findings)

        # 6. Check vitals for abnormalities
        vital_findings = self._check_vitals(
            handoff_summary.get("vitals"),
            emr_record.get("vitals", {})
        )
        findings.extend(vital_findings)

        # Calculate overall risk score
        overall_risk = self._calculate_overall_risk(findings)

        # Generate summary
        summary = self._generate_summary(findings, overall_risk)

        return VerificationResult(
            findings=findings,
            overall_risk_score=overall_risk,
            summary=summary,
        )
