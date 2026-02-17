import { showToast } from '../utils/Toasts.js';

// ============================================================================
// RACES MANAGEMENT - API OPERATIONS
// ============================================================================

export async function updateRace(raceId, updates) {
  const { state, globalLoader, apiRequest, render } = window.appContext;
  
  try {
    await globalLoader.wrap(async () => {
      await apiRequest(`/race/${raceId}`, {
        method: 'PATCH',
        body: updates,
      });
    });

    showToast("Race updated successfully", 'success');
    await apiRequest('/race').then(data => {
      state.races = data || [];
    });
    
    setTimeout(() => {
      render();
    }, 500);
  } catch (err) {
    console.error(err);
    showToast(`Failed to update race: ${err.message}`, 'error');
    throw err;
  }
}

export async function deleteRace(raceId) {
  const { state, globalLoader, apiRequest, render } = window.appContext;
  
  if (!confirm('Are you sure you want to delete this race? This action cannot be undone.')) {
    return;
  }
  
  try {
    await globalLoader.wrap(async () => {
      await apiRequest(`/race/${raceId}`, {
        method: 'DELETE',
      });
    });

    showToast('Race deleted successfully', 'success');
    const races = await apiRequest('/race');
    state.races = races || [];
    state.view = 'races-management';
    
    setTimeout(() => {
      render();
    }, 500);
  } catch (err) {
    console.error(err);
    showToast(`Failed to delete race: ${err.message}`, 'error');
    throw err;
  }
}

export async function endRace(raceId) {
  const { state, globalLoader, apiRequest, render } = window.appContext;
  
  try {
    await globalLoader.wrap(async () => {
      await apiRequest(`/race/${raceId}/end`, {
        method: 'POST',
      });
    });

    showToast('Race ended successfully', 'success');
    const races = await apiRequest('/race');
    state.races = races || [];
    
    setTimeout(() => {
      render();
    }, 500);
  } catch (err) {
    console.error(err);
    showToast(`Failed to end race: ${err.message}`, 'error');
    throw err;
  }
}

// ============================================================================
// RACES MANAGEMENT - UI OPERATIONS
// ============================================================================

