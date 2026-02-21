#!/usr/bin/env python3
"""
Quick verification test - Confirm restoration is working
Tests the exact scenarios that were broken after 6:52 PM
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def test_medication_verification():
    """Test that Amlodipine is verified for P045"""
    print("\n" + "="*70)
    print("🧪 TEST 1: Medication Verification (Amlodipine for P045)")
    print("="*70)
    
    # Step 1: Create shift
    print("\n📋 Creating shift for P045...")
    shift_response = requests.post(f"{BASE_URL}/api/shift/start", json={
        "nurse_id": "N001",
        "patient_ids": ["P045"]
    })
    
    if shift_response.status_code != 200:
        print(f"❌ Failed to create shift: {shift_response.status_code}")
        print(shift_response.text)
        return False
    
    shift_data = shift_response.json()
    shift_id = shift_data.get("shift_id")
    print(f"✅ Shift created: {shift_id}")
    
    # Step 2: Add medication update (Amlodipine IS in P045's EMR)
    print("\n💊 Adding Amlodipine update...")
    update_response = requests.post(f"{BASE_URL}/api/patient/P045/update", json={
        "shift_id": shift_id,
        "update_type": "medication",
        "text": "Morning medication given at 9:00 AM Amlodipine 10mg."
    })
    
    if update_response.status_code != 200:
        print(f"❌ Failed to add update: {update_response.status_code}")
        print(update_response.text)
        return False
    
    update_data = update_response.json()
    print(f"✅ Update added: {update_data.get('update_id')}")
    
    # Check structured data
    structured_data = update_data.get("structured_data")
    if not structured_data:
        print("❌ FAILED: No structured_data extracted!")
        return False
    
    print(f"✅ Structured data extracted:")
    print(f"   - Event type: {structured_data.get('event_type')}")
    print(f"   - Medications: {structured_data.get('mentioned_medications')}")
    
    # Check verification
    verification = update_data.get("verification")
    if not verification:
        print("❌ FAILED: No verification performed!")
        return False
    
    print(f"✅ Verification completed:")
    print(f"   - EMR verified: {verification.get('emr_verified')}")
    print(f"   - Issues: {len(verification.get('issues', []))}")
    
    if verification.get('emr_verified'):
        print("✅ TEST PASSED: Amlodipine correctly verified against EMR!")
        return True
    else:
        print("❌ TEST FAILED: Amlodipine should be verified (it's in EMR)")
        return False


def test_vitals_extraction():
    """Test that vital signs are properly extracted"""
    print("\n" + "="*70)
    print("🧪 TEST 2: Vital Signs Extraction")
    print("="*70)
    
    # Create shift
    print("\n📋 Creating shift for P045...")
    shift_response = requests.post(f"{BASE_URL}/api/shift/start", json={
        "nurse_id": "N002",
        "patient_ids": ["P045"]
    })
    
    if shift_response.status_code != 200:
        print(f"❌ Failed to create shift")
        return False
    
    shift_data = shift_response.json()
    shift_id = shift_data.get("shift_id")
    print(f"✅ Shift created: {shift_id}")
    
    # Add vitals update
    print("\n🩺 Adding vital signs update...")
    update_response = requests.post(f"{BASE_URL}/api/patient/P045/update", json={
        "shift_id": shift_id,
        "update_type": "vital_signs",
        "text": "Vitals: BP 180/20, Temperature 98.4F, SpO2 80%, Heart rate 88"
    })
    
    if update_response.status_code != 200:
        print(f"❌ Failed to add update")
        return False
    
    update_data = update_response.json()
    structured_data = update_data.get("structured_data")
    
    if not structured_data:
        print("❌ FAILED: No structured_data extracted!")
        return False
    
    mentioned_vitals = structured_data.get("mentioned_vitals", {})
    
    print(f"✅ Vitals extracted:")
    print(f"   - BP: {mentioned_vitals.get('bp')}")
    print(f"   - Temp: {mentioned_vitals.get('temp')}")
    print(f"   - SpO2: {mentioned_vitals.get('spo2')}")
    print(f"   - HR: {mentioned_vitals.get('hr')}")
    
    # Check if we got actual values
    if mentioned_vitals.get('bp') and mentioned_vitals.get('spo2'):
        print("✅ TEST PASSED: Vitals properly extracted as structured data!")
        return True
    else:
        print("❌ TEST FAILED: Vitals not extracted properly")
        return False


def test_non_emr_medication():
    """Test that non-EMR medication gets flagged"""
    print("\n" + "="*70)
    print("🧪 TEST 3: Non-EMR Medication Warning (Warfarin for P045)")
    print("="*70)
    
    # Create shift
    shift_response = requests.post(f"{BASE_URL}/api/shift/start", json={
        "nurse_id": "N003",
        "patient_ids": ["P045"]
    })
    
    if shift_response.status_code != 200:
        print(f"❌ Failed to create shift")
        return False
    
    shift_data = shift_response.json()
    shift_id = shift_data.get("shift_id")
    print(f"✅ Shift created: {shift_id}")
    
    # Add medication NOT in EMR
    print("\n💊 Adding Warfarin update (NOT in P045's EMR)...")
    update_response = requests.post(f"{BASE_URL}/api/patient/P045/update", json={
        "shift_id": shift_id,
        "update_type": "medication",
        "text": "Started new medication Warfarin 5mg at 10:00 AM"
    })
    
    if update_response.status_code != 200:
        print(f"❌ Failed to add update")
        return False
    
    update_data = update_response.json()
    verification = update_data.get("verification", {})
    
    emr_verified = verification.get("emr_verified")
    issues = verification.get("issues", [])
    
    print(f"✅ Verification results:")
    print(f"   - EMR verified: {emr_verified}")
    print(f"   - Issues found: {len(issues)}")
    
    if issues:
        for issue in issues:
            print(f"   - ⚠️  {issue.get('type')}: {issue.get('medication')}")
    
    if not emr_verified and issues:
        print("✅ TEST PASSED: Non-EMR medication correctly flagged!")
        return True
    else:
        print("❌ TEST FAILED: Warfarin should be flagged (NOT in EMR)")
        return False


if __name__ == "__main__":
    print("\n" + "="*70)
    print("🚀 CascadeAI Restoration Verification Tests")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    results = []
    
    try:
        results.append(("Medication Verification", test_medication_verification()))
    except Exception as e:
        print(f"❌ Test 1 crashed: {e}")
        results.append(("Medication Verification", False))
    
    try:
        results.append(("Vitals Extraction", test_vitals_extraction()))
    except Exception as e:
        print(f"❌ Test 2 crashed: {e}")
        results.append(("Vitals Extraction", False))
    
    try:
        results.append(("Non-EMR Warning", test_non_emr_medication()))
    except Exception as e:
        print(f"❌ Test 3 crashed: {e}")
        results.append(("Non-EMR Warning", False))
    
    # Summary
    print("\n" + "="*70)
    print("📊 TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED - Restoration successful!")
        print("✅ System is working exactly as it did before 6:30 PM")
    else:
        print("\n⚠️  Some tests failed - may need additional fixes")
    
    print("="*70)
