document.getElementById("app").innerHTML = `
<div class="container">
  <div class="sidebar">
    <h2>ARMY PANEL</h2>
    <button class="active" onclick="showDashboard()">Dashboard</button>
    <button onclick="showRegister()">Register Runner</button>
    <button onclick="showLive()">Live Race</button>
    <button onclick="showResults()">Results</button>
  </div>

  <div class="main">
    <div class="topbar">
      <input class="search" placeholder="Search runner...">
      <span>Hello, Admin</span>
    </div>

    <div id="page"></div>
  </div>
</div>
`;

// Store registered candidates
let registeredCandidates = [
  { rfid: "AAABBBCCCDDDEEEFFF111222", name: "Rajesh Kumar", age: 28, category: "25-30 yrs" },
  { rfid: "111222333444555666777888", name: "Priya Singh", age: 32, category: "30-40 yrs" },
  { rfid: "999888777666555444333222", name: "Amit Patel", age: 45, category: "40-45 yrs" }
];

let currentRFID = null;

function setActiveButton(buttonText) {
  const buttons = document.querySelectorAll('.sidebar button');
  buttons.forEach(btn => {
    btn.classList.remove('active');
  });
  buttons.forEach(btn => {
    if (btn.textContent.includes(buttonText)) {
      btn.classList.add('active');
    }
  });
}

function showDashboard() {
  setActiveButton('Dashboard');
  document.getElementById("page").innerHTML = `
    <div class="cards">
      <div class="card">Total Runners<br><b>500</b></div>
      <div class="card">Started<br><b>320</b></div>
      <div class="card">Finished<br><b>210</b></div>
      <div class="card">Best Time<br><b>24:12</b></div>
    </div>
  `;
}

function showRegisterList() {
  const tableRows = registeredCandidates.map(candidate => `
    <tr>
      <td>${candidate.name}</td>
      <td>${candidate.age}</td>
      <td>${candidate.category}</td>
      <td>${candidate.rfid}</td>
    </tr>
  `).join('');

  document.getElementById("page").innerHTML = `
    <div class="table-container">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <h3>Registered Candidates</h3>
        <button class="btn-primary" onclick="startRFIDScan()">Register New Candidate</button>
      </div>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Age</th>
            <th>Category</th>
            <th>RFID Tag</th>
          </tr>
        </thead>
        <tbody>
          ${tableRows}
        </tbody>
      </table>
    </div>
  `;
}

function startRFIDScan() {
  currentRFID = null;
  document.getElementById("page").innerHTML = `
    <div class="rfid-scan-container">
      <div class="rfid-card">
        <h2>📡 Waiting for RFID Scan</h2>
        <p>Please scan the RFID tag on the runner's hand...</p>
        <div class="scanning-indicator"></div>
        
        <div class="form-group" style="margin-top: 30px;">
          <label>RFID Tag (24-digit hex code):</label>
          <input id="rfidInput" type="text" placeholder="Scan or manually enter RFID tag" autofocus>
        </div>
        
        <div style="margin-top: 20px;">
          <button class="btn-primary" onclick="acceptRFIDTag()">Accept RFID</button>
          <button class="btn-secondary" onclick="showRegisterList()">Cancel</button>
        </div>
      </div>
    </div>
  `;

  const rfidInput = document.getElementById('rfidInput');
  rfidInput.focus();
  
  // Listen for RFID input (RFID readers typically send data followed by Enter)
  rfidInput.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      acceptRFIDTag();
    }
  });
}

function acceptRFIDTag() {
  const rfidInput = document.getElementById('rfidInput');
  currentRFID = rfidInput.value.trim();
  
  if (!currentRFID) {
    alert('Please enter or scan an RFID tag');
    rfidInput.focus();
    return;
  }
  
  if (currentRFID.length !== 24) {
    alert('RFID tag must be 24 digits. Current length: ' + currentRFID.length);
    rfidInput.focus();
    return;
  }
  
  showCandidateForm();
}

function showCandidateForm() {
  document.getElementById("page").innerHTML = `
    <div class="table-container">
      <h3>Register New Candidate</h3>
      <div class="form-group">
        <label>RFID Tag:</label>
        <input type="text" value="${currentRFID}" disabled style="background: #f0f0f0;">
      </div>
      
      <div class="form-group">
        <label>Name:</label>
        <input id="candidateName" type="text" placeholder="Enter candidate name">
      </div>
      
      <div class="form-group">
        <label>Age:</label>
        <input id="candidateAge" type="number" placeholder="Enter age" min="1" max="100">
      </div>
      
      <div class="form-group">
        <label>Category:</label>
        <select id="candidateCategory">
          <option value="">Select Category</option>
          <option value="upto 30 yrs">Up to 30 Years</option>
          <option value="30-40 yrs">30-40 Years</option>
          <option value="40-45 yrs">40-45 Years</option>
        </select>
      </div>
      
      <div style="margin-top: 20px;">
        <button class="btn-primary" onclick="saveCandidateData()">Save Candidate</button>
        <button class="btn-secondary" onclick="showRegisterList()">Cancel</button>
      </div>
    </div>
  `;
  
  document.getElementById('candidateName').focus();
}

function saveCandidateData() {
  const name = document.getElementById('candidateName').value.trim();
  const age = document.getElementById('candidateAge').value;
  const category = document.getElementById('candidateCategory').value;
  
  if (!name || !age || !category) {
    alert('Please fill in all fields');
    return;
  }
  
  // Add new candidate to the list
  registeredCandidates.push({
    rfid: currentRFID,
    name: name,
    age: age,
    category: category
  });
  
  alert(`✓ Candidate ${name} registered successfully!`);
  currentRFID = null;
  showRegisterList();
}

function showRegister() {
  setActiveButton('Register Runner');
  showRegisterList();
}

function showLive() {
  setActiveButton('Live Race');
  document.getElementById("page").innerHTML = `
    <div class="table-container">
      <h3>Live Runner Status</h3>
      <table>
        <tr><th>Name</th><th>RFID</th><th>Start Time</th><th>Finish Time</th><th>Status</th></tr>
        <tr><td>Rahul</td><td>2016</td><td>17:10</td><td>-</td><td>Running</td></tr>
      </table>
    </div>
  `;
}

function showResults() {
  setActiveButton('Results');
  document.getElementById("page").innerHTML = "<div class='table-container'><h3>Race Results</h3></div>";
}

showDashboard();
