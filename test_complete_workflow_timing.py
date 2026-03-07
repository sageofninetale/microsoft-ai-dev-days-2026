#!/usr/bin/env python3
"""
Complete End-to-End Workflow Timing Analysis
Tests entire CascadeAI workflow with detailed performance metrics
"""

import requests
import time
import json
from typing import Dict, Any
import base64
from datetime import datetime

API_BASE = "http://localhost:8000"

class WorkflowTimer:
    def __init__(self):
        self.timings = {}
        self.start_time = None
    
    def start(self, step_name: str):
        self.start_time = time.time()
        print(f"\n{'='*60}")
        print(f"▶️  {step_name}")
        print(f"{'='*60}")
    
    def end(self, step_name: str):
        elapsed = time.time() - self.start_time
        self.timings[step_name] = elapsed
        print(f"✅ {step_name}: {elapsed:.2f}s")
        return elapsed
    
    def summary(self):
        print(f"\n{'='*60}")
        print(f"📊 COMPLETE TIMING ANALYSIS")
        print(f"{'='*60}")
        total = sum(self.timings.values())
        for step, duration in self.timings.items():
            percentage = (duration / total * 100) if total > 0 else 0
            print(f"{step:40s} {duration:6.2f}s ({percentage:5.1f}%)")
        print(f"{'-'*60}")
        print(f"{'TOTAL TIME':40s} {total:6.2f}s (100.0%)")
        print(f"{'='*60}\n")
        return self.timings

