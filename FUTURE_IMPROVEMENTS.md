# 🚀 Future Improvements Checklist

This document tracks enhancement ideas for CascadeAI to implement when time permits.

---

## 📋 Feature Enhancements

### 🎤 Audio & Transcription
- [ ] **Real-time transcription while speaking** (like live captions)
  - Stream audio to Azure Speech API using WebSockets
  - Display text as it's being spoken (continuous recognition mode)
  - Show live captions during recording instead of waiting for full recording to complete
  - Requires: WebSocket connection, Azure Speech SDK continuous recognition, real-time UI updates
  - Estimated effort: 30-60 minutes
  - Benefit: Better UX - nurses can verify accuracy while speaking

### 🎨 UI/UX Improvements
- [ ] TBD (add more as we identify them)

### 🔒 Security & Performance
- [ ] TBD (add more as we identify them)

### 📊 Analytics & Reporting
- [ ] TBD (add more as we identify them)

---

## ✅ Completed Improvements
- [x] **Editable transcription text with keyboard icon** (Feb 27, 2026)
  - Added ⌨️ Edit button to toggle between view and edit modes
  - Transcription text becomes editable textarea when in edit mode
  - Yellow highlight indicates editing mode
  - Users can fix transcription errors before submitting
  - ✅ Done button to save and exit edit mode

---

**Note**: This is a living document. Add new ideas as they come up during development or demos.
