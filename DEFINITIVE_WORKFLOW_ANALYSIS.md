# 🔬 DEFINITIVE WORKFLOW ANALYSIS - Based on Actual Code

**Date**: February 24, 2026  
**Method**: Code trace through backend/api.py, update_agent.py, draft_generator.py, App.js  
**Status**: FACTS ONLY - No assumptions

---

## 📋 **ACTUAL WORKFLOWS IN YOUR APP**

After tracing through your code, you have **TWO SEPARATE WORKFLOWS**:

---

## **WORKFLOW #1: REAL-TIME SHIFT UPDATES** (Primary User Flow)

This is what nurses actually use during their shift:

### **Step-by-Step:**

```
USER ACTION: Nurse records audio or types text update
    ↓
FRONTEND: App.js calls POST /api/patient/{id}/update
    ↓
BACKEND: api.py → get_update_agent()
    ↓
STEP 1: UpdateAgent.process_update()
    ├─ If audio: _transcribe_audio() using Azure Speech
    ├─ Extract structured data: _extract_update_data() using Azure OpenAI
    ├─ Classify update type: medication/vital_signs/procedure/general
    └─ Calls: _verify_update()
        ↓
STEP 2: VerificationAgent (called inside UpdateAgent)
    ├─ Fetch patient EMR from database
    ├─ Cross-check medications mentioned vs EMR
    ├─ Flag discrepancies (new meds, dose mismatches, allergies)
    └─ Return verification result
        ↓
STEP 3: Save to Database
    ├─ Save update to patient_updates table
    └─ Return success response
        ↓
LATER: When shift ends, nurse clicks "Generate Draft"
    ↓
FRONTEND: App.js calls POST /api/patient/{id}/draft
    ↓
BACKEND: api.py → get_draft_generator()
    ↓
STEP 4: DraftGenerator.generate_draft()
    ├─ Fetch ALL updates from patient_updates table
    ├─ Organize by type (medication/vitals/procedure/general)
    ├─ Generate timeline (Azure OpenAI)
    ├─ Generate narrative summary (Azure OpenAI) - PARALLEL
    ├─ Generate clinical status (Azure OpenAI) - PARALLEL
    ├─ Combine into color-coded handoff
    └─ Save to draft_handoffs table
        ↓
STEP 5: Display Final Handoff
    ├─ Timeline of events
    ├─ 150-250 word narrative
    ├─ Color-coded safety alerts (🔴🟠🟡✅)
    └─ Pending actions prioritized
```

### **AGENTS INVOLVED IN THIS WORKFLOW:**

1. **UpdateAgent** (processes each individual update)
   - Sub-calls: Azure Speech (transcription)
   - Sub-calls: Azure OpenAI (extraction)
   - Sub-calls: VerificationAgent (EMR verification)

2. **VerificationAgent** (called BY UpdateAgent, not standalone)
   - Checks medications against EMR
   - Flags discrepancies

3. **DraftGenerator** (aggregates all updates into final handoff)
   - Parallel Azure OpenAI calls for timeline/narrative/status

**NOTE:** IntakeAgent, ProtocolAgent, and CoordinatorAgent are **NOT** used in this workflow!

---

## **WORKFLOW #2: INITIAL HANDOFF INTAKE** (Demo/Testing Only)

This is in your code but NOT exposed via API endpoints to frontend:

### **Step-by-Step:**

```
INPUT: Raw audio file or text transcript of complete handoff
    ↓
STEP 1: IntakeAgent (PatientIntakeAgent)
    ├─ Transcribe audio (Azure Speech)
    ├─ Extract ALL patient data (Azure OpenAI)
    ├─ Calculate confidence score
    └─ Return HandoffSummary
        ↓
STEP 2: CoordinatorAgent.process_handoff()
    ├─ Calls: VerificationAgent
    │   └─ Cross-check handoff data vs EMR
    ├─ Calls: ProtocolAgent  
    │   └─ Check clinical protocols (ACS, Fall Risk, HTN)
    ├─ Calculate weighted risk score
    └─ Generate executive summary
        ↓
OUTPUT: Complete risk assessment with prioritized actions
```

### **AGENTS INVOLVED IN THIS WORKFLOW:**

1. **IntakeAgent** (extracts structured data from audio)
2. **CoordinatorAgent** (orchestrates verification + protocol)
   - Sub-calls: VerificationAgent
   - Sub-calls: ProtocolAgent
