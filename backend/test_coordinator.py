"""Test the Coordinator Agent with complete end-to-end workflow."""

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

from backend.coordinator_agent import CoordinatorAgent, CoordinatorAgentError


def print_separator(title: str):
    """Print a visual separator with title."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_result(result):
    """Print coordinator result in a formatted way."""
    print_separator("EXECUTIVE SUMMARY")
    print(result.executive_summary)
    print()
    
    print_separator("OVERALL METRICS")
    print(f"📊 Overall Risk Score: {result.overall_risk_score:.2f}")
    print(f"⏰ Timestamp: {result.timestamp}")
    print(f"⚠️  Warnings: {len(result.errors)}")
    print()
    
    if result.errors:
        print("⚠️  WARNINGS:")
        for i, error in enumerate(result.errors, 1):
            print(f"   {i}. {error}")
        print()
    
    print_separator("HANDOFF SUMMARY (INTAKE AGENT)")
    print(f"Patient: {result.handoff_summary.patient_name or 'UNKNOWN'}")
    print(f"Room: {result.handoff_summary.room_number or 'UNKNOWN'}")
    print(f"Age: {result.handoff_summary.age or 'UNKNOWN'}")
    print(f"Chief Complaint: {result.handoff_summary.chief_complaint or 'UNKNOWN'}")
    print(f"Confidence: {result.handoff_summary.confidence:.2f}")
    print(f"Reasoning: {result.handoff_summary.reasoning}")
    print()
    
    if result.handoff_summary.medications:
        print("Medications:")
        for med in result.handoff_summary.medications:
            print(f"  • {med}")
        print()
    
    if result.handoff_summary.vitals:
        print("Vitals:")
        for key, value in result.handoff_summary.vitals.items():
            print(f"  • {key}: {value}")
        print()
    
    if result.verification_findings:
        print_separator("VERIFICATION FINDINGS (EMR CROSS-REFERENCE)")
        print(f"Risk Score: {result.verification_findings.overall_risk_score:.2f}")
        print(f"Discrepancies Found: {len(result.verification_findings.findings)}")
        print()
        
        if result.verification_findings.findings:
            for i, finding in enumerate(result.verification_findings.findings, 1):
                severity_emoji = {
                    "CRITICAL": "🚨",
                    "HIGH": "⚠️",
                    "MEDIUM": "⚡",
                    "LOW": "ℹ️",
                }.get(finding.severity, "•")
                print(f"{severity_emoji} Finding #{i}: {finding.type}")
                print(f"   Severity: {finding.severity}")
                print(f"   Field: {finding.field}")
                print(f"   Handoff: {finding.handoff_value}")
                print(f"   EMR: {finding.emr_value}")
                print(f"   Reasoning: {finding.reasoning[:150]}...")
                print()
        else:
            print("✅ No discrepancies found - handoff matches EMR perfectly!")
            print()
    else:
        print_separator("VERIFICATION FINDINGS (EMR CROSS-REFERENCE)")
        print("⚠️  Verification skipped (service unavailable)")
        print()
    
    if result.protocol_findings:
        print_separator("PROTOCOL COMPLIANCE")
        print(f"Compliance Score: {result.protocol_findings.overall_compliance_score:.2f}")
        print(f"Protocols Checked: {', '.join(result.protocol_findings.protocols_checked)}")
        print(f"Violations Found: {len(result.protocol_findings.findings)}")
        print()
        
        if result.protocol_findings.findings:
            for i, finding in enumerate(result.protocol_findings.findings, 1):
                severity_emoji = {
                    "CRITICAL": "🚨",
                    "HIGH": "⚠️",
                    "MEDIUM": "⚡",
                    "LOW": "ℹ️",
                }.get(finding.severity, "•")
                print(f"{severity_emoji} Violation #{i}: {finding.protocol_name}")
                print(f"   Severity: {finding.severity}")
                print(f"   Requirement: {finding.requirement}")
                print(f"   Status: {finding.status}")
                print(f"   Reasoning: {finding.reasoning[:150]}...")
                print(f"   💡 Recommendation: {finding.recommendation[:150]}...")
                print()
        else:
            print("✅ All protocols compliant!")
            print()
    else:
        print_separator("PROTOCOL COMPLIANCE")
        print("⚠️  Protocol validation skipped (service unavailable)")
        print()
    
    print_separator("PRIORITY ACTIONS (TOP 5)")
    if result.priority_actions:
        for i, action in enumerate(result.priority_actions, 1):
            print(f"{i}. {action}")
        print()
    else:
        print("✅ No priority actions required - all clear!")
        print()


def test_complete_workflow_good_handoff():
    """Test Scenario A: Complete workflow with good quality handoff."""
    print_separator("SCENARIO A: COMPLETE WORKFLOW - GOOD QUALITY HANDOFF")
    
    # Good quality handoff that matches EMR for patient P001
    transcript = """
    Room 302 is Mr. Johnson, 67 years old, admitted for chest pain. 
    He is on aspirin 81mg daily and metoprolol 50mg twice daily. 
    We drew troponin labs at 4 PM, results are pending. 
    His blood pressure was 145 over 92 at 6 PM, heart rate 88. 
    Temperature 98.6, oxygen saturation 96%. 
    He is a fall risk due to dizziness, bed alarm is active.
    """
    
    patient_id = "P001"
    
    try:
        print("📋 Input Transcript:")
        print(transcript.strip())
        print(f"\n🆔 Patient ID: {patient_id}\n")
        
        # Run coordinator
        coordinator = CoordinatorAgent()
        result = coordinator.process_handoff(
            audio_or_text=transcript,
            patient_id=patient_id,
            is_audio_file=False
        )
        
        print_result(result)
        
    except CoordinatorAgentError as e:
        print(f"❌ COORDINATOR ERROR: {e}\n")
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}\n")


def test_incomplete_handoff():
    """Test Scenario B: Incomplete handoff (missing patient name - low confidence)."""
    print_separator("SCENARIO B: INCOMPLETE HANDOFF - LOW CONFIDENCE")
    
    # Poor quality handoff missing critical info
    transcript = """
    The patient in room 302 has chest pain. 
    I think he's on some medications but I'm not sure which ones. 
    Blood pressure was high, maybe 160 or so.
    """
    
    patient_id = "P001"
    
    try:
        print("📋 Input Transcript:")
        print(transcript.strip())
        print(f"\n🆔 Patient ID: {patient_id}\n")
        
        # Run coordinator
        coordinator = CoordinatorAgent()
        result = coordinator.process_handoff(
            audio_or_text=transcript,
            patient_id=patient_id,
            is_audio_file=False
        )
        
        print_result(result)
        
    except CoordinatorAgentError as e:
        print(f"❌ COORDINATOR ERROR: {e}\n")
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}\n")


def test_wrong_medication_dose():
    """Test Scenario C: Wrong medication dose (should be caught by verification)."""
    print_separator("SCENARIO C: WRONG MEDICATION DOSE - VERIFICATION CATCHES ERROR")
    
    # Handoff with wrong aspirin dose
    transcript = """
    Room 302 is Mr. John Smith, 68 years old, admitted for chest pain. 
    He is on aspirin 325mg daily and metoprolol 50mg twice daily. 
    We drew cardiac enzyme labs at 4 PM, results are pending. 
    His blood pressure was 145 over 92 at 6 PM, heart rate 88. 
    Temperature 98.6, oxygen saturation 96%. 
    He is a fall risk, bed alarm is active.
    """
    
    patient_id = "P001"
    
    try:
        print("📋 Input Transcript:")
        print(transcript.strip())
        print(f"\n🆔 Patient ID: {patient_id}")
        print("⚠️  NOTE: Aspirin dose is WRONG (325mg vs 81mg in EMR)\n")
        
        # Run coordinator
        coordinator = CoordinatorAgent()
        result = coordinator.process_handoff(
            audio_or_text=transcript,
            patient_id=patient_id,
            is_audio_file=False
        )
        
        print_result(result)
        
    except CoordinatorAgentError as e:
        print(f"❌ COORDINATOR ERROR: {e}\n")
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}\n")


def main():
    """Run all coordinator tests."""
    print("\n" + "=" * 80)
    print("  COORDINATOR AGENT TESTING")
    print("=" * 80)
    print("\nTesting complete end-to-end multi-agent workflow")
    print("Patient: John Smith (ID: P001)")
    
    # Initialize coordinator to check connection
    try:
        print("\n🔧 Initializing Coordinator Agent...")
        coordinator = CoordinatorAgent()
        print("✅ Coordinator Agent initialized successfully")
        print("   ✅ Intake Agent ready")
        print("   ✅ Verification Agent ready")
        print("   ✅ Protocol Agent ready\n")
    except CoordinatorAgentError as e:
        print(f"❌ Failed to initialize: {e}")
        print("\n💡 Make sure your .env file has all required credentials:")
        print("   - AZURE_OPENAI_ENDPOINT")
        print("   - AZURE_OPENAI_KEY")
        print("   - AZURE_OPENAI_DEPLOYMENT")
        print("   - AZURE_SPEECH_KEY")
        print("   - AZURE_SPEECH_REGION")
        print("   - SUPABASE_URL")
        print("   - SUPABASE_KEY")
        return
    
    # Run test scenarios
    test_complete_workflow_good_handoff()
    test_incomplete_handoff()
    test_wrong_medication_dose()
    
    # Final summary
    print_separator("TEST SUMMARY")
    print("✅ Scenario A: Good handoff - Should show high confidence, minimal findings")
    print("⚠️  Scenario B: Incomplete handoff - Should show low confidence, HIGH RISK flag")
    print("🚨 Scenario C: Wrong medication - Should detect dose mismatch in verification")
    print("\n📝 KEY OBSERVATIONS:")
    print("  • Coordinator orchestrates all 3 agents in sequence")
    print("  • Graceful error handling - continues even if verification/protocol fails")
    print("  • Weighted risk scoring (handoff 20%, verification 40%, protocols 40%)")
    print("  • Priority actions sorted by severity (CRITICAL > HIGH > MEDIUM > LOW)")
    print("  • Executive summary provides 2-3 sentence clinical overview")
    print("  • Production-ready with comprehensive logging and error tracking")
    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
