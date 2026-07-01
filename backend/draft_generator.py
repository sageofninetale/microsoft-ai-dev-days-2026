"""
Draft Generator - Compiles multiple patient updates into structured handoff drafts.
Aggregates updates throughout a shift and generates AI-powered narrative summaries.
"""

from __future__ import annotations
import os
import uuid
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
import json

from llm_client import ask_llm

# Local imports
from models import DraftHandoff, PatientUpdate
from database import get_patient_updates, get_patient, save_draft

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
        """Initialize DraftGenerator — LLM calls go through llm_client.ask_llm()"""
        print("✅ DraftGenerator initialized")
    
    def _sort_timeline_by_time(self, timeline: List[Dict]) -> List[Dict]:
        """Sort timeline events into strict chronological order after LLM generation."""
        from datetime import datetime

        def parse_time(event):
            try:
                return datetime.strptime(event.get('time', '12:00 AM').strip(), '%I:%M %p')
            except Exception:
                try:
                    return datetime.strptime(event.get('time', '00:00').strip(), '%H:%M')
                except Exception:
                    return datetime.min

        return sorted(timeline, key=parse_time)

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
        import time
        start = time.time()
        updates_text = ""
        for update_info in organized_updates["all_chronological"]:
            updates_text += f"\n• {update_info['timestamp']} - {update_info['transcription'][:200]}"

        system_prompt = """You are a clinical timeline analyzer. Generate a detailed chronological timeline with severity classification.

SEVERITY LEVELS — assign the HIGHEST applicable severity for each event (based on NHS NEWS2):
🔴 RED (CRITICAL): SpO2 91% or below | HR 131 or above, or 40 or below | SBP 90 or below, or 220 or above | Temp 102.3°F or above | active bleeding | chest pain | altered consciousness | confirmed respiratory distress
🟠 ORANGE (HIGH RISK): SpO2 92–93% | HR 111–130 or 41–50 | SBP 91–100 | drug-drug interactions | dual anticoagulation | held high-risk medications | pending critical lab results
🟡 YELLOW (CAUTION): SpO2 94–95% | HR 91–110 or 51–60 | SBP 101–110 | Temp 100.4–102.2°F | Pain 4–6/10 | new medications not in EMR | abnormal findings pending review
🟢 GREEN (VERIFIED): All vitals in normal range | medications in EMR administered as scheduled | pain 0–3/10 | stable condition confirmed
🟢 GREEN (VERIFIED): Medications in EMR administered safely as scheduled, normal vitals documented, pain controlled (<5/10), stable stable condition confirmed
🔵 BLUE (INFO): Comfort measures, family updates, patient education, repositioning, ambulation, oral care, routine care
⚪ GRAY (ADMIN): Shift handover only, room number changes, documentation corrections

SEVERITY EXAMPLES (use these to calibrate your judgement):
- "Warfarin 5mg PO given as scheduled" → GREEN (in EMR, safe)
- "Amlodipine 5mg held — BP 98/62 hypotensive" → ORANGE (held high-risk med + reason)
- "BP 98/62, HR 112, SpO2 91%, RR 26 with accessory muscle use" → RED (hypotension + tachycardia + low SpO2)
- "Omeprazole 20mg given — interacts with Warfarin" → ORANGE (drug interaction)
- "Family updated at bedside — agreed full code" → BLUE (communication)
- "Patient repositioned, comfortable" → BLUE (comfort care)
- "Chest X-ray ordered — results pending" → YELLOW (pending result)

IMPORTANT: GRAY is ONLY for pure administrative events (shift start/end, room transfers). Every clinical event — medication administration, vital recording, procedure, test, communication — must use RED/ORANGE/YELLOW/GREEN/BLUE based on clinical significance. Do NOT use GRAY for clinical events.

CRITICAL RULES FOR EVENT DESCRIPTIONS:
- Include EXACT medication names, doses, routes (e.g. "Warfarin 5mg PO administered as scheduled")
- Include EXACT vital values with units (e.g. "BP 98/62, HR 112, RR 26, Temp 100.4°F, SpO2 91% on 4L NC")
- Include clinical context (e.g. "patient short of breath at rest using accessory muscles")
- Include results and findings (e.g. "chest x-ray showing worsening bilateral infiltrates")
- Include who was notified and what was agreed (e.g. "family updated, agreed to full code status")
- Never write vague descriptions like "vitals recorded" — always include the actual values
- Never write "medication given" — always include name, dose, route

Return a JSON object with a single key "timeline" whose value is the array:
{
  "timeline": [
    {
      "time": "HH:MM AM/PM",
      "event": "Detailed clinical description with specific values, context, and outcomes",
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

        # No try/except here — ask_llm() raises on failure and that exception must
        # propagate up to generate_draft()'s outer handler, not be swallowed into a
        # fake "GRAY" timeline that looks like a successful, if boring, report.
        result = ask_llm(system_prompt, user_prompt)

        elapsed = time.time() - start
        print(f"   📅 Timeline call: {elapsed:.2f}s")

        timeline = result.get("timeline")
        if timeline is None:
            timeline = next((v for v in result.values() if isinstance(v, list)), [])
        return timeline

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
        emr_medications = patient_data.get("medications", [])
        emr_allergies = patient_data.get("allergies", [])

        updates_text = ""
        for update_info in organized_updates["all_chronological"]:
            updates_text += f"\n• {update_info['timestamp']} - {update_info['transcription'][:200]}"

        system_prompt = """You are a senior clinical safety analyst generating a nurse shift handoff report. Your job is to produce detailed, actionable safety alerts and pending actions that could prevent patient harm.

