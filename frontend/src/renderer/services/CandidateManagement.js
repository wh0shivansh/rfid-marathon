import { showToast } from '../utils/Toasts.js';

// ============================================================================
// CANDIDATE MANAGEMENT - API OPERATIONS
// ============================================================================

export async function updateCandidate(candidateId, updates) {
  const { globalLoader, ensureAuth, apiRequest, candidateManagementSelectedRaceId, fetchParticipants, render } = window.appContext;
  
  try {
    await globalLoader.wrap(async () => {
      await ensureAuth();
      await apiRequest(`/participant/${candidateId}`, {
        method: 'PATCH',
        body: updates,
      });
    });
    
    showToast('Candidate updated successfully', 'success');
    await fetchParticipants(candidateManagementSelectedRaceId);
    
    setTimeout(() => {
      render();
    }, 500);
  } catch (err) {
    console.error(err);
    const codeTag = err.error_code ? ` [${err.error_code}]` : '';
    showToast(`Failed to update candidate${codeTag}: ${err.message}`, 'error');
    throw err;
  }
}

export async function deleteCandidate(candidateId) {
  const { globalLoader, ensureAuth, apiRequest, candidateManagementSelectedRaceId, fetchParticipants, render } = window.appContext;
  
  if (!confirm('Are you sure you want to delete this candidate? This action cannot be undone.')) {
    return;
  }
  
  try {
    await globalLoader.wrap(async () => {
      await ensureAuth();
      await apiRequest(`/participant/${candidateId}`, {
        method: 'DELETE',
      });
    });
    
    showToast('Candidate deleted successfully', 'success');
    await fetchParticipants(candidateManagementSelectedRaceId);
    
    setTimeout(() => {
      render();
    }, 500);
  } catch (err) {
    console.error(err);
    const codeTag = err.error_code ? ` [${err.error_code}]` : '';
    showToast(`Failed to delete candidate${codeTag}: ${err.message}`, 'error');
    throw err;
  }
}

// ============================================================================
// CANDIDATE MANAGEMENT - UI OPERATIONS
// ============================================================================

export function openCandidateEditModal(participant) {
  const { state, render } = window.appContext;
  
  if (!participant) return;

  const modalContainer = document.createElement('div');
  const formatRaceLabel = window.appContext?.formatRaceLabel || ((race) => String(race?.name || ''));
  const raceOptions = state.races
    .filter(r => r.status === 'created')
    .map(r => `<option value="${r.id}">${formatRaceLabel(r)}</option>`)
    .join('');

  modalContainer.innerHTML = `
    <div class="dark-modal-overlay" style="display: flex;">
      <div class="dark-modal" style="max-width: 600px;">
        <div class="dark-modal-header">
          <div style="display: flex; align-items: center; gap: 12px;">
            <div style="width: 42px; height: 42px; background: linear-gradient(135deg, #00d4ff 0%, #0099ff 100%); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 20px;">👤</div>
            <h2 style="margin: 0; font-size: 22px; font-weight: 700; color: #e2e8f0;">Edit Candidate</h2>
          </div>
          <button class="dark-modal-close" data-action="close">&times;</button>
        </div>
        <form data-action="form" style="margin-top: 24px;">
          <input type="hidden" id="candidate-id" value="${participant.id}">
          
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px;">
            <div class="dark-form-group">
              <label style="display: flex; align-items: center; gap: 6px; margin-bottom: 8px;">
                <span style="color: #cbd5e1; font-weight: 600; font-size: 13px;">📛 Name</span>
                <span style="color: #ef4444; font-weight: 700;">*</span>
              </label>
              <input type="text" id="candidate-name" required style="padding: 12px 14px; font-size: 15px; border-radius: 6px; border: 2px solid #334155; transition: all 0.3s ease; width:100%;">
            </div>

            <div class="dark-form-group">
              <label style="display: flex; align-items: center; gap: 6px; margin-bottom: 8px;">
                <span style="color: #cbd5e1; font-weight: 600; font-size: 13px;">📅 Age</span>
                <span style="color: #ef4444; font-weight: 700;">*</span>
              </label>
              <input type="number" id="candidate-age" style="padding: 12px 14px; font-size: 15px; border-radius: 6px; border: 2px solid #334155; transition: all 0.3s ease; width:100%;">
            </div>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px;">
            <div class="dark-form-group">
              <label style="display: flex; align-items: center; gap: 6px; margin-bottom: 8px;">
                <span style="color: #cbd5e1; font-weight: 600; font-size: 13px;">⚧ Gender</span>
                <span style="color: #ef4444; font-weight: 700;">*</span>
              </label>
              <select id="candidate-gender" required style="padding: 12px 14px; font-size: 15px; border-radius: 6px; border: 2px solid #334155; width:100%; background: #0b1220; color: #e2e8f0;">
                <option value="">Select...</option>
                <option value="M">Male</option>
                <option value="F">Female</option>
                <option value="O">Other</option>
              </select>
            </div>

            <div class="dark-form-group">
              <label style="display: flex; align-items: center; gap: 6px; margin-bottom: 8px;">
                <span style="color: #cbd5e1; font-weight: 600; font-size: 13px;">🏁 Race</span>
                <span style="color: #64748b; font-size: 12px; font-weight: 400;">(view only)</span>
              </label>
              <select disabled style="padding: 12px 14px; font-size: 15px; border-radius: 6px; border: 2px solid #334155; width:100%; background: #0b1220; color: #94a3b8;">
                ${raceOptions}
              </select>
            </div>
          </div>

          <div style="display: flex; gap: 12px; justify-content: flex-end; margin-top: 24px; padding-top: 16px; border-top: 1px solid #334155;">
            <button type="button" data-action="cancel" class="dark-btn-secondary" style="padding: 12px 28px; font-size: 15px; font-weight: 600; border-radius: 6px;">Cancel</button>
            <button type="submit" class="dark-btn-primary" style="padding: 12px 28px; font-size: 15px; border-radius: 6px; display: flex; align-items: center; gap: 8px;">
              <span>💾</span>
              <span>Update Candidate</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  `;

  document.body.appendChild(modalContainer);
  const overlay = modalContainer.querySelector('.dark-modal-overlay');
  const closeBtn = modalContainer.querySelector('[data-action="close"]');
  const cancelBtn = modalContainer.querySelector('[data-action="cancel"]');
  const form = modalContainer.querySelector('[data-action="form"]');

  const cleanup = () => {
    modalContainer.remove();
  };

  if (closeBtn) closeBtn.addEventListener('click', cleanup);
  if (cancelBtn) cancelBtn.addEventListener('click', cleanup);
  if (overlay) {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) cleanup();
    });
  }

  const nameEl = document.getElementById('candidate-name');
  const ageEl = document.getElementById('candidate-age');
  const genderEl = document.getElementById('candidate-gender');

  if (nameEl) nameEl.value = participant.decryptedName || participant.name || '';
  if (ageEl) ageEl.value = participant.age || '';
  if (genderEl) genderEl.value = participant.gender || '';

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const updates = {
        name: nameEl.value.trim(),
        age: ageEl.value ? Number(ageEl.value) : null,
        gender: genderEl.value,
      };
      cleanup();
      await updateCandidate(participant.id, updates);
    });
  }
}