3. **VerificationAgent** (EMR verification)
4. **ProtocolAgent** (protocol compliance)

**NOTE:** This workflow is used in test files (`test_coordinator.py`, `test_intake_api.py`) but **NOT** in the main app!

---

## 🎯 **WHICH WORKFLOW IS ON YOUR LANDING PAGE?**

Looking at your screenshots, you're showing a **HYBRID** that doesn't match either workflow!

**Your diagram shows:**
```
Nurse Audio Input
    ↓
IntakeAgent ← From Workflow #2 (not used in main app)
    ↓
CoordinatorAgent ← From Workflow #2 (not used in main app)
    ↓
[VerificationAgent, ProtocolAgent, UpdateAgent] ← Mix of both!
    ↓
DraftGenerator ← From Workflow #1 (actual app)
    ↓
Verified Report
```

---

## ✅ **THE CORRECT LANDING PAGE WORKFLOW SHOULD BE:**

### **Option A: Show ACTUAL App Flow (What Users Experience)**

```
Nurse Audio/Text Input
    ↓
UpdateAgent
(Transcription → Extraction → Classification)
    ↓
VerificationAgent
(EMR Cross-Check automatically by UpdateAgent)
    ↓
Save to Database
(Real-time updates stored)
    ↓
[Nurse continues shift, adds more updates...]
    ↓
DraftGenerator
(Aggregates all updates → AI narrative)
    ↓
Color-Coded Handoff Report
(Timeline + Narrative + Safety Alerts)
```

**Agents shown:** UpdateAgent → VerificationAgent (embedded) → DraftGenerator

---

### **Option B: Show DEMO Flow (CoordinatorAgent workflow)**

```
Nurse Audio Input
    ↓
IntakeAgent
(Audio → Structured Data)
    ↓
CoordinatorAgent
(Orchestrates verification + protocols)
    ↓
┌────────────┬──────────────┐
│Verification│ ProtocolAgent│
│   Agent    │              │
└────────────┴──────────────┘
    ↓
Risk Assessment Report
(Weighted risk score + prioritized actions)
```

**Agents shown:** IntakeAgent → CoordinatorAgent → [VerificationAgent + ProtocolAgent in parallel]

**NOTE:** This workflow does NOT include DraftGenerator or UpdateAgent!

---

## 🚨 **BRUTAL HONESTY: YOUR CURRENT DIAGRAM IS WRONG**

**What's wrong:**
1. You're mixing agents from TWO different workflows
2. IntakeAgent is NOT used in your main app (only in tests)
3. CoordinatorAgent is NOT used in your main app (only in tests)
4. ProtocolAgent is NOT used in your main app (only in tests)
5. The flow doesn't match what nurses actually experience

**What's technically accurate:**
- UpdateAgent does process updates ✅
- VerificationAgent does check EMR ✅
- DraftGenerator does create handoffs ✅

**But the order/structure is confusing because you're showing a demo workflow that doesn't exist in production.**

---

## 💡 **MY HONEST RECOMMENDATION**

### **FIX #1: Show the REAL app workflow**

```
Nurse Input → UpdateAgent → VerificationAgent (embedded) → 
Database → DraftGenerator → Handoff Report
```

**Pros:** Accurate, matches what nurses experience  
**Cons:** Only 2-3 agents shown (less impressive)

---

### **FIX #2: Implement the full CoordinatorAgent workflow in your API**

Add these endpoints:
- `POST /api/handoff/intake` - Calls CoordinatorAgent
- Make ProtocolAgent actually run
- Show the 5-6 agent workflow

**Pros:** Impressive multi-agent system  
**Cons:** Requires code changes to API

---

### **FIX #3: Show BOTH workflows as different use cases**

- **"Real-Time Updates"** - UpdateAgent → VerificationAgent → DraftGenerator
- **"Initial Intake"** - IntakeAgent → Coordinator → [Verification + Protocol]

**Pros:** Honest, shows full capability  
**Cons:** More complex landing page

---

## 📊 **FINAL ANSWER**

**Your current landing page workflow:** ❌ INCORRECT (mixing two workflows)

**Correct workflow for main app:** 
```
UpdateAgent → VerificationAgent → DraftGenerator
```

**Correct workflow for CoordinatorAgent (demo):**
```
IntakeAgent → CoordinatorAgent → [VerificationAgent + ProtocolAgent]
```

**You need to pick ONE and stick with it, or show both clearly labeled.**

---

**End of Definitive Analysis** 🔬
