# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MIMO Array Visualizer — a web workbench for evaluating MIMO Tx/Rx antenna arrays of 60/77/92 GHz FMCW radars. A Python FastAPI server runs the computation core (virtual array geometry, 2D array factor, DBF dictionary spectra, angle-estimation metrics, PDF reports); a React + TypeScript client provides the UI. It is deployed on a local server and used from a browser.

## Commands

```bash
# Backend setup
python -m venv .venv && .venv/bin/pip install -e ".[dev]"

# Web client (builds into src/virtual_array/server/static)
cd web && npm ci && npm run build

# Run server (serves API + built client)
.venv/bin/mimo-array-server --host 0.0.0.0 --port 8000 --data-dir ./data

# Frontend dev server with hot reload (proxies /api to :8000)
cd web && npm run dev

# Tests
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/test_server.py -q
cd web && npm test && npx tsc -b
cd web && npm run build && npm run e2e   # Playwright smoke tests (web/e2e) against the real server; MIMO_SERVER overrides the server command

# Lint
.venv/bin/ruff check src tests

# Docker
docker compose up -d --build
```

## Architecture

### Computation core (`src/virtual_array/`, no UI dependencies)

- **`geometry.py`** — `ArrayPoint`, `VirtualPoint`, `AntennaArray`. Core coordinates are in **λ/2 units**.
- **`analysis.py`** — `calculate_metrics_and_psf()` (2D array factor + `ArrayMetrics`), DBF spectrum banks (`dbf_azimuth_spectrum_bank` / `dbf_elevation_spectrum_bank`, 181 true × 181 scan angles), `dbf_angle_metrics_from_spectra()` (no-fold range, errors, peak margin, cut reasons), and `Dbf2dScanner` (reuses the 2D scan dictionary across true angles; `dbf_2d_spectrum` wraps it).
- **`dbf_dictionary.py`** — `DbfDictionaryConfig` (ideal / ideal_reversed / channel_pattern / custom) and CSV/XLSX dictionary tables.
- **`element_pattern.py`** — element patterns and per-channel HFSS amplitude/phase series (`ChannelPatternSet`).
- **`performance_report.py`** — multi-page PDF report, angle-error PNG, CSV/JSON data package (matplotlib).
- **`phasor.py`** — fast `exp(1j*phase)` helper used in hot loops.
- **`EvaluationSettings` / `evaluate_dbf_axis`** (in `analysis.py`) — FOV-bounded true angles, scan = FOV ± 10° guard, refined peaks (`dbf_refine_peak_angles`, 0.002°). The legacy bank functions keep the ±90° grid for backward compatibility.
- **`requirements.py`** — `RequirementSpec` → `check_requirements()` pass/fail list; resolution uses the measured 3 dB beamwidth.

### Service layer

- **`project.py`** — Pydantic `Project` document (schema version 2, coordinates in **λ at the design frequency `frequency_ghz`**), plus `band` (60G/77G/92G presets, sweep range), `fov`, `grid_step_lambda`, `requirements`. `project_array(project, operating_ghz)` scales electrical positions by f/f_design. v1 import keeps exact coordinates (no snapping). Imported files are referenced by asset ID. Converts to the core array via `project_array()` (λ → λ/2). Reads/writes the desktop-era v1 layout JSON (`layout_from_v1`, `layout_to_v1`).
- **`assets.py`** — content-addressed store (`<data>/assets/<sha256>/<original name>`).
- **`engine.py`** — `Engine` turns a project into core objects and returns JSON-ready payloads (`evaluate`, `dbf_bank`, `dbf_2d`, `band_sweep`, `compare`, `dictionary_preview`, `resolve_channel_patterns`, `layout_document`, `report_snapshot`). LRU caches are keyed by the JSON digest of only the fields each result depends on.

### Server (`src/virtual_array/server/`)

- **`app.py`** — `create_app(data_dir, static_dir)`; all routes under `/api` (OpenAPI docs at `/api/docs`); serves the built SPA with index fallback.
- **`store.py`** — file-backed project library (`<data>/projects/*.json`).
- **`shares.py`** — immutable share-link snapshots (`<data>/shares/<id>.json`); the 12-char base62 ID is derived from the project's canonical JSON, so equal configurations share one link. The SPA opens `/s/<id>` via `GET /api/shares/{id}` (`openShareFromLocation` in `state/actions.ts`).
- **`jobs.py`** — background export jobs (PDF report / angle-error PNG) with progress, cancel, download.
- **`cli.py`** — `mimo-array-server` entry point (`--host`, `--port`, `--data-dir`; env `MIMO_DATA_DIR`).

### Web client (`web/src/`)

- `api/` typed client + payload types (mirror `project.py` / `engine.py`).
- `state/store.ts` (zustand: project, undo/redo of layout edits, selection, UI prefs; persisted to localStorage), `state/compute.ts` (debounced evaluation, DBF bank cache), `state/actions.ts` (save/open/import/export), `state/jobs.ts`.
- `views/` — `ArrayView` (SVG `PhysicalEditor` with drag/snap/zoom + `VirtualPlot`), `DbfView` (1D playback, client-side from one bank request), `Dbf2dView` (heatmap, prefetching frame batches), `AngleView`, `BandView` (in-band performance + design comparison).
- `dialogs/` — evaluation settings (band/FOV/requirements/grid), DBF dictionary, channel amp/phase + element pattern, report, project library, help.
- `i18n/messages.ts` — zh/en/ja strings (zh is the reference; a unit test checks keys and placeholders match).
- `charts/` — lazily loaded Plotly wrapper and theme tokens.

### Data Flow

```
Browser edits Project ──POST /api/evaluate──▶ Engine.evaluate ─▶ ArrayMetrics + DBF angle metrics
                      ──POST /api/dbf/bank──▶ FOV true × (FOV±10°) scan spectra + refined peaks → 1D playback in browser
                      ──POST /api/band, /api/compare──▶ in-band sweep / design comparison summaries
                      ──POST /api/dbf/2d────▶ batched 2D frames (Dbf2dScanner)
                      ──POST /api/reports───▶ background job → PDF/zip download
```

## Conventions

- Project/API coordinates are λ at the design frequency; the core uses λ/2. Convert only in `project_array()`.
- All angle evaluation goes through `EvaluationSettings` built from `project.fov` (`engine.evaluation_settings`); do not call the ±90° bank functions directly from new service code.
- Channel names derive from list order (`Tx1…`, `Rx1…`); the client renumbers by (x, y) after every edit, like the desktop tool.
- Imported channel phase (HFSS far-field) already contains the geometric phase, so it is the channel response for its plane in both DBF and array-factor metrics (`_channel_response`); geometric steering is kept only for a plane without imported phase, with the sign from `_imported_phase_sign`.
- Non-finite numbers travel as `"Infinity"` / `"-Infinity"` strings; large matrices as `{dtype, shape, data(base64)}`.
- Keep core numerics unchanged when refactoring — the analysis tests pin them.
- Tests use `examples/case4_5tx7rx_sel.py::build_array()` (also the default project) as the reference layout.
