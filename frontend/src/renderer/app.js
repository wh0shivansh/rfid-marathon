// Registration-focused renderer (RFID hub handles caching and timing). This app handles
// user authentication, participant registration, and data viewing.
import { showToast } from './utils/Toasts.js';
import { renderRegistration } from './views/CandidateRegistration.js';
import { renderDashboard } from './views/Dashboard.js';
import { renderCreateRace } from './views/CreateRace.js';
import { renderCandidateManagement } from './views/CandidateManagement.js';
import { renderScoreboard } from './views/Scoreboard.js';
import { renderRaceStart } from './views/RaceStart.js';
import { renderRacesManagement } from './views/RacesManagement.js';

const secureApi = window.secureApi;
const app = document.getElementById("app");

// ============================================================================
// GLOBAL LOADER - Prevents duplicate API calls
// ============================================================================
class GlobalLoader {
  constructor() {
    this.isLoading = false;
    this.loaderElement = null;
  }

  show() {
    if (this.isLoading) return;
    this.isLoading = true;
    
    // Create loader overlay
    this.loaderElement = document.createElement('div');
    this.loaderElement.id = 'global-loader';
    this.loaderElement.innerHTML = `
      <div style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 9999;">
        <div style="background: white; padding: 24px; border-radius: 8px; text-align: center;">
          <div class="spinner" style="border: 4px solid #f3f3f3; border-top: 4px solid #3b82f6; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto;"></div>
          <p style="margin-top: 12px; color: #374151;">Loading...</p>
        </div>
      </div>
    `;
    document.body.appendChild(this.loaderElement);
  }

  hide() {
    if (!this.isLoading) return;
    this.isLoading = false;
    
    if (this.loaderElement) {
      this.loaderElement.remove();
      this.loaderElement = null;
    }
  }

  async wrap(asyncFn) {
    if (this.isLoading) {
      console.warn('Request blocked: loader already active');
      return null;
    }
    
    try {
      this.show();
      const result = await asyncFn();
      return result;
    } finally {
      this.hide();
    }
  }
}

const globalLoader = new GlobalLoader();

const state = {
  view: "dashboard",
  config: secureApi.getConfig(),
  auth: { token: null, expiresAt: 0 },
  races: [],
  registrations: [],
  selectedRace: null,
  showRaceModal: false,
  // Registration wizard state
  registrationStep: 1, // 1 = race selection, 2 = RFID scan, 3 = participant details
  scannedRFID: null,
  rfidListenerActive: false,
  todayRegistrations: [], // Track registrations in current session
  dashboardData: {
    totalRaces: 0,
    totalParticipants: 0,
    todayRegistrations: 0,
    startedToday: 0,
    finishedToday: 0,
    raceStats: {},
  },
  // Results/Data View state
  participants: [],
  selectedRaceFilter: null, // For filtering participants by race
};

// RFID Deduplication Set - populated on registration page load
let existingRFIDSet = new Set();

// Candidate Management View state
let candidateManagementSelectedRaceId = null;
let scoreboardSelectedRaceId = null;

// Race Start View state
let raceStartSelectedRaceId = null;
// Group selection removed; default to group 1 when starting
let raceStartSelectedGroupNumber = 1;
let raceStartTime = null;
let raceStartPollingInterval = null;

// Expose state to CandidateRegistration component
window.appState = state;
window.authToken = null;

