export function renderRegistration(el) {
  el.innerHTML = `
    <h2>Candidate Registration</h2>
    <input id="name" placeholder="Name"><br><br>
    <input id="age" placeholder="Age"><br><br>
    <input id="rfid" placeholder="Scan RFID"><br><br>
    <button onclick="registerCandidate()">Register</button>
    <div id="list"></div>
  `;
}

window.registerCandidate = () => {
  const name = document.getElementById("name").value;
  const age = document.getElementById("age").value;
  const rfid = document.getElementById("rfid").value;

  const list = document.getElementById("list");
  list.innerHTML += `<p>${name} | ${age} yrs | Tag: ${rfid}</p>`;
};
