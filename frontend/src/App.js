import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import './App.css';

const API_BASE = 'http://localhost:8000';

// ===== INLINE HELPER COMPONENT =====
function WaveformAnimation({ isRecording }) {
  return (
    <div className="flex items-end gap-1.5 h-10 justify-center">
      {[...Array(8)].map((_, i) => (
        <div
          key={i}
          className={`w-1.5 rounded-full transition-all ${isRecording ? 'waveform-bar bg-primary' : 'h-2 bg-gray-300'
            }`}
          style={!isRecording ? { height: '8px' } : undefined}
        />
      ))}
    </div>
  );
}

function App() {
  // ===== STATE (PRESERVED EXACTLY) =====
  const [nurses, setNurses] = useState([]);
  const [selectedNurse, setSelectedNurse] = useState('');
  const [patientIds, setPatientIds] = useState('P001');
  const [patientName, setPatientName] = useState('');
  const [shiftId, setShiftId] = useState('');
  const [updateText, setUpdateText] = useState('');
  const [updateType, setUpdateType] = useState('medication');
  const [updates, setUpdates] = useState([]);
  const [draft, setDraft] = useState(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Clear shift on page load to prevent stale shift IDs
  useEffect(() => {
    setShiftId('');
    setUpdates([]);
    setDraft(null);
    setPatientName('');
  }, []);

  // Audio recording state
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [mediaRecorder, setMediaRecorder] = useState(null);
  const [audioBlob, setAudioBlob] = useState(null);
  const [transcription, setTranscription] = useState('');
  const [processingSteps, setProcessingSteps] = useState([]);
  const [isEditingTranscription, setIsEditingTranscription] = useState(false);
  const timerIntervalRef = useRef(null);
  const recordingStartRef = useRef(null);

  // Microphone permission state
  const [micPermission, setMicPermission] = useState('checking'); // 'granted', 'denied', 'checking'
  const [showMicHelp, setShowMicHelp] = useState(false);

  // Check microphone permission on mount
  useEffect(() => {
    checkMicrophonePermission();
  }, []);

  const checkMicrophonePermission = async () => {
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setMicPermission('denied');
        return;
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach(track => track.stop()); // Stop immediately after checking
      setMicPermission('granted');
    } catch (err) {
      console.log('Microphone permission:', err.name);
      setMicPermission('denied');
    }
  };

  // Clean up timer on unmount
  useEffect(() => {
    return () => {
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
    };
  }, []);

  // ===== ALL FUNCTIONS (PRESERVED EXACTLY) =====

  // Auto-dismiss helper for toasts
  const showToast = (msg, duration = 5000) => {
    setMessage(msg);
    setTimeout(() => setMessage(''), duration);
  };

  const showError = (msg, duration = 8000) => {
    setError(msg);
    setTimeout(() => setError(''), duration);
  };

  // Copy to clipboard function
  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      showToast('✅ Narrative summary copied to clipboard!', 3000);
    }).catch(err => {
      showError('Failed to copy to clipboard');
      console.error('Copy error:', err);
    });
  };

  // Fetch nurses on load
  useEffect(() => {
    fetchNurses();
  }, []);

  const fetchNurses = async () => {
    try {
      console.log('🔍 Fetching nurses...');
      const response = await axios.get(`${API_BASE}/api/nurses`);
      console.log('✅ Nurses:', response.data);
      setNurses(response.data);
      if (response.data.length > 0) {
        setSelectedNurse(response.data[0].id);
      }
    } catch (err) {
      console.error('❌ Error fetching nurses:', err);
      setError('Failed to fetch nurses: ' + err.message);
    }
  };

  const startShift = async () => {
    if (!selectedNurse) {
      setError('Please select a nurse');
      return;
    }

    setLoading(true);
    setError('');
    setMessage('');

    try {
      const nurse = nurses.find(n => n.id === selectedNurse);
      const patientIdArray = patientIds.split(',').map(id => id.trim());

      console.log('🏥 Starting shift for', nurse.name, 'with patients', patientIdArray);

      const response = await axios.post(`${API_BASE}/api/shift/start`, {
        nurse_id: nurse.id,
        nurse_name: nurse.name,
        shift_type: 'day',
        patient_ids: patientIdArray
      });

      console.log('✅ Shift started:', response.data);
      setShiftId(response.data.shift_id);
      showToast('✅ Shift started successfully!');

      // Fetch patient info for the first patient
      if (patientIdArray.length > 0) {
        try {
          const patientResponse = await axios.get(`${API_BASE}/api/patient/${patientIdArray[0]}/info`);
          console.log('✅ Patient info:', patientResponse.data);
          setPatientName(patientResponse.data.name);
        } catch (patientErr) {
          console.warn('⚠️ Could not fetch patient name:', patientErr);
          setPatientName('Unknown');
        }
      }
    } catch (err) {
      console.error('❌ Error starting shift:', err);
      setError('Failed to start shift: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  // Audio Recording Functions
  const startRecording = async () => {
    try {
      setProcessingSteps([]);
      setTranscription('');
      setAudioBlob(null);
      setError('');

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunks.push(e.data);
        }
      };

      recorder.onstop = async () => {
        const blob = new Blob(chunks, { type: 'audio/webm' });
        setAudioBlob(blob);

        // Stop all tracks
        stream.getTracks().forEach(track => track.stop());

        // Add processing step — use ref for accurate duration (state has stale closure)
        const duration = Math.floor((Date.now() - recordingStartRef.current) / 1000);
        addProcessingStep(`✅ Audio recorded (${duration}s)`, 'success');

        // Transcribe the audio
        await transcribeAudio(blob);
      };

      recorder.start();
      setMediaRecorder(recorder);
      setIsRecording(true);
      setRecordingTime(0);

      // Clear any stale timer before starting a new one
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);

      // Start timer with ref-tracked interval
      recordingStartRef.current = Date.now();
      timerIntervalRef.current = setInterval(() => {
        setRecordingTime(Math.floor((Date.now() - recordingStartRef.current) / 1000));
      }, 1000);

    } catch (err) {
      console.error('❌ Error starting recording:', err);
      setError('Failed to start recording. Please allow microphone access.');
    }
  };

  const stopRecording = () => {
    // Stop the timer immediately
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      mediaRecorder.stop();
      setIsRecording(false);
    }
  };

  const addProcessingStep = (message, status = 'info') => {
    setProcessingSteps(prev => [...prev, { message, status, timestamp: new Date().toISOString() }]);
  };

  const transcribeAudio = async (blob) => {
    try {
      addProcessingStep('⏳ Transcribing audio with Azure Speech...', 'loading');

      // Convert blob to base64 inside a real Promise so errors propagate correctly
      const base64Audio = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result.split(',')[1]);
        reader.onerror = () => reject(new Error('FileReader failed to read audio blob'));
        reader.readAsDataURL(blob);
      });

      // Send audio to backend for transcription (15-second hard timeout)
      const response = await axios.post(`${API_BASE}/api/transcribe`, {
        audio: base64Audio,
        format: 'webm'
      }, { timeout: 15000 });

      if (response.data.success && response.data.transcription) {
        const transcribedText = response.data.transcription;
        console.log('🎤 Azure Speech transcribed:', transcribedText);

        setTranscription(transcribedText);
        addProcessingStep('✅ Transcribed by Azure Speech API', 'success');
        addProcessingStep('📝 Transcription ready for submission', 'success');
      } else {
        throw new Error(response.data.message || 'Transcription failed');
      }
    } catch (err) {
      console.error('❌ Transcription API error:', err);
      addProcessingStep('❌ Transcription failed: ' + (err.response?.data?.detail || err.message), 'error');
      setError('Transcription failed. Using sample text for demo.');

      // Fallback: Set the actual spoken text as a sample (for testing)
      const fallbackText = "Started heparin drip at 1000 units per hour at 11 AM via IV";
      setTranscription(fallbackText);
      addProcessingStep('⚠️ Using fallback transcription for demo', 'warning');
    }
  };

  const submitAudioUpdate = async () => {
    if (!transcription) {
      setError('Please record and transcribe audio first');
      return;
    }

    if (!shiftId) {
      setError('Please start a shift first');
      return;
    }

    const currentPatientId = patientIds.split(',')[0].trim();
    if (!currentPatientId) {
      setError('Please enter a patient ID');
      return;
    }

    setLoading(true);
    setError('');
    setMessage('');

    try {
      console.log('📝 Submitting audio update...');
      console.log('   Shift ID:', shiftId);
      console.log('   Patient:', currentPatientId);
      console.log('   Text:', transcription);

      const response = await axios.post(`${API_BASE}/api/patient/${currentPatientId}/update`, {
        shift_id: shiftId,
        nurse_id: selectedNurse,
        update_type: updateType,
        text: transcription
      });

      console.log('✅ Audio update submitted:', response.data);

      showToast('✅ Audio update submitted successfully!');

      // Reset audio state
      setTranscription('');
      setAudioBlob(null);
      setProcessingSteps([]);
    } catch (err) {
      console.error('❌ Error submitting audio update:', err);
      setError('Failed to submit audio update: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const submitUpdate = async () => {
    if (!shiftId) {
      setError('Please start a shift first');
      return;
    }
    if (!updateText.trim()) {
      setError('Please enter update text');
      return;
    }

    setLoading(true);
    setError('');
    setMessage('');

    // Add processing step for submission
    if (transcription) {
      addProcessingStep('⏳ Submitting update to backend...', 'loading');
    }

    try {
      console.log('📝 Submitting update...');

      const currentPatientId = patientIds.split(',')[0].trim();
      if (!currentPatientId) {
        setError('Please enter a patient ID');
        setLoading(false);
        return;
      }

      const response = await axios.post(`${API_BASE}/api/patient/${currentPatientId}/update`, {
        shift_id: shiftId,
        nurse_id: selectedNurse,
        update_type: updateType,
        text: updateText
      });

      console.log('✅ Update submitted:', response.data);

      if (transcription) {
        addProcessingStep('✅ Saved to database with timestamp', 'success');
      }

      setMessage('✅ Update submitted successfully!');
      setUpdateText(''); // Clear the textarea

      // Display results
      if (response.data.success) {
        const issues = response.data.verification_issues || [];

        // Add EMR verification step
        if (transcription) {
          if (issues.length > 0) {
            addProcessingStep(`✅ Verified against EMR - Found ${issues.length} issue(s)`, 'warning');
          } else {
            addProcessingStep('✅ Verified against EMR - All clear', 'success');
          }
          addProcessingStep('✅ Ready for draft generation', 'success');
        }

        const issuesText = issues.length > 0 ? `\n⚠️ Issues: ${issues.map(i => typeof i === 'object' ? (i.message || i.issue || JSON.stringify(i)) : i).join(', ')}` : '';
        showToast(
          `✅ Update submitted!\n` +
          `📝 ${(response.data.transcription || updateText).substring(0, 60)}...\n` +
          `${response.data.emr_verified ? '✅' : '⚠️'} EMR: ${response.data.emr_verified ? 'Verified' : 'Pending'}${issuesText}`
        );
      }
    } catch (err) {
      console.error('❌ Error submitting update:', err);
      setError('Failed to submit update: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const showAllUpdates = async () => {
    if (!shiftId) {
      setError('Please start a shift first');
      return;
    }

    setLoading(true);
    setError('');

    try {
      console.log('🔍 Fetching all updates...');

      const currentPatientId = patientIds.split(',')[0].trim();
      if (!currentPatientId) {
        setError('Please enter a patient ID');
        setLoading(false);
        return;
      }

      const response = await axios.get(`${API_BASE}/api/patient/${currentPatientId}/updates/${shiftId}`);

      console.log('✅ Updates:', response.data);
      setUpdates(response.data);
      showToast(`✅ Found ${response.data.length} update(s)`, 3000);
    } catch (err) {
      console.error('❌ Error fetching updates:', err);
      setError('Failed to fetch updates: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const generateDraft = async () => {
    if (!shiftId) {
      setError('Please start a shift first');
      return;
    }

    setLoading(true);
    setError('');

    try {
      console.log('📋 Generating draft handoff...');

      const currentPatientId = patientIds.split(',')[0].trim();
      if (!currentPatientId) {
        setError('Please enter a patient ID');
        setLoading(false);
        return;
      }

      const response = await axios.post(`${API_BASE}/api/patient/${currentPatientId}/draft`, {
        shift_id: shiftId
      });

      console.log('✅ Draft generated:', response.data);
      setDraft(response.data.draft_content);
      showToast('✅ Draft generated successfully!');
    } catch (err) {
      console.error('❌ Error generating draft:', err);
      setError('Failed to generate draft: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  // ===== HELPER FUNCTIONS =====

  // Format timestamp to clinical time (HH:MM in 24-hour format)
  const formatClinicalTime = (timestamp) => {
    const date = new Date(timestamp);
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    return `${hours}:${minutes}`;
  };

  // ===== SEVERITY HELPER =====
  const getSeverityClasses = (severity) => {
    const s = (severity || '').toUpperCase();
    switch (s) {
      case 'RED': return { bg: 'bg-red-50', border: 'border-red-200', bar: 'bg-red-500', dot: 'bg-red-500', text: 'text-red-800', badge: 'bg-red-500 text-white' };
      case 'ORANGE': return { bg: 'bg-orange-50', border: 'border-orange-200', bar: 'bg-orange-500', dot: 'bg-orange-500', text: 'text-orange-800', badge: 'bg-orange-500 text-white' };
      case 'YELLOW': return { bg: 'bg-yellow-50', border: 'border-yellow-200', bar: 'bg-yellow-400', dot: 'bg-yellow-400', text: 'text-yellow-800', badge: 'bg-yellow-400 text-black' };
      case 'GREEN': return { bg: 'bg-green-50', border: 'border-green-200', bar: 'bg-green-500', dot: 'bg-green-500', text: 'text-green-800', badge: 'bg-green-500 text-white' };
      case 'BLUE': return { bg: 'bg-blue-50', border: 'border-blue-200', bar: 'bg-blue-500', dot: 'bg-blue-500', text: 'text-blue-800', badge: 'bg-blue-500 text-white' };
      default: return { bg: 'bg-gray-50', border: 'border-gray-200', bar: 'bg-gray-400', dot: 'bg-gray-400', text: 'text-gray-700', badge: 'bg-gray-400 text-white' };
    }
  };

  const getCategoryClasses = (category) => {
    const c = (category || '').toUpperCase();
    switch (c) {
      case 'CRITICAL': return { bg: 'bg-red-50', border: 'border-red-100', bar: 'bg-red-500', icon: 'text-red-500', badge: 'bg-red-500 text-white' };
      case 'HIGH': return { bg: 'bg-orange-50', border: 'border-orange-100', bar: 'bg-orange-500', icon: 'text-orange-500', badge: 'bg-orange-500 text-white' };
      default: return { bg: 'bg-blue-50', border: 'border-blue-100', bar: 'bg-blue-500', icon: 'text-blue-500', badge: 'bg-blue-500 text-white' };
    }
  };

  // ===== NEW TAILWIND UI =====
  return (
    <div className="min-h-screen bg-background-light font-sans">

      {/* ===== GLOBAL MESSAGES ===== */}
      <div className="fixed top-4 right-4 z-50 max-w-sm space-y-2">
        {message && (
          <div className="bg-green-50 border border-green-200 text-green-800 px-5 py-3 rounded-xl shadow-lg text-sm font-medium whitespace-pre-wrap relative pr-10">
            <button onClick={() => setMessage('')} className="absolute top-2 right-3 text-green-400 hover:text-green-700 text-lg font-bold leading-none" title="Dismiss">×</button>
            {message}
          </div>
        )}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-800 px-5 py-3 rounded-xl shadow-lg text-sm font-medium relative pr-10">
            <button onClick={() => setError('')} className="absolute top-2 right-3 text-red-400 hover:text-red-700 text-lg font-bold leading-none" title="Dismiss">×</button>
            {error}
          </div>
        )}
      </div>

      {/* ===== MICROPHONE PERMISSION INDICATOR ===== */}
      <div className="fixed top-4 left-4 z-50">
        {micPermission === 'granted' && (
          <div className="bg-green-50 border border-green-200 px-4 py-2 rounded-full shadow-md flex items-center gap-2">
            <span className="material-icons-outlined text-green-600 text-lg">mic</span>
            <span className="text-green-700 text-xs font-semibold">Mic Ready</span>
          </div>
        )}
        {micPermission === 'denied' && (
          <div className="relative">
            <button
              onClick={() => setShowMicHelp(!showMicHelp)}
              className="bg-red-50 border border-red-200 px-4 py-2 rounded-full shadow-md flex items-center gap-2 hover:bg-red-100 transition-colors cursor-pointer"
            >
              <span className="material-icons-outlined text-red-600 text-lg">mic_off</span>
              <span className="text-red-700 text-xs font-semibold">Mic Blocked</span>
            </button>
            {showMicHelp && (
              <div className="absolute top-full left-0 mt-2 bg-white border border-red-200 rounded-xl shadow-xl p-4 w-72 z-50">
                <p className="text-sm text-slate-700 mb-3">
                  Please allow microphone access in your browser settings, then refresh the page.
                </p>
                <button
                  onClick={checkMicrophonePermission}
                  className="w-full bg-forest-green text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-black transition-colors"
                >
                  Retry Permission Check
                </button>
              </div>
            )}
          </div>
        )}
        {micPermission === 'checking' && (
          <div className="bg-yellow-50 border border-yellow-200 px-4 py-2 rounded-full shadow-md flex items-center gap-2">
            <span className="material-icons-outlined text-yellow-600 text-lg">mic</span>
            <span className="text-yellow-700 text-xs font-semibold">Checking...</span>
          </div>
        )}
      </div>

      {/* ===== BACK TO WEBSITE BUTTON ===== */}
      {!draft && !shiftId && (
        <div className="fixed top-4 right-4 z-40 mr-64">
          <a
            href="/app/website/"
            className="bg-white border border-slate-200 px-4 py-2 rounded-full shadow-md flex items-center gap-2 hover:bg-slate-50 transition-colors text-slate-700 font-semibold text-sm"
          >
            <span className="material-icons-outlined text-slate-600 text-lg">arrow_back</span>
            Back to Website
          </a>
        </div>
      )}

      {/* ===== LOADING OVERLAY ===== */}
      {loading && (
        <div className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40 flex items-center justify-center">
          <div className="bg-white rounded-2xl shadow-2xl px-8 py-6 flex items-center gap-4">
            <div className="w-6 h-6 border-3 border-primary border-t-transparent rounded-full animate-spin" style={{ borderWidth: '3px' }}></div>
            <span className="text-forest-green font-semibold">Processing...</span>
          </div>
        </div>
      )}

      {/* ========================================= */}
      {/* STAGE 1: SHIFT SETUP (when !shiftId)      */}
      {/* ========================================= */}
      {!shiftId && (
        <main className="flex-1 flex flex-col items-center justify-center min-h-screen p-8 lg:p-12">
          {/* Hero heading */}
          <div className="max-w-3xl w-full text-center mb-12">
            <p className="text-xs font-bold tracking-[0.2em] uppercase text-forest-green mb-4">
              Powered by Azure AI
            </p>
            <h1 className="text-5xl lg:text-7xl font-display text-slate-900 leading-tight mb-4">
              Ready for <span className="italic">your shift?</span>
            </h1>
            <p className="text-slate-500 text-lg">
              Select your assignment to let CascadeAI begin verifying EMR records and preparing your handoff workspace.
            </p>
          </div>

          {/* Shift Setup Card */}
          <div className="max-w-2xl w-full bg-white p-10 rounded-3xl shadow-sm border border-slate-100">
            <div className="space-y-8">
              {/* Nurse Selection */}
              <div>
                <label className="block text-sm font-semibold text-slate-500 mb-3 ml-2">Assigned Nurse</label>
                <select
                  value={selectedNurse}
                  onChange={(e) => setSelectedNurse(e.target.value)}
                  disabled={loading}
                  className="w-full bg-slate-50 border-none rounded-2xl py-5 px-6 focus:ring-2 focus:ring-forest-green text-lg cursor-pointer"
                >
                  {nurses.map(nurse => (
                    <option key={nurse.id} value={nurse.id}>
                      {nurse.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Patient ID */}
              <div>
                <div className="flex justify-between items-center mb-3 ml-2">
                  <label className="block text-sm font-semibold text-slate-500">Patient ID</label>
                </div>
                <input
                  type="text"
                  value={patientIds}
                  onChange={(e) => setPatientIds(e.target.value)}
                  placeholder="e.g. P055"
                  disabled={loading}
                  className="w-full bg-slate-50 border-none rounded-2xl py-5 px-6 focus:ring-2 focus:ring-forest-green text-lg"
                />
              </div>

              {/* AI Agents Badge */}
              <div className="flex items-center gap-4 p-4 bg-forest-green/5 rounded-2xl border border-forest-green/10">
                <span className="material-icons-outlined text-forest-green">verified_user</span>
                <p className="text-sm text-slate-600">
                  <strong>5 AI Agents</strong> will cross-check clinical data against EMR records as you start.
                </p>
              </div>

              {/* Start Shift Button */}
              <button
                onClick={startShift}
                disabled={loading}
                className="w-full bg-primary hover:bg-primary-dark transition-all text-forest-green font-bold py-6 rounded-2xl text-xl flex items-center justify-center gap-2 group shadow-lg shadow-primary/20"
              >
                Start Shift
                <span className="material-icons-outlined group-hover:translate-x-1 transition-transform">arrow_forward</span>
              </button>
            </div>
          </div>

          {/* Footer links */}
          <div className="mt-12 flex gap-8 text-sm font-medium text-slate-400">
            <span className="hover:text-forest-green transition-colors cursor-pointer">Privacy Policy</span>
            <span className="hover:text-forest-green transition-colors cursor-pointer">Support</span>
            <span className="hover:text-forest-green transition-colors cursor-pointer">v2.4.0</span>
          </div>
        </main>
      )}

      {/* ========================================= */}
      {/* STAGE 2: UPDATES INTERFACE                */}
      {/* (when shiftId && !draft)                  */}
      {/* ========================================= */}
      {shiftId && !draft && (
        <div className="max-w-4xl mx-auto px-6 py-8">

          {/* Shift Header Bar */}
          <div className="flex items-center justify-between mb-8 pb-6 border-b border-slate-200">
            <div>
              <p className="text-xs font-bold tracking-[0.2em] uppercase text-forest-green mb-1">Active Shift</p>
              <h1 className="font-display text-3xl text-slate-900">
                Patient <span className="italic">{patientIds.split(',')[0].trim()}</span>
                {patientName && <span className="text-slate-500 text-xl ml-2">— {patientName}</span>}
              </h1>
            </div>
            <button
              onClick={() => {
                setShiftId('');
                setUpdates([]);
                setDraft(null);
                setMessage('');
                setError('');
                setUpdateText('');
                setPatientName('');
              }}
              className="flex items-center gap-2 px-5 py-2.5 border border-red-200 rounded-xl text-sm font-semibold text-red-600 hover:bg-red-50 transition-colors"
            >
              <span className="material-icons-outlined text-lg">logout</span>
              End Shift
            </button>
          </div>

          {/* SECTION: Add Patient Update */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden mb-8">
            <div className="p-8">
              {/* Title */}
              <div className="text-center border-b border-slate-100 pb-6 mb-8">
                <h2 className="text-sm font-bold uppercase tracking-widest text-slate-400 mb-2">Add Patient Update</h2>
                <h3 className="font-display text-2xl italic text-forest-green">
                  {patientName || patientIds.split(',')[0].trim()} | {patientIds.split(',')[0].trim()}
                </h3>
              </div>

              {/* Update Type Selector */}
              <div className="mb-8">
                <label className="block text-sm font-bold text-slate-700 mb-4 text-center">Select Update Type</label>
                <div className="flex flex-wrap items-center justify-center gap-3">
                  {['medication', 'vital_signs', 'procedure', 'general'].map(type => (
                    <button
                      key={type}
                      onClick={() => setUpdateType(type)}
                      className={`px-6 py-3 rounded-full border-2 font-medium transition-colors capitalize ${updateType === type
                        ? 'border-forest-green bg-forest-green text-primary'
                        : 'border-slate-200 text-slate-500 hover:border-forest-green hover:text-forest-green'
                        }`}
                    >
                      {type.replace('_', ' ')}
                    </button>
                  ))}
                </div>
              </div>

              {/* Audio Recording Section */}
              <div className="flex flex-col items-center text-center mb-10">
                <div className="w-full max-w-md bg-slate-50 rounded-2xl p-8 mb-6 flex flex-col items-center border border-dashed border-slate-200">
                  {/* Waveform */}
                  <div className="mb-6">
                    <WaveformAnimation isRecording={isRecording} />
                  </div>

                  {/* Recording Timer */}
                  {isRecording && (
                    <p className="text-red-500 font-semibold text-lg mb-4 animate-pulse">
                      🔴 Recording... {recordingTime}s
                    </p>
                  )}

                  {/* Record / Stop Button */}
                  {!isRecording && !transcription && (
                    <button
                      onClick={startRecording}
                      disabled={loading}
                      className="group relative bg-primary hover:bg-primary-dark text-forest-green font-bold py-4 px-8 rounded-full flex items-center gap-3 transition-all transform hover:scale-105 active:scale-95 shadow-lg shadow-primary/20"
                    >
                      <span className="material-icons-outlined">mic</span>
                      Record Audio Update
                      <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 border-2 border-white rounded-full animate-pulse"></span>
                    </button>
                  )}

                  {isRecording && (
                    <button
                      onClick={stopRecording}
                      className="bg-red-500 hover:bg-red-600 text-white font-bold py-4 px-8 rounded-full flex items-center gap-3 transition-all"
                    >
                      <span className="material-icons-outlined">stop</span>
                      Stop Recording
                    </button>
                  )}
                </div>

                {/* Transcription Box */}
                {transcription && (
                  <div className="w-full max-w-md bg-white border border-slate-200 rounded-2xl p-6 text-left">
                    <h4 className="text-sm font-bold text-slate-700 mb-3 flex items-center gap-2">
                      <span className="material-icons-outlined text-forest-green text-sm">edit_note</span>
                      Transcription
                    </h4>
                    {isEditingTranscription ? (
                      <textarea
                        rows="4"
                        value={transcription}
                        onChange={(e) => setTranscription(e.target.value)}
                        autoFocus
                        className="w-full bg-yellow-50 border-2 border-yellow-400 rounded-xl p-4 text-sm focus:ring-yellow-400 focus:border-yellow-400 resize-none"
                      />
                    ) : (
                      <p className="bg-slate-50 border-l-4 border-primary rounded-lg p-4 text-sm text-slate-700 leading-relaxed">
                        {transcription}
                      </p>
                    )}
                    <div className="flex gap-2 mt-4 flex-wrap">
                      <button
                        onClick={() => setIsEditingTranscription(!isEditingTranscription)}
                        disabled={loading}
                        title={isEditingTranscription ? "Done editing" : "Edit transcription"}
                        className="bg-amber-500 hover:bg-amber-600 text-white px-4 py-2 rounded-xl text-sm font-semibold flex items-center gap-1 transition-colors"
                      >
                        <span className="material-icons-outlined text-sm">{isEditingTranscription ? 'check' : 'edit'}</span>
                        {isEditingTranscription ? 'Done' : '⌨️ Edit'}
                      </button>
                      <button
                        onClick={submitAudioUpdate}
                        disabled={loading}
                        className="bg-forest-green hover:bg-forest-green/90 text-primary px-4 py-2 rounded-xl text-sm font-semibold flex items-center gap-1 transition-colors"
                      >
                        <span className="material-icons-outlined text-sm">send</span>
                        Submit Audio Update
                      </button>
                      <button
                        onClick={() => {
                          setTranscription('');
                          setAudioBlob(null);
                          setProcessingSteps([]);
                          setIsEditingTranscription(false);
                        }}
                        disabled={loading}
                        className="bg-slate-400 hover:bg-slate-500 text-white px-4 py-2 rounded-xl text-sm font-semibold flex items-center gap-1 transition-colors"
                      >
                        <span className="material-icons-outlined text-sm">delete</span>
                        Clear
                      </button>
                    </div>
                  </div>
                )}

                {/* Processing Steps */}
                {processingSteps.length > 0 && (
                  <div className="w-full max-w-md mt-4 bg-white border border-slate-200 rounded-2xl p-5 text-left">
                    <h4 className="text-sm font-bold text-slate-700 mb-3">🔄 Processing Steps</h4>
                    <ul className="space-y-2">
                      {processingSteps.map((step, index) => {
                        const stepColors = {
                          success: 'bg-green-50 border-l-4 border-green-500 text-green-800',
                          loading: 'bg-blue-50 border-l-4 border-blue-500 text-blue-800',
                          error: 'bg-red-50 border-l-4 border-red-500 text-red-800',
                          warning: 'bg-yellow-50 border-l-4 border-yellow-500 text-yellow-800',
                          info: 'bg-slate-50 border-l-4 border-slate-400 text-slate-700',
                        };
                        return (
                          <li key={index} className={`px-4 py-2 rounded-r-lg text-sm font-mono ${stepColors[step.status] || stepColors.info}`}>
                            {step.message}
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                )}

                {/* OR divider */}
                <div className="flex items-center gap-4 w-full max-w-md mt-8 mb-2">
                  <div className="h-px flex-1 bg-slate-200"></div>
                  <span className="text-xs uppercase tracking-widest text-slate-400 font-bold">OR</span>
                  <div className="h-px flex-1 bg-slate-200"></div>
                </div>
              </div>

              {/* Text Input Section */}
              <div className="max-w-2xl mx-auto">
                <label className="block text-sm font-bold text-slate-700 mb-3 flex items-center gap-2">
                  <span className="material-icons-outlined text-forest-green text-sm">edit_note</span>
                  Type Text Observation
                </label>
                <div className="relative">
                  <textarea
                    rows="4"
                    value={updateText}
                    onChange={(e) => setUpdateText(e.target.value)}
                    placeholder="Describe the update here..."
                    disabled={loading}
                    className="w-full bg-slate-50 border border-slate-200 rounded-2xl p-6 text-base focus:ring-primary focus:border-primary transition-all placeholder:text-slate-400 resize-none"
                  />
                  <div className="absolute bottom-4 right-4">
                    <button
                      onClick={submitUpdate}
                      disabled={loading}
                      className="bg-forest-green hover:bg-black text-white px-6 py-2.5 rounded-xl font-bold flex items-center gap-2 transition-colors text-sm"
                    >
                      Submit
                      <span className="material-icons-outlined text-sm">send</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* SECTION: View All Updates */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden mb-8">
            <div className="p-8">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  <div className="bg-blue-600 text-white w-8 h-8 rounded-lg flex items-center justify-center font-bold text-sm">3</div>
                  <h2 className="font-display text-2xl text-forest-green">
                    View All <span className="italic">Updates</span>
                  </h2>
                </div>
                <button
                  onClick={showAllUpdates}
                  disabled={loading}
                  className="flex items-center gap-2 px-6 py-2 border border-slate-200 rounded-full text-sm font-semibold text-slate-600 hover:bg-slate-50 transition-colors"
                >
                  <span className="material-icons-outlined text-lg">search</span>
                  Show All Updates
                </button>
              </div>

              {/* Updates Feed */}
              {updates.length > 0 && (
                <div className="space-y-4">
                  {updates.map((update, index) => {
                    const typeColors = {
                      medication: 'bg-blue-50 text-blue-700',
                      vital_signs: 'bg-purple-50 text-purple-700',
                      procedure: 'bg-orange-50 text-orange-700',
                      general: 'bg-green-50 text-green-700',
                    };
                    return (
                      <div key={update.id} className="bg-white border border-slate-100 rounded-xl p-6 transition-all hover:shadow-md">
                        <div className="flex items-center gap-3 mb-3 flex-wrap">
                          <span className="text-slate-400 font-bold text-sm">#{index + 1}</span>
                          <span className="text-slate-700 font-bold text-sm">{formatClinicalTime(update.timestamp)}</span>
                          <span className="text-slate-300 font-bold text-sm">|</span>
                          <span className={`px-3 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider ${typeColors[update.update_type] || 'bg-gray-50 text-gray-700'}`}>
                            {update.update_type}
                          </span>
                          <span className={`flex items-center gap-1 px-3 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider border ${update.emr_verified
                            ? 'bg-green-50 text-green-700 border-green-100'
                            : 'bg-amber-50 text-amber-700 border-amber-100'
                            }`}>
                            <span className="material-icons-outlined text-xs">
                              {update.emr_verified ? 'verified' : 'warning'}
                            </span>
                            {update.emr_verified ? 'Verified' : 'Unverified'}
                          </span>
                        </div>
                        <p className="font-display text-lg text-slate-800 leading-relaxed">
                          {update.transcription.length > 250
                            ? update.transcription.substring(0, 250) + '...'
                            : update.transcription
                          }
                        </p>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* SECTION: Generate Draft Handoff */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden mb-8">
            <div className="p-8">
              <div className="flex items-center gap-3 mb-6">
                <div className="bg-blue-600 text-white w-8 h-8 rounded-lg flex items-center justify-center font-bold text-sm">4</div>
                <h2 className="font-display text-2xl text-forest-green">
                  Generate <span className="italic">Draft Handoff</span>
                </h2>
              </div>
              <button
                onClick={generateDraft}
                disabled={loading}
                className="w-full bg-primary hover:bg-primary-dark text-forest-green py-5 px-8 rounded-xl font-bold text-lg flex items-center justify-center gap-3 transition-all hover:scale-[1.01] shadow-xl shadow-primary/10"
              >
                <span className="material-icons-outlined">assignment_turned_in</span>
                Generate Draft Handoff
              </button>
              <p className="mt-4 text-center text-slate-400 text-sm italic">
                The AI will aggregate all verified updates into a clinical-grade handoff report.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ========================================= */}
      {/* STAGE 3: DRAFT HANDOFF (when draft)       */}
      {/* ========================================= */}
      {draft && (
        <div className="max-w-4xl mx-auto px-6 py-8">
          {/* Draft Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 mb-8 border-b border-slate-200">
            <div>
              <h1 className="text-3xl font-display text-forest-green mb-1">
                Clinical Handoff <span className="italic">Report</span>
              </h1>
              <p className="text-sm text-slate-500">
                Patient: {patientIds.split(',')[0].trim()} {patientName && `— ${patientName}`}
              </p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setDraft(null)}
                className="flex items-center gap-2 px-5 py-2.5 border border-slate-200 rounded-xl text-sm font-semibold text-slate-600 hover:bg-slate-50 transition-colors"
              >
                <span className="material-icons-outlined text-lg">arrow_back</span>
                Back to Updates
              </button>
              <button
                onClick={() => {
                  setShiftId('');
                  setUpdates([]);
                  setDraft(null);
                  setMessage('');
                  setError('');
                  setUpdateText('');
                  setPatientName('');
                }}
                className="flex items-center gap-2 px-5 py-2.5 border border-red-200 rounded-xl text-sm font-semibold text-red-600 hover:bg-red-50 transition-colors"
              >
                <span className="material-icons-outlined text-lg">logout</span>
                End Shift
              </button>
            </div>
          </div>

          {/* Safety Alerts */}
          {draft.safety_alerts && draft.safety_alerts.length > 0 && (
            <section className="mb-8">
              <h2 className="text-xl font-display text-slate-900 flex items-center gap-2 mb-4">
                <span className="material-icons-outlined text-orange-500">warning</span>
                Safety Alerts
              </h2>
              <div className="space-y-3">
                {draft.safety_alerts.map((alert, index) => {
                  const alertObj = typeof alert === 'object' ? alert : { message: alert, severity: 'YELLOW' };
                  const sc = getSeverityClasses(alertObj.severity);
                  return (
                    <div key={index} className={`${sc.bg} border ${sc.border} rounded-xl p-5 flex items-start gap-4 shadow-sm relative overflow-hidden`}>
                      <div className={`absolute top-0 left-0 w-1.5 h-full ${sc.bar}`}></div>
                      <div className={`w-8 h-8 rounded-full ${sc.bg} flex items-center justify-center shrink-0 ml-2`}>
                        <div className={`w-4 h-4 rounded-full ${sc.dot}`}></div>
                      </div>
                      <p className={`text-sm ${sc.text} leading-relaxed font-medium`}>
                        {alertObj.message || alert}
                      </p>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {/* Timeline */}
          {draft.timeline && draft.timeline.length > 0 && (
            <section className="mb-8">
              <h2 className="text-xl font-display text-slate-900 flex items-center gap-2 mb-4">
                <span className="material-icons-outlined text-slate-500">calendar_today</span>
                Timeline
              </h2>
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
                <div className="relative pl-6 border-l-2 border-gray-200 space-y-6">
                  {draft.timeline.map((event, index) => {
                    if (typeof event === 'string') {
                      return (
                        <div key={index} className="relative">
                          <div className="absolute w-3 h-3 bg-gray-400 rounded-full -left-[25px] top-1 ring-4 ring-white"></div>
                          <p className="text-sm text-slate-600">{event}</p>
                        </div>
                      );
                    }
                    const sc = getSeverityClasses(event.severity);
                    return (
                      <div key={index} className="relative">
                        <div className={`absolute w-3 h-3 ${sc.dot} rounded-full -left-[25px] top-1 ring-4 ring-white`}></div>
                        <div className="flex items-baseline gap-2 mb-1">
                          <span className="text-sm font-bold text-slate-700">{event.time}</span>
                          <span className="text-slate-300 font-bold">|</span>
                          <p className="text-sm text-slate-600 flex-1">{event.event}</p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </section>
          )}

          {/* Current Status */}
          {draft.current_status && (
            <section className="mb-8">
              <h2 className="text-xl font-display text-slate-900 flex items-center gap-2 mb-4">
                <span className="material-icons-outlined text-slate-500">monitor_heart</span>
                Current Status
              </h2>

              {/* Medications */}
              {draft.current_status.medications && (
                <div className="mb-6">
                  <h3 className="font-semibold text-slate-600 mb-3">Medications:</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {Array.isArray(draft.current_status.medications)
                      ? draft.current_status.medications.map((med, i) => {
                        if (typeof med === 'string') {
                          return (
                            <div key={i} className="bg-white border border-slate-200 rounded-lg p-4 flex justify-between items-center shadow-sm relative overflow-hidden">
                              <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-green-500"></div>
                              <div className="flex items-center gap-3 pl-2">
                                <div className="w-3 h-3 rounded-full bg-green-500 shrink-0"></div>
                                <p className="text-sm font-medium font-mono text-gray-700">{med}</p>
                              </div>
                              <span className="bg-green-100 text-green-800 text-[10px] font-bold px-2 py-1 rounded tracking-wide">VERIFIED</span>
                            </div>
                          );
                        }
                        const status = med.status || 'VERIFIED';
                        const statusColors = {
                          'VERIFIED': { badge: 'bg-green-100 text-green-800', bar: 'bg-green-500', dot: 'bg-green-500' },
                          'NEW': { badge: 'bg-yellow-100 text-yellow-800', bar: 'bg-yellow-400', dot: 'bg-yellow-400' },
                          'CONFLICTING': { badge: 'bg-red-100 text-red-800', bar: 'bg-red-500', dot: 'bg-red-500' },
                        };
                        const colors = statusColors[status] || { badge: 'bg-gray-100 text-gray-800', bar: 'bg-gray-500', dot: 'bg-gray-500' };
                        return (
                          <div key={i} className={`bg-white border border-slate-200 rounded-lg p-4 flex justify-between items-center shadow-sm relative overflow-hidden`}>
                            <div className={`absolute left-0 top-0 bottom-0 w-1.5 ${colors.bar}`}></div>
                            <div className="flex items-center gap-3 pl-2">
                              <div className={`w-3 h-3 rounded-full ${colors.dot} shrink-0`}></div>
                              <p className="text-sm font-medium font-mono text-gray-700">{med.display || med.name}</p>
                            </div>
                            <span className={`text-[10px] font-bold px-2 py-1 rounded tracking-wide ${colors.badge}`}>
                              {status}
                            </span>
                          </div>
                        );
                      })
                      : <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-sm relative overflow-hidden">
                        <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-green-500"></div>
                        <p className="text-sm font-medium text-gray-700 pl-4">{draft.current_status.medications}</p>
                      </div>
                    }
                  </div>
                </div>
              )}

              {/* Latest Vitals */}
              {draft.current_status.latest_vitals && Object.keys(draft.current_status.latest_vitals).length > 0 && (
                <div className="mb-6">
                  <h3 className="font-semibold text-slate-600 mb-3">Latest Vitals:</h3>
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                    {Object.entries(draft.current_status.latest_vitals).map(([key, vital]) => {
                      const value = typeof vital === 'object' && vital.value ? vital.value : vital;
                      const severity = typeof vital === 'object' ? (vital.severity || 'GREEN') : 'GREEN';
                      const sc = getSeverityClasses(severity);
                      return (
                        <div key={key} className="bg-white border border-slate-200 rounded-lg p-4 flex flex-col items-center justify-center shadow-sm relative overflow-hidden text-center">
                          <div className={`absolute left-0 top-0 bottom-0 w-1.5 ${sc.bar}`}></div>
                          <div className={`w-3 h-3 rounded-full ${sc.dot} mb-2`}></div>
                          <p className="text-xs font-bold text-gray-500 mb-1">{key.toUpperCase()}:</p>
                          <p className="text-sm font-semibold font-mono">{value}</p>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Overall Condition */}
              {draft.current_status.overall_condition && (
                <div>
                  <h3 className="font-semibold text-slate-600 mb-2">Overall Condition:</h3>
                  <p className="text-sm leading-relaxed text-slate-600 border-b border-slate-200 pb-6">
                    {draft.current_status.overall_condition}
                  </p>
                </div>
              )}
            </section>
          )}

          {/* Key Changes */}
          {draft.key_changes && draft.key_changes.length > 0 && (
            <section className="mb-8">
              <h2 className="text-xl font-display text-slate-900 flex items-center gap-2 mb-4">
                <span className="material-icons-outlined text-slate-500">notifications_active</span>
                Key Changes
              </h2>
              <div className="space-y-3">
                {draft.key_changes.map((change, index) => {
                  if (typeof change === 'string') {
                    return (
                      <div key={index} className="bg-white border border-slate-200 rounded-lg p-4 flex gap-4 shadow-sm relative overflow-hidden items-center">
                        <div className="absolute left-0 top-0 bottom-0 w-1 bg-blue-500"></div>
                        <div className="w-3 h-3 rounded-full bg-blue-500 shrink-0 ml-2"></div>
                        <p className="text-sm font-medium leading-relaxed">{change}</p>
                      </div>
                    );
                  }
                  const sc = getSeverityClasses(change.severity);
                  return (
                    <div key={index} className={`bg-white border border-slate-200 rounded-lg p-4 flex gap-4 shadow-sm relative overflow-hidden items-center`}>
                      <div className={`absolute left-0 top-0 bottom-0 w-1 ${sc.bar}`}></div>
                      <div className={`w-3 h-3 rounded-full ${sc.dot} shrink-0 ml-2`}></div>
                      <p className="text-sm font-medium leading-relaxed">{change.change}</p>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {/* Pending Actions */}
          {draft.pending_actions && draft.pending_actions.length > 0 && (
            <section className="mb-8">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-display text-slate-900 flex items-center gap-2">
                  <span className="material-icons-outlined text-slate-500">fact_check</span>
                  Pending Actions
                </h2>
                <span className="bg-white border border-slate-200 px-3 py-1 rounded-full text-xs font-semibold shadow-sm">
                  {draft.pending_actions.length} Tasks
                </span>
              </div>
              <div className="space-y-3">
                {draft.pending_actions
                  .sort((a, b) => {
                    const priorityA = typeof a === 'object' ? (a.priority || 3) : 3;
                    const priorityB = typeof b === 'object' ? (b.priority || 3) : 3;
                    return priorityA - priorityB;
                  })
                  .map((action, index) => {
                    if (typeof action === 'string') {
                      const category = action.includes('🚨') || action.toLowerCase().includes('critical') ? 'CRITICAL' :
                        action.includes('⚠️') || action.toLowerCase().includes('high') ? 'HIGH' : 'ROUTINE';
                      const cc = getCategoryClasses(category);
                      return (
                        <div key={index} className={`${cc.bg} border ${cc.border} rounded-lg shadow-sm relative overflow-hidden`}>
                          <div className={`absolute left-0 top-0 bottom-0 w-1.5 ${cc.bar}`}></div>
                          <div className="p-4 pl-6 flex items-start gap-4">
                            <span className={`material-icons-outlined ${cc.icon} bg-opacity-10 p-1.5 rounded text-lg`}>
                              {category === 'CRITICAL' ? 'error' : category === 'HIGH' ? 'warning' : 'content_paste'}
                            </span>
                            <div className="flex-grow">
                              <div className="flex justify-between items-start gap-4">
                                <p className="text-sm font-medium leading-relaxed pr-4">{action}</p>
                                <span className={`shrink-0 ${cc.badge} text-[10px] font-bold px-2 py-1 rounded uppercase tracking-wide`}>
                                  {category}
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    }
                    const category = (action.category || 'ROUTINE').toUpperCase();
                    const cc = getCategoryClasses(category);
                    return (
                      <div key={index} className={`${cc.bg} border ${cc.border} rounded-lg shadow-sm relative overflow-hidden`}>
                        <div className={`absolute left-0 top-0 bottom-0 w-1.5 ${cc.bar}`}></div>
                        <div className="p-4 pl-6 flex items-start gap-4">
                          <span className={`material-icons-outlined ${cc.icon} bg-opacity-10 p-1.5 rounded text-lg`}>
                            {category === 'CRITICAL' ? 'error' : category === 'HIGH' ? 'warning' : 'content_paste'}
                          </span>
                          <div className="flex-grow">
                            <div className="flex justify-between items-start gap-4">
                              <p className="text-sm font-medium leading-relaxed pr-4">{action.action}</p>
                              <span className={`shrink-0 ${cc.badge} text-[10px] font-bold px-2 py-1 rounded uppercase tracking-wide`}>
                                {action.category || 'ROUTINE'}
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
              </div>
            </section>
          )}

          {/* Narrative Summary */}
          {draft.narrative_summary && (
            <section className="mb-8">
              <h2 className="text-xl font-display text-slate-900 flex items-center gap-2 mb-1">
                <span className="material-icons-outlined text-slate-500">notes</span>
                Narrative Summary
              </h2>
              <p className="text-sm text-slate-500 mb-4">Copy-paste ready handoff summary for documentation</p>
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm relative">
                <button
                  onClick={() => copyToClipboard(draft.narrative_summary)}
                  className="absolute top-4 right-4 text-forest-green hover:bg-slate-100 transition-colors flex items-center gap-1 text-xs font-semibold border border-slate-200 px-3 py-1.5 rounded-lg bg-white"
                  title="Copy to clipboard"
                >
                  <span className="material-icons-outlined text-sm">content_copy</span>
                  Copy
                </button>
                <p className="text-sm leading-relaxed text-slate-600 pr-20">
                  {draft.narrative_summary}
                </p>
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );

  // ===== OLD UI (COMMENTED OUT - BACKUP) =====
  // The original return statement (lines 418-883 from the old App.js) has been
  // replaced with the new Tailwind UI above. The old code can be found in the
  // git backup branch: backup-2026-03-06-working
  // ===== END OLD UI =====
}

export default App;
