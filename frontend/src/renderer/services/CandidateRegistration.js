import { showToast } from '../utils/Toasts.js';

// ============================================================================
// CANDIDATE REGISTRATION - RFID LISTENER
// ============================================================================

export function startRFIDListener() {
  const { state, getSelectedRaceId, getRFIDSetForRace } = window.appContext;
  
  if (state.rfidListenerActive) return;
  
  state.rfidListenerActive = true;
  console.debug('[Registration] startRFIDListener()');
  let rfidBuffer = '';
  let rfidTimeout = null;
  
  window.rfidKeyListener = (e) => {
    if (state.registrationStep !== 2) return;
    // Prevent keystrokes from landing in whichever field has focus
    e.preventDefault();
    e.stopPropagation();
    
    if (e.key === 'Enter') {
      if (rfidBuffer.length >= 8 && /^[A-Fa-f0-9]+$/.test(rfidBuffer)) {
        state.scannedRFID = rfidBuffer.toUpperCase();
        console.log('[Registration] RFID scanned:', state.scannedRFID);
        const selRace = getSelectedRaceId();
        const setHas = selRace ? getRFIDSetForRace(selRace).has(state.scannedRFID.toUpperCase()) : false;
        console.debug('[Registration][startRFIDListener] buffer=', rfidBuffer, 'scanned=', state.scannedRFID, 'perRaceHas=', setHas, 'race=', selRace);
        
        const rfidDisplay = document.getElementById('rfid-display');
        if (rfidDisplay) {
          rfidDisplay.textContent = state.scannedRFID;
          rfidDisplay.style.borderColor = '#22c55e';
          rfidDisplay.style.color = '#22c55e';
        }
        
        setTimeout(() => {
          goToRegistrationStep3();
        }, 500);
      }
      rfidBuffer = '';
    } else if (e.key.length === 1) {
      rfidBuffer += e.key;
      clearTimeout(rfidTimeout);
      rfidTimeout = setTimeout(() => {
        rfidBuffer = '';
      }, 100);
    }
  };
  
  document.addEventListener('keypress', window.rfidKeyListener);
  console.log('[Registration] RFID listener started');
}

export function stopRFIDListener() {
  const { state } = window.appContext;
  
  if (window.rfidKeyListener) {
    document.removeEventListener('keypress', window.rfidKeyListener);
    window.rfidKeyListener = null;
  }
  state.rfidListenerActive = false;
  console.log('[Registration] RFID listener stopped');
  console.debug('[Registration] stopRFIDListener()');
}

// ============================================================================
// CANDIDATE REGISTRATION - WIZARD STEPS
// ============================================================================

export function goToRegistrationStep2() {
  const { state, render } = window.appContext;
  
  if (!state.selectedRace) {
    showToast('Please select a race first', 'warning');
    return;
  }
  state.registrationStep = 2;
  state.scannedRFID = null;
  render();
  startRFIDListener();
}

export async function goToRegistrationStep3() {
  const { state, getSelectedRaceId, getRFIDSetForRace, populateRFIDSetForRace, render, perRaceRFIDMap } = window.appContext;
  
  if (!state.scannedRFID) {
    showToast('Please scan an RFID tag first', 'warning');
    return;
  }
  
  // Ensure we check duplicates for the selected race only
  const rfidUpper = state.scannedRFID.toUpperCase();
  const selectedRaceId = getSelectedRaceId();
  if (!selectedRaceId) {
    showToast('Please select a race before continuing', 'warning');
    return;
  }

  // Populate per-race set if not already present
  if (!perRaceRFIDMap.has(selectedRaceId)) {
    await populateRFIDSetForRace(selectedRaceId);
  }

  const existingSet = getRFIDSetForRace(selectedRaceId);
  console.debug('[Registration][goToRegistrationStep3] scannedRFID=', state.scannedRFID, 'existingSet_size=', existingSet.size);
  if (existingSet.has(rfidUpper)) {
    console.debug('[Registration][goToRegistrationStep3] Duplicate detected for', rfidUpper, 'in race', selectedRaceId);
    showToast('This RFID tag is already registered for this race. Please use a different RFID tag.', 'error');
    // Clear the scanned RFID and stay on step 2
    state.scannedRFID = null;
    const rfidDisplay = document.getElementById('rfid-display');
    if (rfidDisplay) {
      rfidDisplay.textContent = 'Duplicate RFID - Please scan again';
      rfidDisplay.style.borderColor = '#ef4444';
      rfidDisplay.style.color = '#ef4444';
    }
    return;
  }
  
  state.registrationStep = 3;
  stopRFIDListener();
  render();
  
  // Focus on the name input
  setTimeout(() => {
    const nameInput = document.getElementById('name');
    if (nameInput) nameInput.focus();
  }, 100);
}

