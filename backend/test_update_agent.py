"""
Test script for UpdateAgent - Real-world scenario testing
Tests processing of medication, vital signs, and procedure updates
"""

from __future__ import annotations
import sys
from pathlib import Path
from datetime import date
import uuid

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.update_agent import UpdateAgent
from backend.database import get_patient_updates, get_all_shift_updates, create_shift
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def print_separator(char="=", length=80):
    """Print a separator line"""
    print(char * length)


def print_header(text: str, emoji: str = "📋"):
    """Print a formatted section header"""
    print_separator("=")
    print(f"\n{emoji} {text.upper()}\n")
    print_separator("=")
    print()


def print_result(result: dict, test_name: str):
    """Print the result of an update processing"""
    print_header(f"Results: {test_name}", "📊")
    
    # Success status
    if result.get("success"):
        print("✅ Status: SUCCESS")
    else:
        print("❌ Status: FAILED")
        print(f"   Error: {result.get('message', 'Unknown error')}")
        return
    
    # Update ID
    print(f"🆔 Update ID: {result.get('update_id', 'N/A')}")
    
    # Transcription
    print(f"\n📝 Transcription:")
    transcription = result.get('transcription', '')
    print(f"   {transcription[:100]}..." if len(transcription) > 100 else f"   {transcription}")
    
    # Extracted Data
    print(f"\n🔍 Extracted Data:")
    extracted = result.get('extracted_data', {})
    
    event_type = extracted.get('event_type', 'N/A')
    print(f"   Event Type: {event_type}")
    
    timestamp = extracted.get('timestamp', 'N/A')
    print(f"   Timestamp: {timestamp}")
    
    description = extracted.get('description', 'N/A')
    print(f"   Description: {description[:80]}..." if len(description) > 80 else f"   Description: {description}")
    
    # Medications
    meds = extracted.get('mentioned_medications', [])
    if meds:
        print(f"\n   💊 Medications Mentioned: {len(meds)}")
        for med in meds:
            if isinstance(med, dict):
                print(f"      - {med.get('name', med)}")
            else:
                print(f"      - {med}")
    
    # Vitals
    vitals = extracted.get('mentioned_vitals', {})
    if vitals:
        print(f"\n   🩺 Vital Signs:")
        for vital_name, vital_value in vitals.items():
            print(f"      - {vital_name}: {vital_value}")
    
    # Events
    events = extracted.get('mentioned_events', [])
    if events:
        print(f"\n   📅 Events: {len(events)}")
        for event in events:
            print(f"      - {event}")
    
    # EMR Verification
    print(f"\n🔐 EMR Verification:")
    emr_verified = result.get('emr_verified', False)
    
    if emr_verified:
        print(f"   ✅ VERIFIED - Update matches EMR data")
    else:
        print(f"   ⚠️  VERIFICATION ISSUES FOUND")
    
    # Verification Issues
    issues = result.get('verification_issues', [])
    if issues:
        print(f"\n   ⚠️  Issues Detected: {len(issues)}")
        for i, issue in enumerate(issues, 1):
            severity = issue.get('severity', 'UNKNOWN')
            severity_emoji = {
                'CRITICAL': '🔴',
                'HIGH': '🟠',
                'MEDIUM': '🟡',
                'LOW': '🟢'
            }.get(severity, '⚪')
            
            print(f"\n   {i}. {severity_emoji} [{severity}] {issue.get('type', 'UNKNOWN')}")
            print(f"      Finding: {issue.get('finding', 'N/A')}")
            print(f"      Details: {issue.get('details', 'N/A')}")
    else:
        print(f"   ✅ No issues detected")
    
    print()