MEDICATION STATUS:
- VERIFIED (🟢): In EMR, administered safely as scheduled, no dosing error, no allergy conflict, not held/withheld
- NEW (🟡): Not in EMR yet, needs reconciliation
- CONFLICTING (🔴): A problem with THIS SPECIFIC medication — ANY of: allergy conflict | dosing error | medication was HELD or WITHHELD during this shift
- INTERACTION-VS-STATUS RULE: A drug-drug interaction with ANOTHER medication does NOT by itself make a medication's own status CONFLICTING. If a medication was administered correctly, as scheduled, with no dosing error, no allergy conflict, and was not held or withheld, its status stays VERIFIED even if it interacts with another drug the patient is on — document that interaction in safety_alerts only (see MANDATORY DRUG INTERACTION CHECKS below), never by changing either drug's own medication status. Example: Warfarin and Omeprazole are both given correctly as scheduled but interact via CYP2C19 — both stay VERIFIED in current_status.medications, and the interaction is reported once as a DRUG_INTERACTION safety alert.
- HELD MEDICATION RULE: If a medication was held or withheld for ANY reason (hypotension, clinical concern, etc.), it MUST be marked CONFLICTING and the display field MUST include "— Held: [reason]" (e.g. "Amlodipine 10mg oral daily — Held: hypotension BP 98/62")

VITAL SEVERITY — apply each threshold strictly per vital in isolation. Do NOT elevate a vital's colour based on the overall patient context; that belongs in Safety Alerts:

Heart Rate (bpm):
- RED (🔴): 130 or above, OR 40 or below
- ORANGE (🟠): 111 to 130, OR 41 to 50
- YELLOW (🟡): 91 to 110, OR 51 to 60 (mild tachycardia/bradycardia)
- GREEN (🟢): 61 to 90

Systolic Blood Pressure (mmHg) — READ CAREFULLY:
- RED (🔴): 90 OR BELOW, OR 220 or above — SBP must be 90 or lower to be RED
- ORANGE (🟠): 91 to 100 — SBP 91, 92, 93, 94, 95, 96, 97, 98, 99, 100 are ALL ORANGE not RED
- YELLOW (🟡): 101 to 110 (borderline low)
- GREEN (🟢): 111 to 219
- CRITICAL RULE: SBP 98 is ORANGE. SBP 91 is ORANGE. Only SBP 90 and below is RED.

