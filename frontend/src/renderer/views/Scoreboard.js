// Scoreboard View - HTML Only
// All JavaScript logic is in app.js
// Shows only COMPLETED races with participant time calculations

export function renderScoreboard(races = [], participants = [], selectedRaceId = null, options = {}) {
  // Filter only completed races
  const completedRaces = races.filter(r => r.status === 'completed');
  const searchQuery = (options.searchQuery || '').trim().toLowerCase();
  const sortKey = options.sortKey || 'durationMs';
  const sortDir = options.sortDir || 'asc';
  const ageFilter = options.ageFilter || '';
  const remarksFilter = options.remarksFilter || '';

  const selectedRace = races.find(r => String(r.id) === String(selectedRaceId));

  // Filter participants for selected race
  let filteredParticipants = selectedRaceId
    ? participants.filter(p => String(p.race_id) === String(selectedRaceId))
    : [];

  // Calculate duration for each participant (unsorted)
  const participantsWithDurationUnsorted = filteredParticipants
    .map(p => {
      const startTime = p.start_time ? new Date(p.start_time) : null;
      const midTime = p.mid_time ? new Date(p.mid_time) : null;
      const endTime = p.end_time ? new Date(p.end_time) : null;

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

      const remarks = getRemarks(selectedRace, p.age, durationMs, midTime);

      return {
        ...p,
        durationMs,
        formattedDuration,
        startTime,
        midTime,
        endTime,
        remarks
      };
    });

  let participantsFiltered = participantsWithDurationUnsorted;

  // Apply search filter (by decryptedName, name or encrypted_name)
  if (searchQuery) {
    participantsFiltered = participantsFiltered.filter(p => {
      const name = (p.decryptedName || p.name || p.encrypted_name || '').toString().toLowerCase();
      return name.includes(searchQuery);
    });
  }

  // Apply age category filter
  if (ageFilter) {
    participantsFiltered = participantsFiltered.filter(p => {
      const age = Number(p.age);
      if (!Number.isFinite(age)) return false;
      if (ageFilter === 'upto30') return age <= 30;
      if (ageFilter === 'upto40') return age > 30 && age <= 40;
      if (ageFilter === '40_45') return age > 40 && age <= 45;
      return true;
    });
  }

  // Apply remarks filter
  if (remarksFilter) {
    participantsFiltered = participantsFiltered.filter(p => {
      return String(p.remarks || '').toLowerCase() === String(remarksFilter).toLowerCase();
    });
  }

  // Build a baseline rank map based on duration ascending (shortest = rank 1)
  const baseline = [...participantsFiltered].sort((a, b) => {
    if (a.durationMs === null) return 1;
    if (b.durationMs === null) return -1;
    return a.durationMs - b.durationMs;
  });
  const baselineRankMap = new Map();
  baseline.forEach((p, idx) => {
    const r = idx + 1;
    // assign rank onto participant object (baseline rank)
    try { p.positionRank = r; } catch (err) { /* ignore if immutable */ }
    const key = p.id ?? (p.rfid || p.rfid_tag || p.encrypted_name || idx);
    baselineRankMap.set(key, r);
  });

  // Now sort according to selected sortKey/sortDir. When sortKey === 'rank', use baselineRankMap.
  const participantsWithDuration = participantsFiltered.sort((a, b) => {
    const dir = sortDir === 'desc' ? -1 : 1;
    const getVal = (item, key) => {
      switch (key) {
        case 'name': return (item.decryptedName || item.name || item.encrypted_name || '').toString().toLowerCase();
        case 'rfid': return (item.rfid || item.rfid_tag || '').toString().toLowerCase();
        case 'army_number': return (item.army_number || '').toString().toLowerCase();
        case 'rankField': return (item.rank || '').toString().toLowerCase();
        case 'age': return Number(item.age) || 0;
        case 'gender': return (item.gender || '').toString().toLowerCase();
        case 'category': return (item.category || '').toString().toLowerCase();
        case 'startTime': return item.startTime ? item.startTime.getTime() : Number.MAX_SAFE_INTEGER;
        case 'midTime': return item.midTime ? item.midTime.getTime() : Number.MAX_SAFE_INTEGER;
        case 'endTime': return item.endTime ? item.endTime.getTime() : Number.MAX_SAFE_INTEGER;
        case 'durationMs': return item.durationMs === null ? Number.MAX_SAFE_INTEGER : item.durationMs;
        case 'rank': {
          // Prefer assigned positionRank on item; fall back to baseline map using stable keys
          const r = Number(item.positionRank);
          if (!Number.isNaN(r) && r > 0) return r;
          const stableKey = item.id ?? (item.rfid || item.rfid_tag || item.encrypted_name);
          const mapped = baselineRankMap.get(stableKey);
          return mapped ?? Number.MAX_SAFE_INTEGER;
        }
        default: return item[key];
      }
    };

    const va = getVal(a, sortKey);
    const vb = getVal(b, sortKey);
    if (va === vb) return 0;
    return va > vb ? dir : -dir;
  });

  function getRaceStartTime(race) {
    if (!race) return null;
    const times = [race.up30start_time, race.upto40start_time, race['40_45start_time'], race.start_time_40_45]
      .filter(Boolean)
      .map(t => new Date(t).getTime());
    if (!times.length) return null;
    return new Date(Math.min(...times));
  }

  function getRemarks(race, age, durationMs, midTime) {
    if (!midTime) return 'fail';
    if (!race || durationMs === null || durationMs === undefined || !age) return 'fail';
    const durationSec = durationMs / 1000;
    let thresholds = null;
    if (age < 30) {
      thresholds = {
        excellent: race.age_upto30_excellent,
        good: race.age_upto30_good,
        satisfactory: race.age_upto30_satisfactory,
      };
    } else if (age < 40) {
      thresholds = {
        excellent: race.age_upto40_excellent,
        good: race.age_upto40_good,
        satisfactory: race.age_upto40_satisfactory,
      };
    } else {
      thresholds = {
        excellent: race.age_40to45_excellent,
        good: race.age_40to45_good,
        satisfactory: race.age_40to45_satisfactory,
      };
    }

    if (durationSec > thresholds.satisfactory) return 'fail';
    if (durationSec <= thresholds.excellent) return 'excellent';
    if (durationSec <= thresholds.good) return 'good';
    return 'satisfied';
  }

  const filtersActive = Boolean(searchQuery || ageFilter || remarksFilter);

  const statsParticipants = participantsWithDurationUnsorted;

  return `
    <div class="page" style="background:#0b1220; min-height:100vh; color:#e2e8f0; padding:16px;">
      <!-- Header Section -->
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; padding: 20px; background: #111827; border-radius: 8px; border: 1px solid #1f2937; gap: 16px;">
        <div style="display: flex; flex-direction: column; gap: 12px; flex: 1;">
          <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
            <h1 style="color: #e2e8f0; margin: 0; font-size: 24px; font-weight: 600;">🏆 Scoreboard</h1>
            <select id="scoreboard-race-filter-dropdown" style="padding: 10px 14px; background: #0f172a; border: 2px solid #334155; border-radius: 6px; color: #e2e8f0; font-size: 0.95em; cursor: pointer; min-width: 300px;">
              <option value="">-- Select a completed race --</option>
              ${completedRaces.map(race => `
                <option value="${race.id}" ${String(selectedRaceId) === String(race.id) ? 'selected' : ''}>
                  ${race.name} - ${race.location} (${new Date(race.scheduled_date).toLocaleDateString()})
                </option>
              `).join('')}
            </select>

            <input id="scoreboard-search-input" placeholder="Search by name..." value="${options.searchQuery || ''}" style="padding: 10px 12px; background: #0f172a; border: 2px solid #334155; border-radius: 6px; color: #e2e8f0; font-size: 0.95em; min-width: 240px;" />
          </div>
        </div>

        <div style="display: flex; align-items: center; gap: 10px;">
          <select id="scoreboard-export-format" style="padding: 8px 10px; background: #0f172a; border: 2px solid #334155; border-radius: 6px; color: #e2e8f0; font-size: 0.9em; cursor: pointer; min-width: 150px;">
          <option value="word">Export: Word</option>
            <option value="excel">Export: Excel</option>
            <option value="pdf">Export: PDF</option>
          </select>
          <button id="export-scoreboard-btn" style="padding: 8px 14px; background: #2563eb; border: 1px solid #1d4ed8; border-radius: 6px; color: #ffffff; font-size: 0.9em; cursor: pointer; font-weight: 600;">Export Results</button>
        </div>
      </div>

      ${!selectedRaceId ? `
        <div class="empty-state" style="text-align: center; padding: 60px; background: #111827; border-radius: 8px; border: 1px solid #1f2937;">
          <div style="font-size: 48px; margin-bottom: 16px; opacity: 0.3;">🏁</div>
          <p style="color: #64748b; font-size: 16px;">Select a completed race to view the scoreboard.</p>
          ${completedRaces.length === 0 ? `
            <p style="color: #64748b; font-size: 14px; margin-top: 8px;">No completed races available yet.</p>
          ` : ''}
        </div>
        ` : participantsWithDurationUnsorted.length === 0 ? `` : `
          <!-- Race Summary Card -->
          <div style="margin-bottom: 24px; padding: 24px; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-radius: 8px; border: 1px solid #334155;">
            <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 20px;">
              <div style="text-align: center;">
                <div style="color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Total Participants</div>
                <div style="color: #e2e8f0; font-size: 32px; font-weight: 700;">${statsParticipants.length}</div>
              </div>
              <div style="text-align: center;">
                <div style="color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Finished</div>
                <div style="color: #22c55e; font-size: 32px; font-weight: 700;">${statsParticipants.filter(p => p.durationMs !== null).length}</div>
              </div>
              <div style="text-align: center;">
                <div style="color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Start Time</div>
                <div style="color: #e2e8f0; font-size: 32px; font-weight: 600;">${(() => {
                  const startTime = getRaceStartTime(selectedRace);
                  return startTime ? `${startTime.toLocaleTimeString()}` : 'N/A';
                })()}
                </div>
              </div>
              <div style="text-align: center;">
                <div style="color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Fastest Time</div>
                <div style="color: #fbbf24; font-size: 32px; font-weight: 700;">${statsParticipants.find(p => p.durationMs !== null)?.formattedDuration || 'N/A'}</div>
              </div>
              <div style="text-align: center;">
                <div style="color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Race</div>
                <div style="color: #e2e8f0; font-size: 18px; font-weight: 600;">${(() => {
                  const race = races.find(r => String(r.id) === String(selectedRaceId));
                  return race ? `${race.distance_meters}m` : 'N/A';
                })()}
                </div>
              </div>
            </div>
          </div>
          `}
          ${selectedRaceId ? `
          <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
            <select id="scoreboard-age-filter-dropdown" style="padding: 8px 10px; background: #0f172a; border: 2px solid #334155; border-radius: 6px; color: #e2e8f0; font-size: 0.9em; cursor: pointer; min-width: 180px;">
              <option value="">Age category</option>
              <option value="upto30" ${ageFilter === 'upto30' ? 'selected' : ''}>Upto 30</option>
              <option value="upto40" ${ageFilter === 'upto40' ? 'selected' : ''}>Upto 40</option>
              <option value="40_45" ${ageFilter === '40_45' ? 'selected' : ''}>40 - 45</option>
            </select>

            <select id="scoreboard-remarks-filter-dropdown" style="padding: 8px 10px; background: #0f172a; border: 2px solid #334155; border-radius: 6px; color: #e2e8f0; font-size: 0.9em; cursor: pointer; min-width: 180px;">
              <option value="">Remarks</option>
              <option value="excellent" ${remarksFilter === 'excellent' ? 'selected' : ''}>Excellent</option>
              <option value="good" ${remarksFilter === 'good' ? 'selected' : ''}>Good</option>
              <option value="satisfied" ${remarksFilter === 'satisfied' ? 'selected' : ''}>Satisfied</option>
              <option value="fail" ${remarksFilter === 'fail' ? 'selected' : ''}>Fail</option>
            </select>

            <button id="scoreboard-clear-filters" style="padding: 8px 12px; background: #1f2937; border: 1px solid #334155; border-radius: 6px; color: #e2e8f0; font-size: 0.9em; cursor: pointer;">Clear filters</button>
            <span style="color: ${filtersActive ? '#f59e0b' : '#64748b'}; font-size: 12px;">${filtersActive ? 'Filters active' : 'No filters applied'}</span>
          </div>
          ` : ``}

          ${selectedRaceId ? `
            <!-- Scoreboard Table -->
            <div style="background: #111827; border: 1px solid #1f2937; border-radius: 8px; overflow: hidden;">
            ${participantsWithDuration.length > 0 ? `
              <div style="padding: 16px 20px; background: #0f172a; border-bottom: 1px solid #1f2937; display:flex; align-items:center; justify-content:space-between;">
                <h2 style="margin: 0; color: #e2e8f0; font-size: 18px; font-weight: 600;">Race Results</h2>
                <div style="color:#94a3b8; font-size:12px;">Sorted by: ${sortKey} (${sortDir})</div>
              </div>
              <div style="overflow-x: auto;">
                <table id="scoreboard-table" style="width: 100%; border-collapse: collapse;">
                  <thead>
                    <tr style="background: #1e293b; border-bottom: 2px solid #334155;">
                      <th style="padding: 14px 16px; text-align: left; color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Pos <button class="scoreboard-sort-toggle" data-key="rank" style="margin-left:8px;background:transparent;border:none;color:#94a3b8;cursor:pointer">⇅</button></th>
                      <th style="padding: 14px 16px; text-align: left; color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Army No <button class="scoreboard-sort-toggle" data-key="army_number" style="margin-left:8px;background:transparent;border:none;color:#94a3b8;cursor:pointer">⇅</button></th>
                      <th style="padding: 14px 16px; text-align: left; color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Rank <button class="scoreboard-sort-toggle" data-key="rankField" style="margin-left:8px;background:transparent;border:none;color:#94a3b8;cursor:pointer">⇅</button></th>
                      <th style="padding: 14px 16px; text-align: left; color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Name <button class="scoreboard-sort-toggle" data-key="name" style="margin-left:8px;background:transparent;border:none;color:#94a3b8;cursor:pointer">⇅</button></th>
                      <th style="padding: 14px 16px; text-align: center; color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Age <button class="scoreboard-sort-toggle" data-key="age" style="margin-left:8px;background:transparent;border:none;color:#94a3b8;cursor:pointer">⇅</button></th>
                      <th style="padding: 14px 16px; text-align: center; color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Start Time <button class="scoreboard-sort-toggle" data-key="startTime" style="margin-left:8px;background:transparent;border:none;color:#94a3b8;cursor:pointer">⇅</button></th>
                      <th style="padding: 14px 16px; text-align: center; color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Mid Time <button class="scoreboard-sort-toggle" data-key="midTime" style="margin-left:8px;background:transparent;border:none;color:#94a3b8;cursor:pointer">⇅</button></th>
                      <th style="padding: 14px 16px; text-align: center; color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">End Time <button class="scoreboard-sort-toggle" data-key="endTime" style="margin-left:8px;background:transparent;border:none;color:#94a3b8;cursor:pointer">⇅</button></th>
                      <th style="padding: 14px 16px; text-align: center; color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">⏱️ Duration <button class="scoreboard-sort-toggle" data-key="durationMs" style="margin-left:8px;background:transparent;border:none;color:#94a3b8;cursor:pointer">⇅</button></th>
                      <th style="padding: 14px 16px; text-align: center; color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Remarks</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${participantsWithDuration.map((p, index) => {
                      const displayName = p.decryptedName || p.name || (p.encrypted_name ? p.encrypted_name.substring(0, 10) + "..." : 'Unknown');
                      const stableKey = p.id ?? (p.rfid || p.rfid_tag || p.encrypted_name);
                      const rank = p.positionRank ?? baselineRankMap.get(stableKey) ?? (p.durationMs !== null ? index + 1 : '-');
                      const rankNum = Number(rank);
                      const isTop3 = Number.isFinite(rankNum) && rankNum >= 1 && rankNum <= 3;
                      const medalColor = rankNum === 1 ? '#fbbf24' : rankNum === 2 ? '#94a3b8' : rankNum === 3 ? '#cd7f32' : '';
                      const remarks = p.remarks || 'fail';
                      const remarkColor = remarks === 'fail' ? '#ef4444' : remarks === 'excellent' ? '#10b981' : remarks === 'good' ? '#f59e0b' : '#60a5fa';

                      return `
                        <tr style="border-bottom: 1px solid #1f2937; transition: background 0.2s;" class="scoreboard-row">
                          <td style="padding: 16px; color: #e2e8f0; font-size: 16px; font-weight: ${isTop3 ? '700' : '500'};">
                            ${isTop3 ? `<span style="color: ${medalColor}; font-size: 20px;">${rankNum === 1 ? '🥇' : rankNum === 2 ? '🥈' : '🥉'}</span> ${rank}` : rank}
                          </td>
                          <td style="padding: 16px; color: #cbd5e1; font-size: 13px;">${p.army_number || 'N/A'}</td>
                          <td style="padding: 16px; color: #cbd5e1; font-size: 13px;">${p.rank || 'N/A'}</td>
                          <td style="padding: 16px; color: #e2e8f0; font-size: 15px; font-weight: ${isTop3 ? '600' : '500'};">${displayName}</td>
                          <td style="padding: 16px; text-align: center; color: #cbd5e1; font-size: 14px;">${p.age ?? 'N/A'}</td>
                          <td style="padding: 16px; text-align: center; color: #94a3b8; font-size: 13px;">${p.startTime ? new Date(p.startTime).toLocaleTimeString() : 'N/A'}</td>
                          <td style="padding: 16px; text-align: center; color: #94a3b8; font-size: 13px;">${p.midTime ? new Date(p.midTime).toLocaleTimeString() : 'N/A'}</td>
                          <td style="padding: 16px; text-align: center; color: #94a3b8; font-size: 13px;">${p.endTime ? new Date(p.endTime).toLocaleTimeString() : 'N/A'}</td>
                          <td style="padding: 16px; text-align: center; color: ${isTop3 ? medalColor : '#22c55e'}; font-size: ${isTop3 ? '16px' : '15px'}; font-weight: ${isTop3 ? '700' : '600'}; font-family: monospace;">
                            ${p.formattedDuration}
                          </td>
                          <td style="padding: 16px; text-align: center; color: ${remarkColor}; font-size: 13px; font-weight: 600; text-transform: capitalize;">${remarks}</td>
                        </tr>
                      `;
                    }).join('')}
                  </tbody>
                </table>
              </div>
          ` : `
            <div class="empty-state" style="text-align: center; padding: 60px; background: #111827; border-radius: 8px; border: 1px solid #1f2937;">
              <div style="font-size: 48px; margin-bottom: 16px; opacity: 0.3;">👥</div>
              <p style="color: #64748b; font-size: 16px;">${filtersActive ? 'No participants match the current filters.' : 'No participants found for this race.'}</p>
            </div>
          `}
        </div>
      ` : ``}
    </div>

    <style>
      .scoreboard-row:hover {
        background: #1e293b;
      }
      #scoreboard-race-filter-dropdown:focus, #scoreboard-search-input:focus {
        outline: none;
        border-color: #3b82f6;
      }
      #export-scoreboard-btn:hover {
        box-shadow: 0 4px 15px rgba(139, 92, 246, 0.4);
        transform: translateY(-1px);
      }
      .scoreboard-sort-toggle:hover { color: #fff; }
    </style>
  `;
}
