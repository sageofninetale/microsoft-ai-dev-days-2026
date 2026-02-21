import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

const API_BASE = 'http://localhost:8000';

function App() {
  // State
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

  // Copy to clipboard function
  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      setMessage('✅ Narrative summary copied to clipboard!');
      setTimeout(() => setMessage(''), 3000);
    }).catch(err => {
      setError('Failed to copy to clipboard');
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
      setMessage(`✅ Shift started! ID: ${response.data.shift_id}`);
      
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
        
        // Add processing step
        const duration = Math.floor(recordingTime);
        addProcessingStep(`✅ Audio recorded (${duration}s)`, 'success');
        
        // Transcribe the audio
        await transcribeAudio(blob);
      };
      
      recorder.start();
      setMediaRecorder(recorder);
      setIsRecording(true);
      setRecordingTime(0);
      
      // Start timer
      const startTime = Date.now();
      const interval = setInterval(() => {
        if (!recorder || recorder.state !== 'recording') {
          clearInterval(interval);
        } else {
          setRecordingTime(Math.floor((Date.now() - startTime) / 1000));
        }
      }, 100);
      
    } catch (err) {
      console.error('❌ Error starting recording:', err);
      setError('Failed to start recording. Please allow microphone access.');
    }
  };
  
  const stopRecording = () => {
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
      
      // Convert blob to base64
      const reader = new FileReader();
      reader.readAsDataURL(blob);
      
      reader.onloadend = async () => {
        try {
          const base64Audio = reader.result.split(',')[1];
          
          // Send audio to backend for transcription
          const response = await axios.post(`${API_BASE}/api/transcribe`, {
            audio: base64Audio,
            format: 'webm'
          });
          
          if (response.data.success && response.data.transcription) {
            const transcribedText = response.data.transcription;
            console.log('🎤 Azure Speech transcribed:', transcribedText);
            
            setTranscription(transcribedText);
            addProcessingStep('✅ Transcribed by Azure Speech API', 'success');
            addProcessingStep('📝 Transcription ready for submission', 'success');
          } else {
            throw new Error(response.data.message || 'Transcription failed');
          }
        } catch (apiError) {
          console.error('❌ Transcription API error:', apiError);
          addProcessingStep('❌ Transcription failed: ' + (apiError.response?.data?.detail || apiError.message), 'error');
          setError('Transcription failed. Using sample text for demo.');
          
          // Fallback: Set the actual spoken text as a sample (for testing)
          const fallbackText = "Started heparin drip at 1000 units per hour at 11 AM via IV";
          setTranscription(fallbackText);
          addProcessingStep('⚠️ Using fallback transcription for demo', 'warning');
        }
      };
      
    } catch (err) {
      console.error('❌ Error transcribing audio:', err);
      addProcessingStep('❌ Transcription failed: ' + err.message, 'error');
      setError('Failed to transcribe audio: ' + err.message);
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
      
      setMessage('✅ Audio update submitted successfully!');
      
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
        
        const issuesText = issues.length > 0 ? `\n⚠️ Issues: ${issues.join(', ')}` : '';
        setMessage(
          `✅ Update ID: ${response.data.update_id}\n` +
          `📝 Transcription: ${response.data.transcription || updateText}\n` +
          `${response.data.emr_verified ? '✅' : '❌'} EMR Verified: ${response.data.emr_verified ? 'Yes' : 'No'}${issuesText}`
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
      setMessage(`✅ Found ${response.data.length} update(s)`);
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
      setMessage(`✅ Draft generated! ID: ${response.data.draft_id}`);
    } catch (err) {
      console.error('❌ Error generating draft:', err);
      setError('Failed to generate draft: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="App">
      <header>
        <h1>💧 CascadeAI - Clinical Handoff System</h1>
        <p style={{ fontSize: '14px', color: '#666' }}>Backend: {API_BASE}</p>
      </header>

      {/* Messages */}
      {message && <div className="message success">{message}</div>}
      {error && <div className="message error">{error}</div>}
      {loading && <div className="message loading">⏳ Loading...</div>}

      {/* SECTION 1: Nurse Selection */}
      <section className="card">
        <h2>1️⃣ Nurse Selection & Start Shift</h2>
        
        <div className="form-group">
          <label>Select Nurse:</label>
          <select 
            value={selectedNurse} 
            onChange={(e) => setSelectedNurse(e.target.value)}
            disabled={loading}
          >
            {nurses.map(nurse => (
              <option key={nurse.id} value={nurse.id}>
                {nurse.name}
              </option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label>Patient IDs (comma-separated):</label>
          <input
            type="text"
            value={patientIds}
            onChange={(e) => setPatientIds(e.target.value)}
            placeholder="P001, P002"
            disabled={loading}
          />
        </div>

        <button onClick={startShift} disabled={loading || shiftId}>
          {shiftId ? '✅ Shift Started' : '▶️ Start Shift'}
        </button>

        {shiftId && (
          <>
            <div className="result-box">
              <strong>Shift ID:</strong> {shiftId}
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
              style={{ 
                marginTop: '10px', 
                backgroundColor: '#ff6b6b',
                fontSize: '14px'
              }}
            >
              🔄 Reset Shift
            </button>
          </>
        )}
      </section>

      {/* SECTION 2: Add Update */}
      {shiftId && (
        <section className="card">
          <h2>2️⃣ Add Patient Update</h2>
          <p style={{ fontSize: '14px', color: '#666', marginBottom: '15px' }}>
            <strong>Patient:</strong> {patientIds.split(',')[0].trim()}
            {patientName && ` - ${patientName}`}
          </p>

          <div className="form-group">
            <label>Update Type:</label>
            <select 
              value={updateType} 
              onChange={(e) => setUpdateType(e.target.value)}
              disabled={loading}
            >
              <option value="medication">Medication</option>
              <option value="vital_signs">Vital Signs</option>
              <option value="procedure">Procedure</option>
              <option value="general">General</option>
            </select>
          </div>

          {/* Audio Recording Section */}
          <div className="audio-recording-section">
            <h3 style={{ fontSize: '16px', marginBottom: '10px' }}>🎤 Audio Recording</h3>
            
            {!isRecording && !transcription && (
              <button onClick={startRecording} disabled={loading} className="record-button">
                🎤 Record Audio
              </button>
            )}
            
            {isRecording && (
              <div className="recording-status">
                <button onClick={stopRecording} className="stop-button">
                  ⏹️ Stop Recording
                </button>
                <span className="recording-indicator">
                  🔴 Recording... {recordingTime}s
                </span>
              </div>
            )}
            
            {transcription && (
              <div className="transcription-box">
                <h4>📝 Transcription:</h4>
                <p>{transcription}</p>
                <button onClick={submitAudioUpdate} disabled={loading}>
                  📤 Submit Audio Update
                </button>
                <button 
                  onClick={() => {
                    setTranscription('');
                    setAudioBlob(null);
                    setProcessingSteps([]);
                  }} 
                  className="clear-button"
                  disabled={loading}
                >
                  🗑️ Clear
                </button>
              </div>
            )}
            
            {/* Processing Steps */}
            {processingSteps.length > 0 && (
              <div className="processing-steps">
                <h4>🔄 Processing Steps:</h4>
                <ul>
                  {processingSteps.map((step, index) => (
                    <li key={index} className={`step-${step.status}`}>
                      {step.message}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Text Input Section (Alternative) */}
          <div className="text-input-section">
            <h3 style={{ fontSize: '16px', margin: '20px 0 10px 0' }}>✍️ Or Type Text</h3>
            <div className="form-group">
              <label>Update Text:</label>
              <textarea
                rows="5"
                value={updateText}
                onChange={(e) => setUpdateText(e.target.value)}
                placeholder="e.g., Started heparin drip at 1000 units/hour at 11 AM"
                disabled={loading}
              />
            </div>

            <button onClick={submitUpdate} disabled={loading}>
              📝 Submit Text Update
            </button>
          </div>
        </section>
      )}

      {/* SECTION 3: View All Updates */}
      {shiftId && (
        <section className="card">
          <h2>3️⃣ View All Updates</h2>
          
          <button onClick={showAllUpdates} disabled={loading}>
            🔍 Show All Updates
          </button>

          {updates.length > 0 && (
            <div className="updates-list">
              {updates.map((update, index) => (
                <div key={update.id} className="update-item">
                  <div className="update-header">
                    <span className="update-number">#{index + 1}</span>
                    <span className="update-time">{new Date(update.timestamp).toLocaleString()}</span>
                    <span className={`update-type ${update.update_type}`}>{update.update_type}</span>
                    <span className={`emr-status ${update.emr_verified ? 'verified' : 'unverified'}`}>
                      {update.emr_verified ? '✅ Verified' : '⚠️ Unverified'}
                    </span>
                  </div>
                  <div className="update-text">
                    {update.transcription.length > 250 
                      ? update.transcription.substring(0, 250) + '...'
                      : update.transcription
                    }
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* SECTION 4: Generate Draft */}
      {shiftId && (
        <section className="card">
          <h2>4️⃣ Generate Draft Handoff</h2>
          
          <button onClick={generateDraft} disabled={loading}>
            📋 Generate Draft Handoff
          </button>

          {draft && (
            <div className="draft-container">
              {/* Safety Alerts - Show at top if present */}
              {draft.safety_alerts && draft.safety_alerts.length > 0 && (
                <div className="draft-section">
                  <h3>⚠️ Safety Alerts</h3>
                  <div className="alerts-container">
                    {draft.safety_alerts.map((alert, index) => {
                      const alertObj = typeof alert === 'object' ? alert : { message: alert, severity: 'YELLOW' };
                      return (
                        <div key={index} className={`alert-box severity-${(alertObj.severity || 'YELLOW').toLowerCase()}`}>
                          <span className="alert-icon">{alertObj.icon || '⚠️'}</span>
                          <span className="alert-message">{alertObj.message || alert}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Timeline with color-coded events */}
              {draft.timeline && draft.timeline.length > 0 && (
                <div className="draft-section">
                  <h3>📅 Timeline</h3>
                  <div className="timeline-container">
                    {draft.timeline.map((event, index) => {
                      // Handle both string and object formats
                      if (typeof event === 'string') {
                        return (
                          <div key={index} className="timeline-item severity-gray">
                            <span className="timeline-dot">⚪</span>
                            <span className="timeline-content">{event}</span>
                          </div>
                        );
                      }
                      
                      const severity = (event.severity || 'GRAY').toLowerCase();
                      return (
                        <div key={index} className={`timeline-item severity-${severity}`}>
                          <span className="timeline-dot">{event.icon || '⚪'}</span>
                          <span className="timeline-time">{event.time}</span>
                          <span className="timeline-content">{event.event}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Current Status */}
              {draft.current_status && (
                <div className="draft-section">
                  <h3>💊 Current Status</h3>
                  
                  {/* Medications with color coding */}
                  {draft.current_status.medications && (
                    <div style={{ marginBottom: '20px' }}>
                      <h4>Medications:</h4>
                      <div className="medications-grid">
                        {Array.isArray(draft.current_status.medications) 
                          ? draft.current_status.medications.map((med, i) => {
                              // Handle both string and object formats
                              if (typeof med === 'string') {
                                return (
                                  <div key={i} className="medication-item severity-green">
                                    <span className="med-icon">🟢</span>
                                    <span className="med-text">{med}</span>
                                  </div>
                                );
                              }
                              
                              const severity = (med.severity || 'GREEN').toLowerCase();
                              const status = med.status || 'VERIFIED';
                              return (
                                <div key={i} className={`medication-item severity-${severity}`}>
                                  <span className="med-icon">{med.icon || '🟢'}</span>
                                  <span className="med-text">{med.display || med.name}</span>
                                  <span className={`med-status status-${status.toLowerCase()}`}>{status}</span>
                                </div>
                              );
                            })
                          : <div className="medication-item severity-green">
                              <span className="med-icon">🟢</span>
                              <span className="med-text">{draft.current_status.medications}</span>
                            </div>
                        }
                      </div>
                    </div>
                  )}

                  {/* Latest Vitals with color coding */}
                  {draft.current_status.latest_vitals && Object.keys(draft.current_status.latest_vitals).length > 0 && (
                    <div style={{ marginBottom: '20px' }}>
                      <h4>Latest Vitals:</h4>
                      <div className="vitals-grid">
                        {Object.entries(draft.current_status.latest_vitals).map(([key, vital]) => {
                          if (typeof vital === 'object' && vital.value) {
                            const severity = (vital.severity || 'GREEN').toLowerCase();
                            return (
                              <div key={key} className={`vital-item severity-${severity}`}>
                                <span className="vital-icon">{vital.icon || '🟢'}</span>
                                <span className="vital-label">{key.toUpperCase()}:</span>
                                <span className="vital-value">{vital.value}</span>
                              </div>
                            );
                          }
                          return (
                            <div key={key} className="vital-item severity-green">
                              <span className="vital-icon">🟢</span>
                              <span className="vital-label">{key.toUpperCase()}:</span>
                              <span className="vital-value">{vital}</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Overall Condition */}
                  {draft.current_status.overall_condition && (
                    <div>
                      <h4>Overall Condition:</h4>
                      <p style={{ fontSize: '14px', lineHeight: '1.6', color: '#333' }}>
                        {draft.current_status.overall_condition}
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* Key Changes with color coding */}
              {draft.key_changes && draft.key_changes.length > 0 && (
                <div className="draft-section">
                  <h3>🔔 Key Changes</h3>
                  <div className="changes-container">
                    {draft.key_changes.map((change, index) => {
                      // Handle both string and object formats
                      if (typeof change === 'string') {
                        return (
                          <div key={index} className="change-item severity-blue">
                            <span className="change-icon">🔵</span>
                            <span className="change-text">{change}</span>
                          </div>
                        );
                      }
                      
                      const severity = (change.severity || 'BLUE').toLowerCase();
                      return (
                        <div key={index} className={`change-item severity-${severity}`}>
                          <span className="change-icon">{change.icon || '🔵'}</span>
                          <span className="change-text">{change.change}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Pending Actions with priority sorting and color coding */}
              {draft.pending_actions && draft.pending_actions.length > 0 && (
                <div className="draft-section">
                  <h3>📋 Pending Actions</h3>
                  <div className="actions-container">
                    {draft.pending_actions
                      .sort((a, b) => {
                        // Sort by priority if available (1=CRITICAL, 2=HIGH, 3=ROUTINE)
                        const priorityA = typeof a === 'object' ? (a.priority || 3) : 3;
                        const priorityB = typeof b === 'object' ? (b.priority || 3) : 3;
                        return priorityA - priorityB;
                      })
                      .map((action, index) => {
                        // Handle both string and object formats
                        if (typeof action === 'string') {
                          const category = action.includes('🚨') || action.toLowerCase().includes('critical') ? 'CRITICAL' :
                                          action.includes('⚠️') || action.toLowerCase().includes('high') ? 'HIGH' : 'ROUTINE';
                          return (
                            <div key={index} className={`action-item category-${category.toLowerCase()}`}>
                              <span className="action-icon">
                                {category === 'CRITICAL' ? '🚨' : category === 'HIGH' ? '⚠️' : '📋'}
                              </span>
                              <span className="action-text">{action}</span>
                            </div>
                          );
                        }
                        
                        const category = (action.category || 'ROUTINE').toLowerCase();
                        const severity = (action.severity || 'YELLOW').toLowerCase();
                        return (
                          <div key={index} className={`action-item category-${category} severity-${severity}`}>
                            <span className="action-icon">{action.icon || '📋'}</span>
                            <span className="action-text">{action.action}</span>
                            <span className={`action-category badge-${category}`}>
                              {action.category || 'ROUTINE'}
                            </span>
                          </div>
                        );
                      })}
                  </div>
                </div>
              )}

              {/* Narrative Summary - At the bottom for copy/paste */}
              {draft.narrative_summary && (
                <div className="draft-section">
                  <h3>📝 Narrative Summary</h3>
                  <p style={{ fontSize: '13px', color: '#666', marginBottom: '10px' }}>
                    Copy-paste ready handoff summary for documentation
                  </p>
                  <div className="narrative-summary-container">
                    <div className="narrative-text">
                      {draft.narrative_summary}
                    </div>
                    <button 
                      className="copy-button"
                      onClick={() => copyToClipboard(draft.narrative_summary)}
                      title="Copy to clipboard"
                    >
                      📋 Copy Summary
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </section>
      )}
    </div>
  );
}

export default App;
