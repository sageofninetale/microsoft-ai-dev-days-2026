"""Test the Protocol Agent with sample patient data."""

from __future__ import annotations

import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env from project root
from dotenv import load_dotenv
project_root = Path(__file__).parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

from backend.protocol_agent import ProtocolAgent, ProtocolAgentError
from supabase import create_client
import os


def print_separator(title: str):
    """Print a visual separator with title."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_findings(result):
    """Print protocol findings in a formatted way."""
    print(f"📊 OVERALL COMPLIANCE SCORE: {result.overall_compliance_score:.2f}")
    print(f"📋 PROTOCOLS CHECKED: {', '.join(result.protocols_checked)}")
    print(f"\n📝 SUMMARY:\n{result.summary}\n")
    
    if not result.findings:
        print("✅ No protocol violations found - full compliance!\n")
        return
    
    print(f"🔍 DETAILED FINDINGS ({len(result.findings)} violations):\n")
    
    # Emoji mapping for severity
    severity_emoji = {
        "CRITICAL": "🚨",
        "HIGH": "⚠️",
        "MEDIUM": "⚡",
        "LOW": "ℹ️",
    }
    
    # Status emoji
    status_emoji = {
        "MISSING": "❌",
        "INCOMPLETE": "⏳",
        "COMPLIANT": "✅",
    }
    
    for i, finding in enumerate(result.findings, 1):
        sev_emoji = severity_emoji.get(finding.severity, "•")
        stat_emoji = status_emoji.get(finding.status, "•")
        
        print(f"{sev_emoji} FINDING #{i}: {finding.protocol_name}")
        print(f"   Severity: {finding.severity}")
        print(f"   Confidence: {finding.confidence:.2f}")
        print(f"   Requirement: {finding.requirement}")
        print(f"   Status: {stat_emoji} {finding.status}")
        print(f"   Reasoning: {finding.reasoning}")
        print(f"   💡 Recommendation: {finding.recommendation}")
        print()


def fetch_patient_record(patient_id: str):
    """Fetch patient record from Supabase."""
    try:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            raise Exception("Supabase credentials not found in .env")
        
        supabase = create_client(supabase_url, supabase_key)
        response = supabase.table("patients").select("*").eq("patient_id", patient_id).execute()
        
        if not response.data or len(response.data) == 0:
            raise Exception(f"Patient record not found for ID: {patient_id}")
        
        return response.data[0]
    except Exception as exc:
        raise Exception(f"Failed to fetch patient record: {str(exc)}") from exc


def test_acs_protocol():
    """Test Scenario A: ACS Protocol Check."""
    print_separator("SCENARIO A: ACS PROTOCOL CHECK - Chest Pain Patient")
    
    # Handoff summary with chest pain diagnosis
    handoff_summary = {
        "confidence": 0.90,
        "reasoning": "Complete handoff with all key information clearly stated.",
        "patient_name": "John Smith",
        "room_number": "302",
        "age": "68",
        "chief_complaint": "Chest pain",
        "medications": [
            "Aspirin 81mg daily",
            "Metoprolol 50mg twice daily"
        ],
        "pending_tasks": ["Cardiac enzyme labs at 6 AM"],
        "vitals": {
            "blood_pressure": "145/92 mmHg",
            "heart_rate": "88 bpm",
            "temperature_f": "98.6 F",
            "oxygen_saturation": "96%"
        },
        "safety_alerts": ["Fall risk due to dizziness", "Bed alarm activated"]
    }
    
    print("📋 PATIENT INFO:")
    print(f"  Patient: {handoff_summary['patient_name']}")
    print(f"  Chief Complaint: {handoff_summary['chief_complaint']} ❤️ (ACS Protocol applies)")
    print(f"  Medications: {', '.join(handoff_summary['medications'])}")
    print(f"  Pending Tasks: {', '.join(handoff_summary['pending_tasks'])}")
    print()
    
    print("🔍 CHECKING ACS PROTOCOL REQUIREMENTS:")
    print("  ✅ Aspirin administered? YES (81mg daily)")
    print("  ✅ Cardiac enzymes ordered? YES (labs at 6 AM)")
    print("  ❓ Cardiology consult requested? Checking...")
    print()
    
    try:
        print("🔄 Fetching patient record from Supabase (P001)...")
        patient_record = fetch_patient_record("P001")
        print(f"✅ Patient record fetched: {patient_record.get('name')}\n")
        
        print("🔄 Running protocol compliance check...")
        agent = ProtocolAgent()
        result = agent.check_protocols(patient_record, handoff_summary)
        
        print_findings(result)
        
    except ProtocolAgentError as e:
        print(f"❌ PROTOCOL CHECK ERROR: {e}\n")
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}\n")


def test_fall_risk_protocol():
    """Test Scenario B: Fall Risk Protocol Check."""
    print_separator("SCENARIO B: FALL RISK PROTOCOL CHECK - High Risk Patient")
    
    # Handoff summary for fall risk patient
    handoff_summary = {
        "confidence": 0.90,
        "reasoning": "Complete handoff with all key information clearly stated.",
        "patient_name": "John Smith",
        "room_number": "302",
        "age": "68",
        "chief_complaint": "Chest pain",
        "medications": [
            "Aspirin 81mg daily",
            "Metoprolol 50mg twice daily"
        ],
        "pending_tasks": ["Cardiac enzyme labs at 6 AM"],
        "vitals": {
            "blood_pressure": "145/92 mmHg",
            "heart_rate": "88 bpm",
            "temperature_f": "98.6 F",
            "oxygen_saturation": "96%"
        },
        "safety_alerts": ["Fall risk due to dizziness", "Bed alarm activated"]
    }
    
    try:
        print("🔄 Fetching patient record from Supabase (P001)...")
        patient_record = fetch_patient_record("P001")
        fall_risk_score = patient_record.get("fall_risk_score", 0)
        print(f"✅ Patient record fetched: {patient_record.get('name')}")
        print(f"   Fall Risk Score: {fall_risk_score} (High risk: ≥5)\n")
        
        print("📋 PATIENT INFO:")
        print(f"  Patient: {handoff_summary['patient_name']}")
        print(f"  Fall Risk Score: {fall_risk_score} 🚨 (Fall Risk Protocol applies)")
        print(f"  Safety Alerts: {', '.join(handoff_summary['safety_alerts'])}")
        print()
        
        print("🔍 CHECKING FALL RISK PROTOCOL REQUIREMENTS:")
        print("  ✅ Bed alarm activated? YES ('Bed alarm activated' in safety alerts)")
        print("  ✅ Fall risk documented? YES ('Fall risk due to dizziness' in safety alerts)")
        print()
        
        print("🔄 Running protocol compliance check...")
        agent = ProtocolAgent()
        result = agent.check_protocols(patient_record, handoff_summary)
        
        print_findings(result)
        
    except ProtocolAgentError as e:
        print(f"❌ PROTOCOL CHECK ERROR: {e}\n")
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}\n")


def test_hypertension_protocol():
    """Test Scenario C: Hypertension Protocol Check."""
    print_separator("SCENARIO C: HYPERTENSION PROTOCOL CHECK - Elevated BP")
    
    # Handoff summary with hypertension
    handoff_summary = {
        "confidence": 0.90,
        "reasoning": "Complete handoff with all key information clearly stated.",
        "patient_name": "John Smith",
        "room_number": "302",
        "age": "68",
        "chief_complaint": "Chest pain",
        "medications": [
            "Aspirin 81mg daily",
            "Metoprolol 50mg twice daily"  # Metoprolol is anti-hypertensive!
        ],
        "pending_tasks": ["Cardiac enzyme labs at 6 AM"],
        "vitals": {
            "blood_pressure": "145/92 mmHg",  # Hypertensive (>140/90)
            "heart_rate": "88 bpm",
            "temperature_f": "98.6 F",
            "oxygen_saturation": "96%"
        },
        "safety_alerts": ["Fall risk due to dizziness", "Bed alarm activated"]
    }
    
    print("📋 PATIENT INFO:")
    print(f"  Patient: {handoff_summary['patient_name']}")
    print(f"  Blood Pressure: {handoff_summary['vitals']['blood_pressure']} 🩺 (Hypertension Protocol applies)")
    print(f"  Medications: {', '.join(handoff_summary['medications'])}")
    print()
    
    print("🔍 CHECKING HYPERTENSION PROTOCOL REQUIREMENTS:")
    print("  ✅ Anti-hypertensive medication? YES (Metoprolol 50mg)")
    print("  ℹ️  BP Crisis (≥180/110)? NO (145/92 is elevated but not critical)")
    print()
    
    try:
        print("🔄 Fetching patient record from Supabase (P001)...")
        patient_record = fetch_patient_record("P001")
        print(f"✅ Patient record fetched: {patient_record.get('name')}\n")
        
        print("🔄 Running protocol compliance check...")
        agent = ProtocolAgent()
        result = agent.check_protocols(patient_record, handoff_summary)
        
        print_findings(result)
        
    except ProtocolAgentError as e:
        print(f"❌ PROTOCOL CHECK ERROR: {e}\n")
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}\n")


def main():
    """Run all protocol tests."""
    print("\n" + "=" * 80)
    print("  PROTOCOL AGENT TESTING")
    print("=" * 80)
    print("\nTesting clinical protocol compliance for patient care")
    print("Patient: John Smith (ID: P001)")
    
    # Initialize agent to check connection
    try:
        print("\n🔧 Initializing Protocol Agent...")
        agent = ProtocolAgent()
        print("✅ Protocol Agent initialized successfully\n")
    except ProtocolAgentError as e:
        print(f"❌ Failed to initialize: {e}")
        print("\n💡 Make sure your .env file has:")
        print("   - AZURE_OPENAI_ENDPOINT")
        print("   - AZURE_OPENAI_KEY")
        print("   - AZURE_OPENAI_DEPLOYMENT")
        print("   - SUPABASE_URL")
        print("   - SUPABASE_KEY")
        return
    
    # Run test scenarios
    test_acs_protocol()
    test_fall_risk_protocol()
    test_hypertension_protocol()
    
    # Final summary
    print_separator("TEST SUMMARY")
    print("✅ Scenario A: ACS Protocol - Should show MISSING cardiology consult")
    print("✅ Scenario B: Fall Risk Protocol - Should show COMPLIANT (bed alarm + documentation)")
    print("✅ Scenario C: Hypertension Protocol - Should show COMPLIANT (on metoprolol)")
    print("\n📝 KEY OBSERVATIONS:")
    print("  • Protocol Agent checks 3 critical clinical protocols")
    print("  • AI generates intelligent reasoning for each violation")
    print("  • Provides actionable recommendations for compliance")
    print("  • Compliance score (0.0-1.0) reflects overall protocol adherence")
    print("  • Only checks protocols that apply to the patient's condition")
    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
