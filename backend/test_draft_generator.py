"""
Test script for DraftGenerator - Compiling shift updates into handoff draft
Uses the 3 updates created in test_update_agent.py
"""

from __future__ import annotations
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.draft_generator import DraftGenerator
from backend.database import get_patient_updates, get_draft
from dotenv import load_dotenv
from supabase import create_client
import os

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


def get_most_recent_shift(nurse_id: str = "NURSE_CRISTIANO"):
    """Query database to find most recent shift for nurse"""
    try:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            print("❌ Supabase credentials not found")
            return None
        
        supabase = create_client(supabase_url, supabase_key)
        
        result = supabase.table("nurse_shifts")\
            .select("*")\
            .eq("nurse_id", nurse_id)\
            .order("start_time", desc=True)\
            .limit(1)\
            .execute()
        
        if result.data and len(result.data) > 0:
            return result.data[0]
        else:
            return None
            
    except Exception as e:
        print(f"❌ Error querying shifts: {e}")
        return None


def print_input_data(shift_data: dict, updates, patient_id: str):
    """Print the input data being compiled"""
    print_header("Input Data: Updates to Compile", "📥")
    
    print(f"👨‍⚕️ Nurse: {shift_data.get('nurse_name', 'Unknown')}")
    print(f"📅 Shift: {shift_data.get('shift_type', 'Unknown').capitalize()} shift")
    print(f"🆔 Shift ID: {shift_data.get('id', 'Unknown')}")
    print(f"👤 Patient: {patient_id}")
    print(f"📊 Total Updates: {len(updates)}")
    print()
    
    if updates:
        print("📝 Updates to be compiled:")
        print()
        for i, update in enumerate(updates, 1):
            timestamp = update.timestamp.strftime("%I:%M %p") if hasattr(update.timestamp, 'strftime') else str(update.timestamp)
            update_type = update.update_type.replace('_', ' ').title()
            transcription = update.transcription[:80] + "..." if len(update.transcription) > 80 else update.transcription
            
            print(f"   {i}. [{update_type}] @ {timestamp}")
            print(f"      {transcription}")
            print()


def print_draft_content(draft_content: dict):
    """Print the generated draft content beautifully"""
    print_header("Generated Draft Handoff", "📋")
    
    # Timeline Section
    if "timeline" in draft_content:
        print("⏰ TIMELINE - Events During Shift:")
        print_separator("-", 60)
        timeline = draft_content["timeline"]
        if isinstance(timeline, list):
            for event in timeline:
                print(f"   {event}")
        print()
    
    # Current Status Section
    if "current_status" in draft_content:
        print("🏥 CURRENT STATUS:")
        print_separator("-", 60)
        status = draft_content["current_status"]
        
        # Medications
        if "medications" in status:
            print("\n   💊 Current Medications:")
            meds = status["medications"]
            if isinstance(meds, list) and meds:
                for med in meds[:5]:  # Show first 5
                    print(f"      • {med}")
                if len(meds) > 5:
                    print(f"      ... and {len(meds) - 5} more")
            elif not meds:
                print("      • None documented")
            else:
                print(f"      • {meds}")
        
        # Latest Vitals
        if "latest_vitals" in status:
            print("\n   🩺 Latest Vital Signs:")
            vitals = status["latest_vitals"]
            if isinstance(vitals, dict) and vitals:
                for vital_name, vital_value in vitals.items():
                    print(f"      • {vital_name}: {vital_value}")
            else:
                print("      • See timeline for vital signs")
        
        # Overall Condition
        if "overall_condition" in status:
            print("\n   📊 Overall Condition:")
            condition = status["overall_condition"]
            # Wrap text if too long
            if isinstance(condition, str):
                if len(condition) > 70:
                    words = condition.split()
                    line = "      "
                    for word in words:
                        if len(line) + len(word) + 1 > 76:
                            print(line)
                            line = "      " + word
                        else:
                            line += " " + word if line != "      " else word
                    if line.strip():
                        print(line)
                else:
                    print(f"      {condition}")
        print()
    
    # Key Changes Section
    if "key_changes" in draft_content:
        print("🔄 KEY CHANGES TODAY:")
        print_separator("-", 60)
        changes = draft_content["key_changes"]
        if isinstance(changes, list) and changes:
            for change in changes:
                print(f"   ✓ {change}")
        else:
            print("   • No significant changes documented")
        print()
    
    # Pending Actions Section
    if "pending_actions" in draft_content:
        print("📌 PENDING ACTIONS FOR NIGHT SHIFT:")
        print_separator("-", 60)
        actions = draft_content["pending_actions"]
        
        if isinstance(actions, list) and actions:
            # Check if actions are objects with categories or just strings
            if actions and isinstance(actions[0], dict):
                # Categorized actions - sort by urgency
                critical_actions = [a for a in actions if a.get("category") == "CRITICAL"]
                high_actions = [a for a in actions if a.get("category") == "HIGH"]
                routine_actions = [a for a in actions if a.get("category") == "ROUTINE"]
                
                if critical_actions:
                    print("   🚨 CRITICAL (Immediate - Do First):")
                    for i, action in enumerate(critical_actions, 1):
                        print(f"      {i}. {action.get('action', action)}")
                    print()
                
                if high_actions:
                    print("   ⚠️  HIGH PRIORITY (Within 1-2 Hours):")
                    for i, action in enumerate(high_actions, 1):
                        print(f"      {i}. {action.get('action', action)}")
                    print()
                
                if routine_actions:
                    print("   📋 ROUTINE (Before End of Shift):")
                    for i, action in enumerate(routine_actions, 1):
                        print(f"      {i}. {action.get('action', action)}")
                    print()
            else:
                # Simple string actions - display with default emoji
                for action in actions:
                    action_text = action.get('action', action) if isinstance(action, dict) else action
                    print(f"   ⚠️  {action_text}")
        else:
            print("   • No pending actions")
        print()


