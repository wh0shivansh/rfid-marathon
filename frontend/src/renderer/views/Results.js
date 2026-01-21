export function renderResults(el) {
  el.innerHTML = `
    <h2>Final Race Results</h2>
    <p>All completed runners will appear here</p>
    <table border="1" width="100%" style="background:white;color:black">
      <tr>
        <th>Name</th><th>Age</th><th>Time</th><th>Category</th>
      </tr>
      <tbody id="resultsTable"></tbody>
    </table>
  `;
}
