"""
Draft Generator - Compiles multiple patient updates into structured handoff drafts.
Aggregates updates throughout a shift and generates AI-powered narrative summaries.
"""

from __future__ import annotations
import os
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
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
    
    async def _generate_timeline_async(
        self,
        patient_data: dict,
        organized_updates: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate timeline events with severity classification (async).
        
        Args:
            patient_data: Patient EMR data
            organized_updates: Organized updates by type
        
        Returns:
            List of timeline events with severity markers
        """
        def _sync_timeline_call():
            import time
            try:
                start = time.time()
                updates_text = ""
                for update_info in organized_updates["all_chronological"]:
                    updates_text += f"\n• {update_info['timestamp']} - {update_info['transcription'][:200]}"
                
                system_prompt = """You are a clinical timeline analyzer. Generate a chronological timeline with severity classification.

SEVERITY LEVELS:
🔴 RED (CRITICAL): SpO2 <90%, HR >120/<50, SBP >180/<90, Temp >103°F, active bleeding, chest pain
🟠 ORANGE (HIGH RISK): Dual anticoagulation, abnormal vitals trending worse (BP 160-179/100-109, HR 100-120, SpO2 90-93%)
🟡 YELLOW (CAUTION): New meds not in EMR, mild abnormal vitals (BP 140-159 SBP, Temp 100.4-102°F, Pain 6-7/10)
🟢 GREEN (VERIFIED): Meds in EMR, vitals normal, pain controlled (<5/10), stable
🔵 BLUE (INFO): Comfort measures, family updates, routine care
⚪ GRAY (ADMIN): Shift changes, room transfers, general observations

Return a JSON object with a single key "timeline" whose value is the array:
{
  "timeline": [
    {
      "time": "HH:MM AM/PM",
      "event": "Brief description",
      "severity": "RED|ORANGE|YELLOW|GREEN|BLUE|GRAY",
      "icon": "🔴|🟠|🟡|🟢|🔵|⚪"
    }
  ]
}"""

                user_prompt = f"""Patient: {patient_data.get('name', 'Unknown')} (Age {patient_data.get('age', '?')})
Allergies: {', '.join(patient_data.get('allergies', [])) if patient_data.get('allergies') else 'None'}

UPDATES:
{updates_text}

Generate timeline with severity classification."""

                response = self.openai_client.chat.completions.create(
                    model=self.deployment,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                
                elapsed = time.time() - start
                print(f"   📅 Timeline call: {elapsed:.2f}s")
                
                result = json.loads(response.choices[0].message.content)
                timeline = result.get("timeline")
                if timeline is None:
                    timeline = next((v for v in result.values() if isinstance(v, list)), [])
                return timeline
                
            except Exception as e:
                print(f"⚠️ Timeline generation error: {e}")
                return [{"time": u['timestamp'], "event": u['transcription'][:100], "severity": "GRAY", "icon": "⚪"} 
                       for u in organized_updates["all_chronological"]]
        
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(executor, _sync_timeline_call)
    
    async def _generate_clinical_status_async(
        self,
        patient_data: dict,
        organized_updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate current clinical status, vitals, and medication analysis (async).
        
        Args:
            patient_data: Patient EMR data
            organized_updates: Organized updates by type
        
        Returns:
            Dictionary with current_status, safety_alerts, key_changes
        """
        try:
            emr_medications = patient_data.get("medications", [])
            emr_allergies = patient_data.get("allergies", [])
            
            updates_text = ""
            for update_info in organized_updates["all_chronological"]:
                updates_text += f"\n• {update_info['timestamp']} - {update_info['transcription'][:200]}"
            
            system_prompt = """You are a clinical status analyzer. Extract current status, vitals, medications, and safety alerts.

MEDICATION STATUS:
- VERIFIED (🟢): In EMR, safe dose, no interactions
- NEW (🟡): Not in EMR yet, needs verification
- CONFLICTING (🔴): Drug interaction, allergy, dosing error

VITAL SEVERITY:
- RED (🔴): HR >120/<50, BP >180/<90 or <90/<60, Temp >103°F, SpO2 <90%, RR >30/<10
- YELLOW (🟡): HR 100-120/50-60, BP 140-179/90-109, Temp 100.4-102°F, SpO2 90-93%, Pain 6-7/10
- GREEN (🟢): Normal ranges

Return JSON:
{
  "current_status": {
    "medications": [
      {
        "name": "MedicationName",
        "dose": "Dose",
        "route": "PO|IV|SubQ|IM",
        "frequency": "daily|BID|TID|QID|PRN|continuous",
        "status": "VERIFIED|NEW|CONFLICTING",
        "severity": "RED|YELLOW|GREEN",
        "icon": "🔴|🟡|🟢",
        "display": "MedicationName Dose Route Frequency"
      }
    ],
    "latest_vitals": {
      "hr": {"value": "X bpm", "severity": "RED|YELLOW|GREEN", "icon": "🔴|🟡|🟢"},
      "bp": {"value": "X/X mmHg", "severity": "RED|YELLOW|GREEN", "icon": "🔴|🟡|🟢"},
      "temp": {"value": "X°F", "severity": "RED|YELLOW|GREEN", "icon": "🔴|🟡|🟢"},
      "spo2": {"value": "X%", "severity": "RED|YELLOW|GREEN", "icon": "🔴|🟡|🟢"},
      "pain": {"value": "X/10", "severity": "RED|YELLOW|GREEN", "icon": "🔴|🟡|🟢"}
    },
    "overall_condition": "1-2 sentence summary"
  },
  "safety_alerts": [
    {
      "type": "DRUG_INTERACTION|ABNORMAL_VITAL|ALLERGY|CRITICAL_LAB",
      "severity": "RED|ORANGE|YELLOW",
      "icon": "🔴|🟠|🟡",
      "message": "Detailed alert"
    }
  ],
  "key_changes": [
    {
      "change": "Description",
      "severity": "RED|ORANGE|YELLOW|GREEN|BLUE",
      "icon": "🔴|🟠|🟡|🟢|🔵"
    }
  ],
  "pending_actions": [
    {
      "action": "Description",
      "category": "CRITICAL|HIGH|ROUTINE",
      "severity": "RED|ORANGE|YELLOW",
      "icon": "🚨|⚠️|📋",
      "priority": 1|2|3
    }
  ]
}"""

            user_prompt = f"""Patient: {patient_data.get('name', 'Unknown')}
Age: {patient_data.get('age') or 'Unknown'}
Room: {patient_data.get('room_number') or patient_data.get('room') or 'Unknown'}
Allergies: {', '.join(emr_allergies) if emr_allergies else 'None'}
EMR Medications: {', '.join([str(m) for m in emr_medications]) if emr_medications else 'None'}

SHIFT UPDATES:
{updates_text}

Analyze current clinical status, medications, vitals, safety alerts, and pending actions."""

            import time
            start = time.time()
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.openai_client.chat.completions.create(
                    model=self.deployment,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"}
                )
            )
            
            elapsed = time.time() - start
            print(f"   🏥 Clinical status call: {elapsed:.2f}s")
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            print(f"⚠️ Clinical status error: {e}")
            return {
                "current_status": {
                    "medications": patient_data.get("medications", []),
                    "latest_vitals": {},
                    "overall_condition": "See updates for details"
                },
                "safety_alerts": [],
                "key_changes": ["See timeline"],
                "pending_actions": [{"action": "Review updates", "category": "ROUTINE", "icon": "📋", "priority": 3}]
            }
    
    async def _generate_narrative_async(
        self,
        patient_data: dict,
        organized_updates: Dict[str, Any],
        update_count: int
    ) -> str:
        """
        Generate narrative summary paragraph (async).
        
        Args:
            patient_data: Patient EMR data
            organized_updates: Organized updates by type
            update_count: Total update count
        
        Returns:
            150-250 word narrative paragraph
        """
        try:
            updates_text = ""
            for update_info in organized_updates["all_chronological"]:
                updates_text += f"\n• {update_info['timestamp']} - {update_info['transcription'][:200]}"
            
            emr_medications = patient_data.get("medications", [])
            emr_allergies = patient_data.get("allergies", [])
            
            system_prompt = """You are a clinical documentation specialist. Generate a professional narrative handoff paragraph (150-250 words).

STRUCTURE:
1. Opening: "PatientName (PatientID, Room XXX, Age XX) had a [stable/eventful/concerning] shift..."
2. Vital signs: "with vital signs [within normal limits / showing X] (HR X, BP X/X)."
3. Key events: "At HH:MM, [event]. "
4. Medication changes: Mention new/discontinued meds and EMR status
5. Pending items: "Blood work pending, [specialty] consulted for [reason]."
6. Status: "Patient remains [comfortable/stable/requiring monitoring] with [no acute changes / X concerns]."
7. Critical action: "Critical action required: [most urgent task]."

TONE: Conversational handoff style, professional, readable

EXAMPLE: "Willie Bennett (P056, Room 405, Age 72) had a stable shift with vital signs remaining within normal limits (HR 90, BP 120/90). At 02:00, the patient received paracetamol and aspirin for pain management, though these medications are not currently documented in the EMR and require reconciliation. Blood work is pending, and cardiothoracic surgery has been consulted for angiogram planning. The patient remains comfortable with no acute changes. Critical action required: Reconcile aspirin administration with medication record and assess bleeding risk given concurrent Warfarin therapy."

Return JSON: {"narrative_summary": "Your 150-250 word paragraph here"}"""

            user_prompt = f"""Patient: {patient_data.get('name', 'Unknown Patient')}
Patient ID: {patient_data.get('patient_id', 'Unknown')}
Room: {patient_data.get('room_number') or patient_data.get('room') or 'Unknown'}
Age: {patient_data.get('age') or 'Unknown'}
Allergies: {', '.join(emr_allergies) if emr_allergies else 'None'}
EMR Medications: {', '.join([str(m) for m in emr_medications]) if emr_medications else 'None'}

SHIFT UPDATES ({update_count} total):
{updates_text}

Generate 150-250 word narrative handoff summary."""

            import time
            start = time.time()
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.openai_client.chat.completions.create(
                    model=self.deployment,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"}
                )
            )
            
            elapsed = time.time() - start
            print(f"   📝 Narrative call: {elapsed:.2f}s")
            
            result = json.loads(response.choices[0].message.content)
            return result.get("narrative_summary", "See updates for details.")
            
        except Exception as e:
            print(f"⚠️ Narrative generation error: {e}")
            return f"Patient {patient_data.get('name', 'Unknown')} had {update_count} updates this shift. See timeline for details."
    
    async def _generate_handoff_summary_async(
        self,
        patient_data: dict,
        organized_updates: Dict[str, Any],
        update_count: int
    ) -> Dict[str, Any]:
        """
        Use Azure OpenAI to generate structured handoff summary with parallel API calls (async).
        
        Args:
            patient_data: Patient EMR data
            organized_updates: Organized updates by type
            update_count: Total number of updates
        
        Returns:
            Dictionary with structured handoff content
        """
        try:
            import time
            print(f"🤖 Generating AI-powered handoff summary (parallel mode)...")
            start_time = time.time()
            
            # Run 3 OpenAI calls in parallel for 60-70% speedup
            timeline, clinical_data, narrative = await asyncio.gather(
                self._generate_timeline_async(patient_data, organized_updates),
                self._generate_clinical_status_async(patient_data, organized_updates),
                self._generate_narrative_async(patient_data, organized_updates, update_count)
            )
            
            elapsed = time.time() - start_time
            print(f"⏱️  Parallel API calls completed in {elapsed:.2f}s")
            
            # Merge results into final structure
            summary = {
                "timeline": timeline,
                "current_status": clinical_data.get("current_status", {}),
                "safety_alerts": clinical_data.get("safety_alerts", []),
                "key_changes": clinical_data.get("key_changes", []),
                "pending_actions": clinical_data.get("pending_actions", []),
                "narrative_summary": narrative
            }
            
            print(f"✅ Generated handoff summary with {len(timeline)} timeline events (parallel optimization)")
            
            return summary
            
        except Exception as e:
            print(f"❌ Error generating AI summary: {e}")
            import traceback
            traceback.print_exc()
            # Return fallback structure
            return {
                "timeline": [{"time": u['timestamp'], "event": u['transcription'][:100], "severity": "GRAY", "icon": "⚪"} 
                            for u in organized_updates["all_chronological"]],
                "current_status": {
                    "medications": patient_data.get("medications", []),
                    "latest_vitals": {},
                    "overall_condition": "See individual updates for details"
                },
                "safety_alerts": [],
                "key_changes": [{"change": "See timeline for all changes", "severity": "BLUE", "icon": "🔵"}],
                "pending_actions": [{"action": "Review all updates for pending tasks", "category": "ROUTINE", "icon": "📋", "priority": 3}],
                "narrative_summary": f"Patient {patient_data.get('name', 'Unknown')} had {update_count} updates this shift. See timeline for details."
            }
    
    async def generate_draft(self, patient_id: str, shift_id: str) -> Dict[str, Any]:
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
            draft_content = await self._generate_handoff_summary_async(
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
