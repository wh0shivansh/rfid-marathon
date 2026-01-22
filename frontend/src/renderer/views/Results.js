export function renderResults(races = [], participants = [], selectedRaceId = null) {
  const filteredParticipants = selectedRaceId
    ? participants.filter(p => String(p.race_id) === String(selectedRaceId))
    : participants;

  const participantListHTML = filteredParticipants.length > 0
    ? filteredParticipants.map(p => `
        <div style="padding: 14px; margin: 10px 0; background: #0f172a; border-radius: 6px; border-left: 3px solid #3b82f6; display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 10px; align-items: center;">
          <div>
            <div style="font-weight: bold; color: #9fb3e5; margin-bottom: 4px;">${p.decryptedName || p.name || (p.encrypted_name ? p.encrypted_name.substring(0, 10) + "..." : 'Unknown')}</div>
            <div style="color: #64748b; font-size: 0.85em;">RFID: ${p.rfid || p.rfid_tag}</div>
          </div>
          <div style="color: #cbd5e1; font-size: 0.9em;">
            Age: ${p.age ?? 'N/A'} • ${p.gender === 'M' ? 'Male' : p.gender === 'F' ? 'Female' : (p.gender || 'Other')}
          </div>
          <div style="color: #cbd5e1; font-size: 0.9em;">
            Category: ${p.category || 'N/A'}
          </div>
          <div style="color: #94a3b8; font-size: 0.85em; text-align: right;">
            ${p.registered_at ? new Date(p.registered_at).toLocaleString() : 'N/A'}
          </div>
        </div>
      `).join('')
    : '<p style="color: #94a3b8; text-align: center; padding: 40px;">No participants found for this race</p>';

  return `
    <div class="page" style="background:#0b1220; min-height:100vh; color:#e2e8f0; padding:16px;">
      <div class="panel" style="background:#111827; border:1px solid #1f2937; border-radius:8px;">
        <div class="panel-header" style="display: flex; justify-content: space-between; align-items: center; padding:12px 16px; border-bottom:1px solid #1f2937;">
          <div style="display: flex; align-items: center; gap: 16px; flex: 1;">
            <span style="font-weight: 600;">Participants</span>
            <select id="race-filter-dropdown" style="padding: 8px 12px; background: #0f172a; border: 2px solid #334155; border-radius: 6px; color: #e2e8f0; font-size: 0.95em; cursor: pointer; min-width: 250px;">
              <option value="">All Races</option>
              ${races.map(race => `
                <option value="${race.id}" ${String(selectedRaceId) === String(race.id) ? 'selected' : ''}>
                  ${race.name} - ${race.location} (${race.scheduled_date ? new Date(race.scheduled_date).toLocaleDateString() : ''})
                </option>
              `).join('')}
            </select>
          </div>
          <button id="register-new-candidate-btn" style="padding: 10px 20px; background: #22c55e; border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 0.95em; font-weight: 600; display: flex; align-items: center; gap: 8px; transition: background 0.2s;">
            <span style="font-size: 1.2em;">+</span> Register New Candidate
          </button>
        </div>
        
        <div style="padding: 16px;">
          <div style="margin-bottom: 16px; padding: 12px; background: #1e293b; border-radius: 6px; border-left: 4px solid #3b82f6;">
            <div style="color: #94a3b8; font-size: 0.9em;">
              Showing <strong style="color: #e2e8f0;">${filteredParticipants.length}</strong> participant${filteredParticipants.length !== 1 ? 's' : ''}
              ${selectedRaceId ? (() => {
                const race = races.find(r => String(r.id) === String(selectedRaceId));
                return race ? ` for <strong style="color: #e2e8f0;">${race.name}</strong>` : '';
              })() : ' across all races'}
            </div>
          </div>

          <div id="participants-list">
            ${participantListHTML}
          </div>
        </div>
      </div>
    </div>

    <style>
      #register-new-candidate-btn:hover {
        background: #16a34a;
      }
      #race-filter-dropdown:focus {
        outline: none;
        border-color: #3b82f6;
      }
    </style>
  `;
}
