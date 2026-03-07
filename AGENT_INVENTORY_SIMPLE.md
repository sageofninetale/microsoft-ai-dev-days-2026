# 🤖 DEFINITIVE AGENT COUNT - Clear & Simple

**Date**: February 24, 2026  
**Based on**: Actual files in `/backend/` directory

---

## 📊 **YOU HAVE 6 AI COMPONENTS TOTAL**

Here's every single one, with exactly what they do:

---

## **1. IntakeAgent** (`intake_agent.py`)

**Class Name:** `PatientIntakeAgent`

**What it does:**
- Takes COMPLETE handoff audio/text at START of shift
- Transcribes audio using Azure Speech
- Extracts ALL patient data (name, age, room, meds, vitals, complaints) using Azure OpenAI
- Calculates confidence score (0.0-1.0) - rejects low-quality handoffs

**Input:** Full handoff recording (e.g., "80-year-old female in room 305, BP 145/88...")  
**Output:** `HandoffSummary` object with structured patient data

**Used in:** Test files only (`test_coordinator.py`, `test_intake_api.py`)  
**NOT used in main app** ❌

---

## **2. VerificationAgent** (`verification_agent.py`)

**Class Name:** `VerificationAgent`

**What it does:**
- Fetches patient record from Supabase EMR database
- Cross-checks medications mentioned vs patient's actual medication list
- Flags discrepancies:
  - 🔴 CRITICAL: Allergy conflicts (giving NSAID to NSAID-allergic patient)
  - 🟠 HIGH: Dose mismatches (EMR shows 81mg, nurse says 325mg)
  - 🟡 MEDIUM: New medication not in EMR
  - ℹ️ INFO: Extra medication in EMR but not mentioned

**Input:** Extracted patient data + patient_id  
**Output:** `VerificationResult` with list of findings and risk score

**Used in:** 
- ✅ Main app (called BY UpdateAgent automatically)
- ✅ CoordinatorAgent workflow (demo/tests)

---

## **3. ProtocolAgent** (`protocol_agent.py`)

**Class Name:** `ProtocolAgent`

**What it does:**
- Checks if patient care follows clinical protocols:
  - **ACS Protocol** (Acute Coronary Syndrome): Aspirin + P2Y12 inhibitor + anticoagulation
  - **Fall Risk Protocol**: Age >65, orthostatic hypotension → bed alarm, hourly rounding
  - **Hypertension Protocol**: BP <140/90, ACE inhibitor or ARB
  - **Diabetes Protocol**: Glucose 80-180 mg/dL, insulin sliding scale
- Flags missing protocol elements with severity levels

**Input:** Patient EMR data + handoff data  
**Output:** `ProtocolResult` with compliance score and findings

**Used in:** CoordinatorAgent workflow only (demo/tests)  
**NOT used in main app** ❌

---

## **4. UpdateAgent** (`update_agent.py`)

**Class Name:** `UpdateAgent`

**What it does:**
- Processes INDIVIDUAL updates DURING the shift (not full handoffs)
- Transcribes audio snippets (Azure Speech)
- Extracts structured data (Azure OpenAI)
- Auto-classifies update type: medication, vital_signs, procedure, general
- **Automatically calls VerificationAgent** to check medications vs EMR
- Saves update to `patient_updates` database table

**Input:** Single update text/audio (e.g., "Gave Metoprolol 25mg at 2 PM")  
**Output:** Saved `PatientUpdate` record with verification status

**Used in:** ✅ Main app (`/api/patient/{id}/update` endpoint)  
**This is what nurses use!**

---

## **5. DraftGenerator** (`draft_generator.py`)

**Class Name:** `DraftGenerator`

**What it does:**
- Fetches ALL updates for a patient during a shift
- Organizes by type (medication/vitals/procedure/general)
- Generates three things in PARALLEL (faster):
  1. **Timeline** - Chronological list of events with timestamps
  2. **Narrative** - 150-250 word summary (Azure OpenAI)
  3. **Clinical Status** - Current meds, vitals, allergies
- Color-codes safety alerts (🔴 Critical, 🟠 High, 🟡 Caution, ✅ Verified)
- Saves to `draft_handoffs` database table