function generateNonce() {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

function isTokenValid() {
  return state.auth.token && state.auth.expiresAt > Date.now() + 30000;
}

async function apiRequest(path, options = {}) {
  const { method = "GET", body = null, auth = true } = options;
  const headers = { "Content-Type": "application/json" };
  if (auth && state.auth.token) headers["Authorization"] = `Bearer ${state.auth.token}`;

  const response = await fetch(`${state.config.apiBaseUrl}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : null,
  });

  const data = await response.json().catch(() => ({ success: false, message: "Bad JSON" }));
  if (!response.ok || !data.success) {
    throw new Error(data.message || `Request failed (${response.status})`);
  }
  return data.data;
}

async function login() {
  // Use an ISO8601 string compatible with Python's datetime.fromisoformat
  // (replace 'Z' with '+00:00') to avoid parsing issues on the backend.
  const timestamp = new Date().toISOString().replace('Z', '+00:00');
  const nonce = generateNonce();
  const { username, password } = state.config;
  if (!username || !password) throw new Error("Missing FRONTEND_USERNAME/PASSWORD in .env");

  const data = await apiRequest("/auth/login", {
    method: "POST",
    body: { username, password, timestamp, nonce },
    auth: false,
  });

  state.auth.token = data.access_token;
  state.auth.expiresAt = Date.now() + data.expires_in * 1000;
  window.authToken = data.access_token; // Expose for CandidateRegistration
}

async function ensureAuth() {
  if (isTokenValid()) return;
  await login();
}

function showStartGroupStatus(message, type = 'info') {
  const statusElement = document.getElementById('status-message');
  if (statusElement) {
    statusElement.innerHTML = message;
    statusElement.className = `status-${type}`;
    statusElement.style.display = 'block';
  }
}

async function fetchRaces() {
  try {
    await ensureAuth();
    const races = await apiRequest("/race");
    state.races = races;
  } catch (err) {
    console.error(err);
    showToast(`Failed to fetch races: ${err.message}`, 'error');
  }
}

async function fetchDashboardData() {
  try {
    await ensureAuth();
    const data = await apiRequest("/dashboard-data");
    state.dashboardData = {
      totalRaces: data.total_races,
      totalParticipants: data.total_participants,
      todayRegistrations: data.today_registrations,
      startedToday: data.started_today,
      finishedToday: data.finished_today,
      raceStats: data.race_stats,
    };
  } catch (err) {
    console.error(err);
    showToast(`Failed to fetch dashboard data: ${err.message}`, 'error');
    // Initialize with default data
    state.dashboardData = {
      totalRaces: state.races.length,
      totalParticipants: 0,
      todayRegistrations: 0,
      startedToday: 0,
      finishedToday: 0,
      raceStats: {},
    };
  }
}

function decryptName(encryptedName, key) {
  // Get the Fernet wrapper from the bridge
  const Fernet = window.secureApi?.Fernet;
  
  if (!Fernet) {
    console.error("[Decryption] Fernet library not found in secureApi.");
    return null;
  }

  if (!encryptedName || !key) {
    return null;
  }

  try {
    // Use the wrapper's decrypt method
    const decrypted = Fernet.decrypt(String(key).trim(), String(encryptedName).trim());
    return decrypted;
  } catch (err) {
    console.error(`[Decryption] Error: ${err.message}`);
    return null;
  }
}

async function fetchParticipants(raceId = null) {
  try {
    await ensureAuth();
    const endpoint = raceId ? `/race/${raceId}/participants` : `/participants`;
    const participants = await apiRequest(endpoint);
    
    state.participants = (participants || []).map(p => {
      // Use the key returned per-row from the backend
      const decrypted = decryptName(p.encrypted_name, p.encryption_key);
      return {
        ...p,
        decryptedName: decrypted || "Decryption Failed"
      };
    });
  } catch (err) {
    console.error(err);
    state.participants = [];
  }
}

async function registerRunner(formData) {
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

    state.registrations.unshift({
      race_id: formData.raceId,
      rfid_tag: formData.rfid.toUpperCase(),
      name: formData.name,
      category: formData.category || "",
      created_at: new Date().toISOString(),
    });

    showToast("Runner registered successfully", 'success');
    render();
  } catch (err) {
    console.error(err);
    showToast(`Registration failed: ${err.message}`, 'error');
    alert(`Registration failed: ${err.message}`);
  }
}

// ============================================================================
// RACE CRUD OPERATIONS
// ============================================================================

async function createRace(raceData) {
  return await globalLoader.wrap(async () => {
    try {
      await ensureAuth();
      await apiRequest("/race", {
        method: "POST",
        body: raceData,
      });
      
      showToast("Race created successfully", 'success');
      await fetchRaces();
      render();
    } catch (err) {
      console.error(err);
      showToast(`Failed to create race: ${err.message}`, 'error');
      throw err;
    }
  });
}

async function updateRace(raceId, updates) {
  return await globalLoader.wrap(async () => {
    try {
      await ensureAuth();
      await apiRequest(`/race/${raceId}`, {
        method: "PATCH",
        body: updates,
      });
      
      showToast("Race updated successfully", 'success');
      await fetchRaces();
      render();
    } catch (err) {
      console.error(err);
      showToast(`Failed to update race: ${err.message}`, 'error');
      throw err;
    }
  });
}

async function deleteRace(raceId) {
  if (!confirm('Are you sure you want to delete this race? This action cannot be undone.')) {
    return;
  }
  
  return await globalLoader.wrap(async () => {
    try {
      await ensureAuth();
      await apiRequest(`/race/${raceId}`, {
        method: "DELETE",
      });
      
      showToast("Race deleted successfully", 'success');
      await fetchRaces();
      render();
    } catch (err) {
      console.error(err);
      showToast(`Failed to delete race: ${err.message}`, 'error');
      throw err;
    }
  });
}

async function startRace(raceId) {
  return await globalLoader.wrap(async () => {
    try {
      await ensureAuth();
      await apiRequest(`/race/${raceId}/start`, {
        method: "POST",
      });
      
      showToast("Race started successfully", 'success');
      await fetchRaces();
      render();
    } catch (err) {
      console.error(err);
      showToast(`Failed to start race: ${err.message}`, 'error');
      throw err;
    }
  });
}

async function endRace(raceId) {
  return await globalLoader.wrap(async () => {
    try {
      await ensureAuth();
      await apiRequest(`/race/${raceId}/end`, {
        method: 'POST'
      });

      // Refresh races to check transitions
      await fetchRaces();

      // Sanity check: ensure at most one active race
      const activeCount = state.races.filter(r => r.status === 'active').length;
      if (activeCount > 1) {
        showToast(`Warning: ${activeCount} active races detected`, 'error');
      } else {
        showToast('Race completed successfully', 'success');
      }

      render();
    } catch (err) {
      console.error(err);
      showToast(`Failed to end race: ${err.message}`, 'error');
      throw err;
    }
  });
}

async function updateRaceStatus(raceId, status) {
  return await globalLoader.wrap(async () => {
    try {
      await ensureAuth();
      await apiRequest(`/race/${raceId}/status/update`, {
        method: 'POST',
        body: { status }
      });

      showToast(`Race status updated to ${status}`, 'success');
      await fetchRaces();
      render();
    } catch (err) {
      console.error(err);
      showToast(`Failed to update race status: ${err.message}`, 'error');
      throw err;
    }
  });
}

function renderSidebar() {
  return `
    <div class="sidebar">
      <div class="brand">RFID Marathon</div>
      <nav class="sidebar-nav">
          <button class="nav-btn ${state.view === "dashboard" ? "active" : ""}" data-view="dashboard">Dashboard</button>
          <button class="nav-btn ${state.view === "races-management" ? "active" : ""}" data-view="races-management">Races Management</button>
          <button class="nav-btn ${state.view === "race-start" ? "active" : ""}" data-view="race-start">Start Race</button>
          <button class="nav-btn ${state.view === "register" ? "active" : ""}" data-view="register">Register</button>
          <button class="nav-btn ${state.view === "candidate-management" ? "active" : ""}" data-view="candidate-management">Candidate Management</button>
          <button class="nav-btn ${state.view === "scoreboard" ? "active" : ""}" data-view="scoreboard">Scoreboard</button>
      </nav>
      <div class="sidebar-meta">
        <div>API: ${state.config.apiBaseUrl}</div>
        <div>Device: ${state.config.deviceId}</div>
        <div>Caching: RFID hub</div>
      </div>
    </div>
  `;
}

function renderHeader() {
  const statusText = navigator.onLine ? "Online" : "Offline";
  const statusClass = navigator.onLine ? "status-online" : "status-offline";
  return `
    <div class="topbar">
      <div class="status-group">
        <span class="pill ${statusClass}">${statusText}</span>
        <span class="pill">Registrations done today: ${state.dashboardData.todayRegistrations}</span>
      </div>
      <div class="actions">
        <button class="ghost" id="refresh-btn">Refresh races</button>
      </div>
    </div>
  `;
}

function renderRegister() {
  // Use the CandidateRegistration component as simple HTML renderer
  return renderRegistration(state.registrationStep, state.scannedRFID, state.races, state.selectedRace, state.dashboardData.todayRegistrations);
}

async function render() {
  // Cleanup polling when leaving race-start view
  // Inside document.querySelectorAll(".nav-btn").forEach((btn) => { ... })
  if (state.view !== "race-start" && raceStartPollingInterval) {
    stopRaceDataPolling();
  }
  
  // Cleanup RFID listener when leaving registration view
  if (state.view !== "register" && state.rfidListenerActive) {
    stopRFIDListener();
    // Clear existingRFIDSet when leaving registration page
    existingRFIDSet.clear();
  }
  
  const htmlContent = `
    <div class="layout">
      ${renderSidebar()}
      <div class="main">
        ${renderHeader()}
        ${state.view === "dashboard" ? renderDashboard(state.races, state.dashboardData.todayRegistrations, state.dashboardData.totalParticipants, state.dashboardData.startedToday, state.dashboardData.finishedToday, state.dashboardData.raceStats) : ""}
        ${state.view === "races-management" ? renderRacesManagement(state.races) : ""}
        ${state.view === "create" ? renderCreateRace() : ""}
        ${state.view === "race-start" ? renderRaceStart(state.races, raceStartSelectedRaceId) : ""}
        ${state.view === "register" ? renderRegister() : ""}
        ${state.view === "candidate-management" ? renderCandidateManagement(state.races, state.participants, candidateManagementSelectedRaceId) : ""}
        ${state.view === "scoreboard" ? renderScoreboard(state.races, state.participants, scoreboardSelectedRaceId) : ""}
      </div>
    </div>
  `;
  app.innerHTML = htmlContent;

  // Force reflow
  void app.offsetHeight;

  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      const newView = e.target.dataset.view;

      // Reset registration wizard when navigating to register view
      if (newView === 'register') {
        state.registrationStep = 1;
        state.scannedRFID = null;
        state.selectedRace = null;
        // Fetch all participants and populate existingRFIDSet
        await fetchRaces();
        await fetchParticipants();
        existingRFIDSet.clear();
        state.participants.forEach(p => {
          const rfid = (p.rfid || p.rfid_tag || '').toUpperCase();
          if (rfid) existingRFIDSet.add(rfid);
        });
        console.debug('[Registration] existingRFIDSet populated', { size: existingRFIDSet.size });
      }
      if (newView === 'race-start') {
        // Clear previous selection so user must select a race manually
        raceStartSelectedRaceId = null; 
        await fetchRaces();
      }

      // When opening dashboard, refresh data from backend first
      if (newView === 'dashboard') {
        await fetchRaces();
        await fetchDashboardData();
      }

      // When opening candidate management view, fetch participants
      if (newView === 'candidate-management') {
        await fetchRaces();
        await fetchParticipants(candidateManagementSelectedRaceId);
      }

      // When opening scoreboard view, fetch participants
      if (newView === 'scoreboard') {
        await fetchRaces();
        await fetchParticipants(scoreboardSelectedRaceId);
      }

      state.view = newView;
      render();
    });
  });

  const refreshBtn = document.getElementById("refresh-btn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", async () => {
      await fetchRaces();
      await fetchDashboardData();
      if (state.view === 'candidate-management') {
        await fetchParticipants(candidateManagementSelectedRaceId);
      }
      if (state.view === 'scoreboard') {
        await fetchParticipants(scoreboardSelectedRaceId);
      }
      render();
    });
  }

  // Candidate Management view handlers
  attachCandidateManagementHandlers();
  // Attach modal controls if the modal exists
  attachCandidateModalControls();
  
  // Scoreboard view handlers
  attachScoreboardHandlers();

  // Results view: Race filter dropdown handler
  const raceFilterDropdown = document.getElementById("race-filter-dropdown");
  if (raceFilterDropdown) {
    raceFilterDropdown.addEventListener("change", async (e) => {
      const selectedValue = e.target.value;
      state.selectedRaceFilter = selectedValue || null;
      await fetchParticipants(state.selectedRaceFilter);
      render();
    });
  }

  // Results view: Register New Candidate button handler
  const registerNewCandidateBtn = document.getElementById("register-new-candidate-btn");
  if (registerNewCandidateBtn) {
    registerNewCandidateBtn.addEventListener("click", () => {
      state.view = "register";
      state.registrationStep = 1;
      state.scannedRFID = null;
      state.selectedRace = null;
      render();
    });
  }

  // Registration wizard handlers
  attachRegistrationWizardHandlers();

  // Step 1: Continue to step 2 (after selecting race)
  const continueToStep2Btn = document.getElementById("continue-to-step2");
  if (continueToStep2Btn) {
    continueToStep2Btn.addEventListener("click", () => {
      const raceSelect = document.getElementById("race-select-step1");
      if (raceSelect && raceSelect.value) {
        const selectedRace = state.races.find(r => r.id === raceSelect.value);
        if (selectedRace) {
          state.selectedRace = selectedRace;
          state.registrationStep = 2;
          render();
          
          // Auto-focus RFID input
          setTimeout(() => {
            const rfidInput = document.getElementById("rfid-input-step2");
            if (rfidInput) rfidInput.focus();
          }, 100);
        } else {
          showToast('Please select a valid race', 'warning');
        }
      } else {
        showToast('Please select a race to continue', 'warning');
      }
    });
  }

  // Step 2: Back to step 1
  const backToStep1Btn = document.getElementById("back-to-step1");
  if (backToStep1Btn) {
    backToStep1Btn.addEventListener("click", () => {
      state.registrationStep = 1;
      state.scannedRFID = null;
      render();
    });
  }

  // Step 2: Continue to step 3 (after scanning RFID)
  const continueToStep3Btn = document.getElementById("continue-to-step3");
  if (continueToStep3Btn) {
    continueToStep3Btn.addEventListener("click", () => {
      const rfidInput = document.getElementById("rfid-input-step2");
      if (rfidInput && rfidInput.value) {
        const rfid = rfidInput.value.trim();
        if (rfid.length >= 8 && /^[A-Fa-f0-9]+$/.test(rfid)) {
          state.scannedRFID = rfid.toUpperCase();
          state.registrationStep = 3;
          stopRFIDListener();
          render();
        } else {
          showToast('Please enter a valid RFID tag (8-32 hex characters)', 'warning');
          rfidInput.focus();
        }
      } else {
        showToast('Please scan or enter an RFID tag', 'warning');
        if (rfidInput) rfidInput.focus();
      }
    });
  }

  // Step 2: Allow Enter key to continue
  const rfidInputStep2 = document.getElementById("rfid-input-step2");
  if (rfidInputStep2) {
    rfidInputStep2.addEventListener("keypress", (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const continueBtn = document.getElementById("continue-to-step3");
        if (continueBtn) continueBtn.click();
      }
    });
  }

  // Step 3: Back to step 2
  const backToStep2Btn = document.getElementById("back-to-step2");
  if (backToStep2Btn) {
    backToStep2Btn.addEventListener("click", () => {
      state.registrationStep = 2;
      render();
      
      // Restore RFID input value
      setTimeout(() => {
        const rfidInput = document.getElementById("rfid-input-step2");
        if (rfidInput && state.scannedRFID) {
          rfidInput.value = state.scannedRFID;
        }
      }, 100);
    });
  }

  // Step 3: Submit registration form
  const regFormStep3 = document.getElementById("register-form-step3");
  if (regFormStep3) {
    regFormStep3.addEventListener("submit", async (e) => {
      e.preventDefault();
      const formData = Object.fromEntries(new FormData(regFormStep3).entries());
      
      if (!state.selectedRace) {
        showToast('No race selected', 'error');
        return;
      }
      
      if (!state.scannedRFID) {
        showToast('No RFID tag scanned', 'error');
        return;
      }
      
      formData.raceId = state.selectedRace.id;
      formData.rfid = state.scannedRFID;
      
      await registerRunner(formData);
      
      // Reset wizard to step 1 after successful registration
      state.registrationStep = 1;
      state.scannedRFID = null;
      state.selectedRace = null;
      
      regFormStep3.reset();
      render();
    });
  }

  // Legacy form handler (kept for compatibility)
  const regForm = document.getElementById("register-form");
  if (regForm) {
    regForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const formData = Object.fromEntries(new FormData(regForm).entries());
      if (!state.selectedRace) {
        alert('Please select a race first');
        return;
      }
      formData.raceId = state.selectedRace.id;
      await registerRunner(formData);
      regForm.reset();
    });
  }

  // Modal controls
  const closeModalBtn = document.getElementById("close-modal-btn");
  if (closeModalBtn) {
    closeModalBtn.addEventListener("click", async () => {
      state.showRaceModal = false;
      if (!state.selectedRace) {
        // If no race selected, go to dashboard
        await fetchRaces();
        await fetchDashboardData();
        state.view = 'dashboard';
      }
      render();
    });
  }

  // Race select button handler
  const selectRaceBtn = document.getElementById("select-race-btn");
  if (selectRaceBtn) {
    selectRaceBtn.addEventListener("click", () => {
      const raceSelect = document.getElementById("race-select");
      if (raceSelect && raceSelect.value) {
        const selectedRace = state.races.find(r => r.id === raceSelect.value);
        if (selectedRace) {
          state.selectedRace = selectedRace;
          state.showRaceModal = false;
          render();
        } else {
          alert('Please select a race from the dropdown');
        }
      } else {
        alert('Please select a race from the dropdown');
      }
    });
  }

  // Open modal on initial render if in register view and no race selected
  if (state.view === "register" && !state.selectedRace && !state.showRaceModal) {
    setTimeout(() => {
      state.showRaceModal = true;
      render();
    }, 100);
  }

  const createForm = document.getElementById("create-race-form");
  if (createForm) {
    createForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const formData = Object.fromEntries(new FormData(createForm).entries());
      // Convert scheduled_date (YYYY-MM-DD) to ISO +00:00
      // The form field is named `scheduled_date` in the CreateRace view; accept either key for safety.
      const rawDate = formData.scheduled_date || formData.schedule_date;
      if (!rawDate) {
        showToast('Please provide a scheduled date', 'warning');
        return;
      }
      const parsedDate = new Date(rawDate);
      if (Number.isNaN(parsedDate.getTime())) {
        showToast('Invalid scheduled date format', 'error');
        return;
      }
      const isoDate = parsedDate.toISOString().replace('Z', '+00:00');
      
      // Get selected time unit and convert to seconds
      const timeUnit = document.getElementById('time-unit-selector')?.value || 'minutes';
      
      // Default values in minutes (from placeholder values)
      const defaults = {
        age_upto30_excellent: 25,
        age_upto30_good: 26.30,
        age_upto30_satisfactory: 27,
        age_upto40_excellent: 28.30,
        age_upto40_good: 30,
        age_upto40_satisfactory: 31,
        age_40to45_excellent: 31.30,
        age_40to45_good: 33,
        age_40to45_satisfactory: 35
      };
      
      const convertToSeconds = (value, fieldName) => {
        // Use default if value is empty
        const num = value ? Number(value) : defaults[fieldName];
        if (timeUnit === 'hours') return num * 3600;
        if (timeUnit === 'minutes') return num * 60;
        return num; // already in seconds
      };
      
      try {
        await ensureAuth();
        await apiRequest("/race", {
          method: "POST",
          body: {
            name: formData.name,
            distance_meters: Number(formData.distance_meters),
            location: formData.location,
            scheduled_date: isoDate,
            description: formData.description || undefined,
            age_upto30_excellent: convertToSeconds(formData.age_upto30_excellent, 'age_upto30_excellent'),
            age_upto30_good: convertToSeconds(formData.age_upto30_good, 'age_upto30_good'),
            age_upto30_satisfactory: convertToSeconds(formData.age_upto30_satisfactory, 'age_upto30_satisfactory'),
            age_upto40_excellent: convertToSeconds(formData.age_upto40_excellent, 'age_upto40_excellent'),
            age_upto40_good: convertToSeconds(formData.age_upto40_good, 'age_upto40_good'),
            age_upto40_satisfactory: convertToSeconds(formData.age_upto40_satisfactory, 'age_upto40_satisfactory'),
            age_40to45_excellent: convertToSeconds(formData.age_40to45_excellent, 'age_40to45_excellent'),
            age_40to45_good: convertToSeconds(formData.age_40to45_good, 'age_40to45_good'),
            age_40to45_satisfactory: convertToSeconds(formData.age_40to45_satisfactory, 'age_40to45_satisfactory'),
          },
        });
        showToast("Race created successfully", 'success');
        await fetchRaces(); // Refresh race list
        render();
      } catch (err) {
        console.error(err);
        showToast(`Create race failed: ${err.message}`, 'error');
        alert(`Create race failed: ${err.message}`);
      }
      createForm.reset();
    });
  }

  // ============================================================================
  // RACES MANAGEMENT VIEW EVENT LISTENERS
  // ============================================================================
  
  if (state.view === "races-management") {
    // Create New Race Button — navigate to full Create Race page
    const createNewRaceBtn = document.getElementById("create-new-race-btn");
    if (createNewRaceBtn) {
      createNewRaceBtn.addEventListener("click", async () => {
        // Switch to the dedicated Create Race view instead of opening the modal
        state.view = 'create';
        // clear any modal state
        state.showRaceModal = false;
        // ensure races and related data are current
        await fetchRaces();
        render();
      });
    }

    // Close Modal
    const closeRaceModal = document.getElementById("close-race-modal");
    if (closeRaceModal) {
      closeRaceModal.addEventListener("click", () => {
        document.getElementById("race-modal").style.display = "none";
      });
    }

    // Cancel Form
    const cancelRaceForm = document.getElementById("cancel-race-form");
    if (cancelRaceForm) {
      cancelRaceForm.addEventListener("click", () => {
        document.getElementById("race-modal").style.display = "none";
      });
    }

    // Race Form Submit
    const raceForm = document.getElementById("race-form");
    if (raceForm) {
      raceForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const raceId = document.getElementById("race-id").value;
        const formData = {
          name: document.getElementById("race-name").value,
          distance_meters: Number(document.getElementById("race-distance").value),
          location: document.getElementById("race-location").value,
          scheduled_date: document.getElementById("race-scheduled-date").value,
          description: document.getElementById("race-description").value || undefined,
        };

        try {
          if (raceId) {
            // Update existing race
            await updateRace(raceId, formData);
          } else {
            // Create new race
            await createRace(formData);
          }
          
          document.getElementById("race-modal").style.display = "none";
        } catch (err) {
          console.error("Form submission error:", err);
        }
      });
    }

    // Edit Race Buttons
    document.querySelectorAll(".edit-race-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const raceId = btn.dataset.raceId;
        const race = state.races.find(r => r.id === raceId);
        
        if (race) {
          const modal = document.getElementById("race-modal");
          const modalTitle = document.getElementById("modal-title");
          
          modalTitle.textContent = "Edit Race";
          document.getElementById("race-id").value = race.id;
          document.getElementById("race-name").value = race.name;
          document.getElementById("race-distance").value = race.distance_meters;
          document.getElementById("race-location").value = race.location;
          document.getElementById("race-scheduled-date").value = race.scheduled_date.split('T')[0];
          document.getElementById("race-description").value = race.description || "";
          
          modal.style.display = "flex";
        }
      });
    });

    // Delete Race Buttons
    document.querySelectorAll(".delete-race-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const raceId = btn.dataset.raceId;
        await deleteRace(raceId);
      });
    });

    // Toggle Active/Created Buttons (Activate / Deactivate)
    document.querySelectorAll(".toggle-active-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const raceId = btn.dataset.raceId;
        const race = state.races.find(r => r.id === raceId);
        if (!race) return;

        try {
          if (race.status === 'active') {
            // Deactivate -> set to 'created' via backend system action
            if (!confirm('Deactivate this race (set status to created)?')) return;
            await updateRaceStatus(raceId, 'created');
          } else {
            // Activate -> set to 'active' (this will demote any existing active race)
            if (!confirm('Activate this race (this will demote any existing active race)?')) return;
            await updateRaceStatus(raceId, 'active');
          }
        } catch (err) {
          console.error('Toggle active error:', err);
        }
      });
    });
  }

  // Race Start view: Polling-powered live RFID handler
  if (state.view === "race-start") {
    loadRaceStartRaces();
    startRaceDataPolling(); // Start polling for live updates
    // Attach End Race button handler
    const endRaceBtn = document.getElementById('end-race-btn');
    if (endRaceBtn) {
      endRaceBtn.addEventListener('click', async () => {
        if (!raceStartSelectedRaceId) {
          showRaceStartStatusMessage('Please select a race first', 'warning');
          return;
        }

        if (!confirm('Are you sure you want to end this race? This is irreversible.')) return;

        try {
          await endRace(raceStartSelectedRaceId);
        } catch (e) {
          console.error('Failed to end race:', e);
        }
      });
    }
    
    const raceSelect = document.getElementById('race-select');
    if (raceSelect) raceSelect.addEventListener('change', handleRaceStartRaceChange);
    
    const startForm = document.getElementById('start-race-form');
    if (startForm) startForm.addEventListener('submit', handleRaceStartSubmit);
    
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) refreshBtn.addEventListener('click', refreshRaceStartData);
  }

  // Registration wizard event listeners
  if (state.view === "register") {
    // Step 1: Continue button
    const continueStep1 = document.getElementById('continue-step1');
    if (continueStep1) {
      continueStep1.addEventListener('click', () => {
        const dropdown = document.getElementById('race-select-dropdown');
        const raceId = dropdown ? dropdown.value : '';
        if (!raceId) {
          showToast('Please select a race first', 'warning');
          return;
        }
        state.selectedRace = raceId;
        goToRegistrationStep2();
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
}

// ============================================================================
// REGISTRATION WIZARD HANDLERS
// ============================================================================

function attachRegistrationWizardHandlers() {
  if (state.view !== 'register') return;

  // Step 1: Race Selection
  const continueStep1 = document.getElementById('continue-step1');
  if (continueStep1) {
    continueStep1.addEventListener('click', () => {
      const raceSelect = document.getElementById('race-select-dropdown');
      if (raceSelect && raceSelect.value) {
        state.selectedRace = raceSelect.value;
        state.registrationStep = 2;
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
// CANDIDATE MANAGEMENT VIEW HANDLERS
// ============================================================================

function attachCandidateManagementHandlers() {
  if (state.view !== 'candidate-management') return;

  // Race filter dropdown
  const raceFilterDropdown = document.getElementById('candidate-race-filter-dropdown');
  if (raceFilterDropdown) {
    raceFilterDropdown.addEventListener('change', async (e) => {
      candidateManagementSelectedRaceId = e.target.value || null;
      await fetchParticipants(candidateManagementSelectedRaceId);
      render();
    });
  }

  // Create New Candidate Button
  const createNewCandidateBtn = document.getElementById('create-new-candidate-btn');
  if (createNewCandidateBtn) {
    createNewCandidateBtn.addEventListener('click', async () => {
      // Open the registration view instead of an in-place modal
      state.registrationStep = 1;
      state.scannedRFID = null;
      // If a race filter is selected, preselect it in the registration flow
      state.selectedRace = candidateManagementSelectedRaceId || null;
      // Ensure races are loaded for the registration page
      await fetchRaces();
      state.view = 'register';
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

      // Open edit modal and populate fields
      const modal = document.getElementById('candidate-modal');
      const modalTitle = document.getElementById('candidate-modal-title');
      modalTitle.textContent = 'Edit Candidate';
      document.getElementById('candidate-id').value = candidateId;
      document.getElementById('candidate-race-id').value = participant.race_id;

      // Decrypt name if needed (leave as encrypted fallback)
      let decryptedName = participant.encrypted_name || participant.name;
      if (participant.encryption_key && decryptedName) {
        try {
          const dec = await window.electronAPI.decryptFernet(decryptedName, participant.encryption_key);
          decryptedName = dec;
        } catch (err) {
          console.error('Failed to decrypt name:', err);
        }
      }

      document.getElementById('candidate-name').value = decryptedName || '';
      document.getElementById('candidate-rfid').value = participant.rfid_tag || participant.rfid || '';
      document.getElementById('candidate-age').value = participant.age || '';
      document.getElementById('candidate-gender').value = participant.gender || '';

      // Disable RFID and race selection on edit to avoid moving between per-race tables
      const rfidEl = document.getElementById('candidate-rfid');
      if (rfidEl) { rfidEl.disabled = true; }
      const raceEl = document.getElementById('candidate-race-id');
      if (raceEl) { raceEl.disabled = true; }

      modal.style.display = 'flex';
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

  // Note: Modal-based create/edit has been replaced by the registration page.
  // Candidate creation and editing now use the dedicated registration flow.
}

// Re-attach modal controls for CandidateManagement (close/cancel/submit)
function attachCandidateModalControls() {
  const closeCandidateModal = document.getElementById('close-candidate-modal');
  if (closeCandidateModal) {
    closeCandidateModal.addEventListener('click', () => {
      const modal = document.getElementById('candidate-modal');
      if (modal) modal.style.display = 'none';
    });
  }

  const cancelCandidateForm = document.getElementById('cancel-candidate-form');
  if (cancelCandidateForm) {
    cancelCandidateForm.addEventListener('click', () => {
      const modal = document.getElementById('candidate-modal');
      if (modal) modal.style.display = 'none';
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
        }
        const modal = document.getElementById('candidate-modal');
        if (modal) modal.style.display = 'none';
      } catch (err) {
        // Errors handled by updateCandidate
      }
    });
  }
}

// ============================================================================
// SCOREBOARD VIEW HANDLERS
// ============================================================================

function attachScoreboardHandlers() {
  if (state.view !== 'scoreboard') return;

  // Race filter dropdown (only completed races)
  const scoreboardRaceFilterDropdown = document.getElementById('scoreboard-race-filter-dropdown');
  if (scoreboardRaceFilterDropdown) {
    scoreboardRaceFilterDropdown.addEventListener('change', async (e) => {
      scoreboardSelectedRaceId = e.target.value || null;
      await fetchParticipants(scoreboardSelectedRaceId);
      render();
    });
  }

  // Export Scoreboard Button (future feature)
  const exportScoreboardBtn = document.getElementById('export-scoreboard-btn');
  if (exportScoreboardBtn) {
    exportScoreboardBtn.addEventListener('click', () => {
      showToast('Export feature coming soon', 'info');
    });
  }
}

// ============================================================================
// CANDIDATE CRUD OPERATIONS (Using existing /participant/register endpoint)
// ============================================================================

async function createCandidate(candidateData) {
  return await globalLoader.wrap(async () => {
    try {
      await ensureAuth();
      // Use existing /participant/register endpoint
      await apiRequest('/participant/register', {
        method: 'POST',
        body: candidateData,
      });
      
      showToast('Candidate created successfully', 'success');
      await fetchParticipants(candidateManagementSelectedRaceId);
      render();
    } catch (err) {
      console.error(err);
      showToast(`Failed to create candidate: ${err.message}`, 'error');
      throw err;
    }
  });
}

async function updateCandidate(candidateId, updates) {
  return await globalLoader.wrap(async () => {
    try {
      await ensureAuth();
      await apiRequest(`/participant/${candidateId}`, {
        method: 'PATCH',
        body: updates,
      });
      
      showToast('Candidate updated successfully', 'success');
      await fetchParticipants(candidateManagementSelectedRaceId);
      render();
    } catch (err) {
      console.error(err);
      showToast(`Failed to update candidate: ${err.message}`, 'error');
      throw err;
    }
  });
}

async function deleteCandidate(candidateId) {
  if (!confirm('Are you sure you want to delete this candidate? This action cannot be undone.')) {
    return;
  }
  
  return await globalLoader.wrap(async () => {
    try {
      await ensureAuth();
      await apiRequest(`/participant/${candidateId}`, {
        method: 'DELETE',
      });
      
      showToast('Candidate deleted successfully', 'success');
      await fetchParticipants(candidateManagementSelectedRaceId);
      render();
    } catch (err) {
      console.error(err);
      showToast(`Failed to delete candidate: ${err.message}`, 'error');
      throw err;
    }
  });
}

async function bootstrap() {
  try {
    await ensureAuth();
    await fetchRaces();
    await fetchDashboardData();
  } catch (err) {
    console.error(err);
    showToast(`Bootstrap failed: ${err.message}`, 'error');
  }
  render();
}

window.openRaceModal = () => {
  state.showRaceModal = true;
  render();
};

window.addEventListener("online", () => {
  showToast("Back online", 'success');
  render();
});

window.addEventListener("offline", () => {
  showToast("Offline - hub caching active", 'warning');
  render();
});

// Registration wizard functions
function goToRegistrationStep2() {
  if (!state.selectedRace) {
    showToast('Please select a race first', 'warning');
    return;
  }
  state.registrationStep = 2;
  state.scannedRFID = null;
  render();
  startRFIDListener();
}

function goToRegistrationStep3() {
  if (!state.scannedRFID) {
    showToast('Please scan an RFID tag first', 'warning');
    return;
  }
  
  // Check if RFID already exists in existingRFIDSet
  console.debug('[Registration][goToRegistrationStep3] scannedRFID=', state.scannedRFID, 'existingRFIDSet_size=', existingRFIDSet.size);
  const rfidUpper = state.scannedRFID.toUpperCase();
  if (existingRFIDSet.has(rfidUpper)) {
    console.debug('[Registration][goToRegistrationStep3] Duplicate detected for', rfidUpper);
    showToast('This RFID tag is already registered. Please use a different RFID tag.', 'error');
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

function startRFIDListener() {
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
        console.debug('[Registration][startRFIDListener] buffer=', rfidBuffer, 'scanned=', state.scannedRFID, 'existingSetHas=', existingRFIDSet.has(state.scannedRFID));
        
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

function stopRFIDListener() {
  if (window.rfidKeyListener) {
    document.removeEventListener('keypress', window.rfidKeyListener);
    window.rfidKeyListener = null;
  }
  state.rfidListenerActive = false;
  console.log('[Registration] RFID listener stopped');
  console.debug('[Registration] stopRFIDListener()');
}

async function submitRegistration() {
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
    const response = await fetch(`${state.config.apiBaseUrl}/participant/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${state.auth.token}`
      },
      body: JSON.stringify({
        race_id: state.selectedRace,
        rfid_tag: rfid.toUpperCase(),
        name: name,
        age: age ? Number(age) : undefined,
          gender: gender.toUpperCase()
      })
    });

    const data = await response.json();
    if (data.success) {
      // Add RFID to existingRFIDSet to prevent duplicate registration in same session
      const rfidUpper = rfid.toUpperCase();
      console.debug('[Registration][submitRegistration] before add existingRFIDSet_has=', existingRFIDSet.has(rfidUpper), 'size=', existingRFIDSet.size);
      existingRFIDSet.add(rfidUpper);
      console.debug('[Registration][submitRegistration] after add size=', existingRFIDSet.size);
      
      document.getElementById('registration-form').reset();
      
      const timestamp = new Date().toLocaleTimeString();
      const race = state.races.find(r => r.id === state.selectedRace);
      const raceName = race ? race.name : 'Unknown Race';
      const category = data.data.category || 'N/A';
      
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
    } else {
      showToast(`Registration failed: ${data.message || 'Unknown error'}`, 'error');
    }
  } catch (err) {
    console.error('Registration error:', err);
    showToast(`Registration failed: ${err.message}`, 'error');
  }
}

// ===== Race Start View Helper Functions =====

function startRaceDataPolling() {
  // Initial fetch
  refreshRaceStartData();
  
  // Poll every 2 seconds for live updates
  if (raceStartPollingInterval) {
    clearInterval(raceStartPollingInterval);
  }
  
  raceStartPollingInterval = setInterval(() => {
    refreshRaceStartData();
  }, 2000);
  
  console.log('✓ Started polling race data from backend');
  updateRaceStartWSStatus(true, 'Polling Active');
}

function stopRaceDataPolling() {
  if (raceStartPollingInterval) {
    clearInterval(raceStartPollingInterval);
    raceStartPollingInterval = null;
    console.log('⏹ Stopped polling race data');
    updateRaceStartWSStatus(false, 'Polling Stopped');
  }
}

function updateRaceStartCandidateDisplay(grouped) {
  const container = document.getElementById('groups-container');
  if (!container) return;

  const { registered = [], grace = [], running = [], completed = [] } = grouped;

  if (registered.length === 0 && grace.length === 0 && running.length === 0 && completed.length === 0) {
    container.innerHTML = '<div style="background: #0f172a; border: 1px solid #334155; border-radius: 4px; padding: 12px; color: #cbd5e1; font-size: 12px;"><p style="color: #64748b; margin: 0;">No participants yet. Register participants first.</p></div>';
    return;
  }

  const renderParticipantList = (title, color, participants, emptyText) => {
    const rows = participants && participants.length
      ? participants.map((p) => formatRaceStartCandidateRow(p, title.toLowerCase())).join('')
      : `<p style="color: #64748b; margin: 0;">${emptyText}</p>`;

    return `
      <div style="background: #0b1222; border: 1px solid #1f2937; border-radius: 4px; padding: 8px; min-height: 60px;">
        <div style="color: ${color}; font-size: 12px; font-weight: 600; margin-bottom: 6px;">${title} (${participants.length})</div>
        ${rows}
      </div>
    `;
  };

  // Render four sections: Registered, Grace Period, Running, Completed
  const html = `
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;">
      ${renderParticipantList('Grace Period', '#60a5fa', grace, 'No runners in grace')}
      ${renderParticipantList('Running', '#fbbf24', running, 'No runners started yet')}
      ${renderParticipantList('Completed', '#34d399', completed, 'No finished runners yet')}
    </div>
  `;

  container.innerHTML = html;
}

function formatRaceStartCandidateRow(candidate, type) {
  let duration = '';
  let durationMin = '';
  
  if (candidate.status === 'completed' && candidate.start_time && candidate.end_time) {
    const startTime = new Date(candidate.start_time);
    const endTime = new Date(candidate.end_time);
    const durationMs = endTime - startTime;
    const durationSeconds = durationMs / 1000;
    const minutes = Math.floor(durationSeconds / 60);
    const seconds = Math.floor(durationSeconds % 60);
    
    duration = `${minutes}:${String(seconds).padStart(2, '0')}`;
  }
  
  const startTimeStr = candidate.start_time 
    ? new Date(candidate.start_time).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : 'pending';
  
  const endTimeStr = candidate.end_time
    ? new Date(candidate.end_time).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '-';
  
  let color = '#cbd5e1';
  if (type === 'running') color = '#fbbf24';
  else if (type === 'grace period') color = '#60a5fa';
  else if (type === 'completed') color = '#34d399';
  else if (type === 'registered') color = '#a78bfa';
  
  if (type === 'completed'){
    return `
      <div style="display: grid; grid-template-columns: 180px 100px 100px 60px; gap: 8px; padding: 8px; border-bottom: 1px solid #334155; color: ${color};">
        <div style="font-family: monospace; font-weight: bold;">${candidate.rfid_tag || 'N/A'}</div>
        <div>${startTimeStr}</div>
        <div>${endTimeStr}</div>
        <div>${duration}</div>
      </div>
    `;
  } else if (type === 'grace period'){
    return `
      <div style="display: grid; grid-template-columns: 180px auto; gap: 8px; padding: 8px; border-bottom: 1px solid #334155; color: ${color};">
        <div style="font-family: monospace; font-weight: bold;">${candidate.rfid_tag || 'N/A'}</div>
      </div>
    `;
  } else {
    return `
      <div style="display: grid; grid-template-columns: 180px 100px auto; gap: 8px; padding: 8px; border-bottom: 1px solid #334155; color: ${color};">
        <div style="font-family: monospace; font-weight: bold;">${candidate.rfid_tag || 'N/A'}</div>
        <div>${startTimeStr}</div>
        <div>${duration}</div>
      </div>
    `;
  }
}

function updateRaceStartStatistics(participants) {
  let registered = participants.length;
  let grace = 0;
  let running = 0;
  let completed = 0;
  console.log(participants);
  for (const p of participants) {
    if (p.status === 'grace') grace++;
    else if (p.status === 'running') running++;
    else if (p.status === 'completed') completed++;
  }
  
  const registeredEl = document.getElementById('stat-registered');
  if (registeredEl) registeredEl.textContent = registered;
  
  const graceEl = document.getElementById('stat-grace');
  if (graceEl) graceEl.textContent = grace;
  
  const runningEl = document.getElementById('stat-running');
  if (runningEl) runningEl.textContent = running;
  
  const completedEl = document.getElementById('stat-completed');
  if (completedEl) completedEl.textContent = completed;
}

function updateRaceStartWSStatus(connected, status) {
  const statusEl = document.getElementById('ws-status');
  if (!statusEl) return;
  
  if (connected) {
    statusEl.innerHTML = '🟢 ' + status;
    statusEl.style.color = '#34d399';
  } else {
    statusEl.innerHTML = '🔴 ' + status;
    statusEl.style.color = '#ef4444';
  }
}

async function loadRaceStartRaces() {
  try {
    await ensureAuth();
    const races = await apiRequest('/race');

    const raceSelect = document.getElementById('race-select');
    if (!raceSelect) return;

    raceSelect.innerHTML = '<option value="">Select a race...</option>';

    if (Array.isArray(races) && races.length > 0) {
      races.forEach((race) => {
        const option = document.createElement('option');
        option.value = race.id;
        option.textContent = race.name;
        // Only set selected if it matches the current state
        if (race.id === raceStartSelectedRaceId) {
            option.selected = true;
        }
        raceSelect.appendChild(option);
      });
    }
  } catch (e) {
    console.error('Failed to load races:', e);
    showRaceStartStatusMessage('Failed to load races', 'error');
  }
}

function handleRaceStartRaceChange(event) {
  const newId = event.target.value;
  
  if (!newId) {
    raceStartSelectedRaceId = null;
    stopRaceDataPolling();
    render();
    return;
  }

  raceStartSelectedRaceId = newId;
  
  // Re-render to update UI panels/buttons
  render();
  
  // Start polling now that a race is explicitly selected
  startRaceDataPolling();
}

async function handleRaceStartSubmit(event) {
  event.preventDefault();
  
  if (!raceStartSelectedRaceId) {
    showRaceStartStatusMessage('Please select a race', 'error');
    return;
  }
  
  return await globalLoader.wrap(async () => {
    try {
      await ensureAuth();
      
      // Call backend API to start the race
      await apiRequest(`/race/${raceStartSelectedRaceId}/start`, {
        method: 'POST'
      });
      
      raceStartTime = new Date();
      showToast('✓ Race started successfully', 'success');
      
      // Refresh races and re-render to update button state
      await fetchRaces();
      render();
      
      // Refresh data to show updated times and status
      await refreshRaceStartData();
    } catch (e) {
      console.error('Failed to start race:', e);
      showRaceStartStatusMessage(`Failed to start race: ${e.message}`, 'error');
    }
  });
}


async function refreshRaceStartData() {
  if (!raceStartSelectedRaceId) {
    console.warn('No race selected for race start view');
    return;
  }
  
  try {
    // Ensure authentication token is valid
    await ensureAuth();
    
    // Fetch participants with timing data from backend using authenticated API request
    const participants = await apiRequest(`/race/${raceStartSelectedRaceId}/participants?include_timing=true`);
    
    // Group participants by status for display (status values: registered, grace, running, completed)
    const grouped = {
      registered: participants.filter(p => p.status === 'registered'),
      grace: participants.filter(p => p.status === 'grace'),
      running: participants.filter(p => p.status === 'running'),
      completed: participants.filter(p => p.status === 'completed')
    };
    updateRaceStartCandidateDisplay(grouped);
    updateRaceStartStatistics(participants);
  } catch (e) {
    console.error('Failed to refresh race data from backend:', e);
    updateRaceStartWSStatus(false, 'Connection Error');
  }
}

function showRaceStartStatusMessage(message, type = 'info') {
  const statusEl = document.getElementById('status-message');
  if (!statusEl) return;
  
  const colors = {
    'success': '#10b981',
    'error': '#ef4444',
    'info': '#0ea5e9'
  };
  
  statusEl.innerHTML = `<div style="padding: 12px; background: ${colors[type]}20; border: 1px solid ${colors[type]}; border-radius: 4px; color: ${colors[type]};">${message}</div>`;
}

// ===== End Race Start View Helper Functions =====

bootstrap();