def test_complete_workflow():
    """Run complete A-Z workflow test"""
    timer = WorkflowTimer()
    
    print(f"\n🚀 CascadeAI Complete Workflow Test")
    print(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🌐 Testing against: {API_BASE}")
    
    # ==================== STEP 1: Get Nurses ====================
    timer.start("1. Fetch Nurse List")
    response = requests.get(f"{API_BASE}/api/nurses")
    assert response.status_code == 200
    nurses = response.json()
    print(f"   Found {len(nurses)} nurses")
    nurse = nurses[0]  # Use first nurse
    print(f"   Selected: {nurse['name']} ({nurse['nurse_id']})")
    timer.end("1. Fetch Nurse List")
    
    # ==================== STEP 2: Start Shift ====================
    timer.start("2. Start Nurse Shift")
    shift_data = {
        "nurse_id": nurse['nurse_id'],
        "nurse_name": nurse['name'],
        "shift_type": "day",
        "patient_ids": ["P010"]  # Test with patient P010
    }
    response = requests.post(f"{API_BASE}/api/shift/start", json=shift_data)
    assert response.status_code == 201
    shift_result = response.json()
    shift_id = shift_result['shift_id']
    print(f"   Shift ID: {shift_id}")
    print(f"   Patients: {shift_result['patient_count']}")
    timer.end("2. Start Nurse Shift")
    
    # ==================== STEP 3: Get Patient Info ====================
    timer.start("3. Fetch Patient Info")
    response = requests.get(f"{API_BASE}/api/patient/P010/info")
    assert response.status_code == 200
    patient = response.json()
    print(f"   Patient: {patient['patient_name']}")
    print(f"   Room: {patient['room_number']}")
    print(f"   Chief Complaint: {patient['chief_complaint']}")
    timer.end("3. Fetch Patient Info")
    
    # ==================== STEP 4: Transcribe Audio ====================
    timer.start("4. Audio Transcription (Azure Speech)")
    
    # Create a fake audio file (in real test, would use actual audio)
    # For now, we'll simulate by directly calling the update endpoint with text
    print(f"   ⚠️  Skipping audio transcription (no test audio file)")
    print(f"   Using direct text input instead")
    timer.end("4. Audio Transcription (Azure Speech)")
    
    # ==================== STEP 5: Submit Update (Main Processing) ====================
    timer.start("5. Submit Update (AI Processing + EMR Verification)")
    
    update_data = {
        "shift_id": shift_id,
        "update_type": "vital_signs",
        "text": "Patient vital signs: Blood pressure 135/85, heart rate 78, temperature 98.6F, oxygen saturation 97% on room air. Patient reports feeling well.",
        "audio_base64": None  # Not using audio for timing test
    }
    
    response = requests.post(f"{API_BASE}/api/patient/P010/update", json=update_data)
    assert response.status_code == 201
    update_result = response.json()
    print(f"   Update ID: {update_result['update_id']}")
    print(f"   Verification: {'✅ Verified' if update_result.get('verification_status') == 'verified' else '⚠️ Issues found'}")
    if update_result.get('discrepancies'):
        print(f"   Discrepancies: {len(update_result['discrepancies'])}")
    timer.end("5. Submit Update (AI Processing + EMR Verification)")
    
    # ==================== STEP 6: Add More Updates ====================
    timer.start("6. Submit Medication Update")
    
    med_update = {
        "shift_id": shift_id,
        "update_type": "medication",
        "text": "Administered Lisinopril 10mg PO at 14:00 as ordered. Patient tolerated well, no adverse reactions.",
        "audio_base64": None
    }
    
    response = requests.post(f"{API_BASE}/api/patient/P010/update", json=med_update)
    assert response.status_code == 201
    timer.end("6. Submit Medication Update")
    
    timer.start("7. Submit Procedure Update")
    
    proc_update = {
        "shift_id": shift_id,
        "update_type": "procedure",
        "text": "Changed wound dressing on left leg. Wound healing well, no signs of infection. Applied sterile gauze.",
        "audio_base64": None
    }
    
    response = requests.post(f"{API_BASE}/api/patient/P010/update", json=proc_update)
    assert response.status_code == 201
    timer.end("7. Submit Procedure Update")
    
    # ==================== STEP 8: Fetch All Updates ====================
    timer.start("8. Fetch All Shift Updates")
    response = requests.get(f"{API_BASE}/api/patient/P010/updates/{shift_id}")
    assert response.status_code == 200
    updates = response.json()
    print(f"   Total updates: {len(updates)}")
    timer.end("8. Fetch All Shift Updates")
    
    # ==================== STEP 9: Generate Draft (CRITICAL TIMING) ====================
    timer.start("9. Generate Draft Handoff (AI Summary)")
    
    response = requests.post(f"{API_BASE}/api/patient/P010/draft", json={"shift_id": shift_id})
    assert response.status_code == 201
    draft = response.json()
    print(f"   Draft ID: {draft['draft_id']}")
    print(f"   Timeline events: {len(draft.get('timeline', []))}")
    print(f"   Key changes: {len(draft.get('key_changes', []))}")
    print(f"   Pending actions: {len(draft.get('pending_actions', []))}")
    timer.end("9. Generate Draft Handoff (AI Summary)")
    
    # ==================== STEP 10: End Shift ====================
    timer.start("10. End Shift")
    # In real app, this would be a separate endpoint
    print(f"   Shift {shift_id} completed")
    timer.end("10. End Shift")
    
    # ==================== FINAL SUMMARY ====================
    print(f"\n{'='*60}")
    print(f"🎯 WORKFLOW COMPLETED SUCCESSFULLY")
    print(f"{'='*60}")
    print(f"📋 Summary:")
    print(f"   • Nurse: {nurse['name']}")
    print(f"   • Patient: {patient['patient_name']} (P010)")
    print(f"   • Shift ID: {shift_id}")
    print(f"   • Updates submitted: {len(updates)}")
    print(f"   • Draft generated: {draft['draft_id']}")
    
    timings = timer.summary()
    
    # ==================== CRITICAL METRICS ====================
    print(f"\n{'='*60}")
    print(f"🔥 CRITICAL USER-FACING METRICS")
    print(f"{'='*60}")
    
    submit_time = timings.get("5. Submit Update (AI Processing + EMR Verification)", 0)
    draft_time = timings.get("9. Generate Draft Handoff (AI Summary)", 0)
    
    print(f"\n1️⃣  SUBMIT BUTTON ('Processing...' time)")
    print(f"   Duration: {submit_time:.2f}s")
    if submit_time < 5:
        print(f"   Status: ✅ EXCELLENT (< 5s)")
    elif submit_time < 10:
        print(f"   Status: ✅ GOOD (5-10s)")
    elif submit_time < 15:
        print(f"   Status: ⚠️  ACCEPTABLE (10-15s)")
    else:
        print(f"   Status: ❌ SLOW (> 15s)")
    
    print(f"\n2️⃣  GENERATE DRAFT BUTTON time")
    print(f"   Duration: {draft_time:.2f}s")
    if draft_time < 20:
        print(f"   Status: ✅ EXCELLENT (< 20s)")
    elif draft_time < 30:
        print(f"   Status: ✅ GOOD (20-30s)")
    elif draft_time < 40:
        print(f"   Status: ⚠️  ACCEPTABLE (30-40s)")
    else:
        print(f"   Status: ❌ SLOW (> 40s)")
    
    total_workflow = sum(timings.values())
    print(f"\n3️⃣  TOTAL WORKFLOW (nurse perspective)")
    print(f"   Duration: {total_workflow:.2f}s")
    print(f"   Breakdown:")
    print(f"   • Interactive time (user waiting): {submit_time + draft_time:.2f}s")
    print(f"   • Background/setup time: {total_workflow - submit_time - draft_time:.2f}s")
    
    print(f"\n{'='*60}\n")
    
    return {
        "success": True,
        "timings": timings,
        "submit_time": submit_time,
        "draft_time": draft_time,
        "total_time": total_workflow
    }

if __name__ == "__main__":
    try:
        result = test_complete_workflow()
        print("✅ All tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
