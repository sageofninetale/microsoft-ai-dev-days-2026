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

### � Clinical Features (from Physiotherapist Feedback)
- [ ] **Investigation updates** (lab orders, imaging requests)
  - Add "Investigation" as 5th update type
  - Track lab orders, imaging requests, pending results
  - Alert when results are due but not documented
  - Benefit: Complete clinical workflow coverage
  
- [ ] **Pre-operative and post-operative care tracking**
  - Add "Pre-Op" and "Post-Op" update types
  - Track surgical prep checklist items
  - Monitor post-op vitals and recovery milestones
  - Generate specialized handoffs for surgical patients
  - Benefit: Better support for surgical units

### � Multi-Patient Batch Processing System (HIGH PRIORITY)
- [ ] **Task-based batch workflow for 10+ patients**
  - **Problem**: Current system requires documenting each patient individually (time-consuming, unnatural workflow)
  - **Solution**: Batch updates by task type (matches real nursing workflow)
  
  **Workflow Redesign:**
  1. **Shift Start**: Nurse enters multiple patient IDs (P001-P010)
  2. **Task-Based Rounds**:
     - Medication Round: Record meds for all 10 patients consecutively
     - Vitals Round: Record vitals for all 10 patients consecutively
     - Procedures Round: Record procedures for 5-6 patients who need them
     - General Round: Ad-hoc updates as needed
  3. **Review Stage**: View updates grouped by patient with count badges
     - Visual priority: 🔴 P005 (7 updates) vs 🟢 P009 (0 updates)
     - Expand each patient to see their timeline
     - Quality control: Catch missing data before handoff
  4. **Batch Generation**: Generate 10 separate handoff PDFs simultaneously
     - Individual [View] and [Download] buttons per patient
     - [Download All as ZIP] for bulk download
     - [Email to Next Shift] option
  
  **Key Features:**
  - Patient selector dropdown in update form: "Which patient is this for?"
  - Left sidebar with patient list + status indicators (🟢🟡🔴)
  - Updates grouped by patient_id in database (add patient_id column to patient_updates table)
  - Backend loop: For each patient, generate separate handoff PDF
  - Frontend state: `updatesByPatient = { 'P001': [...], 'P003': [...] }`
  
  **Why This is Better:**
  - ✅ Matches real nursing workflow (task-based rounds, not patient-by-patient)
  - ✅ Time savings: 30 minutes per shift (2 hours vs 2.5 hours)
  - ✅ Reduced cognitive load: 4 context switches vs 10
  - ✅ Better prioritization: Visual urgency indicators
  - ✅ Error detection: Review stage catches missing data
  - ✅ ROI: $27,350 saved per nurse per year in time savings
  - ✅ Market differentiator: Epic/Cerner don't have intelligent batch processing
  
  **Technical Implementation:**
  - Database: Add `patient_id` column to `patient_updates` table
  - Frontend: Patient selector component, patient sidebar, grouped review view
  - Backend: New endpoint `/api/shift/{shift_id}/generate-all-handoffs`
  - PDF Generation: Loop through patients, generate individual PDFs, return as array
  - ZIP Download: Bundle PDFs using Python `zipfile` or Node.js `archiver`
  
  **Estimated Effort**: 12-15 hours (2-3 days post-hackathon)
  - Database changes: 1 hour
  - Frontend UI (sidebar + selector): 4 hours
  - Backend batch generation: 3 hours
  - PDF generation library integration: 4 hours
  - Testing with 10 patients: 2 hours
  
  **Testing Strategy:**
  - Create 10 test patients (P001-P010) in Supabase
  - Record 5-7 updates per patient across different types
  - Verify each patient's handoff contains only their updates
  - Test ZIP download with all 10 PDFs
  - Validate with real nurse feedback (critical!)
  
  **Success Metrics:**
  - Time to document 10 patients < 2 hours
  - Nurse satisfaction score > 8/10
  - Error detection rate in review stage > 80%
  - Hospital adoption willingness > 70%

