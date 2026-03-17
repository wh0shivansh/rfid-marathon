import { showToast } from '../utils/Toasts.js';

// ============================================================================
// SCOREBOARD - FILTERS AND EXPORT UTILITIES
// ============================================================================

export function areScoreboardFiltersActive() {
  const { scoreboardSearchQuery, scoreboardAgeFilter, scoreboardRemarksFilter } = window.appContext;
  
  return Boolean(
    (scoreboardSearchQuery && scoreboardSearchQuery.trim()) ||
    scoreboardAgeFilter ||
    scoreboardRemarksFilter
  );
}

export function getScoreboardExportRows() {
  const table = document.getElementById('scoreboard-table');
  if (!table) return null;
  const headerCells = Array.from(table.querySelectorAll('thead th'));
  const hasMidColumn = headerCells.some((th) => String(th.textContent || '').toLowerCase().includes('mid time'));
  const rows = Array.from(table.querySelectorAll('tbody tr'));
  return rows.map((row, index) => {
    const cells = row.querySelectorAll('td');
    if (!cells || cells.length < 9) return null;

    const clean = (val) => String(val || '').replace(/\s+/g, ' ').trim();

    const startIdx = 5;
    const midIdx = hasMidColumn ? 6 : -1;
    const endIdx = hasMidColumn ? 7 : 6;
    const resultIdx = hasMidColumn ? 9 : 8;

    return {
      sno: String(index + 1),
      army_number: clean(cells[1].textContent),
      rank: clean(cells[2].textContent),
      name: clean(cells[3].textContent),
      age: clean(cells[4].textContent),
      start: clean(cells[startIdx]?.textContent),
      mid: hasMidColumn ? clean(cells[midIdx]?.textContent) : '',
      end: clean(cells[endIdx]?.textContent),
      result: clean(cells[resultIdx]?.textContent)
    };
  }).filter(Boolean);
}

export function buildScoreboardExportHtml(rows, title, includeMid = true) {
  const safeTitle = title || 'Scoreboard Export';
  const bodyRows = rows.map(r => {
    const midCell = includeMid ? `<td>${r.mid}</td>` : '';
    return `
      <tr>
        <td>${r.sno}</td>
        <td>${r.army_number}</td>
        <td>${r.rank}</td>
        <td>${r.name}</td>
        <td>${r.age}</td>
        <td>${r.start}</td>
        ${midCell}
        <td>${r.end}</td>
        <td>${r.result}</td>
      </tr>
    `;
  }).join('');

  return `
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8" />
        <title>${safeTitle}</title>
        <style>
          body { font-family: Arial, sans-serif; padding: 24px; }
          h1 { font-size: 18px; margin-bottom: 12px; }
          table { width: 100%; border-collapse: collapse; font-size: 12px; }
          th, td { border: 1px solid #cccccc; padding: 6px 8px; text-align: left; }
          th { background: #f3f4f6; }
        </style>
      </head>
      <body>
        <h1>${safeTitle}</h1>
        <table>
          <thead>
            <tr>
              <th>S.No.</th>
              <th>Army Number</th>
              <th>Rank</th>
              <th>Name</th>
              <th>Age</th>
              <th>Start Time</th>
              ${includeMid ? '<th>Mid Time</th>' : ''}
              <th>End Time</th>
              <th>Result</th>
            </tr>
          </thead>
          <tbody>
            ${bodyRows}
          </tbody>
        </table>
      </body>
    </html>
  `;
}

