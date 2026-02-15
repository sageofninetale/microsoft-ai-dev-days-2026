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
                    "You are a clinical documentation assistant. Return ONLY valid JSON with these keys: patient_name (string), room_number (string), age (string, not number), chief_complaint (string), medications (array of strings), pending_tasks (array of strings), vitals (object), safety_alerts (array of strings). Use null when information is missing."
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
