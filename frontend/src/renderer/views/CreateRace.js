export function renderCreateRace() {
  const config = window.appContext?.state?.config || {};
  const defaultPrefix = String(config.rfidDefaultPrefix || '2').trim();

  const parsedDigits = Number(config.rfidDefaultSuffixDigits);
  const defaultSuffixDigits = Number.isFinite(parsedDigits)
    ? Math.min(12, Math.max(1, Math.floor(parsedDigits)))
    : 3;

  const parsedStart = Number(config.rfidDefaultSuffixStartNumber);
  const defaultSuffixStart = Number.isFinite(parsedStart)
    ? Math.max(0, Math.floor(parsedStart))
    : 130;

  const today = new Date();
  const defaultScheduledDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
  const initialPreview = `${defaultPrefix}${String(defaultSuffixStart).padStart(defaultSuffixDigits, '0')}`;

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
            <label>Scheduled Date</label>
            <input name="scheduled_date" type="date" value="${defaultScheduledDate}" required />
          </div>

          <div class="dark-form-group">
            <label>RFID Placement Mode</label>
            <select name="rfid_placement_mode" required>
              <option value="end_intersection" selected>Dual End antennas (intersection, no mid check)</option>
              <option value="mid_end_reader_diff">Mid + End readers (reader differentiation)</option>
            </select>
          </div>

          <div class="dark-form-group">
            <label>Location (Optional)</label>
            <input name="location" />
          </div>
          
          <div class="dark-form-group">
            <label>Description (Optional)</label>
            <textarea name="description"></textarea>
          </div>

          <div id="rfid-settings-panel" class="panel" style="grid-column: 1 / -1; margin-top: 16px; padding: 12px; border-radius: 4px;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;">
              <h3 style="margin: 0; color: #9fb3e5; font-size: 15px;">Rfid tag allotment settings</h3>
              <button
                type="button"
                id="rfid-settings-edit-btn"
                title="Enable editing"
                style="border: 1px solid #475569; background: #0f172a; color: #cbd5e1; border-radius: 4px; width: 30px; height: 30px; cursor: pointer;"
              >
                ✎
              </button>
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px;">
              <div class="dark-form-group" style="margin: 0;">
                <label>RFID Auto Prefix (Bulk Upload)</label>
                <input
                  id="rfid-prefix-input"
                  name="rfid_prefix"
                  value="${defaultPrefix}"
                  required
                  disabled
                  style="background: #334155; color: #94a3b8; border: 1px solid #475569; cursor: not-allowed;"
                />
              </div>

              <div class="dark-form-group" style="margin: 0;">
                <label>RFID Auto Suffix Digits</label>
                <input
                  id="rfid-suffix-digits-input"
                  name="rfid_suffix_digits"
                  type="number"
                  min="1"
                  max="12"
                  value="${defaultSuffixDigits}"
                  required
                  disabled
                  style="background: #334155; color: #94a3b8; border: 1px solid #475569; cursor: not-allowed;"
                />
              </div>

              <div class="dark-form-group" style="margin: 0;">
                <label>RFID Suffix Start Number</label>
                <input
                  id="rfid-suffix-start-number-input"
                  name="rfid_suffix_start_number"
                  type="number"
                  min="0"
                  value="${defaultSuffixStart}"
                  required
                  disabled
                  style="background: #334155; color: #94a3b8; border: 1px solid #475569; cursor: not-allowed;"
                />
              </div>
            </div>
            <div style="margin-top: 8px;">
              <label style="color: #94a3b8; font-size: 12px;">First auto-assigned RFID:</label>
              <div id="rfid-preview-value" style="margin-top: 4px; color: #cbd5e1; font-family: monospace; font-size: 13px;">${initialPreview}</div>
            </div>
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