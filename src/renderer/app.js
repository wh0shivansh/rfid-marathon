import { renderDashboard } from "./views/Dashboard.js";
import { renderRegistration } from "./views/CandidateRegistration.js";
import { renderResults } from "./views/Results.js";

const app = document.getElementById("app");

// Track active page
let activePage = "dashboard";

app.innerHTML = `
  <div style="display:flex;height:100vh">
    <div class="sidebar">
      <h3>Army Panel</h3>
      <nav class="sidebar-nav">
        <button class="nav-btn active" data-page="dashboard">Dashboard</button>
        <button class="nav-btn" data-page="register">Register</button>
        <button class="nav-btn" data-page="results">Results</button>
      </nav>
    </div>
    <div id="page" style="flex:1;padding:20px;overflow:auto"></div>
  </div>
`;

// Attach event listeners to nav buttons
const navButtons = document.querySelectorAll(".nav-btn");
navButtons.forEach((btn) => {
  btn.addEventListener("click", (e) => {
    const page = e.target.dataset.page;
    showPage(page);
  });
});

window.showPage = (page) => {
  const pageEl = document.getElementById("page");
  
  // Update active button styling
  navButtons.forEach((btn) => {
    if (btn.dataset.page === page) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });
  
  activePage = page;
  
  if (page === "dashboard") renderDashboard(pageEl);
  if (page === "register") renderRegistration(pageEl);
  if (page === "results") renderResults(pageEl);
};

showPage("dashboard");