export async function exportScoreboardResults() {
  const { state, scoreboardSelectedRaceId, scoreboardAgeFilter, scoreboardRemarksFilter, scoreboardSearchQuery } = window.appContext;
  
  if (!scoreboardSelectedRaceId) {
    showToast('Please select a completed race first', 'warning');
    return;
  }

  const rows = getScoreboardExportRows();
  if (!rows || rows.length === 0) {
    showToast('No scoreboard rows to export', 'warning');
    return;
  }

  if (areScoreboardFiltersActive()) {
    const ok = confirm('Filters are applied. Export will include only the filtered results. Continue?');
    if (!ok) return;
  }

  const formatSelect = document.getElementById('scoreboard-export-format');
  const format = formatSelect ? formatSelect.value : 'excel';
  const race = state.races.find(r => String(r.id) === String(scoreboardSelectedRaceId));
  const includeMid = race?.rfid_placement_mode !== 'end_intersection';
  const baseTitle = race ? `Scoreboard - ${race.name}` : 'Scoreboard';
  const baseName = race ? `scoreboard_${race.name.replace(/\s+/g, '_').toLowerCase()}` : 'scoreboard';
  const sanitizePart = (val) => String(val || '')
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9_-]/g, '')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');
  const filterParts = [];
  if (scoreboardAgeFilter) filterParts.push(`age-${sanitizePart(scoreboardAgeFilter)}`);
  if (scoreboardRemarksFilter) filterParts.push(`remarks-${sanitizePart(scoreboardRemarksFilter)}`);
  if (scoreboardSearchQuery && scoreboardSearchQuery.trim()) {
    const searchPart = sanitizePart(scoreboardSearchQuery.trim()).slice(0, 24);
    if (searchPart) filterParts.push(`search-${searchPart}`);
  }
  const filterSuffix = filterParts.length ? `_${filterParts.join('_')}` : '';
  const titleSuffix = filterParts.length ? ` (filters: ${filterParts.join(', ')})` : '';
  const exportTitle = `${baseTitle}${titleSuffix}`;
  const fileBase = `${baseName}${filterSuffix}`;
  const buildXlsx = window.secureApi?.buildXlsx;
  const buildDocx = window.secureApi?.buildDocx;
  const buildPdf = window.secureApi?.buildPdf;

  const downloadBlob = (content, filename, type) => {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  if (format === 'excel') {
    if (!buildXlsx) {
      showToast('Excel export is unavailable (XLSX not loaded)', 'error');
      return;
    }
    const header = includeMid
      ? ['S.No.', 'Army Number', 'Rank', 'Name', 'Age', 'Start Time', 'Mid Time', 'End Time', 'Result']
      : ['S.No.', 'Army Number', 'Rank', 'Name', 'Age', 'Start Time', 'End Time', 'Result'];
    const aoa = [
      header,
      ...rows.map(r => includeMid
        ? [r.sno, r.army_number, r.rank, r.name, r.age, r.start, r.mid, r.end, r.result]
        : [r.sno, r.army_number, r.rank, r.name, r.age, r.start, r.end, r.result]
      )
    ];
    const xlsxArray = buildXlsx(aoa, 'Scoreboard');
    if (!xlsxArray) {
      showToast('Excel export failed (workbook empty)', 'error');
      return;
    }
    downloadBlob(xlsxArray, `${fileBase}.xlsx`, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    return;
  }

  if (format === 'word') {
    if (!buildDocx) {
      showToast('Word export is unavailable (DOCX not loaded)', 'error');
      return;
    }
    const headers = includeMid
      ? ['S.No.', 'Army Number', 'Rank', 'Name', 'Age', 'Start Time', 'Mid Time', 'End Time', 'Result']
      : ['S.No.', 'Army Number', 'Rank', 'Name', 'Age', 'Start Time', 'End Time', 'Result'];
    const dataRows = rows.map(r => includeMid
      ? [r.sno, r.army_number, r.rank, r.name, r.age, r.start, r.mid, r.end, r.result]
      : [r.sno, r.army_number, r.rank, r.name, r.age, r.start, r.end, r.result]
    );
    const docxArray = await buildDocx(headers, dataRows, exportTitle);
    if (!docxArray) {
      showToast('Word export failed', 'error');
      return;
    }
    downloadBlob(docxArray, `${fileBase}.docx`, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document');
    return;
  }

  if (format === 'pdf') {
    if (!buildPdf) {
      showToast('PDF export is unavailable (PDF library not loaded)', 'error');
      return;
    }
    const headers = includeMid
      ? ['S.No.', 'Army Number', 'Rank', 'Name', 'Age', 'Start Time', 'Mid Time', 'End Time', 'Result']
      : ['S.No.', 'Army Number', 'Rank', 'Name', 'Age', 'Start Time', 'End Time', 'Result'];
    const dataRows = rows.map(r => includeMid
      ? [r.sno, r.army_number, r.rank, r.name, r.age, r.start, r.mid, r.end, r.result]
      : [r.sno, r.army_number, r.rank, r.name, r.age, r.start, r.end, r.result]
    );
    const pdfArray = await buildPdf(headers, dataRows, exportTitle);
    if (!pdfArray) {
      showToast('PDF export failed', 'error');
      return;
    }
    downloadBlob(pdfArray, `${fileBase}.pdf`, 'application/pdf');
  }
}

// ============================================================================
// SCOREBOARD - EVENT HANDLERS
// ============================================================================

export function attachScoreboardHandlers() {
  const { state, render, scoreboardSelectedRaceId, scoreboardAgeFilter, scoreboardRemarksFilter, scoreboardSearchQuery } = window.appContext;
  
  if (state.view !== 'scoreboard') return;

  // Race filter dropdown (only completed races)
  const scoreboardRaceFilterDropdown = document.getElementById('scoreboard-race-filter-dropdown');
  if (scoreboardRaceFilterDropdown) {
    scoreboardRaceFilterDropdown.addEventListener('change', async (e) => {
      window.appContext.scoreboardSelectedRaceId = e.target.value || null;
      window.appContext.scoreboardAgeFilter = '';
      window.appContext.scoreboardRemarksFilter = '';
      window.appContext.scoreboardSearchQuery = '';
      const { fetchParticipants } = window.appContext;
      await fetchParticipants(window.appContext.scoreboardSelectedRaceId, true);
      render();
    });
  }

  // Search input (client-side filter by name)
  const scoreboardSearchInput = document.getElementById('scoreboard-search-input');
  if (scoreboardSearchInput) {
    scoreboardSearchInput.addEventListener('input', (e) => {
      const val = e.target.value || '';
      const pos = (e.target.selectionStart != null) ? e.target.selectionStart : null;
      window.appContext.scoreboardSearchQuery = val;
      render();
      // restore focus and caret after re-render
      setTimeout(() => {
        const el = document.getElementById('scoreboard-search-input');
        if (el) {
          el.focus();
          if (pos !== null) {
            try { el.setSelectionRange(pos, pos); } catch (err) { /* ignore */ }
          }
        }
      }, 0);
    });
  }

  // Age category filter
  const scoreboardAgeFilterDropdown = document.getElementById('scoreboard-age-filter-dropdown');
  if (scoreboardAgeFilterDropdown) {
    scoreboardAgeFilterDropdown.addEventListener('change', (e) => {
      window.appContext.scoreboardAgeFilter = e.target.value || '';
      render();
    });
  }

  // Remarks filter
  const scoreboardRemarksFilterDropdown = document.getElementById('scoreboard-remarks-filter-dropdown');
  if (scoreboardRemarksFilterDropdown) {
    scoreboardRemarksFilterDropdown.addEventListener('change', (e) => {
      window.appContext.scoreboardRemarksFilter = e.target.value || '';
      render();
    });
  }

  // Clear filters button
  const clearFiltersBtn = document.getElementById('scoreboard-clear-filters');
  if (clearFiltersBtn) {
    clearFiltersBtn.addEventListener('click', () => {
      window.appContext.scoreboardAgeFilter = '';
      window.appContext.scoreboardRemarksFilter = '';
      window.appContext.scoreboardSearchQuery = '';
      render();
    });
  }

  // Export results
  const exportBtn = document.getElementById('export-scoreboard-btn');
  if (exportBtn) {
    exportBtn.addEventListener('click', () => {
      exportScoreboardResults();
    });
  }

  // Column sort toggles
  const sortToggles = document.querySelectorAll('.scoreboard-sort-toggle');
  if (sortToggles && sortToggles.length) {
    sortToggles.forEach(btn => {
      btn.addEventListener('click', (e) => {
        const key = btn.dataset.key;
        if (!key) return;
        if (window.appContext.scoreboardSortKey === key) {
          window.appContext.scoreboardSortDir = window.appContext.scoreboardSortDir === 'asc' ? 'desc' : 'asc';
        } else {
          window.appContext.scoreboardSortKey = key;
          window.appContext.scoreboardSortDir = 'asc';
        }
        render();
      });
    });
  }
}

// ============================================================================
// VIEW SETUP - Called when entering scoreboard view from navigation
// ============================================================================

export async function setupScoreboardView() {
  const { fetchRaces, fetchParticipants } = window.appContext;
  
  // Load races and participants with timing data for display
  await fetchRaces();
  await fetchParticipants(window.appContext.scoreboardSelectedRaceId, true);
}
