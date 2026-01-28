// Candidate Management View - HTML Only
// All JavaScript logic is in app.js

export function renderCandidateManagement(races = [], participants = [], selectedRaceId = null) {
  const filteredParticipants = selectedRaceId
    ? participants.filter(p => String(p.race_id) === String(selectedRaceId))
    : participants;

  return `
    <div class="page" style="background:#0b1220; min-height:100vh; color:#e2e8f0; padding:16px;">
      <!-- Header Section -->
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding: 20px; background: #111827; border-radius: 8px; border: 1px solid #1f2937;">
        <div style="display: flex; align-items: center; gap: 16px;">
          <h1 style="color: #e2e8f0; margin: 0; font-size: 24px; font-weight: 600;">Candidate Management</h1>
          <select id="candidate-race-filter-dropdown" style="padding: 10px 14px; background: #0f172a; border: 2px solid #334155; border-radius: 6px; color: #e2e8f0; font-size: 0.95em; cursor: pointer; min-width: 280px;">
            <option value="">All Races</option>
            ${races.map(race => `
              <option value="${race.id}" ${String(selectedRaceId) === String(race.id) ? 'selected' : ''}>
                ${race.name} - ${race.location} (${new Date(race.scheduled_date).toLocaleDateString()})
              </option>
            `).join('')}
          </select>
        </div>
        <button class="dark-btn-primary" id="create-new-candidate-btn" style="padding: 12px 24px; background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%); color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; display: flex; align-items: center; gap: 8px; transition: all 0.3s ease;">
          <span style="font-size: 1.2em;">+</span> Add Candidate
        </button>
      </div>

        <!-- Edit Candidate Modal (used for edits only) -->
        <div id="candidate-modal" class="dark-modal-overlay" style="display: none;">
          <div class="dark-modal" style="max-width: 700px;">
            <div class="dark-modal-header">
              <div style="display: flex; align-items: center; gap: 12px;">
                <div style="width: 42px; height: 42px; background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 20px;">👤</div>
                <h2 id="candidate-modal-title" style="margin: 0; font-size: 22px; font-weight: 700; color: #e2e8f0;">Edit Candidate</h2>
              </div>
              <button id="close-candidate-modal" class="dark-modal-close">&times;</button>
            </div>
          
            <form id="candidate-form" style="margin-top: 24px;">
              <input type="hidden" id="candidate-id" value="">
            
              <div class="dark-form-group">
                <label style="display: flex; align-items: center; gap: 6px; margin-bottom: 8px;">
                  <span style="color: #cbd5e1; font-weight: 600; font-size: 13px;">🏁 Select Race</span>
                </label>
                <select id="candidate-race-id" required style="padding: 12px 14px; font-size: 15px; border-radius: 6px; border: 2px solid #334155; cursor: pointer; transition: all 0.3s ease;">
                  <option value="">-- Choose a race --</option>
                  ${races.filter(r => r.status === 'created').map(race => `
                    <option value="${race.id}">${race.name} - ${race.location} (${new Date(race.scheduled_date).toLocaleDateString()})</option>
                  `).join('')}
                </select>
              </div>

              <div class="candidate-modal-body" style="display:flex; gap:16px; align-items:flex-start;">
                <div class="candidate-panel" style="flex:1; min-width: 260px;">
                  <div style="background: #0f172a; padding: 16px; border-radius: 8px; border: 1px solid #1e293b; margin-bottom: 0;">
                    <div style="color: #94a3b8; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px;">Personal Information</div>
                  
                    <div class="dark-form-group" style="margin-bottom: 14px;">
                      <label style="display: flex; align-items: center; gap: 6px; margin-bottom: 8px;">
                        <span style="color: #cbd5e1; font-weight: 600; font-size: 13px;">👤 Full Name</span>
                        <span style="color: #ef4444; font-weight: 700;">*</span>
                      </label>
                      <input type="text" id="candidate-name" placeholder="Enter participant's full name" required style="padding: 12px 14px; font-size: 15px; border-radius: 6px; border: 2px solid #334155; transition: all 0.3s ease; width:100%;">
                    </div>

                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                      <div class="dark-form-group" style="margin-bottom: 0;">
                        <label style="display: flex; align-items: center; gap: 6px; margin-bottom: 8px;">
                          <span style="color: #cbd5e1; font-weight: 600; font-size: 13px;">🎂 Age</span>
                          <span style="color: #ef4444; font-weight: 700;">*</span>
                        </label>
                        <input type="number" id="candidate-age" min="5" max="120" placeholder="25" required style="padding: 12px 14px; font-size: 15px; border-radius: 6px; border: 2px solid #334155; transition: all 0.3s ease; width:100%;">
                      </div>

                      <div class="dark-form-group" style="margin-bottom: 0;">
                        <label style="display: flex; align-items: center; gap: 6px; margin-bottom: 8px;">
                          <span style="color: #cbd5e1; font-weight: 600; font-size: 13px;">⚧ Gender</span>
                          <span style="color: #ef4444; font-weight: 700;">*</span>
                        </label>
                        <select id="candidate-gender" required style="padding: 12px 14px; font-size: 15px; border-radius: 6px; border: 2px solid #334155; cursor: pointer; transition: all 0.3s ease; width:100%;">
                          <option value="">Select</option>
                          <option value="M">Male</option>
                          <option value="F">Female</option>
                          <option value="O">Other</option>
                        </select>
                      </div>
                    </div>
                  </div>
                </div>

                <div class="candidate-panel" style="flex:1; min-width: 260px;">
                  <div style="background: #0f172a; padding: 16px; border-radius: 8px; border: 1px solid #1e293b;">
                    <div style="color: #94a3b8; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px;">RFID Information</div>
                  
                    <div class="dark-form-group" style="margin-bottom: 0;">
                      <label style="display: flex; align-items: center; gap: 6px; margin-bottom: 8px;">
                        <span style="color: #cbd5e1; font-weight: 600; font-size: 13px;">🏷️ RFID Tag Number</span>
                      </label>
                      <input type="text" id="candidate-rfid" placeholder="e.g., A1B2C3D4" required style="padding: 12px 14px; font-size: 15px; font-family: monospace; border-radius: 6px; border: 2px solid #334155; text-transform: uppercase; transition: all 0.3s ease; width:100%;">
                      <div style="color: #64748b; font-size: 12px; margin-top: 6px; display: flex; align-items: center; gap: 4px;">
                        <span>ℹ️</span>
                        <span>Tag must be unique for this race</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div style="display: flex; gap: 12px; justify-content: flex-end; margin-top: 32px; padding-top: 24px; border-top: 1px solid #334155;">
                <button type="button" id="cancel-candidate-form" class="dark-btn-secondary" style="padding: 12px 28px; font-size: 15px; font-weight: 600; border-radius: 6px;">Cancel</button>
                <button type="submit" class="dark-btn-primary" style="padding: 12px 28px; font-size: 15px; border-radius: 6px; display: flex; align-items: center; gap: 8px;">
                  <span>💾</span>
                  <span>Save Candidate</span>
                </button>
              </div>
            </form>
          </div>
        </div>


      <!-- Candidates Grid -->
      ${filteredParticipants.length === 0 ? `
        <div class="empty-state" style="text-align: center; padding: 60px; background: #111827; border-radius: 8px; border: 1px solid #1f2937;">
          <div style="font-size: 48px; margin-bottom: 16px; opacity: 0.3;">👥</div>
          <p style="color: #64748b; font-size: 16px;">No candidates found${selectedRaceId ? ' for this race' : ''}.</p>
          <p style="color: #64748b; font-size: 14px; margin-top: 8px;">Add a candidate to get started.</p>
        </div>
      ` : `
        <div style="margin-bottom: 16px; padding: 12px; background: #1e293b; border-radius: 6px; border-left: 4px solid #3b82f6;">
          <div style="color: #94a3b8; font-size: 0.9em;">
            Showing <strong style="color: #e2e8f0;">${filteredParticipants.length}</strong> candidate${filteredParticipants.length !== 1 ? 's' : ''}
            ${selectedRaceId ? (() => {
              const race = races.find(r => String(r.id) === String(selectedRaceId));
              return race ? ` for <strong style="color: #e2e8f0;">${race.name}</strong>` : '';
            })() : ' across all races'}
          </div>
        </div>

        <div style="display: flex; flex-direction: column; gap: 12px;">
          ${filteredParticipants.map(p => {
            const race = races.find(r => r.id === p.race_id);
            const displayName = p.decryptedName || p.name || (p.encrypted_name ? p.encrypted_name.substring(0, 10) + "..." : 'Unknown');
            const canEdit = race && race.status === 'created';
            
            return `
              <div style="background: #111827; border: 1px solid #1f2937; border-radius: 8px; padding: 16px; transition: all 0.3s ease; display: flex; align-items: center; gap: 20px;" class="candidate-card">
                <!-- Candidate Info -->
                <div style="flex: 1; display: grid; grid-template-columns: 2fr 1fr 1fr 1fr 1fr 1.5fr; gap: 16px; align-items: center;">
                  <!-- Name & Race -->
                  <div>
                    <h3 style="color: #e2e8f0; margin: 0 0 4px 0; font-size: 16px; font-weight: 600;">${displayName}</h3>
                    <div style="display: inline-block; padding: 2px 8px; background: #1e3a8a; border-radius: 3px; font-size: 10px; font-weight: 600; color: #60a5fa; text-transform: uppercase; letter-spacing: 0.5px;">
                      ${race ? race.name : 'Unknown'}
                    </div>
                  </div>
                  
                  <!-- RFID -->
                  <div>
                    <div style="color: #94a3b8; font-size: 11px; text-transform: uppercase; margin-bottom: 2px;">RFID</div>
                    <span style="color: #cbd5e1; font-size: 13px; font-family: monospace; background: #0f172a; padding: 3px 6px; border-radius: 3px;">${p.rfid || p.rfid_tag || 'N/A'}</span>
                  </div>
                  
                  <!-- Age -->
                  <div>
                    <div style="color: #94a3b8; font-size: 11px; text-transform: uppercase; margin-bottom: 2px;">Age</div>
                    <span style="color: #cbd5e1; font-size: 14px;">${p.age ?? 'N/A'}</span>
                  </div>
                  
                  <!-- Gender -->
                  <div>
                    <div style="color: #94a3b8; font-size: 11px; text-transform: uppercase; margin-bottom: 2px;">Gender</div>
                    <span style="color: #cbd5e1; font-size: 14px;">${p.gender === 'M' ? 'Male' : p.gender === 'F' ? 'Female' : (p.gender || 'Other')}</span>
                  </div>
                  
                  <!-- Category -->
                  <div>
                    <div style="color: #94a3b8; font-size: 11px; text-transform: uppercase; margin-bottom: 2px;">Category</div>
                    <span style="color: #cbd5e1; font-size: 14px;">${p.category || 'N/A'}</span>
                  </div>
                  
                  <!-- Registered -->
                  <div>
                    <div style="color: #94a3b8; font-size: 11px; text-transform: uppercase; margin-bottom: 2px;">Registered</div>
                    <span style="color: #64748b; font-size: 12px;">${p.registered_at ? new Date(p.registered_at).toLocaleDateString() : 'N/A'}</span>
                  </div>
                </div>

                <!-- Action Buttons -->
                <div style="display: flex; gap: 6px; min-width: 120px;">
                  ${canEdit ? `
                    <button class="dark-btn-edit edit-candidate-btn" data-candidate-id="${p.id}" data-race-id="${p.race_id}" title="Edit" style="padding: 8px 12px; background: #3b82f6; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: 500; transition: all 0.2s;">✏️</button>
                    <button class="dark-btn-danger delete-candidate-btn" data-candidate-id="${p.id}" data-race-id="${p.race_id}" title="Delete" style="padding: 8px 12px; background: #ef4444; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: 500; transition: all 0.2s;">🗑️</button>
                  ` : `
                    <div style="padding: 8px 12px; background: #1e293b; border-radius: 4px; color: #64748b; font-size: 11px; text-align: center;">Locked<br/>(${race ? race.status : 'N/A'})</div>
                  `}
                </div>
              </div>
            `;
          }).join('')}
        </div>
      `}
    </div>

    <style>
      .candidate-card:hover {
        border-color: #334155;
        background: #1a2332;
      }
      /* Responsive modal layout for candidate edit/create */
      .candidate-modal-body { display: flex; gap: 16px; align-items: flex-start; }
      .candidate-panel { flex: 1; min-width: 240px; }
      @media (max-width: 720px) {
        .candidate-modal-body { flex-direction: column; }
        .candidate-panel { min-width: 0; }
      }
      .dark-btn-edit:hover {
        background: #2563eb;
        transform: scale(1.05);
      }
      .dark-btn-danger:hover {
        background: #dc2626;
        transform: scale(1.05);
      }
      #create-new-candidate-btn:hover {
        box-shadow: 0 4px 15px rgba(34, 197, 94, 0.4);
        transform: translateY(-1px);
      }
      #candidate-race-filter-dropdown:focus {
        outline: none;
        border-color: #3b82f6;
      }
    </style>
  `;
}