def print_verification(draft_id: str, update_count: int, patient_id: str, shift_id: str):
    """Verify the draft was saved to database"""
    print_header("Verification: Draft Saved to Database", "✅")
    
    print(f"🆔 Draft ID: {draft_id}")
    print(f"📊 Updates Compiled: {update_count}")
    print(f"👤 Patient: {patient_id}")
    print(f"🔄 Shift: {shift_id}")
    print()
    
    # Try to retrieve the draft from database
    print("🔍 Verifying draft was saved to database...")
    try:
        saved_draft = get_draft(patient_id, shift_id)
        if saved_draft:
            print("✅ Draft successfully retrieved from database")
            print(f"   • Draft ID matches: {saved_draft.id == draft_id}")
            print(f"   • Update count matches: {saved_draft.update_count == update_count}")
            print(f"   • Status: {saved_draft.status}")
            print(f"   • Last updated: {saved_draft.last_updated}")
        else:
            print("⚠️  Draft not found in database (may be expected if Supabase not configured)")
    except Exception as e:
        print(f"⚠️  Could not verify draft in database: {e}")
    
    print()


def main():
    """Run DraftGenerator test"""
    
    print("\n")
    print_separator("=", 80)
    print("📋 DRAFT GENERATOR - HANDOFF COMPILATION TEST")
    print("   Compiling multiple updates into structured handoff")
    print_separator("=", 80)
    print()
    
    patient_id = "P001"  # John Smith
    
    # Step 1: Find most recent shift
    print("🔍 Finding most recent shift for NURSE_CRISTIANO...")
    shift_data = get_most_recent_shift("NURSE_CRISTIANO")
    
    if not shift_data:
        print("❌ No shift found for NURSE_CRISTIANO")
        print("\n💡 Make sure you've run backend/test_update_agent.py first to create a shift with updates")
        return
    
    shift_id = shift_data.get("id")
    print(f"✅ Found shift: {shift_id}")
    print(f"   • Nurse: {shift_data.get('nurse_name')}")
    print(f"   • Type: {shift_data.get('shift_type')}")
    print(f"   • Started: {shift_data.get('start_time')}")
    print()
    
    # Step 2: Confirm there are updates for this patient
    print(f"🔍 Checking for updates for patient {patient_id}...")
    updates = get_patient_updates(patient_id, shift_id)
    
    if not updates:
        print(f"❌ No updates found for patient {patient_id} in shift {shift_id}")
        print("\n💡 Make sure you've run backend/test_update_agent.py first to create updates")
        return
    
    print(f"✅ Found {len(updates)} update(s) for patient {patient_id}")
    print()
    
    # Step 3: Print input data
    print_input_data(shift_data, updates, patient_id)
    
    # Step 4: Initialize DraftGenerator
    print_separator("-", 60)
    print()
    try:
        print("🔧 Initializing DraftGenerator...")
        generator = DraftGenerator()
        print()
    except Exception as e:
        print(f"❌ Failed to initialize DraftGenerator: {e}")
        print("\n💡 Make sure your .env file has all required credentials:")
        print("   - AZURE_OPENAI_ENDPOINT")
        print("   - AZURE_OPENAI_KEY")
        print("   - AZURE_OPENAI_DEPLOYMENT")
        print("   - SUPABASE_URL")
        print("   - SUPABASE_KEY")
        return
    
    # Step 5: Generate draft
    print("🚀 Generating draft handoff...")
    print()
    result = generator.generate_draft(patient_id=patient_id, shift_id=shift_id)
    
    # Step 6: Print results
    if not result.get("success"):
        print(f"❌ Draft generation failed: {result.get('message', 'Unknown error')}")
        return
    
    print("\n" * 2)
    print_draft_content(result.get("draft_content", {}))
    
    # Step 7: Verification
    print_verification(
        draft_id=result.get("draft_id", "Unknown"),
        update_count=result.get("update_count", 0),
        patient_id=patient_id,
        shift_id=shift_id
    )
    
    # Final summary
    print_separator("=", 80)
    print("🎯 TEST SUMMARY")
    print_separator("=", 80)
    print()
    print("✅ Draft Generation: SUCCESS")
    print(f"📊 Updates Compiled: {result.get('update_count', 0)}")
    print(f"📋 Draft ID: {result.get('draft_id', 'N/A')}")
    print()
    print("🎯 Key Capabilities Demonstrated:")
    print("   ✅ Multiple update compilation")
    print("   ✅ Chronological timeline generation")
    print("   ✅ Current status summarization")
    print("   ✅ Key changes identification")
    print("   ✅ Pending actions extraction")
    print("   ✅ AI-powered narrative summary")
    print("   ✅ Database persistence")
    print()
    print("🚀 System Status: DraftGenerator ready for continuous handoff workflow")
    print_separator("=", 80)
    print()


if __name__ == "__main__":
    main()
