// Registration-focused renderer (RFID hub handles caching and timing). This app handles
// user authentication, participant registration, and data viewing.
import { showToast } from './utils/Toasts.js';
import { renderRegistration } from './views/CandidateRegistration.js';
import { renderDashboard } from './views/Dashboard.js';
import { renderCreateRace } from './views/CreateRace.js';
import { renderCandidateManagement } from './views/CandidateManagement.js';
import { renderScoreboard } from './views/Scoreboard.js';
import { renderRaceStart, renderRaceStartTimeModal } from './views/RaceStart.js';
import { renderRacesManagement } from './views/RacesManagement.js';

// ============================================================================
// SERVICE IMPORTS - View-specific logic
// ============================================================================
import { updateRace, deleteRace, endRace, openRaceEditModal, attachRacesManagementHandlers, setupRacesManagementView } from './services/RacesManagement.js';
import { startRFIDListener, stopRFIDListener, goToRegistrationStep2, goToRegistrationStep3, submitRegistration, uploadBulkCandidates, registerRunner, attachRegistrationWizardHandlers, setupRegistrationView } from './services/CandidateRegistration.js';
import { updateCandidate, deleteCandidate, openCandidateEditModal, attachCandidateManagementHandlers, attachCandidateModalControls, setupCandidateManagementView } from './services/CandidateManagement.js';
import { attachScoreboardHandlers, areScoreboardFiltersActive, getScoreboardExportRows, buildScoreboardExportHtml, exportScoreboardResults, setupScoreboardView } from './services/Scoreboard.js';
import { startRaceDataPolling, stopRaceDataPolling, updateRaceStartCandidateDisplay, formatRaceStartCandidateRow, updateRaceStartStatistics, updateRaceStartWSStatus, loadRaceStartRaces, handleRaceStartRaceChange, handleRaceStartSubmit, refreshRaceStartData, showRaceStartStatusMessage, formatDuration, getRaceStartTimes, getEarliestStartTime, updateDurationDisplay, startDurationClock, stopDurationClock, updateRaceDetailsDisplay, attachRaceStartHandlers, setupRaceStartView } from './services/RaceStart.js';
import { renderQualifyingTimesGrid, attachCreateRaceHandlers, setupCreateRaceView } from './services/CreateRace.js';

const secureApi = window.secureApi;
const app = document.getElementById("app");

// ============================================================================
// INJECT GLOBAL STYLES - Hide number input spinners
// ============================================================================
(function injectGlobalStyles() {
  if (document.getElementById('app-global-styles')) return; // Prevent duplicate injection
  const style = document.createElement('style');
  style.id = 'app-global-styles';
  style.textContent = `
    /* Hide number input spinner arrows */
    input[type="number"]::-webkit-outer-spin-button,
    input[type="number"]::-webkit-inner-spin-button {
      -webkit-appearance: none;
      margin: 0;
    }
    input[type="number"] {
      -moz-appearance: textfield;
    }
  `;
  document.head.appendChild(style);
})();

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

// ============================================================================
// GLOBAL APP CONTEXT - Shared across all service modules
// ============================================================================
// This will be initialized after state and other globals are set up
let window_appContext = {};

