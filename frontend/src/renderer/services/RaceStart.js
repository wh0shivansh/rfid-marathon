import { showToast } from '../utils/Toasts.js';
import { endRace } from './RacesManagement.js';

// ============================================================================
// RACE START - POLLING
// ============================================================================

export function startRaceDataPolling() {
  const { raceStartPollingInterval } = window.appContext;
  
  console.debug('[RaceStart] Starting polling - fetching initial data');
  // Initial fetch
  refreshRaceStartData();
  
  // Poll every 2 seconds for live updates
  if (window.appContext.raceStartPollingInterval) {
    clearInterval(window.appContext.raceStartPollingInterval);
  }
  
  window.appContext.raceStartPollingInterval = setInterval(() => {
    console.debug('[RaceStart] Polling tick - fetching participants');
    refreshRaceStartData();
  }, 2000);
  
  console.log('[RaceStart] ✓ Started polling race data (participants only - 2s interval)');
  updateRaceStartWSStatus(true, 'Polling Active');
}

export function stopRaceDataPolling() {
  if (window.appContext.raceStartPollingInterval) {
    clearInterval(window.appContext.raceStartPollingInterval);
    window.appContext.raceStartPollingInterval = null;
    console.debug('[RaceStart] Stopped polling');
    console.log('[RaceStart] ⏹ Polling stopped');
    updateRaceStartWSStatus(false, 'Polling Stopped');
  }
}

// ============================================================================
// RACE START - DATA OPERATIONS
// ============================================================================

export async function refreshRaceStartData() {
  const { state, raceStartSelectedRaceId, ensureAuth, apiRequest } = window.appContext;
  
  if (!window.appContext.raceStartSelectedRaceId) {
    console.warn('[RaceStart Polling] No race selected');
    return;
  }
  
  try {
    // Ensure authentication token is valid
    await ensureAuth();
    
    console.debug(`[RaceStart Polling] Fetching participants for race ${window.appContext.raceStartSelectedRaceId}...`);
    
    // Fetch participants with timing data from backend using authenticated API request
    const participants = await apiRequest(`/race/${window.appContext.raceStartSelectedRaceId}/participants?include_timing=true`);
    const selectedRace = state.races.find(r => r.id === window.appContext.raceStartSelectedRaceId);
    const raceMode = selectedRace?.rfid_placement_mode || 'end_intersection';
    const usesMidPoint = raceMode !== 'end_intersection';
    
    console.debug(`[RaceStart Polling] Received ${participants.length} participants`);
    
    // Group participants by status for display (status values: registered, grace, running, mid, completed)
    const grouped = {
      registered: participants.filter(p => p.status === 'registered'),
      grace: participants.filter(p => p.status === 'grace'),
      running: participants.filter(p => p.status === 'running'),
      mid: usesMidPoint ? participants.filter(p => p.mid_time !== null) : [],
      completed: participants.filter(p => p.end_time !== null)
    };
    
    console.debug('[RaceStart Polling] Updating UI with grouped participant data');
    updateRaceStartCandidateDisplay(grouped);
    updateRaceStartStatistics(participants);
    
    // Update race details and duration using cached race data
    updateRaceDetailsDisplay();
    updateDurationDisplay();
  } catch (e) {
    console.error('[RaceStart Polling] Failed to refresh participants:', e);
    updateRaceStartWSStatus(false, 'Connection Error');
  }
}

// ============================================================================
// RACE START - UI DISPLAY
// ============================================================================

