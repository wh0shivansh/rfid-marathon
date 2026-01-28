export function renderRegistration(currentStep, scannedRFID, availableRaces, selectedRace, todayRegistrations = []) {
  // Filter only races with status 'created'
  const createdRaces = availableRaces.filter(r => r.status === 'created');
  
  const registrationListHTML = todayRegistrations.length > 0 
    ? todayRegistrations.map(reg => `
        <div style="padding: 12px; margin: 8px 0; background: #0f172a; border-radius: 4px; border-left: 3px solid #22c55e;">
          <div style="font-weight: bold; color: #9fb3e5;">${reg.name}</div>
          <div style="color: #cbd5e1; font-size: 0.9em; margin-top: 4px;">
            ${reg.raceName} • RFID: ${reg.rfid} • Age: ${reg.age} • Category: ${reg.category} • Gender: ${reg.gender} • ${reg.timestamp}
          </div>
        </div>
      `).join('')
    : '<p style="color: #94a3b8; text-align: center; padding: 20px;">No registrations yet</p>';
  
  return `
    <div class="page" style="background:#0b1220; min-height:100vh; color:#e2e8f0; padding:16px;">
      <!-- Step 1: Race Selection -->
      <div id="step-1-panel" style="display: ${currentStep === 1 ? 'block' : 'none'};">
        <div class="panel" style="background:#111827; border:1px solid #1f2937; border-radius:8px; color:#e2e8f0;">
          <div class="panel-header" style="display: flex; justify-content: space-between; align-items: center; padding:12px 16px; border-bottom:1px solid #1f2937;">
            <span>Step 1: Select Race</span>
            <button id="close-step-1" style="background: none; border: none; color: #94a3b8; cursor: pointer; font-size: 1.5em; padding: 0; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; transition: color 0.2s;">×</button>
          </div>
          <div style="padding: 16px;">
            ${createdRaces.length > 0 ? `
              <label style="display: block; color: #cbd5e1; margin-bottom: 8px; font-weight: 500;">Choose a race:</label>
              <select id="race-select-dropdown" style="width: 100%; padding: 12px; background: #0f172a; border: 2px solid #334155; border-radius: 6px; color: #e2e8f0; font-size: 1em; cursor: pointer;">
                <option value="">-- Select a race --</option>
                ${createdRaces.map(race => `
                  <option value="${race.id}" ${selectedRace === race.id ? 'selected' : ''}>${race.name} - ${race.distance_meters}m - ${race.location} (${new Date(race.scheduled_date).toLocaleDateString()})</option>
                `).join('')}
              </select>
              <button id="continue-step1" style="margin-top: 16px; width: 100%; padding: 12px 16px; background: #3b82f6; border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 1em; font-weight: 600;">Continue to RFID Scan →</button>
            ` : '<p style="color: #cbd5e1; text-align: center; padding: 20px;">No races available for registration. All races are either active or completed.</p>'}
          </div>
        </div>
      </div>

      <!-- Step 2: RFID Scan -->
      <div id="step-2-panel" style="display: ${currentStep === 2 ? 'block' : 'none'};">
        <div class="panel" style="background:#111827; border:1px solid #1f2937; border-radius:8px; color:#e2e8f0;">
          <div class="panel-header" style="display: flex; justify-content: space-between; align-items: center; padding:12px 16px; border-bottom:1px solid #1f2937;">
            <span>Step 2: Scan RFID</span>
            <button id="close-step-2" style="background: none; border: none; color: #94a3b8; cursor: pointer; font-size: 1.5em; padding: 0; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; transition: color 0.2s;">×</button>
          </div>
          <div style="padding: 40px; text-align: center;">
            <div style="font-size: 3em; margin-bottom: 20px;">📡</div>
            <h3 style="color: #e2e8f0; margin-bottom: 10px;">Waiting for RFID Scan</h3>
            <p style="color: #94a3b8; margin-bottom: 30px;">Please scan the participant's RFID tag</p>
            <div id="rfid-display" style="padding: 20px; background: #0f172a; border-radius: 6px; border: 2px dashed #3b82f6; font-family: monospace; font-size: 1.2em; color: #3b82f6; min-height: 60px; display: flex; align-items: center; justify-content: center;">
              ${scannedRFID || 'No RFID detected'}
            </div>
            <div style="margin-top: 30px; display: flex; gap: 10px; justify-content: center;">
              <button id="back-to-step-1" style="padding: 12px 24px; background: #475569; border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 1em;">← Back</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 3: Participant Details -->
      <div id="step-3-panel" style="display: ${currentStep === 3 ? 'block' : 'none'};">
        <div class="panel" style="background:#111827; border:1px solid #1f2937; border-radius:8px; color:#e2e8f0;">
          <div class="panel-header" style="display: flex; justify-content: space-between; align-items: center; padding:12px 16px; border-bottom:1px solid #1f2937;">
            <span>Step 3: Participant Details</span>
            <button id="close-step-3" style="background: none; border: none; color: #94a3b8; cursor: pointer; font-size: 1.5em; padding: 0; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; transition: color 0.2s;">×</button>
          </div>
          <form id="registration-form" class="form-grid" style="padding: 20px;">
            <div style="grid-column: 1 / -1; padding: 16px; background: #1e293b; border-radius: 6px; border-left: 4px solid #3b82f6; margin-bottom: 20px;">
              <div style="font-size: 0.85em; color: #94a3b8; margin-bottom: 4px;">SELECTED RACE</div>
              <div id="race-info-step3" style="font-size: 1.05em; font-weight: 600; color: #e2e8f0;">${selectedRace ? (() => {
                const race = createdRaces.find(r => r.id === selectedRace);
                return race ? `${race.name} - ${race.location} (${new Date(race.scheduled_date).toLocaleDateString()}) - ${race.distance_meters}m` : 'Unknown Race';
              })() : ''}</div>
            </div>
            
            <label>RFID Tag<input id="rfid" name="rfid" value="${scannedRFID || ''}" readonly style="background: #1e293b; color:#e2e8f0; cursor: not-allowed;" /></label>
            <label>Full Name<input id="name" name="name" required style="background:#1e293b; color:#e2e8f0; border:1px solid #334155;" /></label>
            <label>Age<input id="age" name="age" type="number" min="5" max="120" required style="background:#1e293b; color:#e2e8f0; border:1px solid #334155;" /></label>
            <label>Gender
              <select id="gender" name="gender" required style="background:#1e293b; color:#e2e8f0; border:1px solid #334155;">
                <option value="" disabled>-- Select gender --</option>
                <option value="M" selected>Male</option>
                <option value="F">Female</option>
                <option value="O">Other</option>
              </select>
            </label>
            <div class="form-actions" style="grid-column: 1 / -1; display: flex; gap: 10px; justify-content: flex-end;">
              <button type="button" id="back-to-step-2" style="padding: 12px 24px; background: #475569; border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 1em;">← Back</button>
              <button type="submit" style="padding: 12px 24px; background: #22c55e; border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 1em; font-weight: 600;">Submit</button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <style>
      .race-item {
        padding: 14px;
        margin: 10px 0;
        background: #0f172a;
        border-radius: 6px;
        cursor: pointer;
        transition: all 0.2s;
        border-left: 3px solid transparent;
        color:#e2e8f0;
      }
      .race-item:hover {
        background: #1e3a5f;
        border-left-color: #3b82f6;
        transform: translateX(4px);
      }
      #close-step-1:hover, #close-step-2:hover, #close-step-3:hover {
        color: #ef4444;
      }
    </style>
  `;
}