const state = {
  view: "dashboard",
  config: secureApi.getConfig(),
  auth: { token: null, expiresAt: 0, username: "", password: "", remember: false },
  races: [],
  registrations: [],
  selectedRace: null,
  showRaceModal: false,
  raceCategoryFilter: "",
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

const RACE_CATEGORY_CONFIG = { // taken from backend constants.py for easy access in CreateRace view
  BPET: {
    label: "BPET",
    levels: ["Excellent", "Good", "Satisfactory"],
    ageGroups: [
      { key: "bpet_age_upto30", label: "Up to 30 yrs", defaults: [25, 26.5, 27] },
      { key: "bpet_age_upto40", label: "Up to 40 yrs", defaults: [28.5, 30, 31] },
      { key: "bpet_age_40_45", label: "40 to 45 yrs", defaults: [31.5, 33, 35] },
    ],
  },
  CPT: {
    label: "CPT",
    levels: ["Superb", "Excellent", "Good", "Satisfactory"],
    ageGroups: [
      { key: "cpt_age_upto35", label: "Up to 35 yrs", defaults: [14, 15, 16, 17.5] },
      { key: "cpt_age_35_45", label: "35 to 45 yrs", defaults: [16, 17, 18, 19.5] },
      { key: "cpt_age_45_50", label: "45 to 50 yrs", defaults: [17, 18, 19, 20.5] },
      { key: "cpt_age_50_55", label: "50 to 55 yrs", defaults: [28, 30, 32, 34] },
      { key: "cpt_age_55_60", label: "55 to 60 yrs", defaults: [32, 34, 36, 38] },
    ],
  },
  PPT: {
    label: "PPT",
    levels: ["Excellent", "Good", "Satisfactory"],
    ageGroups: [
      { key: "ppt_age_upto30", label: "Up to 30 yrs", defaults: [9, 9.5, 10] },
      { key: "ppt_age_30_40", label: "30 to 40 yrs", defaults: [10.5, 11, 11.5] },
      { key: "ppt_age_40_45", label: "40 to 45 yrs", defaults: [11.5, 12, 12.5] },
      { key: "ppt_age_45_50", label: "45 to 50 yrs", defaults: [13, 14, 15] },
    ],
  },
};

function getRaceCategoryConfig(category) {
  return RACE_CATEGORY_CONFIG[category] || RACE_CATEGORY_CONFIG.BPET;
}

// Per-race RFID deduplication map: raceId -> Set(rfid)
const perRaceRFIDMap = new Map();

function getSelectedRaceId() {
  if (!state.selectedRace) return null;
  return typeof state.selectedRace === 'object' ? state.selectedRace.id : state.selectedRace;
}

function getRFIDSetForRace(raceId) {
  if (!raceId) return new Set();
  if (!perRaceRFIDMap.has(raceId)) perRaceRFIDMap.set(raceId, new Set());
  return perRaceRFIDMap.get(raceId);
}

async function populateRFIDSetForRace(raceId) {
  if (!raceId) return;
  try {
    await fetchParticipants(raceId);
    const set = new Set();
    state.participants.forEach(p => {
      const rfid = (p.rfid || p.rfid_tag || '').toUpperCase();
      if (rfid) set.add(rfid);
    });
    perRaceRFIDMap.set(raceId, set);
    console.debug('[Registration] populated RFID set for race', raceId, { size: set.size });
  } catch (err) {
    console.error('Failed to populate RFID set for race', raceId, err);
  }
}

// Candidate Management View state
let candidateManagementSelectedRaceId = null;
let scoreboardSelectedRaceId = null;
let scoreboardSearchQuery = '';
let scoreboardSortKey = 'durationMs';
let scoreboardSortDir = 'asc';
let scoreboardAgeFilter = '';
let scoreboardRemarksFilter = '';

// Race Start View state
let raceStartSelectedRaceId = null;
let raceStartPollingInterval = null;
let durationClockInterval = null;

// Expose state to CandidateRegistration component
window.appState = state;
window.authToken = null;

// ============================================================================
// INITIALIZE APP CONTEXT - Inject dependencies for service modules
// ============================================================================
function setupAppContext() {
  window.appContext = {
    // State & Config
    state,
    config: state.config,
    globalLoader,
    
    // Authentication & API
    generateNonce,
    isTokenValid,
    apiRequest,
    apiUpload,
    login,
    ensureAuth,
    loadStoredCredentials,
    fetchRaces,
    fetchDashboardData,
    fetchParticipants,
    registerRunner,
    getRaceCategoryConfig,
    
    // RFID Management
    getSelectedRaceId,
    getRFIDSetForRace,
    populateRFIDSetForRace,
    perRaceRFIDMap,
    
    // Common rendering
    render,
    decryptName,
    
    // Candidate Management (proxied to module vars)
    get candidateManagementSelectedRaceId() { return candidateManagementSelectedRaceId; },
    set candidateManagementSelectedRaceId(val) { candidateManagementSelectedRaceId = val; },
    
    // Scoreboard (proxied to module vars)
    get scoreboardSelectedRaceId() { return scoreboardSelectedRaceId; },
    set scoreboardSelectedRaceId(val) { scoreboardSelectedRaceId = val; },
    get scoreboardSearchQuery() { return scoreboardSearchQuery; },
    set scoreboardSearchQuery(val) { scoreboardSearchQuery = val; },
    get scoreboardSortKey() { return scoreboardSortKey; },
    set scoreboardSortKey(val) { scoreboardSortKey = val; },
    get scoreboardSortDir() { return scoreboardSortDir; },
    set scoreboardSortDir(val) { scoreboardSortDir = val; },
    get scoreboardAgeFilter() { return scoreboardAgeFilter; },
    set scoreboardAgeFilter(val) { scoreboardAgeFilter = val; },
    get scoreboardRemarksFilter() { return scoreboardRemarksFilter; },
    set scoreboardRemarksFilter(val) { scoreboardRemarksFilter = val; },
    
    // Race Start (proxied to module vars)
    get raceStartSelectedRaceId() { return raceStartSelectedRaceId; },
    set raceStartSelectedRaceId(val) { raceStartSelectedRaceId = val; },
    get raceStartPollingInterval() { return raceStartPollingInterval; },
    set raceStartPollingInterval(val) { raceStartPollingInterval = val; },
    get durationClockInterval() { return durationClockInterval; },
    set durationClockInterval(val) { durationClockInterval = val; },
    
    // Views
    renderRaceStartTimeModal,
  };
}

function generateNonce() {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

function isTokenValid() {
  return state.auth.token && state.auth.expiresAt > Date.now() + 30000;
}

function formatValidationErrors(errors) {
  if (!Array.isArray(errors) || errors.length === 0) return "Invalid request payload";
  return errors
    .map((item) => {
      const field = Array.isArray(item?.loc) ? item.loc.join(".") : "payload";
      const msg = item?.msg || "Invalid value";
      return `${field}: ${msg}`;
    })
    .join("; ");
}

function extractBackendError(data, status) {
  if (!data || typeof data !== "object") {
    return {
      message: `Request failed (${status})`,
      error_code: null,
      details: {},
    };
  }

  if (data.success === false) {
    const backendDetails = data.details || {};
    const backendValidationErrors = Array.isArray(backendDetails.errors) ? backendDetails.errors : null;
    return {
      message: backendValidationErrors
        ? formatValidationErrors(backendValidationErrors)
        : (data.message || `Request failed (${status})`),
      error_code: data.error_code || null,
      details: backendDetails,
    };
  }

  const rawDetail = data.detail;
  if (Array.isArray(rawDetail) && rawDetail.length > 0) {
    return {
      message: formatValidationErrors(rawDetail),
      error_code: "VALIDATION_ERROR",
      details: { errors: rawDetail },
    };
  }

  return {
    message: data.message || `Request failed (${status})`,
    error_code: data.error_code || null,
    details: data.details || {},
  };
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
    const parsedError = extractBackendError(data, response.status);
    const err = new Error(parsedError.message);
    err.error_code = parsedError.error_code;
    err.details = parsedError.details;
    throw err;
  }
  return data.data;
}

async function apiUpload(path, formData, auth = true) {
  const headers = {};
  if (auth && state.auth.token) headers["Authorization"] = `Bearer ${state.auth.token}`;

  const response = await fetch(`${state.config.apiBaseUrl}${path}`, {
    method: "POST",
    headers,
    body: formData,
  });

  const data = await response.json().catch(() => ({ success: false, message: "Bad JSON" }));
  if (!response.ok || !data.success) {
    const parsedError = extractBackendError(data, response.status);
    const err = new Error(parsedError.message);
    err.error_code = parsedError.error_code;
    err.details = parsedError.details;
    throw err;
  }
  return data.data;
}

async function login() {
  // Use an ISO8601 string compatible with Python's datetime.fromisoformat
  // (replace 'Z' with '+00:00') to avoid parsing issues on the backend.
  const timestamp = new Date().toISOString().replace('Z', '+00:00');
  const nonce = generateNonce();
  const { username, password } = state.auth;
  if (!username || !password) throw new Error("Missing username or password");

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
  if (!state.auth.username || !state.auth.password) {
    throw new Error("Missing credentials");
  }
  await login();
}

function loadStoredCredentials() {
  const stored = secureApi.getStoredCredentials();
  if (stored && stored.username && stored.password) {
    state.auth.username = stored.username;
    state.auth.password = stored.password;
    return true;
  }
  return false;
}

function renderLogin() {
  return `
    <div style="min-height: 100vh; display: flex; align-items: center; justify-content: center; background: #0f172a;">
      <div style="width: 420px; background: #111827; padding: 32px; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.35);">
        <div style="font-size: 20px; font-weight: 600; color: #e5e7eb; margin-bottom: 8px;">RFID Marathon</div>
        <div style="font-size: 13px; color: #9ca3af; margin-bottom: 24px;">Sign in to continue</div>
        <form id="login-form">
          <label style="display:block; font-size: 12px; color:#94a3b8; margin-bottom:6px;">USERNAME</label>
          <input id="login-username" type="text" required style="width:100%; padding:10px 12px; border-radius:8px; border:1px solid #1f2937; background:#0b1220; color:#e2e8f0; margin-bottom:16px;" />
          <label style="display:block; font-size: 12px; color:#94a3b8; margin-bottom:6px;">PASSWORD</label>
          <input id="login-password" type="password" required style="width:100%; padding:10px 12px; border-radius:8px; border:1px solid #1f2937; background:#0b1220; color:#e2e8f0; margin-bottom:16px;" />
          <label style="display:flex; align-items:center; gap:8px; font-size: 12px; color:#94a3b8; margin-bottom:20px;">
            <input id="login-remember" type="checkbox" /> Remember Me
          </label>
          <button type="submit" style="width:100%; padding:10px 12px; border-radius:8px; border:none; background:#3b82f6; color:white; font-weight:600; cursor:pointer;">Login</button>
        </form>
      </div>
    </div>
  `;
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

async function fetchParticipants(raceId = null, includeTiming = false) {
  try {
    await ensureAuth();
    const apipoint = (raceId) ? (`/race/${raceId}/participants` + (includeTiming ? '?include_timing=true' : '')) : `/participants`;
    const participants = await apiRequest(apipoint);
    
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

function renderSidebar() {
  return `
    <div class="sidebar">
      <div class="brand">RFID Marathon</div>
      <nav class="sidebar-nav">
          <button class="nav-btn ${state.view === "dashboard" ? "active" : ""}" data-view="dashboard">Dashboard</button>
          <button class="nav-btn ${state.view === "races-management" ? "active" : ""}" data-view="races-management">Races Management</button>
          <button class="nav-btn ${state.view === "candidate-management" ? "active" : ""}" data-view="candidate-management">Candidate Management</button>
          <button class="nav-btn ${state.view === "register" ? "active" : ""}" data-view="register">Register</button>
          <button class="nav-btn ${state.view === "race-start" ? "active" : ""}" data-view="race-start">Start Race</button>
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
  return `
    <div class="topbar">
      <div class="status-group">
        <span class="pill">Registrations done today: ${state.dashboardData.todayRegistrations}</span>
      </div>
      <div class="actions">
      ${state.view == 'race-start' ? 
        `
        <div>
          <div style="color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Polling Status</div>
          <div id="ws-status" style="color: #ef4444; font-size: 14px;">⚪ Inactive</div>
        </div> 
        `: ``}
        <button class="ghost" id="logout-btn">Logout</button>
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
  if (state.view === "login") {
    app.innerHTML = renderLogin();
    const form = document.getElementById("login-form");
    if (form) {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const username = document.getElementById("login-username").value.trim();
        const password = document.getElementById("login-password").value;
        const remember = document.getElementById("login-remember").checked;
        state.auth.username = username;
        state.auth.password = password;
        state.auth.remember = remember;
        try {
          await ensureAuth();
          if (remember) {
            secureApi.setStoredCredentials(username, password);
          } else {
            secureApi.clearStoredCredentials();
          }
          state.view = "dashboard";
          await fetchRaces();
          await fetchDashboardData();
          render();
        } catch (err) {
          console.error(err);
          showToast(`Login failed: ${err.message}`, 'error');
        }
      });
    }
    return;
  }

  // Cleanup polling when leaving race-start view
  // Inside document.querySelectorAll(".nav-btn").forEach((btn) => { ... })
  if (state.view !== "race-start" && raceStartPollingInterval) {
    stopRaceDataPolling();
  }
  
  // Cleanup duration clock when leaving race-start view
  if (state.view !== "race-start" && durationClockInterval) {
    stopDurationClock();
  }
  
  // Cleanup RFID listener when leaving registration view
  if (state.view !== "register" && state.rfidListenerActive) {
    stopRFIDListener();
    // Clear per-race RFID map when leaving registration page
    perRaceRFIDMap.clear();
  }
  
  const htmlContent = `
    <div class="layout">
      ${renderSidebar()}
      <div class="main">
        ${renderHeader()}
        ${state.view === "dashboard" ? renderDashboard(state.races, state.dashboardData.todayRegistrations, state.dashboardData.totalParticipants, state.dashboardData.startedToday, state.dashboardData.finishedToday, state.dashboardData.raceStats) : ""}
        ${state.view === "races-management" ? renderRacesManagement(
          state.raceCategoryFilter ? state.races.filter(r => r.race_category === state.raceCategoryFilter) : state.races,
          state.raceCategoryFilter
        ) : ""}
        ${state.view === "create" ? renderCreateRace() : ""}
        ${state.view === "race-start" ? renderRaceStart(state.races, raceStartSelectedRaceId) : ""}
        ${state.view === "register" ? renderRegister() : ""}
        ${state.view === "candidate-management" ? renderCandidateManagement(state.races, state.participants, candidateManagementSelectedRaceId) : ""}
        ${state.view === "scoreboard" ? renderScoreboard(state.races, state.participants, scoreboardSelectedRaceId, { searchQuery: scoreboardSearchQuery, sortKey: scoreboardSortKey, sortDir: scoreboardSortDir, ageFilter: scoreboardAgeFilter, remarksFilter: scoreboardRemarksFilter }) : ""}
      </div>
    </div>
  `;
  app.innerHTML = htmlContent;

  // Force reflow
  void app.offsetHeight;

  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      const newView = e.target.dataset.view;

      // Call view-specific setup functions
      try {
        if (newView === 'register') {
          await setupRegistrationView();
        } else if (newView === 'race-start') {
          await setupRaceStartView();
        } else if (newView === 'dashboard') {
          await fetchRaces();
          await fetchDashboardData();
        } else if (newView === 'candidate-management') {
          await setupCandidateManagementView();
        } else if (newView === 'scoreboard') {
          await setupScoreboardView();
        } else if (newView === 'create') {
          await setupCreateRaceView();
        } else if (newView === 'races-management') {
          await setupRacesManagementView();
        }
      } catch (err) {
        console.error(`Failed to setup ${newView} view:`, err);
      }

      state.view = newView;
      render();
    });
  });

  const logoutBtn = document.getElementById("logout-btn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", () => {
      state.auth.token = null;
      state.auth.expiresAt = 0;
      state.auth.username = "";
      state.auth.password = "";
      state.auth.remember = false;
      window.authToken = null;
      secureApi.clearStoredCredentials();
      state.view = "login";
      render();
    });
  }

  const refreshBtn = document.getElementById("refresh-btn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", async () => {
      await fetchRaces();
      if (state.view === 'dashboard') {
        await fetchDashboardData();
      }
      if (state.view === 'candidate-management') {
        await fetchParticipants(candidateManagementSelectedRaceId);
      }
      if (state.view === 'scoreboard') {
        await fetchParticipants(scoreboardSelectedRaceId, true);
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

  // Register new candidate from other views (if button exists in view)
  const registerNewCandidateBtn = document.getElementById("register-new-candidate-btn");
  if (registerNewCandidateBtn) {
    registerNewCandidateBtn.addEventListener("click", async () => {
      await setupRegistrationView();
      state.view = "register";
      render();
    });
  }

  // Registration wizard handlers
  // All registration wizard handlers are attached by service module
  attachRegistrationWizardHandlers();

  if (state.view === "create") {
    // Attach create race form handlers
    attachCreateRaceHandlers();
  }

  // ============================================================================
  // RACES MANAGEMENT VIEW EVENT LISTENERS
  // ============================================================================
  
  if (state.view === "races-management") {
    // Attach handlers from service module
    attachRacesManagementHandlers();
  }

  // Race Start view: Attach handlers
  if (state.view === "race-start") {
    // Attach all race-start view event handlers (async - loads races and sets up polling)
    await attachRaceStartHandlers();
  }
}


async function bootstrap() {
  // Initialize app context for service modules
  setupAppContext();
  
  try {
    const hasStored = loadStoredCredentials();
    if (!hasStored) {
      state.view = "login";
      render();
      return;
    }
    await ensureAuth();
    await fetchRaces();
    await fetchDashboardData();
  } catch (err) {
    console.error(err);
    showToast(`Bootstrap failed: ${err.message}`, 'error');
    state.view = "login";
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

bootstrap();