export function updateRaceStartCandidateDisplay(grouped) {
  const container = document.getElementById('groups-container');
  if (!container) return;

  const { state, raceStartSelectedRaceId } = window.appContext;
  const selectedRace = state.races.find(r => r.id === raceStartSelectedRaceId);
  const raceMode = selectedRace?.rfid_placement_mode || 'end_intersection';
  const usesMidPoint = raceMode !== 'end_intersection';

  const { registered = [], grace = [], running = [], mid = [], completed = [] } = grouped;

  if (registered.length === 0 && grace.length === 0 && running.length === 0 && mid.length === 0 && completed.length === 0) {
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

  const html = usesMidPoint
    ? `
      <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;">
        ${renderParticipantList('Registered', '#a78bfa', registered, 'No runners started yet')}
        ${renderParticipantList('Mid-point', '#60a5fa', mid, 'No runners reached mid-point yet')}
        ${renderParticipantList('Completed', '#34d399', completed, 'No finished runners yet')}
      </div>
    `
    : `
      <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px;">
        ${renderParticipantList('Registered', '#a78bfa', registered, 'No runners started yet')}
        ${renderParticipantList('Completed', '#34d399', completed, 'No finished runners yet')}
      </div>
    `;

  container.innerHTML = html;
}

export function formatRaceStartCandidateRow(candidate, type) {
  const { state, raceStartSelectedRaceId } = window.appContext;
  const selectedRace = state.races.find(r => r.id === raceStartSelectedRaceId);
  const raceMode = selectedRace?.rfid_placement_mode || 'end_intersection';
  const usesMidPoint = raceMode !== 'end_intersection';

  let duration = '';
  
  const hasDurationTimes = usesMidPoint
    ? (candidate.start_time && candidate.mid_time && candidate.end_time)
    : (candidate.start_time && candidate.end_time);

  if (candidate.status === 'completed' && hasDurationTimes) {
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
    : '-';
  
  const midTimeStr = candidate.mid_time
    ? new Date(candidate.mid_time).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '-';

  const endTimeStr = candidate.end_time
    ? new Date(candidate.end_time).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '-';
  
  let color = '#cbd5e1';
  if (type === 'running') color = '#fbbf24';
  else if (type === 'mid-point') color = '#60a5fa';
  else if (type === 'completed') color = '#34d399';
  else if (type === 'registered') color = '#a78bfa';
  
  if (type === 'completed'){
    return `
      <div style="display: grid; grid-template-columns: 180px 100px 100px 60px; gap: 8px; padding: 8px; border-bottom: 1px solid #334155; color: ${color};">
        <div style="font-family: monospace; font-weight: bold;">${candidate.rfid_tag || 'N/A'}</div>
        <div>${startTimeStr}</div>
        <div>${endTimeStr}</div>
        <div style="justify-self: right;">${duration}</div>
      </div>
    `;
  } else if (type === 'mid-point'){
    return `
      <div style="display: grid; grid-template-columns: 180px auto; gap: 8px; padding: 8px; border-bottom: 1px solid #334155; color: ${color};">
        <div style="font-family: monospace; font-weight: bold;">${candidate.rfid_tag || 'N/A'}</div>
        <div style="justify-self: right;">${midTimeStr}</div>
      </div>
    `;
  } else {
    if (usesMidPoint) {
      return `
        <div style="display: grid; grid-template-columns: 180px 100px 100px 100px; gap: 8px; padding: 8px; border-bottom: 1px solid #334155; color: ${color};">
          <div style="font-family: monospace; font-weight: bold;">${candidate.rfid_tag || 'N/A'}</div>
          <div>${startTimeStr}</div>
          <div>${midTimeStr}</div>
          <div>${endTimeStr}</div>
        </div>
      `;
    }

    return `
      <div style="display: grid; grid-template-columns: 180px 120px 120px; gap: 8px; padding: 8px; border-bottom: 1px solid #334155; color: ${color};">
        <div style="font-family: monospace; font-weight: bold;">${candidate.rfid_tag || 'N/A'}</div>
        <div>${startTimeStr}</div>
        <div>${endTimeStr}</div>
      </div>
    `;
  }
}

export function updateRaceStartStatistics(participants) {
  let registered = participants.length;
  let grace = 0;
  let running = 0;
  let completed = 0;
  const { state, raceStartSelectedRaceId } = window.appContext;
  const selectedRace = state.races.find(r => r.id === raceStartSelectedRaceId);
  const raceMode = selectedRace?.rfid_placement_mode || 'end_intersection';
  const usesMidPoint = raceMode !== 'end_intersection';
  console.log(participants);
  for (const p of participants) {
    if (p.status === 'grace') grace++;
    else if (p.status === 'running') running++;
    else if (p.status === 'completed') completed++;
  }
  
  const registeredEl = document.getElementById('stat-registered');
  if (registeredEl) registeredEl.textContent = registered;
  // Started: treat as participants that are in grace or running
  const startedCount = grace + running;
  const startedEl = document.getElementById('stat-started');
  if (startedEl) startedEl.textContent = startedCount;

  // Mid point: count participants who have a mid_time recorded
  if (usesMidPoint) {
    const midCount = participants.reduce((acc, x) => acc + (x.mid_time ? 1 : 0), 0);
    const midEl = document.getElementById('stat-mid');
    if (midEl) midEl.textContent = midCount;
  }
  
  const completedEl = document.getElementById('stat-completed');
  if (completedEl) completedEl.textContent = completed;
}

export function updateRaceStartWSStatus(connected, status) {
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

export function showRaceStartStatusMessage(message, type = 'info') {
  const statusEl = document.getElementById('status-message');
  if (!statusEl) return;
  
  const colors = {
    'success': '#10b981',
    'error': '#ef4444',
    'info': '#0ea5e9'
  };
  
  statusEl.innerHTML = `<div style="padding: 12px; background: ${colors[type]}20; border: 1px solid ${colors[type]}; border-radius: 4px; color: ${colors[type]};">${message}</div>`;
}

// ============================================================================
// RACE START - DURATION CLOCK
// ============================================================================

export function formatDuration(milliseconds) {
  const totalSeconds = Math.floor(milliseconds / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

export function getRaceStartTimes(race) {
  const { getRaceCategoryConfig } = window.appContext;
  
  if (!race) return [];
  const config = getRaceCategoryConfig(race.race_category || 'BPET');
  const key = `${config.label.toLowerCase()}_start_time`;
  const rawTimes = race[key] || [];
  if (!Array.isArray(rawTimes)) return [];
  return rawTimes.filter(Boolean).map(t => new Date(t));
}

export function getEarliestStartTime(race) {
  const times = getRaceStartTimes(race);
  if (!times.length) return null;
  return new Date(Math.min(...times.map(t => t.getTime())));
}

export function updateDurationDisplay() {
  const { state, raceStartSelectedRaceId } = window.appContext;
  
  if (!window.appContext.raceStartSelectedRaceId || !state.races) return;
  
  const selectedRace = state.races.find(r => r.id === window.appContext.raceStartSelectedRaceId);
  if (!selectedRace) return;
  
  const durationContainer = document.getElementById('duration-container');
  const durationDisplay = document.getElementById('race-duration');
  
  if (!durationContainer || !durationDisplay) return;
  
  const earliestStart = getEarliestStartTime(selectedRace);
  // Only show duration if race has start times
  if (!earliestStart) {
    durationContainer.style.display = 'none';
    return;
  }
  
  durationContainer.style.display = 'block';
  
  const startTime = earliestStart;
  let duration;
  
  // If race is completed, use end_time - start_time (static)
  if (selectedRace.status === 'completed' && selectedRace.end_time) {
    const endTime = new Date(selectedRace.end_time);
    duration = endTime - startTime;
  } else {
    // Race is running, use current time - start_time (live)
    duration = Date.now() - startTime;
  }
  
  durationDisplay.textContent = formatDuration(duration);
}

export function startDurationClock() {
  const { state, raceStartSelectedRaceId } = window.appContext;
  
  // Clear existing interval if any
  stopDurationClock();
  
  // Only start if selected race has start times
  if (!window.appContext.raceStartSelectedRaceId || !state.races) return;
  
  const selectedRace = state.races.find(r => r.id === window.appContext.raceStartSelectedRaceId);
  if (!selectedRace || !getEarliestStartTime(selectedRace)) return;
  
  // Update immediately
  updateDurationDisplay();
  
  // Update every second for live races
  if (selectedRace.status === 'started') {
    window.appContext.durationClockInterval = setInterval(updateDurationDisplay, 1000);
  }
}

export function stopDurationClock() {
  if (window.appContext.durationClockInterval) {
    clearInterval(window.appContext.durationClockInterval);
    window.appContext.durationClockInterval = null;
  }
}

export function updateRaceDetailsDisplay() {
  const { state, raceStartSelectedRaceId, getRaceCategoryConfig } = window.appContext;
  
  if (!window.appContext.raceStartSelectedRaceId || !state.races) return;
  
  const selectedRace = state.races.find(r => r.id === window.appContext.raceStartSelectedRaceId);
  const raceInfoEl = document.getElementById('race-info');
  const raceModeLabelEl = document.getElementById('race-mode-label');
  
  if (!raceInfoEl) return;
  
  if (!selectedRace) {
    raceInfoEl.innerHTML = 'Select a race to view details';
    if (raceModeLabelEl) raceModeLabelEl.textContent = 'Select a race';
    return;
  }

  if (raceModeLabelEl) {
    raceModeLabelEl.textContent = (selectedRace.rfid_placement_mode === 'end_intersection')
      ? 'Dual End antennas (intersection, no mid check)'
      : 'Mid + End readers (reader differentiation)';
  }
  
  // Format scheduled date
  const scheduledDate = new Date(selectedRace.scheduled_date).toLocaleDateString('en-US', {
    weekday: 'short',
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });
  
  // Format start and end times if available
  let timingInfo = '';
  const categoryConfig = getRaceCategoryConfig(selectedRace.race_category || 'BPET');
  const startTimesKey = `${categoryConfig.label.toLowerCase()}_start_time`;
  const rawTimes = Array.isArray(selectedRace[startTimesKey]) ? selectedRace[startTimesKey] : [];

  if (rawTimes.length) {
    const fmt = (d) => d ? d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit'}) : 'N/A';
    const rows = categoryConfig.ageGroups.map((group, idx) => {
      const value = rawTimes[idx] ? new Date(rawTimes[idx]) : null;
      return `${group.label}: ${fmt(value)}`;
    }).join('<br>');
    timingInfo += `
      <div style="margin-top: 4px; font-size: 12px; color: #94a3b8;">
        ${rows}
      </div>
    `;
  }
  
  if (selectedRace.end_time) {
    const endTime = new Date(selectedRace.end_time).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
    timingInfo += `<div style="margin-top: 2px; font-size: 12px; color: #94a3b8;">Ended: ${endTime}</div>`;
  }
  
  raceInfoEl.innerHTML = `
    <div style="font-weight: 600; color: #e2e8f0;">${selectedRace.name}</div>
    <div style="margin-top: 4px; font-size: 12px; color: #94a3b8;">${selectedRace.distance_meters}m • ${scheduledDate} • ${selectedRace.race_category || 'BPET'}</div>
    <div style="margin-top: 2px; font-size: 12px; color: #94a3b8;">Status: <span style="color: #10b981;">${selectedRace.status}</span></div>
    ${timingInfo}
  `;
}

async function openRaceModeEditModal(race) {
  const { apiRequest, fetchRaces, render } = window.appContext;
  if (!race || race.status !== 'created') {
    showToast('Mode can be changed only before race start', 'warning');
    return;
  }

  const wrapper = document.createElement('div');
  wrapper.innerHTML = `
    <div class="dark-modal-overlay" style="display:flex;">
      <div class="dark-modal" style="max-width: 460px;">
        <div class="dark-modal-header">
          <h2 style="margin:0;">Edit RFID Mode</h2>
          <button class="dark-modal-close" data-action="close">&times;</button>
        </div>
        <div style="margin-top: 16px;">
          <label style="display:block; color:#cbd5e1; margin-bottom:8px;">Placement Mode</label>
          <select id="race-mode-select" style="width:100%; padding:10px; background:#0f172a; border:1px solid #334155; color:#e2e8f0; border-radius:6px;">
            <option value="end_intersection">Dual End antennas (intersection, no mid check)</option>
            <option value="mid_end_reader_diff">Mid + End readers (reader differentiation)</option>
          </select>
        </div>
        <div style="display:flex; justify-content:flex-end; gap:8px; margin-top:18px;">
          <button class="dark-btn-secondary" data-action="cancel">Cancel</button>
          <button class="dark-btn-primary" data-action="save">Save</button>
        </div>
      </div>
    </div>
  `;

  document.body.appendChild(wrapper);
  const overlay = wrapper.querySelector('.dark-modal-overlay');
  const select = wrapper.querySelector('#race-mode-select');
  const close = () => wrapper.remove();
  if (select) select.value = race.rfid_placement_mode || 'mid_end_reader_diff';

  wrapper.querySelector('[data-action="close"]')?.addEventListener('click', close);
  wrapper.querySelector('[data-action="cancel"]')?.addEventListener('click', close);
  overlay?.addEventListener('click', (e) => { if (e.target === overlay) close(); });

  wrapper.querySelector('[data-action="save"]')?.addEventListener('click', async () => {
    const mode = select?.value || 'mid_end_reader_diff';
    try {
      await apiRequest(`/race/${race.id}`, {
        method: 'PATCH',
        body: { rfid_placement_mode: mode },
      });
      showToast('RFID mode updated', 'success');
      close();
      await fetchRaces();
      render();
    } catch (e) {
      const codeTag = e.error_code ? ` [${e.error_code}]` : '';
      showToast(`Failed to update mode${codeTag}: ${e.message}`, 'error');
    }
  });
}

// ============================================================================
// RACE START - RACE SELECTION
// ============================================================================

export async function loadRaceStartRaces() {
  const { state, ensureAuth, apiRequest } = window.appContext;
  
  try {
    console.debug('[RaceStart] Loading races from API');
    await ensureAuth();
    const races = await apiRequest('/race');
    // keep global state in sync
    state.races = races || [];
    
    console.debug(`[RaceStart] Loaded ${races.length} races`);

    const raceSelect = document.getElementById('race-select');
    if (!raceSelect) return;

    raceSelect.innerHTML = '<option value="">Select a race...</option>';

    if (Array.isArray(races) && races.length > 0) {
      races.forEach((race) => {
        const option = document.createElement('option');
        option.value = race.id;
        option.textContent = `${race.name} - ${race.distance_meters}m - (${new Date(race.scheduled_date).toLocaleDateString()})`;
        // Only set selected if it matches the current state
        if (race.id === window.appContext.raceStartSelectedRaceId) {
            option.selected = true;
        }
        raceSelect.appendChild(option);
      });
      console.debug('[RaceStart] Updated race select dropdown');
    }
  } catch (e) {
    console.error('[RaceStart] Failed to load races:', e);
    showRaceStartStatusMessage(`Failed to load races: ${e.message}`, 'error');
  }
}

export async function handleRaceStartRaceChange(event) {
  const { state, render } = window.appContext;
  
  const newId = event.target.value;
  
  if (!newId) {
    console.debug('[RaceStart] Race deselected');
    window.appContext.raceStartSelectedRaceId = null;
    stopRaceDataPolling();
    stopDurationClock();
    render();
    return;
  }

  window.appContext.raceStartSelectedRaceId = newId;
  console.debug(`[RaceStart] Race selected: ${newId}`);
  
  // Re-render to update UI panels/buttons
  render();
  
  // Update race details display
  updateRaceDetailsDisplay();

  // Fetch a single snapshot of participants so UI can show a static list even if race not started
  try {
    console.debug('[RaceStart] Fetching initial participant snapshot after race change');
    await refreshRaceStartData();
  } catch (e) {
    console.error('[RaceStart] Failed to fetch initial race data:', e);
  }

  // Start polling now that a race is explicitly selected, but only if status is 'started'
  const sel = state.races.find(r => r.id === window.appContext.raceStartSelectedRaceId);
  if (sel && sel.status === 'started') {
    console.debug(`[RaceStart] Race "${sel.name}" is started (${sel.status}) - starting polling`);
    startRaceDataPolling();
  } else {
    console.debug(`[RaceStart] Race not in 'started' status (current: ${sel?.status}) - polling inactive`);
    stopRaceDataPolling();
    updateRaceStartWSStatus(false, 'Polling Inactive (race not started)');
  }

  // Start duration clock if race is started
  startDurationClock();
}

export async function handleRaceStartSubmit(event) {
  const { state, globalLoader, ensureAuth, apiRequest, getRaceCategoryConfig, fetchRaces, render } = window.appContext;
  const { renderRaceStartTimeModal } = window.appContext;
  
  event.preventDefault();
  
  if (!window.appContext.raceStartSelectedRaceId) {
    console.warn('[RaceStart] Submit attempted without race selection');
    showRaceStartStatusMessage('Please select a race', 'error');
    return;
  }
  
  console.debug(`[RaceStart] Starting race ${window.appContext.raceStartSelectedRaceId}`);
  
  const selectedRace = state.races.find(r => r.id === window.appContext.raceStartSelectedRaceId);
  const scheduledDateIso = selectedRace?.scheduled_date;
  const categoryConfig = getRaceCategoryConfig(selectedRace?.race_category || 'BPET');

  // Show the time picker modal
  const modalHtml = renderRaceStartTimeModal(scheduledDateIso, categoryConfig.ageGroups);
  const modalContainer = document.createElement('div');
  modalContainer.innerHTML = modalHtml;
  document.body.appendChild(modalContainer);

  // Get modal elements
  const timeInputs = Array.from(document.querySelectorAll('[data-start-time-index]'));
  const cancelBtn = document.getElementById('cancel-start-time-btn');
  const confirmBtn = document.getElementById('confirm-start-time-btn');

  // Handle cancel
  cancelBtn.addEventListener('click', () => {
    console.debug('[RaceStart] Start time modal cancelled');
    modalContainer.remove();
  });

  // Handle confirm
  confirmBtn.addEventListener('click', async () => {
    const selectedTimes = timeInputs.map(input => input.value);

    if (selectedTimes.some(value => !value)) {
      showToast('Please select all start times', 'warning');
      return;
    }

    console.debug(`[RaceStart] Start times selected: ${selectedTimes.join(', ')}`);

    // Combine date and time into ISO string without UTC date shifting.
    // Using toISOString() on a local-midnight date can move it to previous UTC date.
    const resolveDatePart = (value) => {
      if (!value) {
        const now = new Date();
        const y = now.getFullYear();
        const m = String(now.getMonth() + 1).padStart(2, '0');
        const d = String(now.getDate()).padStart(2, '0');
        return `${y}-${m}-${d}`;
      }

      // Prefer raw date portion from backend string if present.
      const raw = String(value).trim();
      const match = raw.match(/^(\d{4}-\d{2}-\d{2})/);
      if (match && match[1]) return match[1];

      const dt = new Date(raw);
      if (!Number.isNaN(dt.getTime())) {
        const y = dt.getFullYear();
        const m = String(dt.getMonth() + 1).padStart(2, '0');
        const d = String(dt.getDate()).padStart(2, '0');
        return `${y}-${m}-${d}`;
      }

      const now = new Date();
      const y = now.getFullYear();
      const m = String(now.getMonth() + 1).padStart(2, '0');
      const d = String(now.getDate()).padStart(2, '0');
      return `${y}-${m}-${d}`;
    };

    const datePart = resolveDatePart(scheduledDateIso);
    const startTimesIso = selectedTimes.map(timeValue => {
      const dateTime = new Date(`${datePart}T${timeValue}:00`);
      return dateTime.toISOString();
    });

    // Remove modal
    modalContainer.remove();

    // Show loader and send request
    try {
      await globalLoader.wrap(async () => {
        await ensureAuth();
        
        console.debug('[RaceStart] Sending start-times to API');
        // Save age-based start times
        await apiRequest(`/race/${window.appContext.raceStartSelectedRaceId}/start-times`, {
          method: 'POST',
          body: {
            start_times: startTimesIso,
          }
        });

        console.debug('[RaceStart] Sending start signal to API');
        // Activate the race
        await apiRequest(`/race/${window.appContext.raceStartSelectedRaceId}/start`, {
          method: 'POST',
          body: {
            scheduled_date: startTimesIso[0],
          }
        });
        
        // Refresh races and re-render to update button state
        console.debug('[RaceStart] Refreshing races from API');
        await fetchRaces();
      });
      
      showToast('Race started successfully', 'success');
      render();
      
      // Update race details
      updateRaceDetailsDisplay();
      
      // Start duration clock
      startDurationClock();
      
      // Refresh data to show updated times and status
      console.debug('[RaceStart] Fetching updated participant data');
      await refreshRaceStartData();

      // After starting the race on backend, ensure polling begins
      console.debug('[RaceStart] Race started - starting polling');
      startRaceDataPolling();
    } catch (e) {
      console.error('[RaceStart] Failed to start race:', e);
      const codeTag = e.error_code ? ` [${e.error_code}]` : '';
      showToast(`Failed to start race${codeTag}: ${e.message}`, 'error');
      showRaceStartStatusMessage(`Failed to start race${codeTag}: ${e.message}`, 'error');
    }
  });
}

// ============================================================================
// RACE START VIEW HANDLERS - Attach all event listeners for race-start view
// ============================================================================

export async function attachRaceStartHandlers() {
  const { state } = window.appContext;
  
  if (state.view !== 'race-start') return;

  // Populate race dropdown now that DOM exists
  await loadRaceStartRaces();
  
  // Fetch initial participant snapshot
  try {
    await refreshRaceStartData();
  } catch (e) {
    console.error('[RaceStart] Failed to fetch initial race data:', e);
  }
  
  // Determine if polling should start based on race status
  const selected = state.races.find(r => r.id === window.appContext.raceStartSelectedRaceId);
  if (selected && selected.status === 'started') {
    startRaceDataPolling();
  } else {
    stopRaceDataPolling();
    updateRaceStartWSStatus(false, 'Polling Inactive (race not started)');
  }

  // End Race button handler
  const endRaceBtn = document.getElementById('end-race-btn');
  if (endRaceBtn) {
    endRaceBtn.addEventListener('click', async () => {
      const { raceStartSelectedRaceId } = window.appContext;
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
  
  // Race select dropdown handler
  const raceSelect = document.getElementById('race-select');
  if (raceSelect) {
    raceSelect.addEventListener('change', handleRaceStartRaceChange);
  }
  
  // Start race form handler
  const startForm = document.getElementById('start-race-form');
  if (startForm) {
    startForm.addEventListener('submit', handleRaceStartSubmit);
  }

  const editModeBtn = document.getElementById('edit-race-mode-btn');
  if (editModeBtn) {
    editModeBtn.addEventListener('click', async () => {
      const { state, raceStartSelectedRaceId } = window.appContext;
      const selectedRace = state.races.find(r => r.id === raceStartSelectedRaceId);
      await openRaceModeEditModal(selectedRace);
    });
  }
}

// ============================================================================
// VIEW SETUP - Called when entering race start view from navigation
// ============================================================================

export async function setupRaceStartView() {
  console.debug('[RaceStart] setupRaceStartView() called');
  
  // Clear previous selection
  window.appContext.raceStartSelectedRaceId = null;
  
  // Just fetch races into state, dropdown will be populated after render
  const { fetchRaces } = window.appContext;
  await fetchRaces();
}