Temperature (°F):
- RED (🔴): 102.3°F or above, OR 95.0°F or below
- YELLOW (🟡): 100.4°F to 102.2°F (low-grade to moderate fever)
- GREEN (🟢): 97.9°F to 100.3°F

SpO2 (%):
- RED (🔴): 91% or below
- ORANGE (🟠): 92% to 93%
- YELLOW (🟡): 94% to 95%
- GREEN (🟢): 96% or above
- NOTE: If patient is on supplemental oxygen, record that in the value (e.g. "91% on 4L NC") and escalate severity by one level

Pain (0–10):
- RED (🔴): 7 to 10 — severe, immediate intervention required
- YELLOW (🟡): 4 to 6 — moderate, medication review needed
- GREEN (🟢): 0 to 3 — mild or none, controlled
- GREEN (🟢): Not reported — use value "Not reported"

Calibration examples (use these to verify your judgement):
- HR 112 bpm → ORANGE (111 to 130 range)
- HR 128 bpm → ORANGE (111 to 130 range)
- HR 131 bpm → RED (130 or above)
- BP SBP 98 → ORANGE (91 to 100 range)
- BP SBP 85 → RED (90 or below)
- BP SBP 115 → GREEN (111 to 219 range)
- SpO2 91% on room air → RED (91% or below)
- SpO2 92% → ORANGE (92 to 93%)
- SpO2 94% → YELLOW (94 to 95%)
- Temp 100.4°F → YELLOW (100.4 to 102.2°F range)

SAFETY ALERT RULES — Every alert MUST include ALL of these:
1. WHAT: The specific drug name, vital value, or condition (never vague)
2. WHY IT IS DANGEROUS: The clinical mechanism or risk (e.g. "PPI increases warfarin absorption → supratherapeutic INR → bleeding risk")
3. CURRENT CONTEXT: What is happening right now that makes this urgent (e.g. "INR result still pending")
4. WHAT TO DO: Specific action the incoming nurse must take (e.g. "Review INR urgently when available and notify prescribing clinician")

SAFETY ALERT CHECKS — Always check for ALL of these:
- Drug-allergy conflicts (cross-reference every administered medication against patient allergies)
- Drug-drug interactions (especially anticoagulants, antihypertensives, antibiotics, NSAIDs)
- Abnormal vital signs with clinical interpretation
- Held or withheld medications and the reason
- Pending critical lab results or imaging reports
- Any deteriorating clinical trend

MANDATORY DRUG INTERACTION CHECKS — These MUST be flagged if present:
1. Warfarin + Omeprazole (or any PPI): PPIs inhibit CYP2C19 → reduced warfarin metabolism → elevated INR → bleeding risk. Alert: "Warfarin + Omeprazole co-administration: PPI inhibits warfarin metabolism via CYP2C19 — supratherapeutic INR risk. Review INR urgently and notify prescribing clinician."
2. Warfarin + NSAIDs (aspirin, ibuprofen, naproxen): NSAIDs displace warfarin from protein binding + GI bleeding risk. Alert with both mechanisms.
3. Dual anticoagulation (warfarin + heparin, warfarin + DOAC, warfarin + enoxaparin): Additive bleeding risk — always flag.
4. ACE inhibitor + potassium-sparing diuretic: Hyperkalemia risk.
5. Beta-blocker + verapamil/diltiazem: Bradycardia/heart block risk.

MANDATORY RESPIRATORY DISTRESS CHECK — Flag as RED CRITICAL if ALL present:
- RR > 24 breaths/min, AND
- SpO2 < 93%, OR patient using accessory muscles, OR patient dyspnoeic at rest
Alert: "Respiratory deterioration: RR [value], SpO2 [value] [on X L/min O2], [accessory muscle use/dyspnoea at rest]. Clinical picture consistent with [respiratory distress/worsening infection/fluid overload]. Escalate immediately — consider medical review, ABG, and escalation of oxygen therapy."

