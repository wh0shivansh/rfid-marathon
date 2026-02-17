// ============================================================================
// CREATE RACE VIEW - Qualifying Times Grid Renderer
// ============================================================================

import { showToast } from '../utils/Toasts.js';

export function renderQualifyingTimesGrid(category) {
  const { getRaceCategoryConfig } = window.appContext;
  
  const container = document.getElementById('qualifying-times-grid');
  if (!container) return;

  const config = getRaceCategoryConfig(category);
  const numLevels = config.levels.length;

  // Build table HTML
  let tableHtml = '<table style="width: 100%; border-collapse: collapse; font-size: 12px;">';
  
  // Age group header row
  tableHtml += '<tr>';
  tableHtml += '<th style="padding: 8px 4px; border-bottom: 2px solid #334155; text-align: center; color: #cbd5e1; font-weight: bold;">AGE</th>';
  config.ageGroups.forEach(group => {
    tableHtml += `<th colspan="${numLevels}" style="padding: 8px 4px; border-bottom: 2px solid #334155; text-align: center; color: #cbd5e1; font-weight: bold;">${group.label}</th>`;
  });
  tableHtml += '</tr>';
  
  // Level header row (TEST)
  tableHtml += '<tr>';
  tableHtml += '<th style="padding: 6px 4px; border-bottom: 1px solid #475569; text-align: center; color: #a78bfa; font-weight: 600;">TEST</th>';
  config.ageGroups.forEach(group => {
    config.levels.forEach(label => {
      tableHtml += `<th style="padding: 6px 4px; border-bottom: 1px solid #475569; text-align: center; color: #a78bfa; font-weight: 600;">${label}</th>`;
    });
  });
  tableHtml += '</tr>';
  
  // Data row with inputs
  tableHtml += '<tr>';
  tableHtml += `<td style="padding: 6px 4px; text-align: center; background: #1e293b; font-weight: 600; color: #cbd5e1; border-radius: 4px;">${category}</td>`;
  config.ageGroups.forEach(group => {
    config.levels.forEach((_, levelIdx) => {
      const placeholder = group.defaults[levelIdx] ?? '';
      tableHtml += `<td style="padding: 4px 2px;"><input type="number" step="0.01" min="0" data-group-key="${group.key}" data-level-index="${levelIdx}" placeholder="${placeholder}m" style="width: 100%; padding: 6px 4px; background: #0f172a; border: 1px solid #334155; border-radius: 3px; color: #e2e8f0; font-size: 11px; box-sizing: border-box; text-align: center;" /></td>`;
    });
  });
  tableHtml += '</tr>';
  
  tableHtml += '</table>';
  
  container.innerHTML = tableHtml;
}

// ============================================================================
// CREATE RACE VIEW - Form Handlers
// ============================================================================

export function attachCreateRaceHandlers() {
  const { state, fetchRaces, getRaceCategoryConfig, apiRequest, showToast, render, ensureAuth } = window.appContext;
  
  const createForm = document.getElementById("create-race-form");
  if (!createForm) return;

  const categorySelect = document.getElementById('race-category-select');
  if (categorySelect) {
    renderQualifyingTimesGrid(categorySelect.value || 'BPET');
    categorySelect.addEventListener('change', () => {
      renderQualifyingTimesGrid(categorySelect.value || 'BPET');
    });
  }

  createForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    await submitCreateRace(createForm);
  });
}

export async function submitCreateRace(formElement) {
  const { state, fetchRaces, getRaceCategoryConfig, apiRequest, render, ensureAuth, globalLoader } = window.appContext;
  
  try {
    const formData = Object.fromEntries(new FormData(formElement).entries());
    
    // Validate and parse scheduled date
    const rawDate = formData.scheduled_date || formData.schedule_date;
    if (!rawDate) {
      showToast('Please provide a scheduled date', 'warning');
      return;
    }
    
    const parsedDate = new Date(rawDate);
    if (Number.isNaN(parsedDate.getTime())) {
      showToast('Invalid scheduled date format', 'error');
      return;
    }
    
    const isoDate = parsedDate.toISOString().replace('Z', '+00:00');
    
    // Get time unit and race category
    const timeUnit = document.getElementById('time-unit-selector')?.value || 'minutes';
    const categorySelect = document.getElementById('race-category-select');
    const category = formData.race_category || categorySelect?.value || 'BPET';
    const categoryConfig = getRaceCategoryConfig(category);

    // Build qualifying times payload
    const qualifyingPayload = {};
    categoryConfig.ageGroups.forEach(group => {
      const values = categoryConfig.levels.map((_, idx) => {
        const input = formElement.querySelector(`[data-group-key="${group.key}"][data-level-index="${idx}"]`);
        const raw = input ? input.value : '';
        return convertQualifyingTimeToSeconds(raw, group.defaults[idx], timeUnit);
      });
      qualifyingPayload[group.key] = values;
    });
    
    // Wrap API request in loader
    await globalLoader.wrap(async () => {
      await ensureAuth();
      const copyFromRaceId = formData.copy_from_race_id ? String(formData.copy_from_race_id).trim() : "";
      
      await apiRequest("/race", {
        method: "POST",
        body: {
          name: formData.name,
          distance_meters: Number(formData.distance_meters),
          location: formData.location,
          scheduled_date: isoDate,
          description: formData.description || undefined,
          race_category: category,
          ...qualifyingPayload,
          ...(copyFromRaceId ? { copy_from_race_id: copyFromRaceId } : {}),
        },
      });
    });
    
    // Show success toast after loader is hidden
    showToast("Race created successfully", 'success');
    await fetchRaces();
    formElement.reset();
    
    // Delay render to allow toast to display
    setTimeout(() => {
      render();
    }, 2000);
    
  } catch (err) {
    console.error(err);
    showToast(`Create race failed: ${err.message}`, 'error');
    alert(`Create race failed: ${err.message}`);
  }
}

function convertQualifyingTimeToSeconds(value, fallback, timeUnit) {
  const num = value !== '' && value !== undefined && value !== null ? Number(value) : Number(fallback);
  if (Number.isNaN(num)) return Number(fallback);
  if (timeUnit === 'hours') return num * 3600;
  if (timeUnit === 'minutes') return num * 60;
  return num;
}

// ============================================================================
// VIEW SETUP - Called when entering create race view from navigation
// ============================================================================

export async function setupCreateRaceView() {
  const { fetchRaces } = window.appContext;
  
  // Load races for copy-from dropdown
  await fetchRaces();
  
  // Populate the copy-from-race dropdown
  populateCopyFromRaceSelect();
}

function populateCopyFromRaceSelect() {
  const { state } = window.appContext;
  const copyFromRaceSelect = document.getElementById("copy-from-race-id");
  if (!copyFromRaceSelect) return;
  
  const currentValue = copyFromRaceSelect.value;
  const options = [
    '<option value="">Do not copy</option>',
    ...state.races.map((race) => `<option value="${race.id}">${race.name}</option>`)
  ];
  copyFromRaceSelect.innerHTML = options.join("");
  if (currentValue) {
    copyFromRaceSelect.value = currentValue;
  }
}

