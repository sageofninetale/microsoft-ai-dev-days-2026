"""
Data models for the continuous handoff update workflow.
Supports real-time patient updates, draft handoffs, and final handoff delivery.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from enum import Enum


class ShiftType(str, Enum):
    """Enum for shift types"""
    DAY = "day"
    NIGHT = "night"
    EVENING = "evening"


class ShiftStatus(str, Enum):
    """Enum for shift status"""
    ACTIVE = "active"
    COMPLETED = "completed"
    HANDED_OFF = "handed_off"


class UpdateType(str, Enum):
    """Enum for patient update types"""
    VITAL_SIGNS = "vital_signs"
    MEDICATION = "medication"
    PROCEDURE = "procedure"
    GENERAL = "general"
    LAB_RESULT = "lab_result"
    ASSESSMENT = "assessment"


class DraftStatus(str, Enum):
    """Enum for draft handoff status"""
    DRAFT = "draft"
    REVIEWED = "reviewed"
    SENT = "sent"


class HandoffStatus(str, Enum):
    """Enum for final handoff status"""
    SENT = "sent"
    RECEIVED = "received"
    ACKNOWLEDGED = "acknowledged"


@dataclass
class NurseShift:
    """
    Represents a nurse's shift with assigned patients.
    Tracks shift duration, assigned patients, and handoff status.
    """
    id: str
    nurse_id: str
    nurse_name: str
    shift_type: str  # day/night/evening
    shift_date: date
    start_time: datetime
    end_time: Optional[datetime] = None
    patient_ids: List[str] = field(default_factory=list)
    status: str = "active"  # active/completed/handed_off
    
    def __post_init__(self):
        """Validate shift data"""
        # Validate shift type
        valid_shift_types = ["day", "night", "evening"]
        if self.shift_type not in valid_shift_types:
            raise ValueError(f"Invalid shift_type. Must be one of: {valid_shift_types}")
        
        # Validate status
        valid_statuses = ["active", "completed", "handed_off"]
        if self.status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {valid_statuses}")
        
        # Validate end_time is after start_time if provided
        if self.end_time and self.end_time < self.start_time:
            raise ValueError("end_time must be after start_time")
        
        # Validate shift_date matches start_time date
        if self.start_time.date() != self.shift_date:
            raise ValueError("shift_date must match start_time date")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "nurse_id": self.nurse_id,
            "nurse_name": self.nurse_name,
            "shift_type": self.shift_type,
            "shift_date": self.shift_date.isoformat(),
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "patient_ids": self.patient_ids,
            "status": self.status
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> NurseShift:
        """Create NurseShift from dictionary"""
        return cls(
            id=data["id"],
            nurse_id=data["nurse_id"],
            nurse_name=data["nurse_name"],
            shift_type=data["shift_type"],
            shift_date=date.fromisoformat(data["shift_date"]),
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]) if data.get("end_time") else None,
            patient_ids=data.get("patient_ids", []),
            status=data.get("status", "active")
        )
    
    def is_active(self) -> bool:
        """Check if shift is currently active"""
        return self.status == "active"
    
    def add_patient(self, patient_id: str) -> None:
        """Add a patient to this shift"""
        if patient_id not in self.patient_ids:
            self.patient_ids.append(patient_id)
    
    def remove_patient(self, patient_id: str) -> None:
        """Remove a patient from this shift"""
        if patient_id in self.patient_ids:
            self.patient_ids.remove(patient_id)


@dataclass
class PatientUpdate:
    """
    Represents a single update about a patient during a shift.
    Can be from audio dictation or manual entry, includes EMR verification.
    """
    id: str
    shift_id: str
    patient_id: str
    nurse_id: str
    timestamp: datetime
    update_type: str  # vital_signs/medication/procedure/general
    transcription: str
    audio_url: Optional[str] = None
    extracted_data: Dict[str, Any] = field(default_factory=dict)
    emr_verified: bool = False
    verification_notes: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate update data"""
        # Validate update_type
        valid_update_types = ["vital_signs", "medication", "procedure", "general", "lab_result", "assessment"]
        if self.update_type not in valid_update_types:
            raise ValueError(f"Invalid update_type. Must be one of: {valid_update_types}")
        
        # Validate transcription is not empty
        if not self.transcription or not self.transcription.strip():
            raise ValueError("transcription cannot be empty")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "shift_id": self.shift_id,
            "patient_id": self.patient_id,
            "nurse_id": self.nurse_id,
            "timestamp": self.timestamp.isoformat(),
            "update_type": self.update_type,
            "audio_url": self.audio_url,
            "transcription": self.transcription,
            "extracted_data": self.extracted_data,
            "emr_verified": self.emr_verified,
            "verification_notes": self.verification_notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PatientUpdate:
        """Create PatientUpdate from dictionary"""
        return cls(
            id=data["id"],
            shift_id=data["shift_id"],
            patient_id=data["patient_id"],
            nurse_id=data["nurse_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            update_type=data["update_type"],
            transcription=data["transcription"],
            audio_url=data.get("audio_url"),
            extracted_data=data.get("extracted_data", {}),
            emr_verified=data.get("emr_verified", False),
            verification_notes=data.get("verification_notes", {})
        )
    
    def mark_verified(self, notes: Dict[str, Any]) -> None:
        """Mark this update as EMR verified"""
        self.emr_verified = True
        self.verification_notes = notes


@dataclass
class DraftHandoff:
    """
    Represents a continuously-updated draft handoff for a patient.
    Aggregates all updates throughout the shift into a single document.
    """
    id: str
    shift_id: str
    patient_id: str
    draft_content: Dict[str, Any]
    update_count: int = 0
    last_updated: datetime = field(default_factory=datetime.now)
    status: str = "draft"  # draft/reviewed/sent
    
    def __post_init__(self):
        """Validate draft handoff data"""
        # Validate status
        valid_statuses = ["draft", "reviewed", "sent"]
        if self.status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {valid_statuses}")
        
        # Validate update_count is non-negative
        if self.update_count < 0:
            raise ValueError("update_count cannot be negative")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "shift_id": self.shift_id,
            "patient_id": self.patient_id,
            "draft_content": self.draft_content,
            "update_count": self.update_count,
            "last_updated": self.last_updated.isoformat(),
            "status": self.status
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DraftHandoff:
        """Create DraftHandoff from dictionary"""
        return cls(
            id=data["id"],
            shift_id=data["shift_id"],
            patient_id=data["patient_id"],
            draft_content=data["draft_content"],
            update_count=data.get("update_count", 0),
            last_updated=datetime.fromisoformat(data["last_updated"]),
            status=data.get("status", "draft")
        )
    
    def add_update(self, update_data: Dict[str, Any]) -> None:
        """Add a new update to the draft"""
        self.update_count += 1
        self.last_updated = datetime.now()
        
        # Merge update data into draft_content
        # This would contain logic to intelligently merge updates
        if "updates" not in self.draft_content:
            self.draft_content["updates"] = []
        self.draft_content["updates"].append({
            "timestamp": datetime.now().isoformat(),
            "data": update_data
        })
    
    def mark_reviewed(self) -> None:
        """Mark draft as reviewed by nurse"""
        self.status = "reviewed"
        self.last_updated = datetime.now()
    
    def mark_sent(self) -> None:
        """Mark draft as sent to incoming nurse"""
        self.status = "sent"
        self.last_updated = datetime.now()


@dataclass
class FinalHandoff:
    """
    Represents the final handoff document sent to the incoming nurse.
    Includes all verification and protocol checking results.
    """
    id: str
    from_shift_id: str
    to_nurse_id: str
    patient_id: str
    handoff_content: Dict[str, Any]
    verification_results: Dict[str, Any]
    protocol_results: Dict[str, Any]
    risk_score: float
    sent_at: datetime
    status: str = "sent"  # sent/received/acknowledged
    
    def __post_init__(self):
        """Validate final handoff data"""
        # Validate status
        valid_statuses = ["sent", "received", "acknowledged"]
        if self.status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {valid_statuses}")
        
        # Validate risk_score is between 0 and 1
        if not 0 <= self.risk_score <= 1:
            raise ValueError("risk_score must be between 0 and 1")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "from_shift_id": self.from_shift_id,
            "to_nurse_id": self.to_nurse_id,
            "patient_id": self.patient_id,
            "handoff_content": self.handoff_content,
            "verification_results": self.verification_results,
            "protocol_results": self.protocol_results,
            "risk_score": self.risk_score,
            "sent_at": self.sent_at.isoformat(),
            "status": self.status
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FinalHandoff:
        """Create FinalHandoff from dictionary"""
        return cls(
            id=data["id"],
            from_shift_id=data["from_shift_id"],
            to_nurse_id=data["to_nurse_id"],
            patient_id=data["patient_id"],
            handoff_content=data["handoff_content"],
            verification_results=data["verification_results"],
            protocol_results=data["protocol_results"],
            risk_score=data["risk_score"],
            sent_at=datetime.fromisoformat(data["sent_at"]),
            status=data.get("status", "sent")
        )
    
    def mark_received(self) -> None:
        """Mark handoff as received by incoming nurse"""
        self.status = "received"
    
    def mark_acknowledged(self) -> None:
        """Mark handoff as acknowledged by incoming nurse"""
        self.status = "acknowledged"
    
    def get_risk_level(self) -> str:
        """Get risk level based on risk score"""
        if self.risk_score >= 0.7:
            return "HIGH"
        elif self.risk_score >= 0.4:
            return "MODERATE"
        else:
            return "LOW"
    
    def has_critical_findings(self) -> bool:
        """Check if there are any critical findings"""
        # Check verification results
        verification_findings = self.verification_results.get("findings", [])
        for finding in verification_findings:
            if finding.get("severity") == "CRITICAL":
                return True
        
        # Check protocol results
        protocol_findings = self.protocol_results.get("findings", [])
        for finding in protocol_findings:
            if finding.get("severity") == "CRITICAL":
                return True
        
        return False