PENDING ACTIONS RULES:
- For stable patients: minimum 3 actions. For complex/critically ill patients (multiple RED or ORANGE flags): generate 5-6 actions
- Each action must start with an ACTION VERB (Obtain, Notify, Reassess, Monitor, Hold, Escalate, Review, Reconcile, Request, Adjust)
- CRITICAL: Immediate patient safety risk — must be done within 1 hour
- HIGH: Important clinical task — must be done within the shift
- ROUTINE: Standard monitoring or documentation
- Never write vague actions like "assess patient" — always say what specifically to assess and why

MANDATORY PENDING ACTION TRIGGERS — always generate these when applicable:
1. Pending imaging result (X-ray, CT, MRI) → CRITICAL action: "Request attending physician review of [imaging type] result and discuss clinical management plan"
2. Pending lab result (INR, cultures, bloods) → CRITICAL action: "Obtain and review [lab] result urgently and notify prescribing clinician"
3. Held antihypertensive due to hypotension → HIGH action: "Reassess antihypertensive regimen — [drug] held due to [reason]; adjust or restart as clinically indicated given current BP [value]"
4. Respiratory distress → CRITICAL action: "Escalate respiratory status to attending physician — consider increasing O2, high-flow nasal cannula, ABG, or ICU review if work of breathing worsens"
5. Drug interaction flagged → CRITICAL action: specific monitoring step for that interaction
6. Patient on anticoagulant with pending INR → always include INR review as CRITICAL

