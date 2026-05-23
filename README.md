# MIMO Array Visualizer

MIMO Array Visualizer is a desktop tool for editing and evaluating MIMO Tx/Rx
antenna layouts. It computes the virtual array, aperture and resolution metrics,
azimuth/elevation sidelobe indicators, and front-radar azimuth response.

The app is aimed at quick antenna-layout iteration: move elements on a grid,
load an element-pattern CSV, inspect the response, and export a readable layout
JSON for later use.

## Features

- Interactive Tx/Rx layout editor with add, delete, drag, and snap-to-grid.
- Virtual-array visualization with duplicate-channel statistics.
- Array evaluation panel for aperture, resolution, 3 dB beamwidth, PSL, ISLR,
  grating-lobe and elevation-ambiguity indicators.
- Element-pattern CSV import with preview and horizontal/elevation swap support.
- Readable JSON layout import/export with optional evaluation metadata.
- Local cache for last used paths and the last edited array layout.
- PyInstaller onedir packaging for a faster-starting Windows executable.

## Quick Start

PowerShell:

```powershell
.\scripts\setup.ps1
.\scripts\run_gui.ps1
```

If PowerShell blocks script execution in the current terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup.ps1
.\scripts\run_gui.ps1
```

You can also run the entry script directly:

```powershell
.\.venv\Scripts\python.exe GUI.py
```

## Packaged EXE

The packaged Windows build is generated as an onedir app:

```text
dist/MIMOArrayVisualizer/MIMOArrayVisualizer.exe
```

To rebuild it locally:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[packaging]"
.\scripts\build_exe.ps1
```

The `dist/` folder is ignored by git. For public distribution, upload the
contents of `dist/MIMOArrayVisualizer/` as a GitHub Release asset instead of
committing binaries to the repository.

## Layout JSON

Exported layouts use readable Tx/Rx entries:

```json
{
  "version": 1,
  "unit": "lambda",
  "tx": [
    {"name": "Tx1", "x": -9, "y": -12}
  ],
  "rx": [
    {"name": "Rx1", "x": -9, "y": 0}
  ],
  "evaluation": {
    "frequency_mode": "77 GHz"
  }
}
```

The app reads `tx` and `rx` for import. The `evaluation` block is exported for
traceability and can be ignored on import.

## Element Pattern CSV

Use **Load Pattern** in the azimuth-response panel to import an element-pattern
CSV. The app opens a preview dialog before applying the pattern, showing:

- horizontal and elevation cuts from -180 deg to 180 deg,
- peak gain direction,
- 3 dB beamwidth,
- 6 dB beamwidth.

The preview includes a **Swap H/V** button for CSV files that use a different
phi/elevation convention.

## Development

Run tests:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Useful entry points after installation:

```powershell
mimo-array-visualizer
mimo-array-case4
```

Legacy aliases are kept for compatibility:

```powershell
virtual-array-gui
virtual-array-case4
```

## Publishing to GitHub

Suggested repository name:

```text
mimo-array-visualizer
```

Before publishing, choose a license. If you want broad reuse with minimal
friction, MIT is a common choice, but the final license choice should be yours.