**Input:** patient_id + shift_id  
**Output:** Complete `DraftHandoff` with timeline, narrative, safety alerts

**Used in:** ✅ Main app (`/api/patient/{id}/draft` endpoint)  
**This is what generates the final handoff!**

---

## **6. CoordinatorAgent** (`coordinator_agent.py`)

**Class Name:** `CoordinatorAgent`

**What it does:**
- Orchestrates MULTIPLE agents for complete handoff analysis
- Calls IntakeAgent → VerificationAgent → ProtocolAgent in sequence
- Calculates weighted risk score:
  - Handoff confidence: 20%
  - Verification findings: 40%
  - Protocol compliance: 40%
- Prioritizes actions by severity (CRITICAL → HIGH → MEDIUM → LOW)
- Generates executive summary (2-3 sentences)

**Input:** Full handoff audio/text + patient_id  
**Output:** `CoordinatorResult` with risk score and prioritized actions

**Used in:** Test files only (`test_coordinator.py`)  
**NOT used in main app** ❌

---

## 📊 **SUMMARY TABLE**

| # | Agent Name | File | Used in Main App? | What It Does (One Line) |
|---|------------|------|-------------------|------------------------|
| 1 | IntakeAgent | `intake_agent.py` | ❌ NO (demo only) | Extracts complete patient data from full handoff audio |
| 2 | VerificationAgent | `verification_agent.py` | ✅ YES (via UpdateAgent) | Cross-checks medications against EMR database |
| 3 | ProtocolAgent | `protocol_agent.py` | ❌ NO (demo only) | Checks clinical protocol compliance (ACS, Fall, HTN) |
| 4 | UpdateAgent | `update_agent.py` | ✅ YES | Processes individual updates during shift |
| 5 | DraftGenerator | `draft_generator.py` | ✅ YES | Aggregates updates → AI handoff summary |
| 6 | CoordinatorAgent | `coordinator_agent.py` | ❌ NO (demo only) | Orchestrates multi-agent workflow + risk scoring |

---

## 🎯 **WHAT NURSES ACTUALLY USE (Main App Flow)**

```
Nurse adds update → UpdateAgent → VerificationAgent → Database
                                                          ↓
                            [Shift continues, more updates added...]
                                                          ↓
                    Nurse clicks "Generate Draft" → DraftGenerator → Handoff
```

**Only 3 components used:** UpdateAgent, VerificationAgent (embedded), DraftGenerator

---

## 🧪 **WHAT'S IN DEMO/TESTS (Not in main app)**

```
Full handoff audio → IntakeAgent → CoordinatorAgent → VerificationAgent + ProtocolAgent → Risk Report
```

**Only 4 components used:** IntakeAgent, CoordinatorAgent, VerificationAgent, ProtocolAgent

**Note:** DraftGenerator and UpdateAgent are NOT part of this workflow!

---

## ✅ **FOR YOUR LANDING PAGE, YOU CAN SAY:**

### **Option 1 (Honest - What's Actually Running):**
"**3 AI Components** power your shift updates"
- UpdateAgent
- VerificationAgent  
- DraftGenerator

### **Option 2 (Full System - What You Built):**
"**6 AI Components** for complete clinical intelligence"
- IntakeAgent, VerificationAgent, ProtocolAgent, UpdateAgent, DraftGenerator, CoordinatorAgent

### **Option 3 (Marketing - Sounds Best):**
"**5 Specialized AI Agents + 1 Orchestrator**"
- 5 Agents: Intake, Verification, Protocol, Update, DraftGenerator
- 1 Orchestrator: Coordinator

---

## 💡 **MY RECOMMENDATION:**

Say **"5 AI Agents"** and list:
1. IntakeAgent
2. VerificationAgent
3. ProtocolAgent
4. UpdateAgent
5. DraftGenerator

*Small print: "Coordinated by CoordinatorAgent orchestrator"*

**Why?** It's technically accurate, sounds impressive, and doesn't require explaining that some agents aren't in the main app yet.

---

**End of Agent Inventory** 🤖
