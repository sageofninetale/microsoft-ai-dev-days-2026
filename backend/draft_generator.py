"""
Draft Generator - Compiles multiple patient updates into structured handoff drafts.
Aggregates updates throughout a shift and generates AI-powered narrative summaries.
"""

from __future__ import annotations
import os
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
import json

# Azure imports
from openai import AzureOpenAI

# Local imports
from backend.models import DraftHandoff, PatientUpdate
from backend.database import get_patient_updates, get_patient, save_draft

# Load environment variables
load_dotenv()


class DraftGeneratorError(Exception):
    """Custom exception for DraftGenerator errors"""
    pass


class DraftGenerator:
    """
    Compiles multiple patient updates into structured handoff drafts.
    Uses Azure OpenAI to generate intelligent narrative summaries.
    """
    
    def __init__(self):
        """Initialize DraftGenerator with Azure OpenAI client"""
        # Azure OpenAI setup
        self.openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.openai_key = os.getenv("AZURE_OPENAI_KEY")
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
        
        if not all([self.openai_endpoint, self.openai_key, self.deployment]):
            raise DraftGeneratorError("Missing Azure OpenAI credentials in environment variables")
        
        self.openai_client = AzureOpenAI(
            azure_endpoint=self.openai_endpoint,
            api_key=self.openai_key,
            api_version="2024-08-01-preview"
        )
        
        print("✅ DraftGenerator initialized")
    
    def _organize_updates(self, updates: List[PatientUpdate]) -> Dict[str, Any]:
        """
        Organize updates by type and chronological order.
        
        Args:
            updates: List of PatientUpdate objects
        
        Returns:
            Dictionary with organized updates
        """
        # Sort by timestamp
        sorted_updates = sorted(updates, key=lambda u: u.timestamp)
        
        # Group by type
        organized = {
            "medication": [],
            "vital_signs": [],
            "procedure": [],
            "general": [],
            "all_chronological": []
        }
        
        for update in sorted_updates:
            update_type = update.update_type
            
            # Add to type-specific list
            if update_type in organized:
                organized[update_type].append(update)
            else:
                organized["general"].append(update)
            
            # Add to chronological list
            organized["all_chronological"].append({
                "timestamp": update.timestamp.strftime("%I:%M %p") if hasattr(update.timestamp, 'strftime') else str(update.timestamp),
                "type": update_type,
                "transcription": update.transcription,
                "extracted_data": update.extracted_data
            })
        
        return organized
    
    def _generate_handoff_summary(
        self,
        patient_data: dict,
        organized_updates: Dict[str, Any],
        update_count: int
    ) -> Dict[str, Any]:
        """
        Use Azure OpenAI to generate structured handoff summary.
        
        Args:
            patient_data: Patient EMR data
            organized_updates: Organized updates by type
            update_count: Total number of updates
        
        Returns:
            Dictionary with structured handoff content
        """
        try:
            # Prepare context for AI
            patient_name = patient_data.get("name", "Unknown Patient")
            patient_room = patient_data.get("room", "Unknown")
            patient_age = patient_data.get("age", "Unknown")
            emr_medications = patient_data.get("medications", [])
            emr_allergies = patient_data.get("allergies", [])
            
            # Format updates for AI prompt
            updates_text = ""
            for update_info in organized_updates["all_chronological"]:
                updates_text += f"\n• {update_info['timestamp']} - {update_info['transcription'][:200]}"
            
            system_prompt = """You are a clinical handoff documentation assistant. 
Your task is to generate a structured handoff summary from nurse shift updates.

CRITICAL FORMATTING RULES:

MEDICATIONS - Use clinical notation:
- Format: "MedicationName Dose Route Frequency"
- Routes: PO (oral), IV (intravenous), SubQ (subcutaneous), IM (intramuscular)
- Frequency: daily, BID (twice daily), TID (three times daily), QID (four times daily), QHS (at bedtime), PRN (as needed), continuous
- Example: "Aspirin 81mg PO daily" or "Heparin 1000 units/hour IV continuous"

RISK FLAGS - Add severity indicators:
🔴 CRITICAL - Life-threatening: elevated troponin (MI risk), severe bleeding, SpO2 <90%, SBP >180 or <90
🟡 MODERATE - Concerning: elevated BP (140-179 SBP), temp >100.4°F, pain >7/10, new medications
🟢 NORMAL - Stable: vitals within normal range, pain controlled, patient comfortable

Apply flags to timeline events and key changes based on clinical significance.

PENDING ACTIONS - Categorize by urgency:
🚨 CRITICAL (Immediate - Do First): Medication administration/monitoring, bleeding monitoring, critical lab follow-up
⚠️ HIGH PRIORITY (Within 1-2 Hours): Lab verification, vital monitoring, pre-procedure prep, consultant follow-up
📋 ROUTINE (Before End of Shift): Documentation, scheduling confirmation, family communication

For each pending action, include:
{"action": "description", "category": "CRITICAL|HIGH|ROUTINE", "urgency_emoji": "🚨|⚠️|📋"}

JSON STRUCTURE REQUIRED:

1. "timeline": Array of events with risk flags where appropriate
   - Format: "🔴 • HH:MM AM/PM - Critical event" or "• HH:MM AM/PM - Normal event"

2. "current_status": Object with:
   - "medications": Array of strings in clinical notation ("Drug Dose Route Frequency")
   - "latest_vitals": Object with values AND risk flags if abnormal
   - "overall_condition": Brief 1-2 sentence summary

3. "key_changes": Array of changes with risk flags
   - Format: "🔴 Critical change description" or "🟡 Moderate change description"

4. "pending_actions": Array of objects sorted CRITICAL > HIGH > ROUTINE
   - Format: [{"action": "...", "category": "CRITICAL", "urgency_emoji": "🚨"}, ...]

Use proper medical terminology. Be concise but complete. Focus on actionable information."""

            user_prompt = f"""Generate a structured handoff summary for this patient:

PATIENT INFORMATION:
- Name: {patient_name}
- Room: {patient_room}
- Age: {patient_age}
- Known Allergies: {', '.join(emr_allergies) if emr_allergies else 'None documented'}
- EMR Medications: {', '.join([str(m) for m in emr_medications]) if emr_medications else 'None'}

SHIFT UPDATES ({update_count} total):
{updates_text}

Generate the structured handoff summary as JSON with all formatting enhancements (clinical notation for meds, risk flags, categorized pending actions)."""

            print(f"🤖 Generating AI-powered handoff summary...")
            
            response = self.openai_client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            summary = json.loads(response.choices[0].message.content)
            print(f"✅ Generated handoff summary with {len(summary.get('timeline', []))} timeline events")
            
            return summary
            
        except Exception as e:
            print(f"❌ Error generating AI summary: {e}")
            # Return fallback structure
            return {
                "timeline": [f"• {u['timestamp']} - {u['transcription'][:100]}" 
                            for u in organized_updates["all_chronological"]],
                "current_status": {
                    "medications": patient_data.get("medications", []),
                    "latest_vitals": {},
                    "overall_condition": "See individual updates for details"
                },
                "key_changes": ["See timeline for all changes"],
                "pending_actions": [{"action": "Review all updates for pending tasks", "category": "ROUTINE", "urgency_emoji": "📋"}]
            }
    
    def generate_draft(self, patient_id: str, shift_id: str) -> Dict[str, Any]:
        """
        Generate a draft handoff by compiling all updates for a patient during a shift.
        
        Args:
            patient_id: ID of the patient
            shift_id: ID of the shift
        
        Returns:
            Dictionary with draft generation results
        """
        try:
            print(f"\n{'='*60}")
            print(f"📋 Generating draft handoff for patient {patient_id}")
            print(f"🔄 Shift ID: {shift_id}")
            print(f"{'='*60}\n")
            
            # Step 1: Fetch all updates for this patient during this shift
            print(f"🔍 Fetching updates for patient {patient_id}...")
            updates = get_patient_updates(patient_id, shift_id)
            
            if not updates:
                return {
                    "success": False,
                    "message": "No updates found for this patient during this shift",
                    "error": "No updates available"
                }
            
            print(f"✅ Found {len(updates)} update(s)")
            
            # Step 2: Fetch patient EMR data
            print(f"🔍 Fetching EMR data for patient {patient_id}...")
            patient_data = get_patient(patient_id)
            
            if not patient_data:
                print(f"⚠️  Warning: Could not fetch patient {patient_id} from EMR")
                patient_data = {
                    "name": "Unknown Patient",
                    "room": "Unknown",
                    "age": "Unknown",
                    "medications": [],
                    "allergies": []
                }
            else:
                print(f"✅ Retrieved EMR for {patient_data.get('name', 'Unknown')}")
            
            # Step 3: Organize updates
            print(f"📊 Organizing updates by type and time...")
            organized_updates = self._organize_updates(updates)
            
            print(f"   • Medication updates: {len(organized_updates['medication'])}")
            print(f"   • Vital signs updates: {len(organized_updates['vital_signs'])}")
            print(f"   • Procedure updates: {len(organized_updates['procedure'])}")
            print(f"   • General updates: {len(organized_updates['general'])}")
            
            # Step 4: Generate AI-powered summary
            draft_content = self._generate_handoff_summary(
                patient_data,
                organized_updates,
                len(updates)
            )
            
            # Step 5: Create DraftHandoff object
            draft_id = str(uuid.uuid4())
            draft_handoff = DraftHandoff(
                id=draft_id,
                shift_id=shift_id,
                patient_id=patient_id,
                draft_content=draft_content,
                update_count=len(updates),
                last_updated=datetime.now(),
                status="draft"
            )
            
            # Step 6: Save draft to database
            print(f"💾 Saving draft to database...")
            saved_id = save_draft(draft_handoff)
            
            if not saved_id:
                return {
                    "success": False,
                    "message": "Failed to save draft to database",
                    "error": "Database save failed"
                }
            
            # Step 7: Return success result
            print(f"\n{'='*60}")
            print(f"✅ Draft handoff generated successfully!")
            print(f"   Draft ID: {draft_id}")
            print(f"   Updates included: {len(updates)}")
            print(f"   Timeline events: {len(draft_content.get('timeline', []))}")
            print(f"   Key changes: {len(draft_content.get('key_changes', []))}")
            print(f"   Pending actions: {len(draft_content.get('pending_actions', []))}")
            print(f"{'='*60}\n")
            
            return {
                "success": True,
                "draft_id": draft_id,
                "patient_id": patient_id,
                "update_count": len(updates),
                "draft_content": draft_content,
                "message": "Draft generated successfully"
            }
            
        except Exception as e:
            print(f"❌ Error generating draft: {e}")
            return {
                "success": False,
                "message": f"Error generating draft: {str(e)}",
                "error": str(e)
            }