// ============================================================================
// CANDIDATE REGISTRATION - FORM SUBMISSION
// ============================================================================

export async function submitRegistration() {
  const { state, apiRequest, getSelectedRaceId, getRFIDSetForRace, render, ensureAuth } = window.appContext;
  
  const name = document.getElementById('name').value;
  const age = document.getElementById('age').value;
  const rfid = document.getElementById('rfid').value;
  const gender = document.getElementById('gender').value;

  if (!state.selectedRace) {
    showToast('Please select a race first', 'error');
    return;
  }
  
  if (!rfid) {
    showToast('RFID tag is required', 'error');
    return;
  }

  if (!gender) {
    showToast('Gender is required', 'error');
    return;
  }

  try {
    await ensureAuth();
    const result = await apiRequest('/participant/register', {
      method: 'POST',
      body: {
        race_id: state.selectedRace,
        rfid_tag: rfid.toUpperCase(),
        name: name,
        age: age ? Number(age) : undefined,
        gender: gender.toUpperCase()
      }
    });

    // Add RFID to per-race set to prevent duplicate registration in same race/session
    const rfidUpper = rfid.toUpperCase();
    const raceId = getSelectedRaceId();
    if (raceId) {
      const set = getRFIDSetForRace(raceId);
      console.debug('[Registration][submitRegistration] before add perRace_has=', set.has(rfidUpper), 'size=', set.size);
      set.add(rfidUpper);
      console.debug('[Registration][submitRegistration] after add size=', set.size);
    }
    
    document.getElementById('registration-form').reset();
    
    const timestamp = new Date().toLocaleTimeString();
    const race = state.races.find(r => r.id === state.selectedRace);
    const raceName = race ? race.name : 'Unknown Race';
    const category = result.category || 'N/A';
    
    // Add to session registrations array
    state.todayRegistrations.unshift({
      name: name,
      raceName: raceName,
      rfid: rfid.toUpperCase(),
      age: age || 'N/A',
      gender: gender || 'N/A',
      category: category,
      timestamp: timestamp
    });
    
    showToast('Participant registered successfully!', 'success');
    state.registrationStep = 2;
    state.scannedRFID = null;
    render();
    startRFIDListener();
    
    console.log('Participant registered successfully');
  } catch (err) {
    console.error('Registration error:', err);
    const codeTag = err.error_code ? ` [${err.error_code}]` : '';
    showToast(`Registration failed${codeTag}: ${err.message}`, 'error');
  }
}

// ============================================================================
// CANDIDATE REGISTRATION - BULK UPLOAD
// ============================================================================

export async function uploadBulkCandidates(raceId, file) {
  const { globalLoader, ensureAuth, apiUpload, candidateManagementSelectedRaceId, fetchParticipants, render } = window.appContext;
  
  try {
    await globalLoader.wrap(async () => {
      await ensureAuth();
      const formData = new FormData();
      formData.append('file', file);

      await apiUpload(`/races/${raceId}/bulk-upload`, formData);
    });

    showToast('Bulk upload completed', 'success');
    await fetchParticipants(candidateManagementSelectedRaceId);
    
    setTimeout(() => {
      render();
    }, 500);
  } catch (err) {
    console.error(err);
    const codeTag = err.error_code ? ` [${err.error_code}]` : '';
    showToast(`Bulk upload failed${codeTag}: ${err.message}`, 'error', 10000);
    throw err;
  }
}

// ============================================================================
// CANDIDATE REGISTRATION - EVENT HANDLERS
// ============================================================================

