# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MIMO Array Visualizer — a Python desktop application (Tkinter + embedded Matplotlib) for interactively editing and evaluating MIMO Tx/Rx antenna array layouts. Computes virtual array geometry, 2D array factor, and radar-performance metrics (PSL, beamwidth, ISLR, grating lobes, elevation ambiguity).

## Commands

```bash
# Setup (PowerShell)
.\scripts\setup.ps1

# Run GUI
.\.venv\Scripts\python.exe GUI.py
# or
.\.venv\Scripts\python.exe -m virtual_array.gui

# Run tests
.\.venv\Scripts\python.exe -m pytest tests/ -x -q

# Run a single test file
.\.venv\Scripts\python.exe -m pytest tests/test_analysis.py -x -q

# Build Windows EXE
.\scripts\build_exe.ps1
# or
.\.venv\Scripts\pyinstaller.exe MIMOArrayVisualizer.spec --noconfirm
```

## Architecture

**`src/` layout** — all source lives under `src/virtual_array/`. `GUI.py` at the repo root is a thin launcher that adds `src/` to `sys.path` and calls `virtual_array.gui:main()`.

### Core Modules

- **`geometry.py`** — Frozen dataclasses `ArrayPoint(name, x, y)`, `VirtualPoint(tx_name, rx_name, x, y)`, and `AntennaArray`. All coordinates are in λ units. `AntennaArray` owns tuples of Tx/Rx points and provides `virtual_points()`, `unique_virtual_xy()` (with multiplicity counting).

- **`analysis.py`** — All signal processing. Central entry: `calculate_metrics_and_psf(array, ...)` → `(af_db, azimuths, elevations, ArrayMetrics)`. Computes 2D array factor via `exp(j*phase)` summation, optional element-pattern weighting (Tx×Rx). `ArrayMetrics` has 30+ fields (aperture, resolution, beamwidth, PSL, ISLR, grating lobe, front-radar grading, elevation ambiguity, warnings).

- **`element_pattern.py`** — `ElementPattern` frozen dataclass for antenna radiation patterns loaded from CSV/TSV. Auto-detects delimiter, angle column (theta/angle/azimuth/az/deg), and gain columns (gain/db/dbi/realized). Provides interpolated gain lookup and H/V axis swap.

- **`gui.py`** — `VirtualArrayGui` class (~2300 lines). Layout: 2×2 Matplotlib figure grid (Physical, Virtual, Az Response, El Response) + Tkinter evaluation panel + controls bar. Uses `ResponseChart` dataclass to encapsulate per-axis chart state. Interactive: drag elements with snap-to-grid, add/delete Tx/Rx (max 16 each), hover tooltips, element-pattern preview dialog, JSON layout I/O.

- **`plotting.py`** — Standalone matplotlib functions for CLI PNG export (not used by GUI).

### Supporting Modules

- **`app_state.py`** — JSON persistence to `%APPDATA%/antenna-array/state.json` (atomic write via temp+rename).
- **`logging_config.py`** — Rotating file handler (1 MB, 5 backups) to `%APPDATA%/antenna-array/logs/`. Env override: `ANTENNA_ARRAY_LOG_DIR`.
- **`grid.py`** — `GRID_STEP = 1.0`, `snap_to_grid()`.
- **`examples/case4_5tx7rx_sel.py`** — Reference 8Tx/8Rx array. `build_array()` is the default GUI starting layout and primary test fixture.

### Data Flow

```
AntennaArray → calculate_metrics_and_psf() → (af_db, azimuths, elevations, ArrayMetrics)
                                                  ↓
                            _draw_physical_array / _draw_virtual_array / _draw_response
                                                  ↓
                            _update_evaluation_panel (Tkinter widgets)
```

## Conventions

- All antenna coordinates stored in λ (wavelength) units internally; converted to mm for display via `wavelength_mm()`.
- Layout JSON schema: `{"version": 1, "unit": "lambda", "tx": [...], "rx": [...], "evaluation": {...}}`.
- `ArrayMetrics.front_radar_status` grades: "Good" / "Acceptable" / "Risky" / "Bad" — color-coded in the UI.
- GUI theme constants are centralized in the `THEME` dict at the top of `gui.py`.
- Matplotlib figures use `draw_idle()` (not `draw()`) for non-blocking UI updates.
- Tests use the `build_array()` fixture from `examples/case4_5tx7rx_sel.py` as the standard reference layout.