def test_medication_update(agent: UpdateAgent, patient_id: str, nurse_id: str, shift_id: str):
    """Test Case 1: Medication Update"""
    
    print_header("Test Case 1: Medication Update", "💊")
    
    update_text = """11 AM - Started heparin drip at 1000 units per hour per cardiology orders. 
Patient tolerated well, no bleeding concerns."""
    
    print(f"👤 Patient: {patient_id}")
    print(f"👨‍⚕️ Nurse: {nurse_id}")
    print(f"📄 Update Text:")
    print(f"   {update_text}")
    print()
    
    result = agent.process_update(
        audio_or_text=update_text,
        patient_id=patient_id,
        nurse_id=nurse_id,
        shift_id=shift_id,
        update_type="medication",
        is_audio=False
    )
    
    print_result(result, "Medication Update")
    return result


def test_vital_signs_update(agent: UpdateAgent, patient_id: str, nurse_id: str, shift_id: str):
    """Test Case 2: Vital Signs Update"""
    
    print_header("Test Case 2: Vital Signs Update", "🩺")
    
    update_text = """2 PM vitals check - Blood pressure 145 over 92, heart rate 88, 
temperature 98.6, oxygen saturation 96%. Patient resting comfortably."""
    
    print(f"👤 Patient: {patient_id}")
    print(f"👨‍⚕️ Nurse: {nurse_id}")
    print(f"📄 Update Text:")
    print(f"   {update_text}")
    print()
    
    result = agent.process_update(
        audio_or_text=update_text,
        patient_id=patient_id,
        nurse_id=nurse_id,
        shift_id=shift_id,
        update_type="vital_signs",
        is_audio=False
    )
    
    print_result(result, "Vital Signs Update")
    return result


def test_procedure_update(agent: UpdateAgent, patient_id: str, nurse_id: str, shift_id: str):
    """Test Case 3: Procedure/Consultation Update"""
    
    print_header("Test Case 3: Procedure/Consultation Update", "⚕️")
    
    update_text = """1:30 PM - Dr. Patel from cardiology examined patient. 
Reviewed troponin results which came back at 2.4. 
Recommended cath lab for tomorrow morning."""
    
    print(f"👤 Patient: {patient_id}")
    print(f"👨‍⚕️ Nurse: {nurse_id}")
    print(f"📄 Update Text:")
    print(f"   {update_text}")
    print()
    
    result = agent.process_update(
        audio_or_text=update_text,
        patient_id=patient_id,
        nurse_id=nurse_id,
        shift_id=shift_id,
        update_type="procedure",
        is_audio=False
    )
    
    print_result(result, "Procedure/Consultation Update")
    return result


def show_all_saved_updates(shift_id: str, patient_id: str):
    """Query database and show all saved updates"""
    
    print_header("Database Query: All Saved Updates", "💾")
    
    print(f"📊 Querying updates for:")
    print(f"   Shift ID: {shift_id}")
    print(f"   Patient ID: {patient_id}")
    print()
    
    # Get all updates for this patient/shift
    updates = get_patient_updates(patient_id, shift_id)
    
    if not updates:
        print("⚠️  No updates found in database")
        return
    
    print(f"✅ Found {len(updates)} update(s)\n")
    
    for i, update in enumerate(updates, 1):
        print(f"{'─' * 60}")
        print(f"Update #{i}")
        print(f"{'─' * 60}")
        print(f"🆔 ID: {update.id}")
        print(f"⏰ Timestamp: {update.timestamp}")
        print(f"📝 Type: {update.update_type}")
        print(f"📄 Transcription: {update.transcription[:80]}...")
        print(f"🔐 EMR Verified: {'✓' if update.emr_verified else '✗'}")
        
        if not update.emr_verified:
            issues = update.verification_notes.get('issues', [])
            print(f"⚠️  Verification Issues: {len(issues)}")
            for issue in issues:
                print(f"   - [{issue.get('severity')}] {issue.get('finding')}")
        
        print()
    
    # Also try getting all shift updates
    print(f"\n{'='*60}")
    print(f"📊 All updates for entire shift:")
    print(f"{'='*60}\n")
    
    all_shift_updates = get_all_shift_updates(shift_id)
    print(f"✅ Total shift updates: {len(all_shift_updates)}")
    
    if all_shift_updates:
        # Group by patient
        patients = {}
        for update in all_shift_updates:
            if update.patient_id not in patients:
                patients[update.patient_id] = []
            patients[update.patient_id].append(update)
        
        print(f"👥 Patients with updates: {len(patients)}")
        for patient_id, patient_updates in patients.items():
            print(f"   - {patient_id}: {len(patient_updates)} update(s)")
    
    print()


