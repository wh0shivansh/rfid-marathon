/**
 * RFID Marathon Management System - Race Group Start View
 * 
 * Displays admin interface to start race groups and monitor live RFID data.
 * Logic and event handlers are managed in app.js.
 * Data is fetched from backend API via polling (every 2 seconds).
 */

export function renderRaceGroupStart() {
  return `
    <div class="page">
      <!-- Control Panel -->
      <!-- Statistics Panel -->
      <div class="panel" style="margin-top: 24px;">
        <div class="panel-header">Race Statistics</div>
        <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; padding: 16px;">
          <div style="background: #1e293b; padding: 12px; border-radius: 4px;">
            <div style="color: #a78bfa; font-size: 12px; text-transform: uppercase;">Registered</div>
            <div id="stat-registered" style="color: #a78bfa; font-size: 24px; font-weight: bold;">0</div>
          </div>
          <div style="background: #1e293b; padding: 12px; border-radius: 4px;">
            <div style="color: #60a5fa; font-size: 12px; text-transform: uppercase;">Grace</div>
            <div id="stat-grace" style="color: #60a5fa; font-size: 24px; font-weight: bold;">0</div>
          </div>
          <div style="background: #1e293b; padding: 12px; border-radius: 4px;">
            <div style="color: #fbbf24; font-size: 12px; text-transform: uppercase;">Running</div>
            <div id="stat-running" style="color: #fbbf24; font-size: 24px; font-weight: bold;">0</div>
          </div>
          <div style="background: #1e293b; padding: 12px; border-radius: 4px;">
            <div style="color: #34d399; font-size: 12px; text-transform: uppercase;">Completed</div>
            <div id="stat-completed" style="color: #34d399; font-size: 24px; font-weight: bold;">0</div>
          </div>
        </div>
      </div>
      <div class="panel">
        <div class="panel-header">Start Race</div>
        
        
        <form id="start-group-form" class="form-grid">
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
                <div style="color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Polling Status</div>
                <div id="ws-status" style="color: #ef4444; font-size: 14px;">⚪ Inactive</div>
              </div>
            </div>
          </div>
          
          <!-- Action Buttons -->
          <div class="form-actions" style="grid-column: 1 / -1; display: flex; gap: 8px;">
            <button type="submit" id="start-group-btn" style="flex: 1; background: #10b981;">
              Start Race
            </button>
            <button type="button" id="refresh-btn" style="flex: 1; background: #0ea5e9;">
              Refresh
            </button>
          </div>
        </form>
      </div>
      
      <!-- Live Candidates Panel -->
      <div class="panel" style="margin-top: 24px;">
        <div class="panel-header">Live Candidates (Real-time Updates)</div>
        <div id="groups-container" style="display: flex; flex-direction: column; gap: 16px;">
          <div style="background: #0f172a; border: 1px solid #334155; border-radius: 4px; padding: 12px; color: #cbd5e1; font-size: 12px;">
            <p style="color: #64748b; margin: 0;">Waiting for race data...</p>
          </div>
        </div>
      </div>
    </div>
  `;
}
