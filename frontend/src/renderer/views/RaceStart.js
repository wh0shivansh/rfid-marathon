/**
 * RFID Marathon Management System - Start Race View
 * 
 * Displays admin interface to start race and monitor live RFID data.
 * Logic and event handlers are managed in app.js.
 * Data is fetched from backend API via polling (every 2 seconds).
 */

// Global variable to store selected race start time before confirmation
let raceStartTimeSelection = null;

export function renderRaceStart(races = [], selectedRaceId = null) {
  // Find selected race to determine button state
  const selectedRace = races.find(r => r.id === selectedRaceId);
  const raceStatus = selectedRace?.status || 'created';
  const raceMode = selectedRace?.rfid_placement_mode || 'end_intersection';
  const usesMidPoint = raceMode !== 'end_intersection';
  const canEditMode = raceStatus === 'created';
  const modeLabel = raceMode === 'end_intersection'
    ? 'Dual End antennas (intersection, no mid check)'
    : 'Mid + End readers (reader differentiation)';
  
  // Determine button text and state
  let buttonText = 'Start Race';
  let buttonDisabled = false;
  let buttonColor = '#10b981';
  
  // Determine End Race button color
  let endRaceButtonColor = '#ef4444';  // Red when enabled
  
  if (raceStatus === 'started') {
    buttonText = 'Started';
    buttonDisabled = true;
    buttonColor = '#6b7280';
  } else if (raceStatus === 'completed') {
    buttonText = 'Completed';
    buttonDisabled = true;
    buttonColor = '#6b7280';
    endRaceButtonColor = '#6b7280';  // Gray when completed
  } else if (raceStatus === 'completed') {
    buttonText = 'Completed';
    buttonDisabled = true;
    buttonColor = '#6b7280';
    endRaceButtonColor = '#6b7280';  // Gray when completed
  }
  
  // End Race button is disabled if not in an active state that allows completion
  const endRaceDisabled = !['created', 'active', 'started'].includes(raceStatus);
  if (endRaceDisabled) {
    endRaceButtonColor = '#6b7280';  // Gray when disabled
  }
  
  return `
    <div class="page">
      <!-- Control Panel -->
      ${selectedRaceId ? `
      <div class="panel" style="margin-top: 24px;">
        <div class="panel-header">Race Statistics</div>
        <div style="display: grid; grid-template-columns: repeat(${usesMidPoint ? 3 : 2}, 1fr); gap: 16px; padding: 16px;">
          <div style="background: #1e293b; padding: 12px; border-radius: 4px;">
            <div style="color: #a78bfa; font-size: 12px; text-transform: uppercase;">Registered</div>
            <div id="stat-registered" style="color: #a78bfa; font-size: 24px; font-weight: bold;">0</div>
          </div>
          ${usesMidPoint ? `
          <div style="background: #1e293b; padding: 12px; border-radius: 4px;">
            <div id="stat-mid-label" style="color: #fbbf24; font-size: 12px; text-transform: uppercase;">Mid Point</div>
            <div id="stat-mid" style="color: #fbbf24; font-size: 24px; font-weight: bold;">0</div>
          </div>
          ` : ``}
          <div style="background: #1e293b; padding: 12px; border-radius: 4px;">
            <div style="color: #34d399; font-size: 12px; text-transform: uppercase;">Completed</div>
            <div id="stat-completed" style="color: #34d399; font-size: 24px; font-weight: bold;">0</div>
          </div>
        </div>
      </div>
      ` : ''}
      <div class="panel">
        <div class="panel-header">Start Race</div>
        
        
        <form id="start-race-form" class="form-grid">
          <!-- Race Selection -->
          <label for="race-select">
            Race *
            <select id="race-select" name="race_id" required style="width: 100%; margin-top: 4px; padding: 12px; background: #0f172a; border: 2px solid #334155; border-radius: 6px; color: #e2e8f0; font-size: 1em; cursor: pointer;">
              <option value="">Loading races...</option>
            </select>
          </label>
          
          <!-- Race Info Display -->
          <div style="grid-column: 1 / -1; padding: 12px; background: #0f172a; border: 1px solid #334155; border-radius: 4px; margin: 12px 0;">
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px;">
              <div>
                <div style="color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Race Details</div>
                <div id="race-info" style="color: #cbd5e1; font-size: 14px;">Select a race to view details</div>
              </div>
              <div>
                <div style="color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">RFID Mode</div>
                <div style="display: flex; align-items: center; gap: 8px; color: #cbd5e1; font-size: 14px;">
                  <span id="race-mode-label">${selectedRaceId ? modeLabel : 'Select a race'}</span>
                  ${selectedRaceId ? `<button type="button" id="edit-race-mode-btn" title="Edit mode" ${canEditMode ? '' : 'disabled'} style="border: 1px solid #334155; background: #1e293b; color: ${canEditMode ? '#93c5fd' : '#64748b'}; border-radius: 4px; width: 28px; height: 28px; cursor: ${canEditMode ? 'pointer' : 'not-allowed'};">✎</button>` : ''}
                </div>
                ${selectedRaceId && !canEditMode ? '<div style="margin-top: 4px; color: #64748b; font-size: 12px;">Mode editing is disabled after race start.</div>' : ''}
              </div>
              <div id="duration-container" style="display: none;">
                <div style="color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Duration</div>
                <div id="race-duration" style="color: #10b981; font-size: 20px; font-weight: bold;">00:00:00</div>
              </div>
            </div>
          </div>
          
          <!-- Action Buttons -->
          ${selectedRaceId ? `
          <div class="form-actions" style="grid-column: 1 / -1; display: flex; gap: 8px;">
            <button type="submit" id="start-race-btn" style="flex: 1; background: ${buttonColor};" ${buttonDisabled ? 'disabled' : ''}>
              ${buttonText}
            </button>
            ${raceStatus !== 'completed' ? `
            <button type="button" id="end-race-btn" style="flex: 1; background: ${endRaceButtonColor};" ${endRaceDisabled ? 'disabled' : ''}>
              End Race
            </button>
            ` : ''}
            <button type="button" id="refresh-btn" style="flex: 1; background: #0ea5e9;">
              Refresh
            </button>
          </div>
          ` : ``}
        </form>
      </div>
      
      <!-- Live Candidates Panel -->
      ${selectedRaceId ? `
      <div class="panel" style="margin-top: 24px;">
        <div class="panel-header">Live Candidates (Real-time Updates)</div>
        <div id="groups-container" style="display: flex; flex-direction: column; gap: 16px;">
          <div style="background: #0f172a; border: 1px solid #334155; border-radius: 4px; padding: 12px; color: #cbd5e1; font-size: 12px;">
            <p style="color: #64748b; margin: 0;">Waiting for race data...</p>
          </div>
        </div>
      </div>
      ` : ''}
    </div>
  `;
}

