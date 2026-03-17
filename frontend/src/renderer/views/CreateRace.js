export function renderCreateRace() {
  return `
    <div class="page">
      <div class="panel">
        <div class="dark-form-group">
          <label>Race Category</label>
          <select name="race_category" id="race-category-select" required>
            <option value="BPET">BPET</option>
            <option value="CPT">CPT</option>
            <option value="PPT">PPT</option>
          </select>
        </div>
      </div>
      <div class="panel">
        <div class="panel-header">Create Race</div>
        <form id="create-race-form" class="form-grid">
          <div class="dark-form-group">
            <label>Race Name</label>
            <input name="name" required />
          </div>

          <div class="dark-form-group">
            <label>Distance (meters)</label>
            <input name="distance_meters" type="number" min="10" max="100000" required />
          </div>

          <div class="dark-form-group">
            <label>Location</label>
            <input name="location" required />
          </div>

          <div class="dark-form-group">
            <label>RFID Placement Mode</label>
            <select name="rfid_placement_mode" required>
              <option value="mid_end_reader_diff" selected>Mid + End readers (reader differentiation)</option>
              <option value="end_intersection">Dual End antennas (intersection, no mid check)</option>
            </select>
          </div>

          <div class="dark-form-group">
            <label>Scheduled Date</label>
            <input name="scheduled_date" type="date" required />
          </div>

          <div class="dark-form-group">
            <label>Description (Optional)</label>
            <textarea name="description"></textarea>
          </div>
          
          <div style="grid-column: 1 / -1; margin-top: 16px; padding: 12px; background: #1e293b; border-radius: 4px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
              <h3 style="margin: 0; color: #9fb3e5;">Age Category Qualifying Times</h3>
              <div style="display: flex; align-items: center; gap: 8px;">
                <label style="color: #cbd5e1; font-size: 14px;">Unit:</label>
                <select id="time-unit-selector" style="padding: 4px 8px; background: #0f172a; color: #cbd5e1; border: 1px solid #334155; border-radius: 4px;">
                  <option value="seconds">Seconds</option>
                  <option value="minutes" selected>Minutes</option>
                  <option value="hours">Hours</option>
                </select>
              </div>
            </div>
            
            <div style="overflow-x: auto; overflow-y: hidden; border: 1px solid #334155; border-radius: 4px;">
              <div id="qualifying-times-grid" style="min-width: min-content;"></div>
            </div>
          </div>

          <div class="dark-form-group" style="grid-column: 1 / -1;">
            <label>Copy participants from existing race (optional)</label>
            <select id="copy-from-race-id" name="copy_from_race_id">
              <option value="">Do not copy</option>
            </select>
            <div style="margin-top: 6px; color: #94a3b8; font-size: 12px;">Copies name, RFID, age, gender, category, and encryption metadata. Timing fields are left empty.</div>
          </div>
          
          <div class="form-actions" style="grid-column: 1 / -1;">
            <button type="submit" class="dark-btn-primary">Create Race</button>
          </div>
        </form>
      </div>
    </div>
  `;
}