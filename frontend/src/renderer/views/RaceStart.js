/**
 * RFID Marathon Management System - Start Race View
 * 
 * Displays admin interface to start race and monitor live RFID data.
 * Logic and event handlers are managed in app.js.
 * Data is fetched from backend API via polling (every 2 seconds).
 */

export function renderRaceStart(races = [], selectedRaceId = null) {
  // Find selected race to determine button state
  const selectedRace = races.find(r => r.id === selectedRaceId);
  const raceStatus = selectedRace?.status || 'created';
  
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
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; padding: 16px;">
          <div style="background: #1e293b; padding: 12px; border-radius: 4px;">
            <div style="color: #a78bfa; font-size: 12px; text-transform: uppercase;">Registered</div>
            <div id="stat-registered" style="color: #a78bfa; font-size: 24px; font-weight: bold;">0</div>
          </div>
          <div style="background: #1e293b; padding: 12px; border-radius: 4px;">
            <div style="color: #60a5fa; font-size: 12px; text-transform: uppercase;">Started</div>
            <div id="stat-started" style="color: #60a5fa; font-size: 24px; font-weight: bold;">0</div>
          </div>
          <div style="background: #1e293b; padding: 12px; border-radius: 4px;">
            <div style="color: #fbbf24; font-size: 12px; text-transform: uppercase;">Mid Point</div>
            <div id="stat-mid" style="color: #fbbf24; font-size: 24px; font-weight: bold;">0</div>
          </div>
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
