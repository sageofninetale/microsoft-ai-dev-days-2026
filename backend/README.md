# Backend API

FastAPI service for processing patient handoff data using Azure OpenAI and Azure Speech Services.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure `.env` file exists in the project root with:
```
AZURE_OPENAI_ENDPOINT=<your-endpoint>
AZURE_OPENAI_KEY=<your-key>
AZURE_OPENAI_DEPLOYMENT=<your-deployment-name>
AZURE_SPEECH_KEY=<your-speech-key>
AZURE_SPEECH_REGION=<your-region>
```

## Running the Server

```bash
cd backend
python main.py
```

The API will start on `http://localhost:8000`

## API Endpoints

### `GET /`
Health check endpoint.

### `POST /handoff/intake`
Process a patient handoff transcript and extract structured data.

**Request Body:**
```json
{
  "transcript": "Patient John Doe in room 302..."
}
```

**Response:**
```json
{
  "confidence": 0.92,
  "reasoning": "All key fields clearly stated with specific details",
  "patient_name": "John Doe",
  "room_number": "302",
  "age": "68",
  "chief_complaint": "chest pain",
  "medications": ["aspirin 81mg daily", "metoprolol 50mg twice daily"],
  "pending_tasks": ["cardiac enzyme labs at 6 AM"],
  "vitals": {"blood_pressure": "145/92", "heart_rate": "88"},
  "safety_alerts": ["fall risk due to dizziness"]
}
```

**Clinical Safety-Based Confidence Scoring:**

The AI applies strict clinical safety standards to assess handoff quality:

| Confidence Range | Safety Level | Criteria | Usability |
|-----------------|--------------|----------|-----------|
| **0.20-0.30** | 🔴 HARD STOP | Missing patient_name | ❌ **UNUSABLE** - Cannot verify patient identity |
| **0.40-0.50** | 🟠 CRITICAL GAPS | Missing room_number OR chief_complaint | ❌ **UNUSABLE** - Critical info missing |
| **0.55-0.65** | 🟡 IMPORTANT GAPS | Missing 2+ of: age, vitals, medications | ✅ Usable with caution |
| **0.70-0.80** | 🟢 MINOR GAPS | Missing only 1 of: age, vitals, medications | ✅ Usable, one field needed |
| **0.60-0.75** | 🟡 UNCERTAIN DATA | Contains "maybe", "I think", "approximately" | ✅ Usable with verification |
| **0.85-0.95** | 🟢 COMPLETE | All critical + important fields present & clear | ✅ High confidence |

**Key Rules:**
- Applies the **LOWEST** applicable confidence level (e.g., missing patient_name → 0.20-0.30 regardless of other data)
- Reasoning explains safety impact and states if handoff is usable (>0.50) or unusable (≤0.50)
- Based on real clinical handoff safety standards

## Testing

### Test the API endpoint:
```bash
python test_intake_api.py
```

### Test Azure Speech transcription:
```bash
python test_speech.py
```

This will:
1. Automatically convert `test_handoff.m4a` to WAV format (if ffmpeg is installed)
2. Transcribe the audio using Azure Speech Service
3. Extract structured data using the intake agent
4. Display the results

**Requirements:**
- Audio file: `test_handoff.m4a` in project root

### Test edge cases and robustness:
```bash
python test_edge_cases.py
```

This tests the AI's handling of:
- Incomplete transcripts (missing patient name, vitals)
- Messy transcripts (filler words, uncertainty markers)
- Minimal information (bare essentials only)
- Empty transcripts (error handling)
- Complete transcripts (baseline comparison)

Shows how confidence scores adjust based on data quality and completeness.

## Architecture

- `main.py` - FastAPI application with CORS middleware
- `intake_agent.py` - Azure OpenAI + Azure Speech integration for transcription and data extraction
- `test_intake_api.py` - Sample client for testing the API endpoint
- `test_speech.py` - Test script for audio transcription + extraction pipeline
- `test_edge_cases.py` - Edge case testing for robustness validation