export function attachRegistrationWizardHandlers() {
  const { state, getSelectedRaceId, populateRFIDSetForRace, fetchRaces, fetchDashboardData, render } = window.appContext;
  
  if (state.view !== 'register') return;

  // Step 1: Race Selection
  const continueStep1 = document.getElementById('continue-step1');
  if (continueStep1) {
    continueStep1.addEventListener('click', async () => {
      const raceSelect = document.getElementById('race-select-dropdown');
      if (raceSelect && raceSelect.value) {
        state.selectedRace = raceSelect.value;
        state.registrationStep = 2;
        // Populate per-race RFID set for the selected race
        await populateRFIDSetForRace(getSelectedRaceId());
        render();
      } else {
        showToast('Please select a race to continue', 'warning');
      }
    });
  }

  // Step 1-3: Close buttons (go to dashboard)
  ['close-step-1', 'close-step-2', 'close-step-3'].forEach(id => {
    const btn = document.getElementById(id);
    if (btn) {
      btn.addEventListener('click', async () => {
        stopRFIDListener();
        state.registrationStep = 1;
        state.scannedRFID = null;
        state.selectedRace = null;
        await fetchRaces();
        await fetchDashboardData();
        state.view = 'dashboard';
        render();
      });
    }
  });

  // Step 2: Back to step 1
  const backToStep1 = document.getElementById('back-to-step-1');
  if (backToStep1) {
    backToStep1.addEventListener('click', () => {
      stopRFIDListener();
      state.registrationStep = 1;
      state.scannedRFID = null;
      render();
    });
  }

  // Step 2: Bulk upload
  const bulkUploadBtn = document.getElementById('bulk-upload-btn');
  const bulkUploadInput = document.getElementById('bulk-upload-input');
  if (bulkUploadBtn && bulkUploadInput) {
    bulkUploadBtn.addEventListener('click', () => {
      const raceId = getSelectedRaceId();
      if (!raceId) {
        showToast('Select a race before uploading', 'warning');
        return;
      }
      bulkUploadInput.click();
    });

    bulkUploadInput.addEventListener('change', async (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;
      const raceId = getSelectedRaceId();
      if (!raceId) {
        showToast('Select a race before uploading', 'warning');
        bulkUploadInput.value = '';
        return;
      }

      try {
        await uploadBulkCandidates(raceId, file);
      } finally {
        bulkUploadInput.value = '';
      }
    });
  }

  // Step 3: Back to step 2
  const backToStep2 = document.getElementById('back-to-step-2');
  if (backToStep2) {
    backToStep2.addEventListener('click', () => {
      state.registrationStep = 2;
      render();
      startRFIDListener();
    });
  }

  // Step 3: Registration form
  const registrationForm = document.getElementById('registration-form');
  if (registrationForm) {
    // Guard against attaching multiple identical listeners when render() re-initializes handlers
    if (!registrationForm.dataset.submitAttached) {
      registrationForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        await submitRegistration();
      });
      registrationForm.dataset.submitAttached = '1';
    }
  }

  // Start RFID listener if on step 2
  if (state.registrationStep === 2) {
    startRFIDListener();
  } else {
    stopRFIDListener();
  }
}

// ============================================================================
// FORM-BASED PARTICIPANT REGISTRATION
// ============================================================================

export async function registerRunner(formData) {
  const { state, apiRequest, ensureAuth, getRFIDSetForRace, render } = window.appContext;
  
  try {
    await ensureAuth();
    await apiRequest("/participant/register", {
      method: "POST",
      body: {
        race_id: formData.raceId,
        rfid_tag: formData.rfid.toUpperCase(),
        name: formData.name,
        age: formData.age ? Number(formData.age) : undefined,
        gender: formData.gender || undefined,
        category: formData.category || undefined,
      },
    });

    state.registrations = state.registrations || [];
    state.registrations.unshift({
      race_id: formData.raceId,
      rfid_tag: formData.rfid.toUpperCase(),
      name: formData.name,
      category: formData.category || "",
      created_at: new Date().toISOString(),
    });

    // Add to per-race RFID set to prevent immediate duplicate within this race
    try {
      const rfidUpper = formData.rfid.toUpperCase();
      const set = getRFIDSetForRace(formData.raceId);
      set.add(rfidUpper);
    } catch (e) {
      console.debug('Could not add RFID to per-race set', e);
    }

    showToast("Runner registered successfully", 'success');
    render();
  } catch (err) {
    console.error(err);
    const codeTag = err.error_code ? ` [${err.error_code}]` : '';
    showToast(`Registration failed${codeTag}: ${err.message}`, 'error');
  }
}

// ============================================================================
// VIEW SETUP - Called when entering registration view from navigation
// ============================================================================

export async function setupRegistrationView() {
  const { state, fetchRaces } = window.appContext;
  
  // Reset registration wizard state
  state.registrationStep = 1;
  state.scannedRFID = null;
  state.selectedRace = null;
  
  // Load races for selection
  await fetchRaces();
}
