"""Transcribe audio and extract structured patient handoff data."""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()  # Load .env file

import json
import os
from dataclasses import dataclass, fields
from typing import Dict, List, Optional


__all__ = [
    "IntakeAgentError",
    "HandoffSummary",
    "PatientIntakeAgent",
]


class IntakeAgentError(RuntimeError):
    """Raised when the intake agent cannot complete a request."""


@dataclass(slots=True)
class HandoffSummary:
    """Structured details extracted from a patient handoff transcript."""

    confidence: float = 0.0
    reasoning: Optional[str] = None
    patient_name: Optional[str] = None
    room_number: Optional[str] = None
    age: Optional[str] = None
    chief_complaint: Optional[str] = None
    medications: List[str] | None = None
    pending_tasks: List[str] | None = None
    vitals: Dict[str, str] | None = None
    safety_alerts: List[str] | None = None

    @classmethod
    def from_payload(cls, payload: Dict[str, object]) -> "HandoffSummary":
        allowed = {f.name for f in fields(cls)}
        filtered = {key: payload.get(key) for key in allowed}
        return cls(**filtered)

    def as_dict(self) -> Dict[str, object]:
        return {field.name: getattr(self, field.name) for field in fields(self)}


def _env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise IntakeAgentError(f"Environment variable '{name}' must be set.")
    return value


def _require_module(module: str, package_hint: str):
    try:
        return __import__(module, fromlist=["*"])
    except ImportError as exc:  # pragma: no cover - defensive branch
        raise IntakeAgentError(
            f"Missing dependency '{module}'. Install it with 'pip install {package_hint}'."
        ) from exc


