export function renderDashboard(races = [], registrations = 0, totalParticipants = 0, startedToday = 0, finishedToday = 0, raceStats = {}) {
  const cards = [
    { label: "Races", value: races.length || "--" },
    { label: "Total Participants", value: totalParticipants || "--" },
    { label: "Today Registrations", value: registrations || "--" },
    // { label: "Started Today", value: startedToday || "--" },
    { label: "Finished Today", value: finishedToday || "--" },
  ];

  const rows = races
    .map(
      (r) => `
      <tr>
        <td>${r.name}</td>
        <td>${r.distance_meters} m</td>
        <td>${r.location}</td>
        <td>${new Date(r.scheduled_date).toLocaleDateString('en-GB')}</td>
        <td>${raceStats[r.id] || 0}</td>
      </tr>`
    )
    .join("") || "<tr><td colspan=5>No races loaded</td></tr>";

  return `
    <div class="page">
      <div class="card-grid">
        ${cards
          .map(
            (c) => `
          <div class="card">
            <div class="card-label">${c.label}</div>
            <div class="card-value">${c.value}</div>
          </div>`
          )
          .join("")}
      </div>
      <div class="panel">
        <div class="panel-header">Races</div>
        <table class="data-table">
          <thead><tr><th>Name</th><th>Distance</th><th>Location</th><th>Schedule</th><th>Participants</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>
  `;
}
