export function renderDashboard(el) {
  el.innerHTML = `
    <h2>Live Race Dashboard</h2>
    <p>Status: Waiting for runners...</p>
    <table border="1" width="100%" style="background:white;color:black">
      <tr>
        <th>Name</th><th>Age</th><th>RFID</th><th>Start</th><th>Finish</th><th>Time</th><th>Category</th>
      </tr>
      <tbody id="raceTable"></tbody>
    </table>
  `;
}