/**
 * Modal dialog for selecting race start time
 */
export function renderRaceStartTimeModal(scheduledDateIso, ageGroups = []) {
  // Set default time to now, but formatted nicely for the input
  const now = new Date();
  const timeStr = now.toTimeString().split(' ')[0].substring(0, 5); // HH:MM
  const scheduledDate = scheduledDateIso ? new Date(scheduledDateIso) : now;
  const dateDisplay = scheduledDate.toLocaleDateString('en-US', {
    weekday: 'short',
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });

  return `
    <div id="race-start-time-modal" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); display: flex; align-items: center; justify-content: center; z-index: 10000;">
      <div style="background: #0f172a; border: 2px solid #334155; border-radius: 8px; padding: 24px; max-width: 90vw; max-height: 90vh; overflow-y: auto; box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
        <h2 style="color: #e2e8f0; margin: 0 0 16px 0; font-size: 18px;">Select Age Group Start Times</h2>
        <p style="color: #a78bfa; font-size: 12px; margin: 0 0 8px 0;">Set start times for each age category.</p>
        <div style="color: #cbd5e1; font-size: 12px; margin: 0 0 16px 0;">Date: ${dateDisplay}</div>

        <div style="display: grid; grid-template-columns: repeat(${ageGroups.length}, 1fr); gap: 12px; margin-bottom: 20px; min-width: min-content;">
          ${ageGroups.map((group, index) => `
            <div>
              <label for="race-start-time-${index}" style="color: #cbd5e1; font-size: 12px; display: block; margin-bottom: 4px; text-align: center;">${group.label}</label>
              <input 
                type="time" 
                id="race-start-time-${index}" 
                data-start-time-index="${index}"
                value="${timeStr}"
                style="width: 100%; padding: 12px; background: #1e293b; border: 2px solid #334155; border-radius: 4px; color: #e2e8f0; font-size: 14px; box-sizing: border-box;"
              />
            </div>
          `).join('')}
        </div>

        <div style="display: flex; gap: 8px; justify-content: flex-end;">
          <button id="cancel-start-time-btn" style="padding: 12px 20px; background: #6b7280; border: none; border-radius: 4px; color: white; cursor: pointer; font-size: 14px; font-weight: 500;">Cancel</button>
          <button id="confirm-start-time-btn" style="padding: 12px 20px; background: #10b981; border: none; border-radius: 4px; color: white; cursor: pointer; font-size: 14px; font-weight: 500;">Confirm</button>
        </div>
      </div>
    </div>
  `;
}