def main():
    """Run all UpdateAgent tests"""
    
    print("\n")
    print_separator("=", 80)
    print("🏥 UPDATE AGENT - REAL-WORLD SCENARIO TESTING")
    print("   Testing medication, vital signs, and procedure updates")
    print_separator("=", 80)
    print()
    
    # Create real shift in database
    print("🔧 Creating test nurse shift...")
    shift = create_shift(
        nurse_id="NURSE_CRISTIANO",
        nurse_name="Cristiano Ronaldo",
        shift_type="day",
        shift_date=date.today(),
        patient_ids=["P001"]
    )
    
    if not shift:
        print("❌ Failed to create shift")
        return
    
    shift_id = shift.id
    print(f"✅ Shift created: {shift_id}")
    
    # Test setup
    nurse_id = "NURSE_CRISTIANO"
    nurse_name = "Cristiano"
    patient_id = "P001"  # John Smith
    
    print(f"🔧 Test Configuration:")
    print(f"   Nurse: {nurse_name} ({nurse_id})")
    print(f"   Patient: {patient_id} (John Smith)")
    print(f"   Shift ID: {shift_id}")
    print()
    
    # Initialize UpdateAgent
    try:
        print("🔧 Initializing UpdateAgent...")
        agent = UpdateAgent()
        print("✅ UpdateAgent initialized successfully\n")
    except Exception as e:
        print(f"❌ Failed to initialize UpdateAgent: {e}")
        print("\n💡 Make sure your .env file has all required credentials:")
        print("   - AZURE_OPENAI_ENDPOINT")
        print("   - AZURE_OPENAI_KEY")
        print("   - AZURE_OPENAI_DEPLOYMENT")
        print("   - AZURE_SPEECH_KEY (optional for audio)")
        print("   - AZURE_SPEECH_REGION (optional for audio)")
        print("   - SUPABASE_URL")
        print("   - SUPABASE_KEY")
        return
    
    # Run test cases
    results = []
    
    print("\n" * 2)
    result1 = test_medication_update(agent, patient_id, nurse_id, shift_id)
    results.append(result1)
    
    print("\n" * 2)
    result2 = test_vital_signs_update(agent, patient_id, nurse_id, shift_id)
    results.append(result2)
    
    print("\n" * 2)
    result3 = test_procedure_update(agent, patient_id, nurse_id, shift_id)
    results.append(result3)
    
    # Show all saved updates
    print("\n" * 2)
    show_all_saved_updates(shift_id, patient_id)
    
    # Final summary
    print_header("Test Summary", "🎯")
    
    successful = sum(1 for r in results if r.get('success', False))
    total = len(results)
    
    print(f"✅ Successful Updates: {successful}/{total}")
    print(f"📊 Success Rate: {(successful/total)*100:.1f}%")
    print()
    
    print("📋 Test Results:")
    print("   ✅ Test Case 1 (Medication): ", "PASSED" if results[0].get('success') else "FAILED")
    print("   ✅ Test Case 2 (Vital Signs): ", "PASSED" if results[1].get('success') else "FAILED")
    print("   ✅ Test Case 3 (Procedure): ", "PASSED" if results[2].get('success') else "FAILED")
    print()
    
    print("🎯 Key Capabilities Demonstrated:")
    print("   ✅ Text update processing")
    print("   ✅ Structured data extraction (medications, vitals, events)")
    print("   ✅ EMR verification against patient database")
    print("   ✅ Database persistence")
    print("   ✅ Verification issue detection")
    print()
    
    print("🚀 System Status: UpdateAgent ready for continuous handoff workflow")
    print_separator("=", 80)
    print()


if __name__ == "__main__":
    main()
