// Scoreboard View - HTML Only
// All JavaScript logic is in app.js
// Shows only COMPLETED races with participant time calculations

export function renderScoreboard(races = [], participants = [], selectedRaceId = null) {
  // Filter only completed races
  const completedRaces = races.filter(r => r.status === 'completed');
  
  // Filter participants for selected race
  const filteredParticipants = selectedRaceId
    ? participants.filter(p => String(p.race_id) === String(selectedRaceId))
    : [];

  // Calculate duration for each participant and sort by fastest time
  const participantsWithDuration = filteredParticipants
    .map(p => {
      const startTime = p.start_time ? new Date(p.start_time) : null;
      const endTime = p.end_time ? new Date(p.end_time) : null;
      
      let duration = null;
      let durationMs = null;
      let formattedDuration = 'N/A';
      
      if (startTime && endTime) {
        durationMs = endTime - startTime;
        const hours = Math.floor(durationMs / 3600000);
        const minutes = Math.floor((durationMs % 3600000) / 60000);
        const seconds = Math.floor((durationMs % 60000) / 1000);
        const milliseconds = durationMs % 1000;
        
        if (hours > 0) {
          formattedDuration = `${hours}h ${minutes}m ${seconds}s`;
        } else if (minutes > 0) {
          formattedDuration = `${minutes}m ${seconds}s`;
        } else {
          formattedDuration = `${seconds}.${String(milliseconds).padStart(3, '0')}s`;
        }
      }
      
      return {
        ...p,
        durationMs,
        formattedDuration,
        startTime,
        endTime
      };
    })
    .sort((a, b) => {
      // Sort by duration (fastest first), nulls at the end
      if (a.durationMs === null) return 1;
      if (b.durationMs === null) return -1;
      return a.durationMs - b.durationMs;
    });

  return `
    <div class="page" style="background:#0b1220; min-height:100vh; color:#e2e8f0; padding:16px;">
      <!-- Header Section -->
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding: 20px; background: #111827; border-radius: 8px; border: 1px solid #1f2937;">
        <div style="display: flex; align-items: center; gap: 16px;">
          <h1 style="color: #e2e8f0; margin: 0; font-size: 24px; font-weight: 600;">🏆 Scoreboard</h1>
          <select id="scoreboard-race-filter-dropdown" style="padding: 10px 14px; background: #0f172a; border: 2px solid #334155; border-radius: 6px; color: #e2e8f0; font-size: 0.95em; cursor: pointer; min-width: 300px;">
            <option value="">-- Select a completed race --</option>
            ${completedRaces.map(race => `
              <option value="${race.id}" ${String(selectedRaceId) === String(race.id) ? 'selected' : ''}>
                ${race.name} - ${race.location} (${new Date(race.scheduled_date).toLocaleDateString()})
              </option>
            `).join('')}
          </select>
        </div>
        ${selectedRaceId ? `
          <button id="export-scoreboard-btn" style="padding: 12px 24px; background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%); color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; display: flex; align-items: center; gap: 8px; transition: all 0.3s ease;">
            📊 Export Results
          </button>
        ` : ''}
      </div>

      ${!selectedRaceId ? `
        <div class="empty-state" style="text-align: center; padding: 60px; background: #111827; border-radius: 8px; border: 1px solid #1f2937;">
          <div style="font-size: 48px; margin-bottom: 16px; opacity: 0.3;">🏁</div>
          <p style="color: #64748b; font-size: 16px;">Select a completed race to view the scoreboard.</p>
          ${completedRaces.length === 0 ? `
            <p style="color: #64748b; font-size: 14px; margin-top: 8px;">No completed races available yet.</p>
          ` : ''}
        </div>
      ` : participantsWithDuration.length === 0 ? `
        <div class="empty-state" style="text-align: center; padding: 60px; background: #111827; border-radius: 8px; border: 1px solid #1f2937;">
          <div style="font-size: 48px; margin-bottom: 16px; opacity: 0.3;">👥</div>
          <p style="color: #64748b; font-size: 16px;">No participants found for this race.</p>
        </div>
      ` : `
        <!-- Race Summary Card -->
        <div style="margin-bottom: 24px; padding: 24px; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-radius: 8px; border: 1px solid #334155;">
          <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px;">
            <div style="text-align: center;">
              <div style="color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Total Participants</div>
              <div style="color: #e2e8f0; font-size: 32px; font-weight: 700;">${participantsWithDuration.length}</div>
            </div>
            <div style="text-align: center;">
              <div style="color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Finished</div>
              <div style="color: #22c55e; font-size: 32px; font-weight: 700;">${participantsWithDuration.filter(p => p.durationMs !== null).length}</div>
            </div>
            <div style="text-align: center;">
              <div style="color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Fastest Time</div>
              <div style="color: #fbbf24; font-size: 32px; font-weight: 700;">${participantsWithDuration.find(p => p.durationMs !== null)?.formattedDuration || 'N/A'}</div>
            </div>
            <div style="text-align: center;">
              <div style="color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Race</div>
              <div style="color: #e2e8f0; font-size: 18px; font-weight: 600;">${(() => {
                const race = races.find(r => String(r.id) === String(selectedRaceId));
                return race ? `${race.distance_meters}m` : 'N/A';
              })()}</div>
            </div>
          </div>
        </div>

        <!-- Scoreboard Table -->
        <div style="background: #111827; border: 1px solid #1f2937; border-radius: 8px; overflow: hidden;">
          <div style="padding: 16px 20px; background: #0f172a; border-bottom: 1px solid #1f2937;">
            <h2 style="margin: 0; color: #e2e8f0; font-size: 18px; font-weight: 600;">Race Results</h2>
          </div>
          
          <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse;">
              <thead>
                <tr style="background: #1e293b; border-bottom: 2px solid #334155;">
                  <th style="padding: 14px 16px; text-align: left; color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Rank</th>
                  <th style="padding: 14px 16px; text-align: left; color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Name</th>
                  <th style="padding: 14px 16px; text-align: left; color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">RFID</th>
                  <th style="padding: 14px 16px; text-align: center; color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Age</th>
                  <th style="padding: 14px 16px; text-align: center; color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Gender</th>
                  <th style="padding: 14px 16px; text-align: center; color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Category</th>
                  <th style="padding: 14px 16px; text-align: center; color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Start Time</th>
                  <th style="padding: 14px 16px; text-align: center; color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">End Time</th>
                  <th style="padding: 14px 16px; text-align: center; color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">⏱️ Duration</th>
                </tr>
              </thead>
              <tbody>
                ${participantsWithDuration.map((p, index) => {
                  const displayName = p.decryptedName || p.name || (p.encrypted_name ? p.encrypted_name.substring(0, 10) + "..." : 'Unknown');
                  const rank = p.durationMs !== null ? index + 1 : '-';
                  const isTop3 = p.durationMs !== null && index < 3;
                  const medalColor = index === 0 ? '#fbbf24' : index === 1 ? '#94a3b8' : index === 2 ? '#cd7f32' : '';
                  
                  return `
                    <tr style="border-bottom: 1px solid #1f2937; transition: background 0.2s;" class="scoreboard-row">
                      <td style="padding: 16px; color: #e2e8f0; font-size: 16px; font-weight: ${isTop3 ? '700' : '500'};">
                        ${isTop3 ? `<span style="color: ${medalColor}; font-size: 20px;">${index === 0 ? '🥇' : index === 1 ? '🥈' : '🥉'}</span> ${rank}` : rank}
                      </td>
                      <td style="padding: 16px; color: #e2e8f0; font-size: 15px; font-weight: ${isTop3 ? '600' : '500'};">${displayName}</td>
                      <td style="padding: 16px; color: #cbd5e1; font-size: 13px; font-family: monospace;">${p.rfid || p.rfid_tag || 'N/A'}</td>
                      <td style="padding: 16px; text-align: center; color: #cbd5e1; font-size: 14px;">${p.age ?? 'N/A'}</td>
                      <td style="padding: 16px; text-align: center; color: #cbd5e1; font-size: 14px;">${p.gender === 'M' ? 'M' : p.gender === 'F' ? 'F' : (p.gender || 'O')}</td>
                      <td style="padding: 16px; text-align: center; color: #cbd5e1; font-size: 14px;">${p.category || '-'}</td>
                      <td style="padding: 16px; text-align: center; color: #94a3b8; font-size: 13px;">${p.startTime ? new Date(p.startTime).toLocaleTimeString() : 'N/A'}</td>
                      <td style="padding: 16px; text-align: center; color: #94a3b8; font-size: 13px;">${p.endTime ? new Date(p.endTime).toLocaleTimeString() : 'N/A'}</td>
                      <td style="padding: 16px; text-align: center; color: ${isTop3 ? medalColor : '#22c55e'}; font-size: ${isTop3 ? '16px' : '15px'}; font-weight: ${isTop3 ? '700' : '600'}; font-family: monospace;">
                        ${p.formattedDuration}
                      </td>
                    </tr>
                  `;
                }).join('')}
              </tbody>
            </table>
          </div>
        </div>
      `}
    </div>

    <style>
      .scoreboard-row:hover {
        background: #1e293b;
      }
      #scoreboard-race-filter-dropdown:focus {
        outline: none;
        border-color: #3b82f6;
      }
      #export-scoreboard-btn:hover {
        box-shadow: 0 4px 15px rgba(139, 92, 246, 0.4);
        transform: translateY(-1px);
      }
    </style>
  `;
}