// ============================================================================
// CANDIDATE MANAGEMENT - EVENT HANDLERS
// ============================================================================

export function attachCandidateManagementHandlers() {
  const { state, candidateManagementSelectedRaceId, fetchParticipants, render } = window.appContext;
  
  if (state.view !== 'candidate-management') return;

  // Race filter dropdown
  const raceFilterDropdown = document.getElementById('candidate-race-filter-dropdown');
  if (raceFilterDropdown) {
    raceFilterDropdown.addEventListener('change', async (e) => {
      window.appContext.candidateManagementSelectedRaceId = e.target.value || null;
      await fetchParticipants(window.appContext.candidateManagementSelectedRaceId);
      render();
    });
  }

  // Add New Candidate Button
  const addNewCandidateBtn = document.getElementById('add-new-candidate-btn');
  if (addNewCandidateBtn) {
    addNewCandidateBtn.addEventListener('click', async () => {
      state.view = 'register';
      state.registrationStep = 1;
      state.scannedRFID = null;
      state.selectedRace = null;
      const { fetchRaces } = window.appContext;
      await fetchRaces();
      render();
    });
  }

  // Edit Candidate Buttons: navigate to registration view for edits
  const editCandidateBtns = document.querySelectorAll('.edit-candidate-btn');
  editCandidateBtns.forEach(btn => {
    btn.addEventListener('click', async () => {
      const candidateId = btn.dataset.candidateId;
      const participant = state.participants.find(p => p.id === candidateId);
      if (!participant) {
        showToast('Candidate not found', 'error');
        return;
      }

      openCandidateEditModal(participant);
    });
  });

  // Delete Candidate Buttons
  const deleteCandidateBtns = document.querySelectorAll('.delete-candidate-btn');
  deleteCandidateBtns.forEach(btn => {
    btn.addEventListener('click', async () => {
      const candidateId = btn.dataset.candidateId;
      await deleteCandidate(candidateId);
    });
  });
}

export function attachCandidateModalControls() {
  const closeCandidateModal = document.getElementById('close-candidate-modal');
  if (closeCandidateModal) {
    closeCandidateModal.addEventListener('click', () => {
      const modal = document.getElementById('candidate-modal');
      if (modal) {
        modal.style.display = 'none';
        modal.style.pointerEvents = 'none';
      }
    });
  }

  const cancelCandidateForm = document.getElementById('cancel-candidate-form');
  if (cancelCandidateForm) {
    cancelCandidateForm.addEventListener('click', () => {
      const modal = document.getElementById('candidate-modal');
      if (modal) {
        modal.style.display = 'none';
        modal.style.pointerEvents = 'none';
      }
    });
  }

  const candidateForm = document.getElementById('candidate-form');
  if (candidateForm) {
    candidateForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const candidateId = document.getElementById('candidate-id').value;
      const nameVal = document.getElementById('candidate-name').value;
      const ageVal = Number(document.getElementById('candidate-age').value) || null;
      const genderVal = document.getElementById('candidate-gender').value;

      try {
        if (candidateId) {
          const updates = { name: nameVal, age: ageVal, gender: genderVal };
          await updateCandidate(candidateId, updates);
        } else {
          showToast('Please select a candidate to edit', 'error');
          return;
        }
        const modal = document.getElementById('candidate-modal');
        if (modal) {
          modal.style.display = 'none';
          modal.style.pointerEvents = 'none';
        }
      } catch (err) {
        // Errors handled by updateCandidate
      }
    });
  }
}

// ============================================================================
// VIEW SETUP - Called when entering candidate management view from navigation
// ============================================================================

export async function setupCandidateManagementView() {
  const { fetchRaces, fetchParticipants } = window.appContext;
  
  // Load races and participants for display
  await fetchRaces();
  await fetchParticipants(window.appContext.candidateManagementSelectedRaceId);
}