class PatientIntakeAgent:
    """Helper for transcribing audio and extracting structured handoff data."""

    def __init__(
        self,
        speech_key: Optional[str] = None,
        speech_region: Optional[str] = None,
        azure_openai_endpoint: Optional[str] = None,
        azure_openai_key: Optional[str] = None,
        azure_openai_deployment: Optional[str] = None,
        azure_openai_api_version: Optional[str] = None,
    ) -> None:
        self._speechsdk = _require_module("azure.cognitiveservices.speech", "azure-cognitiveservices-speech")
        self._openai = _require_module("openai", "openai")

        self._speech_key = speech_key or _env("AZURE_SPEECH_KEY")
        self._speech_region = speech_region or _env("AZURE_SPEECH_REGION")
        self._aoai_endpoint = azure_openai_endpoint or _env("AZURE_OPENAI_ENDPOINT")
        self._aoai_key = azure_openai_key or _env("AZURE_OPENAI_KEY")
        self._aoai_deployment = azure_openai_deployment or _env("AZURE_OPENAI_DEPLOYMENT")
        self._aoai_api_version = azure_openai_api_version or os.getenv(
            "AZURE_OPENAI_API_VERSION", "2024-02-15-preview"
        )

        self._speech_config = self._speechsdk.SpeechConfig(
            subscription=self._speech_key,
            region=self._speech_region,
        )
        
        # 🎯 FIX: Improve transcription reliability for hackathon demos
        # Set longer timeouts to handle pauses and longer utterances
        self._speech_config.set_property(
            self._speechsdk.PropertyId.Speech_SegmentationSilenceTimeoutMs, "2000"  # 2 seconds of silence before stopping
        )
        self._speech_config.set_property(
            self._speechsdk.PropertyId.SpeechServiceConnection_InitialSilenceTimeoutMs, "10000"  # 10 seconds initial wait
        )
        self._speech_config.set_property(
            self._speechsdk.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs, "2000"  # 2 seconds end silence
        )

        self._aoai_client = self._openai.AzureOpenAI(
            api_key=self._aoai_key,
            azure_endpoint=self._aoai_endpoint,
            api_version=self._aoai_api_version,
        )

    def transcribe(self, audio_path: str) -> str:
        if not os.path.exists(audio_path):
            raise IntakeAgentError(f"Audio file not found: {audio_path}")

        audio_config = self._speechsdk.audio.AudioConfig(filename=audio_path)
        recognizer = self._speechsdk.SpeechRecognizer(
            speech_config=self._speech_config,
            audio_config=audio_config,
        )
        result = recognizer.recognize_once()

        if result.reason == self._speechsdk.ResultReason.RecognizedSpeech:
            return result.text
        if result.reason == self._speechsdk.ResultReason.NoMatch:
            raise IntakeAgentError(
                "Speech service could not recognize any spoken content in the provided audio."
            )
        if result.reason == self._speechsdk.ResultReason.Canceled:
            details = result.cancellation_details
            raise IntakeAgentError(
                f"Speech recognition canceled: {details.reason}. {details.error_details or ''}".strip()
            )
        raise IntakeAgentError(f"Speech recognition failed with reason: {result.reason}")

    def extract(self, transcript: str) -> HandoffSummary:
        if not transcript:
            raise IntakeAgentError("Transcript is empty; cannot extract handoff details.")

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a clinical documentation assistant applying STRICT CLINICAL SAFETY STANDARDS. "
                    "Extract patient handoff information and return ONLY valid JSON.\n\n"
                    
                    "⚠️ CRITICAL INSTRUCTION: Evaluate patient_name FIRST. If missing, score within 0.15-0.30 based on OTHER factors.\n\n"
                    
                    "CONFIDENCE SCORING RULES (Apply the LOWEST applicable level):\n\n"
                    
                    "🚨 HARD STOP - Cannot safely proceed (0.15-0.30) - PATIENT NAME MISSING:\n"
                    "Evaluate patient_name first. If missing, use these nuanced sub-ranges:\n\n"
                    
                    "  • 0.15-0.20: Missing patient_name + UNCERTAIN data\n"
                    "    - Transcript contains uncertainty markers: 'maybe', 'I think', 'approximately', 'like', '?'\n"
                    "    - Reasoning: 'Patient identity unknown AND data quality is poor with uncertainty markers. Handoff completely unusable.'\n\n"
                    
                    "  • 0.20-0.25: Missing patient_name + MULTIPLE other gaps (4+ fields missing)\n"
                    "    - Missing patient_name plus 4 or more other fields (room, age, complaint, meds, tasks, vitals, alerts)\n"
                    "    - Reasoning: 'Patient identity unknown AND multiple critical/important fields missing. Handoff unusable.'\n\n"
                    
                    "  • 0.25-0.30: Missing patient_name + OTHER data is clear/complete\n"
                    "    - Missing ONLY patient_name, but all other fields are present and clear\n"
                    "    - Reasoning: 'Patient identity cannot be verified. Despite complete other data, handoff unusable for patient safety.'\n\n"
                    
                    "❌ CRITICAL GAPS - Very high risk (0.45-0.50) - BUT TECHNICALLY USABLE:\n"
                    "When patient_name IS present but room_number OR chief_complaint is missing:\n"
                    "  • Confidence: 0.45-0.50 (use 0.48 for missing room, 0.45 for missing complaint)\n"
                    "  • KEY DISTINCTION: This is USABLE with extreme caution (unlike missing patient_name which is UNUSABLE)\n"
                    "  • Reasoning MUST include ALL of the following:\n"
                    "    1. 'Patient identified: [name]. Critical contextual gap: missing [room_number/chief_complaint].'\n"
                    "    2. 'Clinical safety impact: [explain specific risk - e.g., cannot locate patient for urgent interventions / lack of clinical context delays appropriate treatment].'\n"
                    "    3. 'Handoff is technically USABLE because patient identity is verified, but requires immediate resolution of missing information before safe care can proceed.'\n"
                    "    4. 'Confidence score (0.45-0.50) reflects high risk but does NOT make handoff completely unusable like missing patient_name would (0.15-0.30).'\n\n"
                    
                    "⚠️ IMPORTANT GAPS - Moderate risk (0.55-0.65):\n"
                    "- Missing 2 or more of: age, vitals, medications\n"
                    "- Reasoning MUST state: 'Multiple important clinical fields missing. Can proceed with caution and immediate data collection.'\n\n"
                    
                    "⚡ MINOR GAPS - Low risk (0.70-0.80):\n"
                    "- Missing only 1 of: age, vitals, medications\n"
                    "- Reasoning MUST state: 'One important field missing but can be quickly obtained.'\n\n"
                    
                    "❓ UNCERTAIN DATA (0.60-0.75) - ONLY if patient_name IS present:\n"
                    "- Fields present but contain uncertainty markers: 'maybe', 'I think', 'approximately', 'like', '?'\n"
                    "- Reasoning must explain which fields are uncertain and why\n\n"
                    
                    "✅ COMPLETE & CLEAR (0.85-0.95):\n"
                    "- All critical fields (patient_name, room_number, chief_complaint) present\n"
                    "- All or most important fields (age, vitals, medications) present\n"
                    "- Data is clear and unambiguous\n"
                    "- Reasoning MUST state: 'Comprehensive handoff with all key information clearly stated.'\n\n"
                    
                    "REASONING REQUIREMENTS:\n"
                    "1. List which critical/important fields are missing or unclear\n"
                    "2. Explain the clinical safety impact\n"
                    "3. State whether handoff is USABLE or UNUSABLE:\n"
                    "   • UNUSABLE (confidence ≤0.30): Missing patient_name - cannot verify who to treat\n"
                    "   • USABLE with extreme caution (0.40-0.50): Patient identified but missing room/complaint - high risk, immediate data collection required\n"
                    "   • USABLE with caution (0.55-0.80): Patient identified with room/complaint but missing other important data\n"
                    "   • USABLE (0.85-0.95): Complete and clear handoff\n\n"
                    
                    "JSON STRUCTURE (return exactly this):\n"
                    "{\n"
                    '  "confidence": <number 0.0-1.0>,\n'
                    '  "reasoning": "<detailed safety assessment>",\n'
                    '  "patient_name": <string or null>,\n'
                    '  "room_number": <string or null>,\n'
                    '  "age": <string or null>,\n'
                    '  "chief_complaint": <string or null>,\n'
                    '  "medications": <array of strings or null>,\n'
                    '  "pending_tasks": <array of strings or null>,\n'
                    '  "vitals": <object or null>,\n'
                    '  "safety_alerts": <array of strings or null>\n'
                    "}\n\n"
                    
                    "🎯 CRITICAL USABILITY THRESHOLD CLARIFICATION:\n"
                    "• Missing patient_name (0.15-0.30) → Handoff is UNUSABLE for safe clinical care (cannot verify who to treat)\n"
                    "• Missing room/complaint but HAS patient_name (0.45-0.50) → Handoff is USABLE with extreme caution (can proceed but requires immediate data collection)\n"
                    "• The distinction: Patient identity verification is the PRIMARY safety barrier. Without it, no care can safely proceed. With it, care can proceed cautiously even with contextual gaps.\n\n"
                    
                    "CRITICAL: Apply the LOWEST applicable confidence level. If patient_name is missing, confidence MUST be 0.15-0.30 based on other data quality."
                ),
            },
            {"role": "user", "content": transcript},
        ]

        response = self._aoai_client.chat.completions.create(
            model=self._aoai_deployment,
            # temperature=0,
            response_format={"type": "json_object"},
            messages=messages,
        )

        content = response.choices[0].message.content
        if not content:
            raise IntakeAgentError("Azure OpenAI returned an empty response.")

        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:  # pragma: no cover - guard clause
            raise IntakeAgentError("Azure OpenAI returned invalid JSON.") from exc

        return HandoffSummary.from_payload(payload)

    def process(self, audio_path: str) -> Dict[str, object]:
        transcript = self.transcribe(audio_path)
        structured = self.extract(transcript)
        return structured.as_dict()


def transcribe_and_extract(audio_path: str) -> Dict[str, object]:
    """Convenience function used by the hackathon demos."""

    return PatientIntakeAgent().process(audio_path)
