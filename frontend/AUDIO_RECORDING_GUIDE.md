# Audio Recording Feature - Test Guide

## 🎤 New Audio Recording Feature Added!

The frontend now includes microphone recording with real-time processing step visualization.

## How to Test

### 1. Start a Shift
- Select a nurse
- Enter patient IDs (P001)
- Click "Start Shift"

### 2. Record Audio Update

**Option A: Use Audio Recording** 🎤
1. Click "🎤 Record Audio" button
2. Allow microphone access when prompted
3. Speak your update (e.g., "Started heparin drip at 1000 units per hour at 11 AM")
4. Watch the timer: "🔴 Recording... 5s"
5. Click "⏹️ Stop Recording"
6. See the transcription appear
7. Click "📤 Submit Audio Update"

**Option B: Type Text** ✍️
1. Scroll to "Or Type Text" section
2. Enter update in textarea
3. Click "📝 Submit Text Update"

### 3. Watch Processing Steps

After recording, you'll see step-by-step processing:

```
🔄 Processing Steps:
✅ Audio recorded (15s)
✅ Transcribed by Azure Speech API
📝 Transcription ready for submission
⏳ Submitting update to backend...
✅ Saved to database with timestamp
✅ Verified against EMR - Found 1 issue(s)
✅ Ready for draft generation
```

## Processing Steps Explained

| Step | What Happens |
|------|--------------|
| **Audio recorded** | Browser MediaRecorder captures your voice |
| **Transcribed by Azure Speech** | Audio → Text using Azure Speech API |
| **Saved to database** | Update stored in Supabase with timestamp |
| **Verified against EMR** | Checks medications/vitals against patient's EMR |
| **Ready for draft** | Update available for AI handoff compilation |

## Status Colors

- 🟢 **Green** - Success
- 🔵 **Blue** - Loading/In Progress
- 🟡 **Yellow** - Warning (e.g., EMR issues found)
- 🔴 **Red** - Error

## Features

✅ Real-time recording with timer  
✅ Microphone permission handling  
✅ Audio → Text transcription simulation  
✅ Step-by-step processing visualization  
✅ EMR verification feedback  
✅ Clear/reset functionality  
✅ Both audio and text input options  

## Current Limitations

⚠️ **Note**: Audio transcription is currently **simulated** because:
- Backend `/api/patient/{id}/update` endpoint expects `text` field
- Azure Speech SDK integration in backend is not yet connected to API

### To Enable Real Audio Transcription:

1. **Backend Option**: Update `backend/api.py` to:
   - Accept `audio` field (base64)
   - Decode to audio file
   - Call `UpdateAgent._transcribe_audio()`
   - Return transcription

2. **Frontend Option**: Add Azure Speech SDK to frontend:
   ```bash
   npm install microsoft-cognitiveservices-speech-sdk
   ```
   Then transcribe in browser before sending to backend.

## Sample Test Workflow

```
1. Click "🎤 Record Audio"
2. Say: "Patient received heparin 1000 units per hour at 11 AM"
3. Click "⏹️ Stop Recording"
4. See: "📝 Transcription: [simulated text]"
5. Click "📤 Submit Audio Update"
6. Watch processing steps appear one by one
7. See EMR verification result
8. Update saved successfully!
```

## Browser Compatibility

- ✅ Chrome/Edge (Recommended)
- ✅ Firefox
- ✅ Safari (iOS 14.3+)
- ❌ IE11 (Not supported)

## Troubleshooting

**"Microphone access denied"**
- Click the 🔒 in address bar
- Allow microphone access
- Refresh the page

**"No audio recording"**
- Check microphone is connected
- Try a different browser
- Check system microphone permissions

**"Processing steps not showing"**
- This means the update failed
- Check browser console for errors
- Verify backend is running on port 8000

## Next Steps

To fully integrate Azure Speech:
1. Add audio upload to backend API
2. Wire Azure Speech SDK in `backend/update_agent.py`
3. Return actual transcription to frontend
4. Remove simulation code

For now, the feature demonstrates the full UX flow! 🎉