### 🔌 EMR Integration Plugin (CRITICAL FOR PRODUCTION)
- [ ] **FHIR Integration Plugin for Real-World Hospital EMR Systems**
  - **Problem**: Current system uses fake Supabase data. Real hospitals have Epic/Cerner/Meditech EMR systems with real patient data.
  - **Solution**: Build integration plugin to connect CascadeAI to ANY hospital EMR via FHIR API
  
  **What to Build:**
  1. **FHIR Adapter Library**: Python/Node.js library that connects to any FHIR-compliant EMR
  2. **Configuration Dashboard**: Web UI where hospital IT enters FHIR endpoint, OAuth credentials, tests connection
  3. **Data Mapping Engine**: Translates hospital data format ↔ CascadeAI format (auto-detect for common EMRs)
  4. **Pre-built EMR Connectors**: Epic, Cerner, Meditech, Allscripts (one-click setup for 80% of market)
  5. **Self-Service Setup Portal**: Hospital signs up, follows wizard, connects in 1 hour without your help
  6. **Monitoring Dashboard**: Connection health, API call success rate, error alerts
  
  **Integration Process** (when hospital wants to use CascadeAI):
  - Week 1: Hospital IT provides API credentials → You configure plugin → Test in sandbox
  - Week 2: Pilot with 10 nurses using real patient data → Monitor for issues
  - Week 3: Full rollout to all nurses → Ongoing support
  
  **Business Benefits:**
  - Enables CascadeAI to work with ANY hospital worldwide (scalability)
  - No data migration needed (read directly from hospital EMR in real-time)
  - HIPAA-compliant (read-only access, data never leaves hospital)
  - Competitive advantage (Epic/Cerner don't have intelligent AI handoff generation)
  
  **Estimated Effort**: 
  - Phase 1 (Core FHIR plugin): 2-3 months
  - Phase 2 (Pre-built connectors): 3-6 months
  - Phase 3 (Self-service portal): 6-9 months
  
  **ROI for Hospitals**:
  - $5K setup fee + $2K/month for 200 nurses
  - Hospital saves $27K per nurse per year in time savings
  - Total ROI: $5.4M saved annually for 200-nurse hospital
  
  **See INTEGRATION_GUIDE.md for complete technical and business details.**

### � UI/UX Improvements
- [ ] Dark mode toggle in UI (designs already support it)
- [ ] Mobile-responsive refinements
- [ ] Accessibility audit (WCAG 2.1 AA compliance)
- [ ] Keyboard shortcuts for power users

### ✅ Pending Actions Task Completion Tracking (IMPORTANT FOR ACCOUNTABILITY)
- [ ] **Task completion tracking system for handoff accountability**
  - **Problem**: Current system shows pending actions in handoff report, but no way to track if incoming nurse actually completes them
  - **Solution**: Add task lifecycle tracking with checkboxes, audit trail, and smart carry-forward logic
  
  **What Happens Now:**
  - Outgoing nurse creates handoff with "Pending Actions" section
  - Incoming nurse reads handoff, sees tasks like "Give 10mg morphine at 20:00"
  - No verification that task was actually done
  - Tasks can get lost between shifts, patient safety risk
  
  **What We Need to Build:**
  
  **1. Database Schema Changes** (add to Supabase):
  ```sql
  -- Add columns to track task completion
  ALTER TABLE patient_updates ADD COLUMN task_id UUID DEFAULT gen_random_uuid();
  ALTER TABLE patient_updates ADD COLUMN task_status VARCHAR(20) DEFAULT 'pending';
    -- Values: 'pending', 'in_progress', 'completed', 'cancelled'
  ALTER TABLE patient_updates ADD COLUMN completed_at TIMESTAMP;
  ALTER TABLE patient_updates ADD COLUMN completed_by VARCHAR(100);
  ALTER TABLE patient_updates ADD COLUMN completion_notes TEXT;
  ALTER TABLE patient_updates ADD COLUMN carried_forward BOOLEAN DEFAULT false;
  ```
  
  **2. Frontend UI Components**:
  - **Checkbox next to each pending action** in handoff report
  - Click checkbox → modal appears: "Add completion note (optional)"
  - Submit → task marked complete with timestamp
  - Visual states:
    * ⏳ Gray checkbox = Pending
    * ⚙️ Blue checkbox + spinner = In Progress
    * ✅ Green checkmark = Completed (shows who + when)
    * 🚫 Red X = Cancelled (shows reason)
  - Strikethrough text for completed/cancelled tasks
  - **Filter buttons**: Show All | Pending Only | Completed Only
  
  **3. Backend API Endpoints**:
  ```python
  # New endpoint in api.py
  @app.post("/api/task/{task_id}/complete")
  async def complete_task(
      task_id: str,
      nurse_id: str,
      completion_notes: Optional[str] = None
  ):
      """Mark a pending action as completed"""
      # Update task_status to 'completed'
      # Record completed_at timestamp
      # Record completed_by nurse
      # Save completion_notes
      # Return updated task
  
  @app.post("/api/task/{task_id}/cancel")
  async def cancel_task(
      task_id: str,
      nurse_id: str,
      reason: str
  ):
      """Cancel a pending action with reason"""
      # Update task_status to 'cancelled'
      # Save cancellation reason
  
  @app.get("/api/shift/{shift_id}/tasks")
  async def get_shift_tasks(shift_id: str, status: Optional[str] = None):
      """Get all tasks for a shift, optionally filtered by status"""
      # Return all pending actions with completion status
  ```
  
  **4. Smart Carry-Forward Logic**:
  - When generating new handoff, check if previous shift has incomplete tasks
  - If task still pending after 2+ hours → auto-carry forward to next handoff
  - Mark with 🔴 "OVERDUE" badge and escalate priority
  - Example: "Give morphine at 20:00" not completed by 22:00 → shows in next handoff as urgent
  
  **5. Audit Trail & Reporting**:
  - Track who completed each task and when
  - Generate completion rate reports per nurse/unit
  - Flag patterns: Nurse always skips certain task types (training issue?)
  - Export compliance reports for management
  
  **Implementation Phases:**
  
  **Phase 1 - Basic (2-3 hours):**
  - Add task_id and task_status columns to database
  - Add checkbox UI next to each pending action
  - Implement `/api/task/{id}/complete` endpoint
  - Visual feedback: strikethrough completed tasks
  
  **Phase 2 - Smart (5-6 hours):**
  - Add completion notes modal
  - Implement carry-forward logic in DraftGenerator
  - Add "OVERDUE" badges for old pending tasks
  - Filter buttons (Show All, Pending, Completed)
  
  **Phase 3 - Advanced (10-12 hours):**
  - Auto-detect completion from nurse updates (e.g., if nurse records "Gave morphine 10mg at 20:15", auto-complete matching pending task)
  - Completion rate dashboard for managers
  - Email alerts for overdue high-priority tasks
  - Mobile push notifications for incoming nurse
  
  **Why This Matters:**
  - ✅ **Accountability**: Clear record of who did what and when
  - ✅ **Continuity**: Tasks don't get lost between shifts
  - ✅ **Compliance**: Audit trail for regulatory requirements
  - ✅ **Efficiency**: Nurses see what's done vs. what's still needed (no duplicate work)
  - ✅ **Safety**: Reduces risk of missed critical tasks (medication errors, monitoring delays)
  
  **Success Metrics:**
  - Task completion rate > 95% within shift
  - Time to complete urgent tasks < 30 minutes
  - Nurse satisfaction with task tracking > 8/10
  - Reduction in medication errors from missed tasks
  
  **Estimated Effort**: 12-15 hours total (Phase 1: 3h, Phase 2: 5h, Phase 3: 10h)
  
  **Priority**: HIGH - Addresses critical gap in accountability loop

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
