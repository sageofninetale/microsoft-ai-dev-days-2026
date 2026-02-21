# CascadeAI Test UI

Simple React-based test interface to verify backend API functionality.

## Quick Start

### 1. Install Dependencies
```bash
cd frontend
npm install
```

### 2. Start Backend (Terminal 1)
```bash
# From project root
python -m backend.api
```
Backend will run on: http://localhost:8000

### 3. Start Frontend (Terminal 2)
```bash
cd frontend
npm start
```
Frontend will run on: http://localhost:3000

## Test Workflow

### Step 1: Start a Shift
1. Select a nurse from the dropdown (default: Cristiano Ronaldo)
2. Enter patient IDs (default: P001)
3. Click "Start Shift"
4. You'll see a shift ID appear

### Step 2: Add Patient Updates
1. Select update type (medication, vital_signs, procedure, general)
2. Type update text, for example:
   - **Medication**: "Started heparin drip at 1000 units/hour at 11 AM"
   - **Vital Signs**: "BP 145/92, HR 88, Temp 98.6, SpO2 96% at 2 PM"
   - **Procedure**: "Dr. Patel cardiology consult completed at 1:30 PM. Troponin 2.4. Recommends cath lab."
3. Click "Submit Update"
4. You'll see transcription and EMR verification status

### Step 3: View All Updates
1. Click "Show All Updates"
2. See list of all updates for patient P001
3. Each update shows:
   - Timestamp
   - Type (color-coded)
   - Transcription (first 100 chars)
   - EMR verification status

### Step 4: Generate Draft Handoff
1. After adding 2-3 updates, click "Generate Draft Handoff"
2. AI will compile all updates into structured handoff with:
   - **Timeline**: Chronological events with risk flags
   - **Current Status**: Medications (clinical notation), vitals, condition
   - **Key Changes**: Significant changes with severity indicators
   - **Pending Actions**: Categorized by urgency (🚨 CRITICAL, ⚠️ HIGH, 📋 ROUTINE)

## Sample Test Updates

Try these in sequence:

```
Type: medication
Text: Started heparin drip at 1000 units/hour at 11 AM

Type: vital_signs
Text: BP 145/92, HR 88, Temp 98.6, SpO2 96% at 2 PM

Type: procedure
Text: Dr. Patel cardiology consult completed at 1:30 PM. Troponin 2.4. Recommends cath lab preparation.
```

## Features Tested

✅ Nurse selection (GET /api/nurses)  
✅ Shift management (POST /api/shift/start)  
✅ Patient updates (POST /api/patient/{id}/update)  
✅ Update retrieval (GET /api/patient/{id}/updates/{shift_id})  
✅ Draft generation (POST /api/patient/{id}/draft)  
✅ EMR verification (medications, vital signs)  
✅ AI-powered narrative compilation  
✅ Clinical output formatting  

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Health check |
| `/api/nurses` | GET | Get nurse list |
| `/api/shift/start` | POST | Start new shift |
| `/api/shift/active/{nurse_id}` | GET | Get active shift |
| `/api/patient/{id}/update` | POST | Add patient update |
| `/api/patient/{id}/updates/{shift_id}` | GET | Get all updates |
| `/api/patient/{id}/draft` | POST | Generate draft |
| `/api/patient/{id}/draft/{shift_id}` | GET | Get existing draft |

## Troubleshooting

**Backend not running?**
```bash
python -m backend.api
```

**Frontend won't start?**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
npm start
```

**CORS errors?**
- Backend CORS is configured for `http://localhost:3000`
- Make sure both servers are running
- Check browser console for specific errors

**Port conflicts?**
- Backend: port 8000 (configurable in `backend/api.py`)
- Frontend: port 3000 (configurable in `package.json`)

## Next Steps

This is a basic test UI. Future enhancements:
- [ ] Audio recording for updates
- [ ] Multiple patient management
- [ ] Real-time updates
- [ ] Shift handoff workflow
- [ ] Beautiful UI with Antigravity components
- [ ] Mobile responsive design
