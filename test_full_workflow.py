#!/usr/bin/env python3
"""
Test full end-to-end workflow via API calls
Simulates what the frontend does
"""
import requests
import json
import time

API_BASE = "http://localhost:8000"

print("="*80)
print("🧪 FULL WORKFLOW TEST - Simulating Frontend Behavior")
print("="*80)
print()

# Step 1: Start a shift
print("📋 Step 1: Starting a shift for Cristiano Ronaldo...")
shift_data = {
    "nurse_id": "NURSE_CRISTIANO",
    "nurse_name": "Cristiano Ronaldo",
    "shift_type": "day",
    "patient_ids": ["P001"]
}

response = requests.post(f"{API_BASE}/api/shift/start", json=shift_data)
if response.status_code == 201:
    shift = response.json()
    shift_id = shift["shift_id"]  # Fixed: use shift_id not id
    print(f"✅ Shift started: {shift_id}")
    print(f"   Nurse: {shift['nurse_name']}")
    print(f"   Patients: {shift['patient_ids']}")
else:
    print(f"❌ Failed to start shift: {response.status_code}")
    print(response.text)
    exit(1)

print()

# Step 2: Submit a patient update (text)
print("📝 Step 2: Submitting patient update...")
update_data = {
    "shift_id": shift_id,
    "nurse_id": "NURSE_CRISTIANO",
    "update_type": "general",  # medication, vital_signs, procedure, general
    "text": "Patient reports chest pain, given aspirin 325mg. Blood pressure 150/95, heart rate 92. Will monitor closely and notify cardiology."
}

response = requests.post(f"{API_BASE}/api/patient/P001/update", json=update_data)
if response.status_code == 201:  # Changed from 200 to 201
    update_result = response.json()
    print(f"✅ Update submitted successfully")
    print(f"   Update type: {update_result.get('update_type', 'unknown')}")
    print(f"   Verification: {update_result.get('verification_status', 'unknown')}")
    if update_result.get('emr_discrepancies'):
        print(f"   ⚠️  Discrepancies: {update_result['emr_discrepancies']}")
else:
    print(f"❌ Failed to submit update: {response.status_code}")
    print(response.text)

print()

# Step 3: Submit another update
print("📝 Step 3: Submitting another update...")
update_data2 = {
    "shift_id": shift_id,
    "nurse_id": "NURSE_CRISTIANO",
    "update_type": "procedure",
    "text": "Cardiology consulted. Dr. Patel recommends ECG and troponin levels. Patient stable, pain reduced to 3/10 after medication."
}

response = requests.post(f"{API_BASE}/api/patient/P001/update", json=update_data2)
if response.status_code == 201:  # Changed from 200 to 201
    print(f"✅ Second update submitted")
else:
    print(f"❌ Failed: {response.status_code}")

print()

# Step 4: Generate draft handoff
print("📋 Step 4: Generating draft handoff...")
print("   (This will use AI to create detailed narrative summary)")
print()

# POST to generate, not GET to retrieve
response = requests.post(f"{API_BASE}/api/patient/P001/draft", json={"shift_id": shift_id})
if response.status_code == 201:  # Changed from 200 to 201
    draft = response.json()
    print(f"✅ Draft handoff generated!")
    print(f"   Response type: {type(draft)}")
    print(f"   Response keys: {draft.keys() if draft else 'None'}")
    print()
    print("="*80)
    print("📖 NARRATIVE SUMMARY (The Critical Feature!)")
    print("="*80)
    
    # Handle different response structures - draft_content is in the response
    draft_content = draft.get("draft_content", {}) if draft else {}
    
    if "narrative_summary" in draft_content:
        narrative = draft_content["narrative_summary"]
        print()
        # Word wrap the narrative
        words = narrative.split()
        line = ""
        for word in words:
            if len(line) + len(word) + 1 > 76:
                print(f"   {line}")
                line = word
            else:
                line += " " + word if line else word
        if line:
            print(f"   {line}")
        print()
        print(f"   Word count: {len(narrative.split())} words")
    else:
        print("   ⚠️  WARNING: No narrative summary generated!")
        print("   This means the AI generation failed")
        print(f"   Available keys: {list(draft_content.keys())}")
    
    print()
    print("="*80)
    print("📊 DRAFT DETAILS")
    print("="*80)
    print(f"   Draft ID: {draft_content.get('id', 'N/A')}")
    print(f"   Updates compiled: {draft_content.get('update_count', 0)}")
    print(f"   Timeline events: {len(draft_content.get('timeline', []))}")
    print(f"   Pending actions: {len(draft_content.get('pending_actions', []))}")
    print()
    
    # Show timeline
    if draft_content.get("timeline"):
        print("⏰ TIMELINE:")
        for event in draft_content["timeline"][:3]:  # Show first 3
            print(f"   • {event}")
        if len(draft_content["timeline"]) > 3:
            print(f"   ... and {len(draft_content['timeline']) - 3} more events")
    
else:
    print(f"❌ Failed to generate draft: {response.status_code}")
    print(response.text)

print()
print("="*80)
print("✅ WORKFLOW TEST COMPLETE")
print("="*80)
print()
print("🎯 What we tested:")
print("   ✅ Backend API running")
print("   ✅ Shift creation")
print("   ✅ Patient updates submission")
print("   ✅ Draft handoff generation with AI narrative")
print()
print("💡 If you saw a detailed narrative summary above, the system is WORKING!")
print("   If not, there's still an issue with AI generation.")
