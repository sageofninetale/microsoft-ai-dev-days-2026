"""
Quick performance test for parallel API optimization.
Tests draft generation speed with the new parallel approach.
"""

import requests
import time

BASE_URL = "http://localhost:8000"

def test_parallel_draft_performance():
    """Test draft generation with parallel API calls"""
    print("\n" + "="*70)
    print("🚀 PERFORMANCE TEST: Parallel API Calls Optimization")
    print("="*70)
    
    # Step 1: Start a shift
    print("\n1️⃣ Starting test shift...")
    shift_response = requests.post(
        f"{BASE_URL}/api/shift/start",
        json={
            "nurse_id": "PERF_TEST_001",
            "nurse_name": "Performance Tester",
            "shift_type": "day",
            "patient_ids": ["P023"]
        }
    )
    
    if shift_response.status_code != 201:
        print(f"❌ Failed to start shift: {shift_response.text}")
        return
    
    shift_data = shift_response.json()
    print(f"📋 Shift response: {shift_data}")
    shift_id = shift_data.get("shift_id") or shift_data.get("shift", {}).get("shift_id")
    print(f"✅ Shift started: {shift_id}")
    
    # Step 2: Add 5 test updates (realistic scenario)
    print("\n2️⃣ Adding test updates...")
    updates = [
        {
            "update_type": "medication",
            "transcription": "Morning medications given at 9:00 AM. Aspirin 81mg and Amlodipine 10mg administered as per medication administration record."
        },
        {
            "update_type": "medication",
            "transcription": "Started new anticoagulation therapy. Apixaban 5mg given at 11:30 AM per physician order for atrial fibrillation."
        },
        {
            "update_type": "vital_signs",
            "transcription": "Patient vitals checked at 2:00 PM. Blood pressure is 145 over 88, heart rate 92 beats per minute, temperature 98.1 Fahrenheit, oxygen saturation 96 percent on room air."
        },
        {
            "update_type": "general",
            "transcription": "Patient ambulating independently in hallway at 3:15 PM. No complaints of dizziness or weakness. Denies any bleeding or bruising."
        },
        {
            "update_type": "general",
            "transcription": "INR result returned at 4:30 PM, value is 1.1. Cardiologist notified of new baseline before starting Apixaban therapy."
        }
    ]
    
    for i, update in enumerate(updates, 1):
        response = requests.post(
            f"{BASE_URL}/api/patient/P023/update",
            json={
                "shift_id": shift_id,
                "nurse_id": "PERF_TEST_001",
                "update_type": update["update_type"],
                "text": update["transcription"]
            }
        )
        if response.status_code == 201:
            print(f"   ✅ Update {i}/5 processed")
        else:
            print(f"   ❌ Update {i}/5 failed: {response.text}")
    
    # Step 3: Generate draft and measure time
    print("\n3️⃣ Generating draft handoff (parallel mode)...")
    print("   ⏱️  Starting timer...")
    
    start_time = time.time()
    
    draft_response = requests.post(
        f"{BASE_URL}/api/patient/P023/draft",
        json={"shift_id": shift_id}
    )
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    print(f"   ⏱️  Completed in {elapsed:.2f} seconds")
    
    # Step 4: Analyze results
    print("\n" + "="*70)
    print("📊 PERFORMANCE RESULTS")
    print("="*70)
    
    if draft_response.status_code == 201:
        draft_data = draft_response.json()
        draft_content = draft_data.get("draft_content", {})
        
        print(f"✅ Draft generated successfully")
        print(f"\n📈 Metrics:")
        print(f"   • Generation time: {elapsed:.2f} seconds")
        print(f"   • Timeline events: {len(draft_content.get('timeline', []))}")
        print(f"   • Pending actions: {len(draft_content.get('pending_actions', []))}")
        print(f"   • Narrative length: {len(draft_content.get('narrative_summary', ''))} characters")
        
        print(f"\n🎯 Performance Analysis:")
        if elapsed < 5:
            print(f"   🏆 EXCELLENT: {elapsed:.2f}s is 65-75% faster than old 10-15s!")
        elif elapsed < 7:
            print(f"   ✅ GOOD: {elapsed:.2f}s is 50-60% faster than old 10-15s")
        elif elapsed < 10:
            print(f"   ⚠️  MODERATE: {elapsed:.2f}s is better, but less than expected")
        else:
            print(f"   ❌ SLOW: {elapsed:.2f}s - parallel optimization may not be working")
        
        print(f"\n📝 Sample Narrative (first 200 chars):")
        print(f"   {draft_content.get('narrative_summary', 'N/A')[:200]}...")
        
    else:
        print(f"❌ Draft generation failed: {draft_response.text}")
    
    print("\n" + "="*70)
    print("✅ Performance test complete!")
    print("="*70 + "\n")

if __name__ == "__main__":
    try:
        test_parallel_draft_performance()
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to backend server at http://localhost:8000")
        print("   Make sure the server is running: python3 backend/main.py")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