export function openRaceEditModal(race) {
  const { state, render } = window.appContext;
  
  if (!race) return;

  const modalContainer = document.createElement('div');
  modalContainer.innerHTML = `
    <div class="dark-modal-overlay" style="display: flex;">
      <div class="dark-modal" style="max-width: 650px;">
        <div class="dark-modal-header">
          <div style="display: flex; align-items: center; gap: 12px;">
            <div style="width: 42px; height: 42px; background: linear-gradient(135deg, #00d4ff 0%, #0099ff 100%); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 20px;">🏁</div>
            <h2 style="margin: 0; font-size: 22px; font-weight: 700; color: #e2e8f0;">Edit Race</h2>
          </div>
          <button class="dark-modal-close" data-action="close">&times;</button>
        </div>
        <form data-action="form" style="margin-top: 24px;">
          <div class="race-modal-body" style="display:flex; gap:16px; align-items:flex-start;">
            <div class="race-panel" style="flex:1; min-width:260px;">
              <div class="dark-form-group">
                <label style="display: flex; align-items: center; gap: 6px; margin-bottom: 8px;">
                  <span style="color: #cbd5e1; font-weight: 600; font-size: 13px;">🏆 Race Name</span>
                  <span style="color: #ef4444; font-weight: 700;">*</span>
                </label>
                <input type="text" data-field="name" required style="padding: 12px 14px; font-size: 15px; border-radius: 6px; border: 2px solid #334155; transition: all 0.3s ease; width:100%;">
              </div>

              <div class="dark-form-group">
                <label style="display: flex; align-items: center; gap: 6px; margin-bottom: 8px;">
                  <span style="color: #cbd5e1; font-weight: 600; font-size: 13px;">📝 Description</span>
                  <span style="color: #64748b; font-size: 12px; font-weight: 400;">(optional)</span>
                </label>
                <textarea data-field="description" rows="6" style="padding: 12px 14px; font-size: 14px; border-radius: 6px; border: 2px solid #334155; resize: vertical; min-height: 120px; line-height: 1.5; transition: all 0.3s ease; width:100%;"></textarea>
              </div>
            </div>

            <div class="race-panel" style="flex:1; min-width:260px;">
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 12px;">
                <div class="dark-form-group">
                  <label style="display: flex; align-items: center; gap: 6px; margin-bottom: 8px;">
                    <span style="color: #cbd5e1; font-weight: 600; font-size: 13px;">📏 Distance (m)</span>
                    <span style="color: #ef4444; font-weight: 700;">*</span>
                  </label>
                  <input type="number" data-field="distance_meters" required style="padding: 12px 14px; font-size: 15px; border-radius: 6px; border: 2px solid #334155; transition: all 0.3s ease; width:100%;">
                </div>

                <div class="dark-form-group">
                  <label style="display: flex; align-items: center; gap: 6px; margin-bottom: 8px;">
                    <span style="color: #cbd5e1; font-weight: 600; font-size: 13px;">📅 Scheduled Date</span>
                    <span style="color: #ef4444; font-weight: 700;">*</span>
                  </label>
                  <input type="date" data-field="scheduled_date" required style="padding: 12px 14px; font-size: 15px; border-radius: 6px; border: 2px solid #334155; transition: all 0.3s ease; width:100%;">
                </div>
              </div>

              <div class="dark-form-group">
                <label style="display: flex; align-items: center; gap: 6px; margin-bottom: 8px;">
                  <span style="color: #cbd5e1; font-weight: 600; font-size: 13px;">📍 Location</span>
                  <span style="color: #ef4444; font-weight: 700;">*</span>
                </label>
                <input type="text" data-field="location" required style="padding: 12px 14px; font-size: 15px; border-radius: 6px; border: 2px solid #334155; transition: all 0.3s ease; width:100%;">
              </div>
            </div>
          </div>

          <div style="display: flex; gap: 12px; justify-content: flex-end; margin-top: 24px; padding-top: 16px; border-top: 1px solid #334155;">
            <button type="button" data-action="cancel" class="dark-btn-secondary" style="padding: 12px 28px; font-size: 15px; font-weight: 600; border-radius: 6px;">Cancel</button>
            <button type="submit" class="dark-btn-primary" style="padding: 12px 28px; font-size: 15px; border-radius: 6px; display: flex; align-items: center; gap: 8px;">
              <span>💾</span>
              <span>Save Race</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  `;

  document.body.appendChild(modalContainer);
  const overlay = modalContainer.querySelector('.dark-modal-overlay');
  const closeBtn = modalContainer.querySelector('[data-action="close"]');
  const cancelBtn = modalContainer.querySelector('[data-action="cancel"]');
  const form = modalContainer.querySelector('[data-action="form"]');

  const cleanup = () => {
    modalContainer.remove();
  };

  if (closeBtn) closeBtn.addEventListener('click', cleanup);
  if (cancelBtn) cancelBtn.addEventListener('click', cleanup);
  if (overlay) {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) cleanup();
    });
  }

  const nameEl = modalContainer.querySelector('[data-field="name"]');
  const distanceEl = modalContainer.querySelector('[data-field="distance_meters"]');
  const locationEl = modalContainer.querySelector('[data-field="location"]');
  const scheduledEl = modalContainer.querySelector('[data-field="scheduled_date"]');
  const descriptionEl = modalContainer.querySelector('[data-field="description"]');

  if (nameEl) nameEl.value = race.name || '';
  if (distanceEl) distanceEl.value = race.distance_meters || '';
  if (locationEl) locationEl.value = race.location || '';
  if (scheduledEl && race.scheduled_date) {
    const d = new Date(race.scheduled_date);
    scheduledEl.value = d.toISOString().split('T')[0];
  }
  if (descriptionEl) descriptionEl.value = race.description || '';

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const updates = {
        name: nameEl.value.trim(),
        distance_meters: Number(distanceEl.value),
        location: locationEl.value.trim(),
        scheduled_date: scheduledEl.value,
        description: descriptionEl.value.trim(),
      };
      cleanup();
      await updateRace(race.id, updates);
    });
  }
}

export function attachRacesManagementHandlers() {
  const { state, render, fetchRaces } = window.appContext;
  
  if (state.view !== 'races-management') return;

  // Create New Race Button
  const createNewRaceBtn = document.getElementById('create-new-race-btn');
  if (createNewRaceBtn) {
    createNewRaceBtn.addEventListener('click', async () => {
      state.view = 'create';
      state.showRaceModal = false;
      await fetchRaces();
      render();
    });
  }

  // Race category filter
  const CategoryFilterSelect = document.getElementById('race-category-filter');
  if (CategoryFilterSelect) {
    CategoryFilterSelect.addEventListener('change', (e) => {
      state.raceCategoryFilter = e.target.value;
      render();
    });
  }

  // Edit Race Button
  const editRaceBtns = document.querySelectorAll('.edit-race-btn');
  editRaceBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const raceId = btn.dataset.raceId;
      const race = state.races.find(r => r.id === raceId);
      if (!race) {
        showToast('Race not found', 'error');
        return;
      }
      openRaceEditModal(race);
    });
  });

  // Delete Race Button
  const deleteRaceBtns = document.querySelectorAll('.delete-race-btn');
  deleteRaceBtns.forEach(btn => {
    btn.addEventListener('click', async () => {
      const raceId = btn.dataset.raceId;
      await deleteRace(raceId);
    });
  });

  // End Race Button
  const endRaceBtns = document.querySelectorAll('.end-race-btn');
  endRaceBtns.forEach(btn => {
    btn.addEventListener('click', async () => {
      const raceId = btn.dataset.raceId;
      await endRace(raceId);
    });
  });
}

// ============================================================================
// VIEW SETUP - Called when entering races management view from navigation
// ============================================================================

export async function setupRacesManagementView() {
  const { fetchRaces } = window.appContext;
  
  // Load races for display
  await fetchRaces();
}
