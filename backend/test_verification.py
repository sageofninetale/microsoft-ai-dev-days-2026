"""Test the Verification Agent with sample patient data."""

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

from backend.verification_agent import VerificationAgent, VerificationAgentError


def print_separator(title: str):
    """Print a visual separator with title."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_findings(findings, overall_risk: float, summary: str):
    """Print verification findings in a formatted way."""
    print(f"📊 OVERALL RISK SCORE: {overall_risk:.2f}")
    print(f"📝 SUMMARY:\n{summary}\n")
    
    if not findings:
        print("✅ No discrepancies found - handoff matches EMR perfectly!\n")
        return
    
    print(f"🔍 DETAILED FINDINGS ({len(findings)} issues):\n")
    
    # Emoji mapping for severity
    severity_emoji = {
        "CRITICAL": "🚨",
        "HIGH": "⚠️",
        "MEDIUM": "⚡",
        "LOW": "ℹ️",
    }
    
    for i, finding in enumerate(findings, 1):
        emoji = severity_emoji.get(finding.severity, "•")
        print(f"{emoji} FINDING #{i}: {finding.type}")
        print(f"   Severity: {finding.severity}")
        print(f"   Confidence: {finding.confidence:.2f}")
        print(f"   Field: {finding.field}")
        print(f"   Handoff Value: {finding.handoff_value}")
        print(f"   EMR Value: {finding.emr_value}")
        print(f"   Reasoning: {finding.reasoning}")
        print()


def test_scenario_a_correct_handoff():
    """Test Scenario A: Correct handoff that matches EMR exactly."""
    print_separator("SCENARIO A: CORRECT HANDOFF - Should Match EMR")
    
    # Create a handoff summary that MATCHES the Supabase EMR for patient P001
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
    
    print("📋 HANDOFF SUMMARY:")
    print(f"  Patient: {handoff_summary['patient_name']}")
    print(f"  Room: {handoff_summary['room_number']}")
    print(f"  Age: {handoff_summary['age']}")
    print(f"  Chief Complaint: {handoff_summary['chief_complaint']}")
    print(f"  Medications: {', '.join(handoff_summary['medications'])}")
    print(f"  Vitals: BP {handoff_summary['vitals']['blood_pressure']}, HR {handoff_summary['vitals']['heart_rate']}")
    print(f"  Safety Alerts: {', '.join(handoff_summary['safety_alerts'])}")
    print()
    
    try:
        print("🔄 Verifying against EMR (Patient ID: P001)...\n")
        agent = VerificationAgent()
        result = agent.verify(handoff_summary, "P001")
        
        print_findings(result.findings, result.overall_risk_score, result.summary)
        
    except VerificationAgentError as e:
        print(f"❌ VERIFICATION ERROR: {e}\n")
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}\n")


def test_scenario_b_wrong_medication():
    """Test Scenario B: Wrong medication dose - should catch the error."""
    print_separator("SCENARIO B: WRONG MEDICATION DOSE - Should Catch Error")
    
    # Create a handoff summary with WRONG aspirin dose (325mg instead of 81mg)
    handoff_summary = {
        "confidence": 0.90,
        "reasoning": "Complete handoff with all key information clearly stated.",
        "patient_name": "John Smith",
        "room_number": "302",
        "age": "68",
        "chief_complaint": "Chest pain",
        "medications": [
            "Aspirin 325mg daily",  # 🚨 WRONG DOSE - EMR says 81mg
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
    
    print("📋 HANDOFF SUMMARY:")
    print(f"  Patient: {handoff_summary['patient_name']}")
    print(f"  Room: {handoff_summary['room_number']}")
    print(f"  Age: {handoff_summary['age']}")
    print(f"  Chief Complaint: {handoff_summary['chief_complaint']}")
    print(f"  Medications: {', '.join(handoff_summary['medications'])} 🚨 WRONG DOSE!")
    print(f"  Vitals: BP {handoff_summary['vitals']['blood_pressure']}, HR {handoff_summary['vitals']['heart_rate']}")
    print(f"  Safety Alerts: {', '.join(handoff_summary['safety_alerts'])}")
    print()
    
    print("⚠️  NOTE: Aspirin dose is 325mg in handoff but EMR shows 81mg\n")
    
    try:
        print("🔄 Verifying against EMR (Patient ID: P001)...\n")
        agent = VerificationAgent()
        result = agent.verify(handoff_summary, "P001")
        
        print_findings(result.findings, result.overall_risk_score, result.summary)
        
    except VerificationAgentError as e:
        print(f"❌ VERIFICATION ERROR: {e}\n")
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}\n")


def main():
    """Run all verification tests."""
    print("\n" + "=" * 80)
    print("  VERIFICATION AGENT TESTING")
    print("=" * 80)
    print("\nTesting handoff verification against Supabase EMR data")
    print("Patient: John Smith (ID: P001)")
    
    # Initialize agent to check connection
    try:
        print("\n🔧 Initializing Verification Agent...")
        agent = VerificationAgent()
        print("✅ Verification Agent initialized successfully\n")
    except VerificationAgentError as e:
        print(f"❌ Failed to initialize: {e}")
        print("\n💡 Make sure your .env file has:")
        print("   - SUPABASE_URL")
        print("   - SUPABASE_KEY")
        print("   - AZURE_OPENAI_ENDPOINT")
        print("   - AZURE_OPENAI_KEY")
        print("   - AZURE_OPENAI_DEPLOYMENT")
        return
    
    # Run test scenarios
    test_scenario_a_correct_handoff()
    test_scenario_b_wrong_medication()
    
    # Final summary
    print_separator("TEST SUMMARY")
    print("✅ Scenario A: Correct handoff - should show NO or LOW findings")
    print("⚠️  Scenario B: Wrong medication dose - should show HIGH/MEDIUM findings")
    print("\n📝 KEY OBSERVATIONS:")
    print("  • Verification Agent compares handoff vs EMR data")
    print("  • AI generates intelligent reasoning for each discrepancy")
    print("  • Severity levels prioritize clinical safety impact")
    print("  • Overall risk score aggregates all findings")
    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