KEY CHANGES RULES:
- Include every medication administered or held during the shift
- Include every abnormal vital or trending change
- Include every procedure, test, or consultation
- Include family/patient communication events

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
    "overall_condition": "2-3 sentence clinical summary including diagnosis context, current stability, and most urgent concern"
  },
  "safety_alerts": [
    {
      "type": "DRUG_INTERACTION|ABNORMAL_VITAL|ALLERGY|CRITICAL_LAB|HELD_MED|PENDING_RESULT",
      "severity": "RED|ORANGE|YELLOW",
      "icon": "🔴|🟠|🟡",
      "message": "DrugA + DrugB: [mechanism of interaction] — patient is [current context] — risk of [specific harm]. Recommended action: [exact step to take]."
    }
  ],
  "key_changes": [
    {
      "change": "Specific description with drug names, values, times, and clinical context",
      "severity": "RED|ORANGE|YELLOW|GREEN|BLUE",
      "icon": "🔴|🟠|🟡|🟢|🔵"
    }
  ],
  "pending_actions": [
    {
      "action": "Action verb + specific task + reason (e.g. Obtain and review INR result urgently and notify prescribing clinician for warfarin dosing decision)",
      "category": "CRITICAL|HIGH|ROUTINE",
      "severity": "RED|ORANGE|YELLOW",
      "icon": "🚨|⚠️|📋",
      "priority": 1
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

        # No try/except here — this is the call site that used to swallow errors
        # and hand back empty safety_alerts / empty vitals / a single ROUTINE
        # action, which looked like a successful report. ask_llm() raises instead,
        # and that propagates up to generate_draft()'s outer handler.
        result = ask_llm(system_prompt, user_prompt)

        elapsed = time.time() - start
        print(f"   🏥 Clinical status call: {elapsed:.2f}s")

        return result

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
        updates_text = ""
        for update_info in organized_updates["all_chronological"]:
            updates_text += f"\n• {update_info['timestamp']} - {update_info['transcription'][:200]}"

        emr_medications = patient_data.get("medications", [])
        emr_allergies = patient_data.get("allergies", [])

        system_prompt = """You are a senior clinical documentation specialist. Generate a comprehensive, professional narrative handoff paragraph (250-400 words) that gives the incoming nurse a complete picture of this patient's shift.

MANDATORY STRUCTURE — include every section:
1. OPENING: "PatientName (PatientID, Room XXX, Age XX) had a [stable/eventful/concerning] shift with vital signs showing [brief summary] (HR X bpm, BP X/X mmHg, RR X, Temp X°F, SpO2 X%)." — RR (respiratory rate) MUST always be included alongside the other vitals.
2. MEDICATIONS: "At HH:MM, [exact drug name and dose] was administered [route]; [note if held and why]. [State whether each drug is in the EMR or requires reconciliation]."
3. KEY EVENTS: "At HH:MM, [procedure/test/consultation with findings]. At HH:MM, [next event]." — include EVERY event with its exact time
4. CLINICAL CONTEXT: Explain any drug interactions, allergy conflicts, or clinical concerns with the reasoning (e.g. "Note that aspirin is an NSAID and patient has a documented NSAID allergy — requires urgent reconciliation")
5. PENDING ITEMS: "The following are pending: [list each pending result, consultation, or action with context]."
6. PATIENT STATUS: "The patient remains [description of current state — comfort, cooperation, mobility, mental status]."
7. CRITICAL ACTION: "Critical action required: [the single most urgent task for the incoming nurse, with specific clinical reasoning]."

QUALITY RULES:
- Always include exact drug names, doses, and routes — never say "medication was given"
- Always include exact vital values — never say "vitals were recorded"
- Always explain WHY something is clinically significant
- Always mention family communication if it occurred
- Always mention consultations and whether results are back or pending
- The incoming nurse should be able to read this paragraph and know everything that happened without looking at any other section

TONE: Professional clinical handoff — clear, specific, no ambiguity

Return JSON: {"narrative_summary": "Your 250-400 word paragraph here"}"""

        user_prompt = f"""Patient: {patient_data.get('name', 'Unknown Patient')}
Patient ID: {patient_data.get('patient_id', 'Unknown')}
Room: {patient_data.get('room_number') or patient_data.get('room') or 'Unknown'}
Age: {patient_data.get('age') or 'Unknown'}
Allergies: {', '.join(emr_allergies) if emr_allergies else 'None'}
EMR Medications: {', '.join([str(m) for m in emr_medications]) if emr_medications else 'None'}

SHIFT UPDATES ({update_count} total):
{updates_text}

Generate 250-400 word narrative handoff summary."""

        import time
        start = time.time()

        # No try/except — a failed narrative must surface as a failed draft,
        # not a generic "N updates, see timeline" string that reads as normal output.
        result = ask_llm(system_prompt, user_prompt)

        elapsed = time.time() - start
        print(f"   📝 Narrative call: {elapsed:.2f}s")

        return result.get("narrative_summary", "See updates for details.")

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
        import time
        print(f"🤖 Generating AI-powered handoff summary...")
        start_time = time.time()

        # No try/except at this level either. If any of the three calls below
        # raises, that exception is meant to propagate all the way up to
        # generate_draft()'s outer try/except, which already returns
        # {"success": False, ...} — this used to never fire because this
        # function's own except block caught everything first and returned a
        # fabricated "successful" summary (empty safety_alerts, no vitals,
        # a single ROUTINE pending action). That silent-fallback behavior is
        # the bug being fixed; do not reintroduce it here.
        timeline = await self._generate_timeline_async(patient_data, organized_updates)
        timeline = self._sort_timeline_by_time(timeline)
        clinical_data = await self._generate_clinical_status_async(patient_data, organized_updates)
        narrative = await self._generate_narrative_async(patient_data, organized_updates, update_count)

        elapsed = time.time() - start_time
        print(f"⏱️  API calls completed in {elapsed:.2f}s")

        # Merge results into final structure
        summary = {
            "timeline": timeline,
            "current_status": clinical_data.get("current_status", {}),
            "safety_alerts": clinical_data.get("safety_alerts", []),
            "key_changes": clinical_data.get("key_changes", []),
            "pending_actions": clinical_data.get("pending_actions", []),
            "narrative_summary": narrative
        }

        print(f"✅ Generated handoff summary with {len(timeline)} timeline events")

        return summary

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
