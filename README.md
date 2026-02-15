# 🏥 MedReconcile - Multi-Agent Clinical Handoff Intelligence

[![Hackathon](https://img.shields.io/badge/AI%20Dev%20Days-Hackathon%202026-blue)](https://aka.ms/aidevdayshackathon)
[![Category](https://img.shields.io/badge/Category-Best%20Multi--Agent%20System-green)]()
[![Status](https://img.shields.io/badge/Week%201-✅%20COMPLETE-brightgreen)]()
[![Progress](https://img.shields.io/badge/Progress-25%25%20(1%2F4%20Agents)-yellow)]()

> **Preventing medical errors through intelligent multi-agent coordination**

80% of serious medical errors involve miscommunication during nurse handoffs. MedReconcile uses a sophisticated multi-agent system to automatically verify, cross-check, and protocol-align clinical handoffs in real-time.

---

## 🎯 Problem Statement

When nurses change shifts, they verbally hand off patient care. Critical information gets lost:
- Missed allergies → adverse reactions
- Forgotten lab results → delayed diagnosis  
- Unclear protocols → suboptimal care

**Current tools are passive** - they just display what nurses manually enter. **MedReconcile is intelligent** - AI agents actively verify and enhance handoffs.

---

## 🤖 Multi-Agent Architecture

Four specialized AI agents work together:

### 1. **Intake Agent** ✅ (Week 1 - COMPLETE)
- Transcribes audio or processes text handoff
- Extracts structured data (patient info, meds, vitals, safety alerts)
- **Output:** Clean JSON with confidence scores

### 2. **Verification Agent** (Week 2 - In Progress)
- Cross-references handoff against mock EMR database
- Identifies gaps, inconsistencies, missing critical info
- **Output:** Flagged findings with severity levels + reasoning

### 3. **Protocol Agent** (Week 2 - In Progress)  
- Checks against clinical protocols (ACS, Fall Risk, Hypertension)
- Evaluates compliance and risk levels
- **Output:** Protocol recommendations with confidence scores

### 4. **Coordinator Agent** (Week 3 - Planned)
- Orchestrates all specialist agents
- Aggregates findings and prioritizes actions
- **Output:** Enhanced verified handoff report
```
┌─────────────┐
│ Audio/Text  │
└──────┬──────┘
       ↓
┌─────────────────┐
│ Intake Agent    │ Extract & Structure
└────────┬────────┘
         ↓
    ┌────┴────┐
    ↓         ↓
┌──────────┐ ┌──────────────┐
│Verification│ │Protocol Agent│
│  Agent    │ │              │
└─────┬────┘ └──────┬───────┘
      ↓             ↓
┌─────────────────────┐
│ Coordinator Agent   │ Synthesize & Prioritize
└──────────┬──────────┘
           ↓
  📋 Enhanced Handoff
```

---

## 🛠️ Tech Stack

**Azure AI Services:**
- **Azure OpenAI** (gpt-5-mini) - All agent reasoning
- **Azure Speech Service** - Audio transcription

**Backend:**
- **Python 3.11+** with FastAPI
- Multi-agent orchestration system

**Frontend:** (Week 4)
- **React** + Tailwind CSS
- Visual agent flow display

**Development:**
- **VS Code** + **GitHub Copilot**
- **Git/GitHub** version control

---

## 📊 Current Status

### ✅ Week 1: COMPLETE
**Intake Agent** - Production-ready with clinical safety confidence scoring

**Next Steps:**
- Build Verification Agent (Week 2)
- Build Protocol Agent (Week 2)
- Build Coordinator Agent (Week 3)
- Frontend + Visual Flow (Week 4)
- Azure deployment (Week 5)

---

## 🎉 Week 1 Progress - INTAKE AGENT COMPLETE

### 1. **Intake Agent - PRODUCTION READY** ✅

**Core Capabilities:**
- ✅ **Text-based handoff extraction** - Azure OpenAI (gpt-5-mini) structured extraction
- ✅ **Audio transcription** - Azure Speech Service with automatic M4A → WAV conversion
- ✅ **Structured JSON output** - HandoffSummary dataclass with 10 fields
- ✅ **Clinical safety confidence scoring** - Nuanced 0.15-0.95 range with reasoning
- ✅ **Intelligent reasoning traces** - Every decision explained with clinical safety impact

**Extracted Fields:**
- `patient_name`, `room_number`, `age`, `chief_complaint`
- `medications` (array), `pending_tasks` (array)
- `vitals` (object with BP, HR, temp, SpO2)
- `safety_alerts` (array - fall risk, isolation, etc.)
- `confidence` (float 0.0-1.0), `reasoning` (string)

---

### 2. **Confidence Scoring System - CLINICAL SAFETY BASED** 🎯

Our confidence scoring reflects **real clinical safety standards** where patient identity is the primary safety barrier:

| Confidence Range | Scenario | Usability | Example |
|-----------------|----------|-----------|---------|
| **0.15-0.30** | Missing `patient_name` | ❌ **UNUSABLE** | Cannot verify patient identity - wrong-patient risk |
| **0.45-0.50** | Missing `room_number` or `chief_complaint` (but has name) | ⚠️ **USABLE with extreme caution** | Patient identified but critical context missing - immediate data collection required |
| **0.55-0.65** | Missing 2+ important fields | ⚠️ **USABLE with caution** | Missing age + vitals - proceed with immediate assessment |
| **0.70-0.80** | Missing 1 important field | ✅ **USABLE with caution** | Missing vitals only - can be quickly obtained |
| **0.85-0.95** | Complete handoff | ✅ **HIGH CONFIDENCE** | All fields present and clear |

**🎯 Critical Distinction:**
- **Without patient_name:** Cannot verify who to treat → **UNUSABLE** (0.15-0.30)
- **With patient_name:** Patient verified, can proceed cautiously → **USABLE** (0.45-0.95)

**Nuanced Sub-Ranges for Missing Patient Name:**
- **0.15-0.20:** Missing name + uncertain data ("maybe", "I think")
- **0.20-0.25:** Missing name + 4+ other fields missing
- **0.25-0.30:** Missing name only (other data clear)

---

### 3. **Edge Case Testing - 7 SCENARIOS VALIDATED** ✅

Comprehensive testing ensures the Intake Agent handles real-world variability:

| Test # | Scenario | Expected Confidence | Actual Result | Status |
|--------|----------|-------------------|---------------|---------|
| 1 | Incomplete (no name, no vitals) | 0.25-0.30 | 0.25 | ✅ Pass |
| 2 | Messy with uncertainty markers | 0.15-0.20 | 0.17-0.18 | ✅ Pass |
| 3 | Minimal info (4+ fields missing) | 0.20-0.25 | 0.22 | ✅ Pass |
| 4 | Empty transcript | Error handling | IntakeAgentError | ✅ Pass |
| 5 | Has name, missing room | 0.45-0.50 | 0.48 | ✅ Pass |
| 6 | Missing only vitals | 0.70-0.80 | 0.70 | ✅ Pass |
| 7 | Complete handoff | 0.85-0.95 | 0.85-0.90 | ✅ Pass |

**Test Script:** `backend/test_edge_cases.py`

---

### 4. **Files Created This Week** 📁

```
backend/
├── intake_agent.py          # Main agent with confidence logic (~230 lines)
├── main.py                  # FastAPI application (~80 lines)
├── test_speech.py          # Audio transcription testing (~90 lines)
├── test_edge_cases.py      # Edge case validation (~170 lines)
└── requirements.txt         # Dependencies

test_handoff.m4a            # Sample audio file for testing
.env                        # Azure credentials (gitignored)
.github/
└── copilot-instructions.md # AI agent guidance
```

---

### 5. **Current Metrics** 📈

- **Lines of code:** ~570 (backend only)
- **Test coverage:** 7 edge cases covering confidence spectrum
- **Azure services integrated:** 2 (OpenAI + Speech)
- **Confidence scoring accuracy:** Production-ready with clinical validation
- **API endpoints:** 2 (health check + handoff intake)
- **Audio format support:** M4A, WAV (auto-conversion via ffmpeg)

---

### 6. **Technical Highlights** ⚡

**Audio Transcription Pipeline:**
- Automatic format detection (M4A → WAV conversion)
- Azure Speech SDK continuous recognition
- Push stream approach for long audio files
- Comprehensive error handling

**Structured Extraction:**
- JSON mode for guaranteed valid output
- Pydantic validation for type safety
- Dataclasses with slots for memory efficiency
- Detailed reasoning traces for transparency

**API Design:**
- FastAPI with automatic OpenAPI docs
- CORS enabled for frontend integration
- Proper error handling (400 for agent errors, 500 for unexpected)
- Type-safe request/response models

---

## 🚀 Installation

### Prerequisites
- Python 3.11+
- Azure account with OpenAI + Speech services
- Node.js 18+ (for frontend, Week 4)

### Setup

1. **Clone repository:**
```bash
git clone https://github.com/sageofninetale/microsoft-ai-dev-days-2026.git
cd microsoft-ai-dev-days-2026
```

2. **Install backend dependencies:**
```bash
pip install -r backend/requirements.txt
```

3. **Configure environment variables:**

Create `.env` file in project root:
```bash
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_KEY=your_key_here
AZURE_OPENAI_DEPLOYMENT=gpt-5-mini

# Azure Speech Service
AZURE_SPEECH_KEY=your_speech_key_here
AZURE_SPEECH_REGION=uksouth
```

4. **Run backend:**
```bash
python -m uvicorn backend.main:app --reload
```

5. **Test API:**
Open browser: http://127.0.0.1:8000/docs

---

## 🎥 Demo

**Demo video:** [Coming Week 5]

**Test the Intake Agent:**
```bash
curl -X POST "http://127.0.0.1:8000/handoff/intake" \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "Room 302 is Mr. Johnson, 67 years old, admitted for chest pain. He is on aspirin 325mg and metoprolol 50mg twice daily. We drew troponin labs at 4 PM, results are pending. His blood pressure was 160 over 95 at 6 PM. He is a fall risk, bed alarm is active."
  }'
```

Expected response: Structured JSON with patient data, medications, vitals, and safety alerts.

---

## 👥 Team

**Developer:** Aryan Subhash
**Microsoft Learn Profile:** [Your profile link]
**GitHub:** [@sageofninetale](https://github.com/sageofninetale)

---

## 📝 License

MIT License - See [LICENSE](LICENSE) file

---

## 🏆 Hackathon Submission

**Event:** AI Dev Days Hackathon 2026  
**Category:** 🤝 Best Multi-Agent System  
**Submission Deadline:** March 15, 2026

**Why Multi-Agent?**
- Single AI can't excel at extraction AND verification AND protocol checking
- Specialist agents = better accuracy per domain
- Transparent reasoning traces for clinical safety
- Enterprise-scalable architecture

---

**Built with ❤️ for safer healthcare**