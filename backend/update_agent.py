"""
Update Agent - Processes individual nurse updates throughout the shift.
Transcribes audio, extracts structured data, verifies against EMR, and saves to database.
"""

from __future__ import annotations
import os
import re
import uuid
import concurrent.futures
from datetime import datetime
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import json

import requests

from llm_client import ask_llm

# Local imports
from models import PatientUpdate
from database import save_update, get_patient
from verification_agent import VerificationAgent

# Load environment variables
load_dotenv()


class UpdateAgentError(Exception):
    """Custom exception for UpdateAgent errors"""
    pass


class UpdateAgent:
    """
    Processes individual nurse updates during a shift.
    Handles audio transcription, data extraction, EMR verification, and database storage.
    """
    
    def __init__(self):
        """Initialize UpdateAgent — LLM calls go through llm_client.ask_llm()"""
        print("✅ UpdateAgent initialized")

        # Deepgram Speech-to-Text
        self.deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
        if not self.deepgram_api_key:
            print("⚠️  Warning: DEEPGRAM_API_KEY not set. Audio transcription will not work.")
        else:
            print(f"✅ Deepgram Nova-2 Medical configured.")
        
        # Initialize verification agent
        try:
            self.verification_agent = VerificationAgent()
            print("✅ UpdateAgent initialized with verification support")
        except Exception as e:
            print(f"⚠️  Warning: Could not initialize VerificationAgent: {e}")
            self.verification_agent = None
    
    def _normalize_clinical_text(self, text: str) -> str:
        """Normalize spoken clinical shorthand into standard notation."""
        # Fix split 3-digit numbers first: "1 20" → "120", "1 80" → "180"
        text = re.sub(r'\b([1-3])\s+(\d{2})\b', r'\1\2', text)
        # "120 by 80" → "120/80" (blood pressure)
        text = re.sub(r'(\d{2,3})\s+[Bb]y\s+(\d{2,3})', r'\1/\2', text)
        # "98 degree(s) Fahrenheit" → "98°F"
        text = re.sub(r'(\d+(?:\.\d+)?)\s+degrees?\s+[Ff]ahrenheit', r'\1°F', text, flags=re.IGNORECASE)
        # "36 degree(s) Celsius" → "36°C"
        text = re.sub(r'(\d+(?:\.\d+)?)\s+degrees?\s+[Cc]elsius', r'\1°C', text, flags=re.IGNORECASE)
        # "98 degree(s)" (no unit) → "98°"
        text = re.sub(r'(\d+(?:\.\d+)?)\s+degrees?(?!\s*[FfCc])', r'\1°', text, flags=re.IGNORECASE)
        # "98 percent" → "98%"
        text = re.sub(r'(\d+)\s+[Pp]ercent', r'\1%', text)
        # "beats per minute" → "bpm"
        text = re.sub(r'beats\s+per\s+minute', 'bpm', text, flags=re.IGNORECASE)
        return text

    def _transcribe_audio(self, audio_path: str) -> Optional[str]:
        """Transcribe audio using Deepgram Nova-2 Medical."""
        if not self.deepgram_api_key:
            print("❌ DEEPGRAM_API_KEY not configured")
            return None

        try:
            with open(audio_path, "rb") as f:
                audio_bytes = f.read()

            print(f"🎤 Sending audio to Deepgram Nova-2 Medical...")
            response = requests.post(
                "https://api.deepgram.com/v1/listen",
                headers={
                    "Authorization": f"Token {self.deepgram_api_key}",
                    "Content-Type": "audio/wav",
                },
                params={
                    "model": "nova-2-medical",
                    "smart_format": "true",
                    "numerals": "true",
                    "language": "en",
                },
                data=audio_bytes,
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()

            transcription = (
                result["results"]["channels"][0]["alternatives"][0]["transcript"].strip()
            )
            if transcription:
                transcription = self._normalize_clinical_text(transcription)
                print(f"✅ Deepgram transcription: {len(transcription)} characters")
                return transcription

            print("❌ Deepgram returned empty transcription")
            return None

        except Exception as e:
            print(f"❌ Error calling Deepgram: {e}")
            return None
    
    def _extract_update_data(self, transcription: str, update_type: str) -> Dict[str, Any]:
        """
        Extract structured data from update transcription using LLM.
        
        Args:
            transcription: Text of the update
            update_type: Type of update (vital_signs/medication/procedure/general)
        
        Returns:
            Dictionary with extracted structured data
        """
        system_prompt = """You are a clinical data extraction assistant.
Extract structured information from nurse's patient updates.

CRITICAL: You MUST analyze the content and determine the CORRECT event_type based on what is actually described, NOT based on what the user selected.

EVENT TYPE CLASSIFICATION RULES:
- medication: Mentions giving/administering/starting/stopping drugs, IV drips, medications
- vital_signs: Contains NUMBERS for HR, BP, temperature, SpO2, respiratory rate, or pain score
- procedure: Mentions procedures, imaging (x-ray, CT, MRI), surgery, tests, consultations, specialist visits
- lab_result: Lab values, blood work results, culture results
- assessment: Patient assessment, condition evaluation, physical exam findings
- general: Observations, ambulation, family visits, patient comfort, positioning

EXAMPLES:
- "Started heparin drip at 1000 units/hour" → medication
- "HR 88, BP 142/85, temp 98.9" → vital_signs  
- "Patient taken to radiology for chest x-ray" → procedure
- "Cardiology consulted for elevated troponin" → procedure
- "Patient ambulated to bathroom with assistance" → general

Extract these fields:
1. timestamp: Any mentioned time (e.g., "11 AM", "2:30 PM") or "current" if not mentioned
2. event_type: Analyze content and choose: medication, vital_signs, procedure, lab_result, assessment, or general (IGNORE user's suggested type)
3. description: A clear, concise summary of the update
4. mentioned_medications: List of any medications mentioned (name and dose if available)
5. mentioned_vitals: Dict of vital signs (bp, hr, temp, spo2, rr, pain)
6. mentioned_events: List of procedures, doctor visits, treatments, or other events

Return ONLY valid JSON. Be precise and extract all clinical details."""

        user_prompt = f"""Nurse suggested type: {update_type} (but analyze content to determine ACTUAL type)

Transcription:
{transcription}

Extract the structured data as JSON. Make sure event_type reflects what is ACTUALLY described in the text."""

        print(f"🤖 Extracting structured data from update...")

        # No try/except — a failed extraction must surface as a failed update
        # submission (process_update()'s outer try/except already returns
        # success: False), not a fabricated minimal record that looks like a
        # real extraction with everything simply defaulted to empty/current.
        extracted_data = ask_llm(system_prompt, user_prompt)
        print(f"✅ Extracted data: {extracted_data.get('event_type', 'unknown')} event")

        return extracted_data


    def _verify_update(self, extracted_data: Dict[str, Any], patient_data: dict) -> Dict[str, Any]:
        """
        Verify update data against patient EMR.
        
        Args:
            extracted_data: Structured data from update
            patient_data: Patient EMR data
        
        Returns:
            Verification results with any discrepancies found
        """
        verification_issues = []
        emr_verified = True
        
        try:
            # Check medications against EMR
            mentioned_meds = extracted_data.get("mentioned_medications", [])
            emr_meds = patient_data.get("medications", [])
            
            if mentioned_meds and emr_meds:
                for med in mentioned_meds:
                    # Simple name matching (could be improved)
                    med_name = med.get("name", med) if isinstance(med, dict) else med
                    med_name_lower = med_name.lower()
                    
                    # Check if medication is in EMR
                    found = False
                    for emr_med in emr_meds:
                        if isinstance(emr_med, dict):
                            emr_med_name = emr_med.get("name", "").lower()
                        else:
                            emr_med_name = str(emr_med).lower()
                        
                        if med_name_lower in emr_med_name or emr_med_name in med_name_lower:
                            found = True
                            break
                    
                    if not found:
                        verification_issues.append({
                            "type": "MEDICATION_NOT_IN_EMR",
                            "severity": "HIGH",
                            "finding": f"Medication '{med_name}' not found in patient's current medication list",
                            "details": f"Mentioned in update but not in EMR"
                        })
                        emr_verified = False
            
            # Check vital signs for reasonableness
            mentioned_vitals = extracted_data.get("mentioned_vitals", {})
            
            if mentioned_vitals:
                # Blood pressure check
                bp = mentioned_vitals.get("bp") or mentioned_vitals.get("blood_pressure")
                if bp:
                    # Basic BP validation (could be more sophisticated)
                    bp_str = str(bp)
                    if "/" in bp_str:
                        try:
                            systolic, diastolic = bp_str.split("/")
                            systolic = int(systolic.strip())
                            diastolic = int(diastolic.strip())
                            
                            if systolic < 70 or systolic > 250:
                                verification_issues.append({
                                    "type": "VITAL_OUT_OF_RANGE",
                                    "severity": "CRITICAL",
                                    "finding": f"Systolic BP {systolic} is outside normal range",
                                    "details": "May indicate critical condition or data entry error"
                                })
                                emr_verified = False
                            
                            if diastolic < 40 or diastolic > 150:
                                verification_issues.append({
                                    "type": "VITAL_OUT_OF_RANGE",
                                    "severity": "CRITICAL",
                                    "finding": f"Diastolic BP {diastolic} is outside normal range",
                                    "details": "May indicate critical condition or data entry error"
                                })
                                emr_verified = False
                        except ValueError:
                            pass
                
                # Heart rate check
                hr = mentioned_vitals.get("hr") or mentioned_vitals.get("heart_rate")
                if hr:
                    try:
                        hr_val = int(str(hr).strip())
                        if hr_val < 30 or hr_val > 200:
                            verification_issues.append({
                                "type": "VITAL_OUT_OF_RANGE",
                                "severity": "CRITICAL",
                                "finding": f"Heart rate {hr_val} is outside normal range",
                                "details": "May indicate critical condition or data entry error"
                            })
                            emr_verified = False
                    except ValueError:
                        pass
                
                # Temperature check
                temp = mentioned_vitals.get("temp") or mentioned_vitals.get("temperature")
                if temp:
                    try:
                        temp_val = float(str(temp).strip())
                        if temp_val < 95 or temp_val > 106:
                            verification_issues.append({
                                "type": "VITAL_OUT_OF_RANGE",
                                "severity": "CRITICAL",
                                "finding": f"Temperature {temp_val}°F is outside normal range",
                                "details": "May indicate critical condition or data entry error"
                            })
                            emr_verified = False
                    except ValueError:
                        pass
            
            # Use VerificationAgent for more comprehensive checking if available
            if self.verification_agent and verification_issues:
                print(f"⚠️  Found {len(verification_issues)} potential issues")
            
            return {
                "emr_verified": emr_verified,
                "issues": verification_issues,
                "checked_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Error during verification: {e}")
            return {
                "emr_verified": False,
                "issues": [{
                    "type": "VERIFICATION_ERROR",
                    "severity": "MEDIUM",
                    "finding": "Could not complete EMR verification",
                    "details": str(e)
                }],
                "checked_at": datetime.now().isoformat()
            }
    
    def process_update(
        self,
        audio_or_text: str,
        patient_id: str,
        nurse_id: str,
        shift_id: str,
        update_type: str = "general",
        is_audio: bool = False
    ) -> Dict[str, Any]:
        """
        Process a patient update from audio or text.
        
        Args:
            audio_or_text: Path to audio file or text update
            patient_id: ID of the patient
            nurse_id: ID of the nurse making the update
            shift_id: ID of the current shift
            update_type: Type of update (vital_signs/medication/procedure/general)
            is_audio: Whether input is audio file (True) or text (False)
        
        Returns:
            Dictionary with processing results
        """
        try:
            print(f"\n{'='*60}")
            print(f"🏥 Processing update for patient {patient_id}")
            print(f"👨‍⚕️ Nurse: {nurse_id} | Shift: {shift_id}")
            print(f"📝 Type: {update_type}")
            print(f"{'='*60}\n")
            
            # Step 1: Get transcription
            if is_audio:
                transcription = self._transcribe_audio(audio_or_text)
                if not transcription:
                    return {
                        "success": False,
                        "message": "Failed to transcribe audio",
                        "error": "Audio transcription failed"
                    }
            else:
                transcription = audio_or_text
                print(f"📄 Using provided text ({len(transcription)} characters)")
            
            # Step 2: Extract structured data
            extracted_data = self._extract_update_data(transcription, update_type)
            
            # Step 3: Fetch patient EMR data
            print(f"🔍 Fetching EMR data for patient {patient_id}")
            patient_data = get_patient(patient_id)
            
            if not patient_data:
                print(f"⚠️  Warning: Could not fetch patient {patient_id} from EMR")
                patient_data = {}  # Continue anyway with empty EMR
            else:
                print(f"✅ Retrieved EMR for {patient_data.get('name', 'Unknown')}")
            
            # Step 4: Verify update against EMR
            verification_results = self._verify_update(extracted_data, patient_data)
            
            # Step 5: Create PatientUpdate object
            update_id = str(uuid.uuid4())
            patient_update = PatientUpdate(
                id=update_id,
                shift_id=shift_id,
                patient_id=patient_id,
                nurse_id=nurse_id,
                timestamp=datetime.now(),
                update_type=extracted_data.get("event_type", update_type),
                transcription=transcription,
                audio_url=audio_or_text if is_audio else None,
                extracted_data=extracted_data,
                emr_verified=verification_results["emr_verified"],
                verification_notes=verification_results
            )
            
            # Step 6: Save to database
            print(f"💾 Saving update to database...")
            saved_id = save_update(patient_update)
            
            if not saved_id:
                return {
                    "success": False,
                    "message": "Failed to save update to database",
                    "error": "Database save failed"
                }
            
            # Step 7: Return success result
            print(f"\n{'='*60}")
            print(f"✅ Update processed successfully!")
            print(f"   Update ID: {update_id}")
            print(f"   EMR Verified: {'✓' if verification_results['emr_verified'] else '✗'}")
            print(f"   Issues Found: {len(verification_results['issues'])}")
            print(f"{'='*60}\n")
            
            return {
                "success": True,
                "update_id": update_id,
                "transcription": transcription,
                "extracted_data": extracted_data,
                "emr_verified": verification_results["emr_verified"],
                "verification_issues": verification_results["issues"],
                "message": "Update saved successfully"
            }
            
        except Exception as e:
            print(f"❌ Error processing update: {e}")
            return {
                "success": False,
                "message": f"Error processing update: {str(e)}",
                "error": str(e)
            }
