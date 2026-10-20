# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MIMO Array Visualizer — a web workbench for interactively editing and evaluating MIMO Tx/Rx antenna array layouts. A Python FastAPI server runs the computation core (virtual array geometry, 2D array factor, DBF dictionary spectra, angle-estimation metrics, PDF reports); a React + TypeScript client provides the UI. It is deployed on a local server and used from a browser.

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

### Service layer

- **`project.py`** — Pydantic `Project` document (schema version 2, coordinates in **λ**, grid 0.5 λ). Imported files are referenced by asset ID. Converts to the core array via `project_array()` (λ → λ/2). Reads/writes the desktop-era v1 layout JSON (`layout_from_v1`, `layout_to_v1`).
- **`assets.py`** — content-addressed store (`<data>/assets/<sha256>/<original name>`).
- **`engine.py`** — `Engine` turns a project into core objects and returns JSON-ready payloads (`evaluate`, `dbf_bank`, `dbf_2d`, `dictionary_preview`, `resolve_channel_patterns`, `layout_document`, `report_snapshot`). LRU caches are keyed by the JSON digest of only the fields each result depends on.

### Server (`src/virtual_array/server/`)

- **`app.py`** — `create_app(data_dir, static_dir)`; all routes under `/api` (OpenAPI docs at `/api/docs`); serves the built SPA with index fallback.
- **`store.py`** — file-backed project library (`<data>/projects/*.json`).
- **`jobs.py`** — background export jobs (PDF report / angle-error PNG) with progress, cancel, download.
- **`cli.py`** — `mimo-array-server` entry point (`--host`, `--port`, `--data-dir`; env `MIMO_DATA_DIR`).

### Web client (`web/src/`)

- `api/` typed client + payload types (mirror `project.py` / `engine.py`).
- `state/store.ts` (zustand: project, undo/redo of layout edits, selection, UI prefs; persisted to localStorage), `state/compute.ts` (debounced evaluation, DBF bank cache), `state/actions.ts` (save/open/import/export), `state/jobs.ts`.
- `views/` — `ArrayView` (SVG `PhysicalEditor` with drag/snap/zoom + `VirtualPlot`), `DbfView` (1D playback, client-side from one bank request), `Dbf2dView` (heatmap, prefetching frame batches), `AngleView`.
- `dialogs/` — DBF dictionary, channel amp/phase + element pattern, report, project library, help.
- `i18n/messages.ts` — zh/en/ja strings (zh is the reference; a unit test checks keys and placeholders match).
- `charts/` — lazily loaded Plotly wrapper and theme tokens.

### Data Flow

```
Browser edits Project ──POST /api/evaluate──▶ Engine.evaluate ─▶ ArrayMetrics + DBF angle metrics
                      ──POST /api/dbf/bank──▶ 181×181 spectra (base64 float32) → 1D playback in browser
                      ──POST /api/dbf/2d────▶ batched 2D frames (Dbf2dScanner)
                      ──POST /api/reports───▶ background job → PDF/zip download
```

## Conventions

- Project/API coordinates are λ; the core uses λ/2. Convert only in `project_array()`.
- Channel names derive from list order (`Tx1…`, `Rx1…`); the client renumbers by (x, y) after every edit, like the desktop tool.
- Non-finite numbers travel as `"Infinity"` / `"-Infinity"` strings; large matrices as `{dtype, shape, data(base64)}`.
- Keep core numerics unchanged when refactoring — the analysis tests pin them.
- Tests use `examples/case4_5tx7rx_sel.py::build_array()` (also the default project) as the reference layout.
