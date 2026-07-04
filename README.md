# MIMO Array Visualizer

MIMO Array Visualizer is a desktop tool for editing and evaluating MIMO Tx/Rx
antenna layouts. It computes the virtual array, aperture and resolution metrics,
azimuth/elevation sidelobe indicators, and front-radar azimuth response.

The app is aimed at quick antenna-layout iteration: move elements on a grid,
load an element-pattern CSV, inspect the response, and export a readable layout
JSON for later use.

## Features

- Interactive Tx/Rx layout editor with add, delete-mode, clear, auto-place by
  Tx/Rx count, drag, and snap-to-grid.
- Clean 1T1R starter layout by default instead of a preloaded MIMO preset.
- Undo/redo for layout edits, plus keyboard shortcuts for common actions.
- Virtual-array visualization with duplicate-channel statistics.
- Array evaluation panel for aperture, resolution, 3 dB beamwidth, PSL, ISLR,
  grating-lobe and elevation-ambiguity indicators.
- Custom frequency input with GHz suffix parsing, plus configurable DBF
  competitor-peak margin threshold.
- DBF dictionary spectrum animation for azimuth and elevation, with draggable
  progress sliders over 181 true angles from -90 deg to +90 deg in 1 deg steps.
- 2D DBF heatmap in the evaluation panel, with independent azimuth/elevation
  sliders and playback controls for combined angle scanning.
- Configurable DBF dictionary modes, including ideal, phase-reversed,
  channel-pattern calibrated, and imported azimuth/elevation CSV/XLSX
  dictionary matrices with tabular preview.
- HFSS channel-pattern CSV import for per-physical-channel amplitude and phase,
  with separate H/E plane files and summary-column mapping.
- Readable JSON layout import/export with optional evaluation metadata.
- Local cache for last used paths, frequency, window geometry, and the last
  edited array layout.
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

## Keyboard Shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl+Z` | Undo layout edit |
| `Ctrl+Y` / `Ctrl+Shift+Z` | Redo layout edit |
| `Ctrl+S` | Export layout |
| `Ctrl+O` | Import layout |
| `Ctrl+G` / `Ctrl+R` | Refresh analysis |
| `Ctrl+F` | Focus frequency input |
| `Delete` | Delete selected element or enter delete mode |
| `Escape` | Clear selection / exit delete mode |

## DBF Angle Spectra

The azimuth and elevation response panels can each play a conventional
DBF/Bartlett-style dictionary spectrum over the virtual-array positions.
When no animation is playing, both panels show the `0 deg` true-angle DBF
reference spectrum.

Use the compact **Play** button under each 1D DBF plot. Each animation has 181
frames. Every frame simulates one true incoming angle from `-90 deg` to
`+90 deg` in `1 deg` steps, multiplies that phase vector by the beamforming
dictionary, and plots the resulting angle spectrum.

The active button changes to **Pause** while playing. Click it to pause on the
current spectrum, then click **Resume** to continue. Drag either full-width
progress slider under the DBF plots to jump to a frame; the animation pauses at
the selected true angle. Use **Stop** to return to the normal response view.
The toolbar **Peak margin (dB)** input controls the competitor-peak margin
threshold used by the no-fold ambiguity evaluation.

Use **Configuration -> Configure DBF Dictionary** to choose the DBF dictionary.
The channel-pattern dictionary uses the configured channel amplitude/phase data
with a 0 deg phase reference. Imported CSV/XLSX dictionaries are loaded
separately for azimuth and elevation. Each file may provide one row per angle
with either virtual channel columns or physical Tx/Rx columns. Numeric values are
treated as phase degrees; complex values such as `1+0.2j` are treated as channel
responses. Imported dictionaries are raw by default, with optional phase reversal
and optional 0 deg phase calibration in the dictionary dialog. The preview shows
the active axis as an angle-by-channel matrix.

The right-side evaluation panel also includes a 2D DBF heatmap. The horizontal
slider selects the true azimuth angle and the vertical slider selects the true
elevation angle. Each axis can play or pause independently, so one axis can stay
fixed while the other scans, or both axes can scan at the same time.

## Layout Editing

Use the buttons in the Physical Array panel to add Tx/Rx elements, clear the
current layout back to a 1T1R starter layout, or enter delete mode. In delete
mode, each clicked Tx/Rx element is removed immediately and the remaining Tx/Rx
names are renumbered by position without gaps. Press `Escape` to exit delete
mode.

The physical canvas starts from a clean 1T1R layout. Dragged elements snap to
the grid live, with a highlighted snap target and guide lines while dragging.
Use the bottom toolbar `Auto` T/R inputs and **Apply Array** to generate a
centered Tx row and Rx row for common quick-start layouts.

Use the **Configuration** menu for array JSON import/export and channel
amplitude/phase CSV setup. Use the **Language** menu to switch the UI between
Chinese, English, and Japanese.

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

## Channel Pattern CSV

Use **Configuration → Set Channel Amp/Phase CSV** to configure HFSS amplitude
and phase patterns for physical Tx/Rx channels. The dialog supports:

- summary amplitude/phase CSV files for H and E planes,
- per-channel amplitude/phase CSV files for H and E planes,
- clearing one channel or all channel-pattern data.

For summary files, data columns after `Theta [deg]` map left-to-right by
physical-channel order: all Tx channels from small to large, then all Rx
channels from small to large. For a 2T2R layout that means `Tx1`, `Tx2`, `Rx1`,
`Rx2`.

Amplitude values are treated as dB and phase values as degrees. Phase curves are
unwrapped, calibrated by subtracting each physical channel's `0 deg` phase, and
then interpolated. Loaded channel patterns are applied as complex
physical-channel weights; each virtual channel uses the product of its Tx weight
and Rx weight. In DBF spectra the scan dictionary stays geometry-based, while
the true-angle signal vector uses the CSV amplitude/phase value at that true
angle. When HFSS phase patterns are loaded, the DBF steering sign is selected
automatically from `-1/+1` using the lower angle-estimation RMS, matching the
postprocess workflow. Requested DBF angles must be inside the CSV `Theta [deg]`
range; the app does not silently clamp out-of-range angles. With no channel
patterns loaded, channels are treated as ideal.

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
