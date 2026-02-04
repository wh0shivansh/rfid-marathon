// Races Management View - HTML Only
// All JavaScript logic is in app.js

export function renderRacesManagement(races = []) {
  return `
    <div class="page" style="background:#0b1220; min-height:100vh; color:#e2e8f0; padding:16px;">
      <!-- Header Section -->
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding: 20px; background: #111827; border-radius: 8px; border: 1px solid #1f2937;">
        <h1 style="color: #e2e8f0; margin: 0; font-size: 24px; font-weight: 600;">Races Management</h1>
        <button class="dark-btn-primary" id="create-new-race-btn" style="padding: 12px 24px; background: linear-gradient(135deg, #00d4ff 0%, #0099ff 100%); color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; display: flex; align-items: center; gap: 8px; transition: all 0.3s ease;"><span style="font-size: 1.2em;">+</span> Create New Race</button>
      </div>

      <!-- Create/Edit Race Modal -->
      <div id="race-modal" class="dark-modal-overlay" style="display: none;">
        <div class="dark-modal" style="max-width: 650px;">
          <div class="dark-modal-header">
            <div style="display: flex; align-items: center; gap: 12px;">
              <div style="width: 42px; height: 42px; background: linear-gradient(135deg, #00d4ff 0%, #0099ff 100%); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 20px;">🏁</div>
              <h2 id="modal-title" style="margin: 0; font-size: 22px; font-weight: 700; color: #e2e8f0;">Create New Race</h2>
            </div>
            <button id="close-race-modal" class="dark-modal-close">&times;</button>
          </div>
          
          <form id="race-form" style="margin-top: 24px;">
            <input type="hidden" id="race-id" value="">

            <div class="race-modal-body" style="display:flex; gap:16px; align-items:flex-start;">
              <div class="race-panel" style="flex:1; min-width:260px;">
                <div class="dark-form-group">
                  <label style="display: flex; align-items: center; gap: 6px; margin-bottom: 8px;">
                    <span style="color: #cbd5e1; font-weight: 600; font-size: 13px;">🏆 Race Name</span>
                    <span style="color: #ef4444; font-weight: 700;">*</span>
                  </label>
                  <input type="text" id="race-name" placeholder="e.g., City Marathon 2026" required style="padding: 12px 14px; font-size: 15px; border-radius: 6px; border: 2px solid #334155; transition: all 0.3s ease; width:100%;">
                </div>

                <div class="dark-form-group">
                  <label style="display: flex; align-items: center; gap: 6px; margin-bottom: 8px;">
                    <span style="color: #cbd5e1; font-weight: 600; font-size: 13px;">📝 Description</span>
                    <span style="color: #64748b; font-size: 12px; font-weight: 400;">(optional)</span>
                  </label>
                  <textarea id="race-description" rows="6" placeholder="Add any additional details about this race..." style="padding: 12px 14px; font-size: 14px; border-radius: 6px; border: 2px solid #334155; resize: vertical; min-height: 120px; line-height: 1.5; transition: all 0.3s ease; width:100%;"></textarea>
                </div>
              </div>

              <div class="race-panel" style="flex:1; min-width:260px;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 12px;">
                  <div class="dark-form-group">
                    <label style="display: flex; align-items: center; gap: 6px; margin-bottom: 8px;">
                      <span style="color: #cbd5e1; font-weight: 600; font-size: 13px;">📏 Distance (m)</span>
                      <span style="color: #ef4444; font-weight: 700;">*</span>
                    </label>
                    <input type="number" id="race-distance" placeholder="5000" required style="padding: 12px 14px; font-size: 15px; border-radius: 6px; border: 2px solid #334155; transition: all 0.3s ease; width:100%;">
                  </div>

                  <div class="dark-form-group">
                    <label style="display: flex; align-items: center; gap: 6px; margin-bottom: 8px;">
                      <span style="color: #cbd5e1; font-weight: 600; font-size: 13px;">📅 Scheduled Date</span>
                      <span style="color: #ef4444; font-weight: 700;">*</span>
                    </label>
                    <input type="date" id="race-scheduled-date" required style="padding: 12px 14px; font-size: 15px; border-radius: 6px; border: 2px solid #334155; transition: all 0.3s ease; width:100%;">
                  </div>
                </div>

                <div class="dark-form-group">
                  <label style="display: flex; align-items: center; gap: 6px; margin-bottom: 8px;">
                    <span style="color: #cbd5e1; font-weight: 600; font-size: 13px;">📍 Location</span>
                    <span style="color: #ef4444; font-weight: 700;">*</span>
                  </label>
                  <input type="text" id="race-location" placeholder="e.g., Central Park, New York" required style="padding: 12px 14px; font-size: 15px; border-radius: 6px; border: 2px solid #334155; transition: all 0.3s ease; width:100%;">
                </div>
              </div>
            </div>

            <div style="display: flex; gap: 12px; justify-content: flex-end; margin-top: 24px; padding-top: 16px; border-top: 1px solid #334155;">
              <button type="button" id="cancel-race-form" class="dark-btn-secondary" style="padding: 12px 28px; font-size: 15px; font-weight: 600; border-radius: 6px;">Cancel</button>
              <button type="submit" class="dark-btn-primary" style="padding: 12px 28px; font-size: 15px; border-radius: 6px; display: flex; align-items: center; gap: 8px;">
                <span>💾</span>
                <span>Save Race</span>
              </button>
            </div>
          </form>
        </div>
      </div>

      <!-- Races Cards Grid -->
      ${races.length === 0 ? `
        <div class="empty-state" style="text-align: center; padding: 60px; background: #111827; border-radius: 8px; border: 1px solid #1f2937;">
          <div style="font-size: 48px; margin-bottom: 16px; opacity: 0.3;">📋</div>
          <p style="color: #64748b; font-size: 16px;">No races found. Create your first race to get started.</p>
        </div>
      ` : `
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 20px;">
          ${races.map(race => `
            <div style="background: #111827; border: 1px solid #1f2937; border-radius: 8px; padding: 20px; transition: all 0.3s ease; position: relative; overflow: hidden;" class="race-card">
              <!-- Status Badge -->
              <div style="position: absolute; top: 12px; right: 12px;">
                <span class="status-badge ${
                  race.status === 'active' ? 'status-badge-active' : 
                  race.status === 'completed' ? 'status-badge-completed' : 
                  'status-badge-created'
                }" style="padding: 6px 12px; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">
                  ${race.status || 'created'}
                </span>
              </div>

              <!-- Race Name -->
              <h3 style="color: #e2e8f0; margin: 0 0 16px 0; font-size: 20px; font-weight: 600; padding-right: 80px;">${race.name}</h3>
              
              <!-- Race Details -->
              <div style="display: flex; flex-direction: column; gap: 12px; margin-bottom: 20px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                  <span style="color: #94a3b8; font-size: 14px;">📏</span>
                  <span style="color: #cbd5e1; font-size: 14px;">${race.distance_meters}m</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                  <span style="color: #94a3b8; font-size: 14px;">📍</span>
                  <span style="color: #cbd5e1; font-size: 14px;">${race.location}</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                  <span style="color: #94a3b8; font-size: 14px;">📅</span>
                  <span style="color: #cbd5e1; font-size: 14px;">${new Date(race.scheduled_date).toLocaleDateString('en-US', { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' })}</span>
                </div>
                ${race.description ? `
                  <div style="margin-top: 8px; padding: 10px; background: #0f172a; border-radius: 4px; border-left: 3px solid #334155;">
                    <p style="color: #94a3b8; font-size: 13px; margin: 0; line-height: 1.5;">${race.description}</p>
                  </div>
                ` : ''}
              </div>

              <!-- Action Buttons -->
              <div style="display: flex; gap: 8px; margin-top: 20px; padding-top: 20px; border-top: 1px solid #1f2937;">
                <button class="dark-btn-edit edit-race-btn" data-race-id="${race.id}" style="flex: 1; padding: 10px; background: #3b82f6; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; font-weight: 500; transition: all 0.2s;">Edit</button>
                
                ${false && race.status !== 'completed' ? `
                <!-- Toggle Active/Created Button -->
                <button class="dark-btn-secondary toggle-active-btn" data-race-id="${race.id}" style="flex: 1; padding: 10px; background: ${race.status === 'active' ? '#f97316' : '#10b981'}; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; font-weight: 500; transition: all 0.2s;">
                  ${race.status === 'active' ? 'Deactivate' : 'Activate'}
                </button>
                ` : ``}
                
                <button class="dark-btn-danger delete-race-btn" data-race-id="${race.id}" ${race.status === 'active' ? 'disabled' : ''} style="flex: 1; padding: 10px; background: ${race.status === 'active' ? '#6b7280' : '#ef4444'}; color: white; border: none; border-radius: 4px; cursor: ${race.status === 'active' ? 'not-allowed' : 'pointer'}; font-size: 14px; font-weight: 500; transition: all 0.2s; opacity: ${race.status === 'active' ? '0.5' : '1'};">Delete</button>
              </div>
            </div>
          `).join('')}
        </div>
      `}
    </div>

    <style>
      .race-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 16px rgba(0, 212, 255, 0.1);
        border-color: #334155;
      }
      .dark-btn-edit:hover {
        background: #2563eb;
      }
      .dark-btn-danger:hover:not(:disabled) {
        background: #dc2626;
      }
      .dark-btn-primary:hover {
        box-shadow: 0 4px 15px rgba(0, 212, 255, 0.4);
        transform: translateY(-1px);
      }
      /* Responsive layout for race modal */
      .race-modal-body { display:flex; gap:16px; align-items:flex-start; }
      .race-panel { flex:1; min-width:240px; }
      @media (max-width:720px) {
        .race-modal-body { flex-direction: column; }
        .race-panel { min-width: 0; }
      }
    </style>
  `;
}
