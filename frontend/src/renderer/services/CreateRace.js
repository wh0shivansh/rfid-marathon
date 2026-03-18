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
    tableHtml += `<th colspan="${numLevels}" style="padding: 8px 4px; border-bottom: 2px solid #334155; border-left: 1px solid #475569; border-right: 1px solid #475569; text-align: center; color: #cbd5e1; font-weight: bold;">${group.label}</th>`;
  });
  tableHtml += '</tr>';
  
  // Level header row (RESULT)
  tableHtml += '<tr>';
  tableHtml += '<th style="padding: 6px 4px; border-bottom: 1px solid #475569; text-align: center; color: #a78bfa; font-weight: 600;">RESULT</th>';
  config.ageGroups.forEach(group => {
    config.levels.forEach((label, levelIdx) => {
      const borderLeft = levelIdx === 0 ? 'border-left: 1px solid #475569;' : '';
      const borderRight = levelIdx === numLevels - 1 ? 'border-right: 1px solid #475569;' : '';
      tableHtml += `<th style="padding: 6px 4px; border-bottom: 1px solid #475569; ${borderLeft} ${borderRight} text-align: center; color: #a78bfa; font-weight: 600;">${label}</th>`;
    });
  });
  tableHtml += '</tr>';
  
  // Data row with inputs
  tableHtml += '<tr>';
  tableHtml += `<td style="padding: 6px 4px; text-align: center; background: #1e293b; font-weight: 600; color: #cbd5e1; border-radius: 4px;">${category}</td>`;
  config.ageGroups.forEach(group => {
    config.levels.forEach((_, levelIdx) => {
      const placeholder = group.defaults[levelIdx] ?? '';
      const borderLeft = levelIdx === 0 ? 'border-left: 1px solid #475569;' : '';
      const borderRight = levelIdx === numLevels - 1 ? 'border-right: 1px solid #475569;' : '';
      tableHtml += `<td style="padding: 4px 2px; ${borderLeft} ${borderRight}"><input type="number" step="0.01" min="0" data-group-key="${group.key}" data-level-index="${levelIdx}" placeholder="${placeholder}m" style="width: 100%; padding: 6px 4px; background: #0f172a; border: 1px solid #334155; border-radius: 3px; color: #e2e8f0; font-size: 11px; box-sizing: border-box; text-align: center;" /></td>`;
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

  // Defensive repopulation in case the view was entered from a path that
  // already rendered the form before setup hook completed.
  populateCopyFromRaceSelect();

  const categorySelect = document.getElementById('race-category-select');
  if (categorySelect) {
    renderQualifyingTimesGrid(categorySelect.value || 'BPET');
    categorySelect.addEventListener('change', () => {
      renderQualifyingTimesGrid(categorySelect.value || 'BPET');
    });
  }

  const rfidPrefixInput = document.getElementById('rfid-prefix-input');
  const rfidSuffixDigitsInput = document.getElementById('rfid-suffix-digits-input');
  const rfidSuffixStartInput = document.getElementById('rfid-suffix-start-number-input');
  const rfidPreviewValue = document.getElementById('rfid-preview-value');

  const updateRfidPreview = () => {
    if (!rfidPreviewValue || !rfidPrefixInput || !rfidSuffixDigitsInput || !rfidSuffixStartInput) return;

    const prefix = String(rfidPrefixInput.value || '').trim().toUpperCase();
    const suffixDigitsRaw = Number(rfidSuffixDigitsInput.value);
    const suffixStartRaw = Number(rfidSuffixStartInput.value);

    const suffixDigits = Number.isFinite(suffixDigitsRaw) ? Math.max(1, Math.min(12, Math.floor(suffixDigitsRaw))) : 1;
    const maxValue = Math.pow(10, suffixDigits) - 1;
    const suffixStart = Number.isFinite(suffixStartRaw) ? Math.max(0, Math.min(maxValue, Math.floor(suffixStartRaw))) : 0;

    const suffixText = String(suffixStart).padStart(suffixDigits, '0');
    rfidPreviewValue.textContent = `${prefix}${suffixText}`;
  };

  [rfidPrefixInput, rfidSuffixDigitsInput, rfidSuffixStartInput].forEach((el) => {
    if (!el) return;
    el.addEventListener('input', updateRfidPreview);
    el.addEventListener('change', updateRfidPreview);
  });

  updateRfidPreview();

  const rfidSettingsEditBtn = document.getElementById('rfid-settings-edit-btn');
  if (rfidSettingsEditBtn) {
    rfidSettingsEditBtn.addEventListener('click', (event) => {
      event.preventDefault();
      const rfidInputs = [
        document.getElementById('rfid-prefix-input'),
        document.getElementById('rfid-suffix-digits-input'),
        document.getElementById('rfid-suffix-start-number-input'),
      ].filter(Boolean);

      const currentlyDisabled = rfidInputs.some((input) => input.disabled);
      rfidInputs.forEach((input) => {
        if (currentlyDisabled) {
          input.removeAttribute('disabled');
          input.style.background = '#0f172a';
          input.style.color = '#e2e8f0';
          input.style.border = '1px solid #334155';
          input.style.cursor = 'text';
        } else {
          input.setAttribute('disabled', 'disabled');
          input.style.background = '#334155';
          input.style.color = '#94a3b8';
          input.style.border = '1px solid #475569';
          input.style.cursor = 'not-allowed';
        }
      });

      rfidSettingsEditBtn.title = currentlyDisabled ? 'Lock editing' : 'Enable editing';
      rfidSettingsEditBtn.textContent = currentlyDisabled ? '✓' : '✎';
      updateRfidPreview();
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
    const config = window.appContext?.state?.config || {};

    const rfidPrefixInput = document.getElementById('rfid-prefix-input');
    const rfidSuffixDigitsInput = document.getElementById('rfid-suffix-digits-input');
    const rfidSuffixStartInput = document.getElementById('rfid-suffix-start-number-input');

    const rfidPrefix = String(
      rfidPrefixInput?.value ?? formData.rfid_prefix ?? config.rfidDefaultPrefix ?? ''
    ).trim().toUpperCase();

    const rawSuffixDigits = Number(
      rfidSuffixDigitsInput?.value ?? formData.rfid_suffix_digits ?? config.rfidDefaultSuffixDigits
    );
    const rfidSuffixDigits = Number.isFinite(rawSuffixDigits)
      ? Math.max(1, Math.min(12, Math.floor(rawSuffixDigits)))
      : 3;

    const rawSuffixStart = Number(
      rfidSuffixStartInput?.value ?? formData.rfid_suffix_start_number ?? config.rfidDefaultSuffixStartNumber
    );
    const maxSuffixStart = Math.pow(10, rfidSuffixDigits) - 1;
    const rfidSuffixStartNumber = Number.isFinite(rawSuffixStart)
      ? Math.max(0, Math.min(maxSuffixStart, Math.floor(rawSuffixStart)))
      : 0;

    if (!rfidPrefix) {
      showToast('RFID prefix is required', 'warning');
      return;
    }
    
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
          location: formData.location ? String(formData.location).trim() : undefined,
          scheduled_date: isoDate,
          description: formData.description || undefined,
          race_category: category,
          rfid_placement_mode: formData.rfid_placement_mode || 'end_intersection',
          rfid_prefix: rfidPrefix,
          rfid_suffix_digits: rfidSuffixDigits,
          rfid_suffix_start_number: rfidSuffixStartNumber,
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
    console.error("ERROR:", err.message, "CODE:", err.error_code, "DETAILS:", err.details)
    const codeTag = err.error_code ? ` [${err.error_code}]` : '';
    showToast(`Create race failed${codeTag}: ${err.message}`, 'error');
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

  const races = Array.isArray(state.races) ? state.races : [];
  
  const currentValue = copyFromRaceSelect.value;
  const options = [
    '<option value="">Do not copy</option>',
    ...races.map((race, idx) => {
      const raceId = String(race?.id || '').trim();
      const raceName = String(race?.name || race?.race_name || '').trim();
      const optionLabel = raceName || (raceId ? `Race ${idx + 1} (${raceId.slice(0, 8)})` : `Race ${idx + 1}`);
      return `<option value="${raceId}">${optionLabel}</option>`;
    })
  ];
  copyFromRaceSelect.innerHTML = options.join("");
  if (currentValue) {
    copyFromRaceSelect.value = currentValue;
  }
}

