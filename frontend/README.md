# RFID Marathon Management System - Frontend

Electron desktop client for race creation, runner registration, race start control, scoreboard review, and results export against the v2 backend.

## Current Scope

- Login against the backend API and keep auth in app state.
- Create and edit races from the desktop UI.
- Configure race category qualifying thresholds.
- Configure RFID placement mode per race before start.
- Start races with frontend-selected start times.
- View race-start progress and scoreboard data.
- Export scoreboard results to Excel, Word, and PDF.

## RFID Placement Modes

The frontend now supports two race timing modes:

- `mid_end_reader_diff`: runners are expected to hit both mid and end readers.
- `end_intersection`: runners are evaluated without a mid checkpoint.

Mode affects the UI and exports:

- Create Race includes an RFID placement mode selector.
- Race edit allows mode changes only while the race is still in `created` status.
- Race Start shows a mode label and provides a mode edit action before start.
- Race Start statistics and candidate columns hide the mid-point section for `end_intersection`.
- Scoreboard hides the `Mid Time` column for `end_intersection`.
- Excel, Word, and PDF exports omit the `Mid Time` column for `end_intersection`.

## Race Start Behavior

When a race is started from the frontend:

- The selected start time is combined with the selected race date without UTC date shifting.
- The frontend sends `scheduled_date` in the start request body.
- If the backend detects that the incoming scheduled date differs from the stored race date, it updates the database before timing proceeds.

This avoids the earlier issue where edited race dates could produce an incorrect duration near 24 hours at start.

## Scoreboard Export Behavior

The frontend supports three export formats from the scoreboard screen:

- Excel via `buildXlsx`
- Word via `buildDocx`
- PDF via `buildPdf`

Recent export updates:

- Export columns follow the active race mode.
- Word tables use fixed column widths and landscape page layout.
- PDF tables use measured text wrapping and landscape layout.
- Long cell content wraps instead of spilling into adjacent columns.

## Validation and Error Handling

The renderer now surfaces backend validation details more clearly:

- API helpers normalize backend error payloads.
- Request validation errors are shown with field-level messages when available.
- UI toasts include backend error codes when present.

This is applied across race creation, race updates, candidate registration, candidate updates, candidate deletion, and bulk upload flows.

## Bulk RFID Test Sender

For backend timing tests, use [backend/v2/send_test_tag.py](../backend/v2/send_test_tag.py).

What it does:

- Builds dummy RFID tag-read payloads in the same shape used by the listener flow.
- Converts them into a bulk request for `/api/v2/rfid/bulk`.
- Infers `reader_id` from `READER_NAME`.
- Prints the resolved timing point and reader ID before posting.

Example configuration inside the script:

- `START_COUNT`
- `END_COUNT`
- `READER_NAME`
- `BULK_ENDPOINT_URL`
- `DRY_RUN`

Common mapping:

- `Reader 2` -> mid -> `reader_id = 2`
- `Reader 3` -> end -> `reader_id = 3`

## Frontend Structure

```text
frontend/
├── src/
│   ├── main/
│   ├── preload.js
│   ├── renderer/
│   │   ├── app.js
│   │   ├── services/
│   │   └── views/
│   ├── index.js
│   └── index.css
├── public/
└── package.json
```

Key frontend areas:

- `src/preload.js`: exposes secure export helpers to the renderer.
- `src/renderer/app.js`: shared API request and error parsing helpers.
- `src/renderer/views/CreateRace.js`: race creation form and RFID mode selector.
- `src/renderer/services/RaceStart.js`: race start date handling, mode-aware polling, and mode editing.
- `src/renderer/views/Scoreboard.js`: mode-aware scoreboard columns.
- `src/renderer/services/Scoreboard.js`: mode-aware export builders.

## Environment Setup

1. Install dependencies:

```bash
cd frontend
npm install
```

2. Configure environment values as needed for the desktop app.

Typical backend base URL:

```text
VITE_API_BASE_URL=http://localhost:8000/api/v2
```

3. Start the frontend in development:

```bash
npm run dev
```

4. Build the desktop app:

```bash
npm run build
```

## Manual Test Checklist

### Race Mode

1. Create a race in `mid_end_reader_diff` and confirm Race Start and Scoreboard show `Mid Time`.
2. Create a race in `end_intersection` and confirm Race Start and Scoreboard hide `Mid Time`.
3. Edit a race in `created` status and confirm mode can be changed.
4. Start the race and confirm mode editing is disabled afterward.

### Race Start Date Sync

1. Edit a race scheduled date.
2. Start the race with a frontend-selected time.
3. Confirm duration starts from the correct date context.
4. Confirm the backend stores the updated scheduled date only when it differs.

### Exports

1. Export a scoreboard in Excel, Word, and PDF.
2. Confirm `Mid Time` is omitted for `end_intersection`.
3. Confirm long names wrap correctly in Word and PDF exports.

### Bulk RFID Test

1. Set `READER_NAME` in [backend/v2/send_test_tag.py](../backend/v2/send_test_tag.py).
2. Run the sender against the v2 backend.
3. Confirm the printed `reader_id` matches the intended timing point.
4. Confirm the backend log shows the same `reader_id`.

## Status

- Frontend is running against the v2 API surface.
- Mode-aware race flow is implemented.
- Mode-aware scoreboard exports are implemented.
- Word and PDF export wrapping is implemented.
- Validation error messages are surfaced more clearly in the UI.

**Last Updated**: March 17, 2026  
**Version**: 2.0.0  
**Status**: Completed development
