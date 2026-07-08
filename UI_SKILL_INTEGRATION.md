# UI Skill Integration Notes

This note records the professional UI skills and references used for the PR #3
interface pass, plus the items that were actually integrated into the desktop
GUI.

## Researched Professional UI Skills

| Skill | Source | Useful principle |
| --- | --- | --- |
| Visual hierarchy | [Nielsen Norman Group, Visual Design](https://www.nngroup.com/topic/visual-design/) | Use scale, contrast, grouping, and consistency so users can scan the most important information first. |
| Responsive grid layout | [Material Design, Responsive Layout Grid](https://m2.material.io/design/layout/responsive-layout-grid.html) | Use grid columns, margins, and responsive sizing to keep layouts stable across window sizes. |
| Dashboard information density | [Carbon Design System, Dashboards](https://carbondesignsystem.com/data-visualization/dashboards/) | Reduce distraction, limit nonessential information, and keep metric/color semantics consistent. |
| Chart anatomy and interaction affordances | [Carbon Design System, Chart Anatomy](https://carbondesignsystem.com/data-visualization/chart-anatomy/) | Keep chart title, axes, legends, frames, tooltips, and controls legible and consistently placed. |
| Non-text contrast and component states | [W3C WAI, Non-text Contrast](https://www.w3.org/WAI/WCAG21/Understanding/non-text-contrast.html) | UI component boundaries, states, and graphical marks need enough contrast to be distinguishable. |
| Gestalt grouping and proximity | [Nielsen Norman Group, Visual Design Principles](https://www.nngroup.com/videos/visual-design-principles-in-action/) | Related controls and metrics should live in clear groups so the interface can be read without extra explanation. |

## Integrated Into This Project

| Integrated skill | Implementation in `src/virtual_array/gui.py` |
| --- | --- |
| Visual hierarchy | Promoted the physical-array actions into a native toolbar, introduced KPI-style metric tiles, and separated primary metrics from angle diagnostics. |
| Responsive grid layout | Added explicit minimum widths and row weights for plot columns and the evaluation side panel. The main plot area now receives predictable space before the footer controls. |
| Dashboard information density | Reworked the evaluation panel into a compact overview plus Az/El diagnostic groups, keeping dense engineering data without a single crowded table. |
| Chart anatomy | Freed the physical plot header by moving edit controls out of Matplotlib canvas buttons; preserved chart labels, legends, hover behavior, and DBF playback controls. |
| Component states and contrast | Added status-aware metric styles and a danger-state delete button so risky modes and diagnostic conditions are visually distinct. |
| Proximity and grouping | Converted the bottom control strip to a grid of stable toolbar groups, keeping configuration, language, frequency, margin, auto layout, and pattern status in predictable areas. |

## Latest Product-Grade UI Pass

| Area | Improvement |
| --- | --- |
| Workspace shell | Added a dark professional workbench header with product identity and live state chips for frequency, DBF dictionary, and pattern mode. |
| Plot surfaces | Unified the physical array, virtual array, and response charts as bordered plot surfaces with consistent gutters and white chart backgrounds. |
| Curve styling | Added a subtle low-alpha underlay to response and DBF curves so the plots feel more polished while preserving exact line readability. |
| Status discipline | Removed repeated status text from the physical-array toolbar; global state now lives in the header chips and bottom status row. |
| High-DPI stability | Moved header chips below the title so they remain visible on smaller or scaled Windows displays. |

## Interaction Layout Pass

| Area | Improvement |
| --- | --- |
| Draggable workspace | Replaced the fixed plot/evaluation columns with a horizontal ttk PanedWindow so users can resize plots versus diagnostics. |
| Evaluation hierarchy | Converted the right-side evaluation stack into Overview, Angle, and 2D DBF tabs to reduce vertical crowding. |
| Header KPI rail | Added live KPI chips for virtual-channel utilization, Az/El resolution, and peak-margin status. |
| Localization cleanup | Moved element-pattern import, preview, status, and dialog strings into UI_TEXT for consistent Chinese/English/Japanese switching. |
| 2D DBF anatomy | Added a fixed normalized-gain colorbar and peak-delta badge to the DBF heatmap while reusing the same colorbar axis on redraw. |

## Codex-Style Menu Pass

| Area | Improvement |
| --- | --- |
| Top menu bar | Moved configuration and language dropdowns into a Codex-style top menu row with File, Edit, View, and Help groups. |
| Footer cleanup | Removed the bottom configuration/language dropdown groups so the footer focuses on frequency, margin, auto layout, pattern state, and status. |
| Header order | Placed the product/KPI information below the new menu bar and kept state chips right-aligned with KPI chips left-aligned. |
| Evaluation merge | Combined Overview and Angle diagnostics into one right-panel tab, leaving 2D DBF as the second tab. |

## Readability And Button Polish Pass

| Area | Improvement |
| --- | --- |
| Default split | Set the initial draggable workspace split to about 50/50 so the four plot modules and the 2D DBF heatmap are both readable. |
| Default DBF focus | Selected the 2D DBF tab by default to match the wide heatmap-oriented startup layout. |
| Button consistency | Unified same-row action buttons to white-background compact buttons with hover/focus highlighting instead of mixed filled blocks. |
| Help manual | Added a scrollable Help > User Manual window covering menus, layout, editing, DBF controls, pattern/dictionary configuration, and save/restore behavior. |

## Direct Angle Manipulation Pass

| Area | Improvement |
| --- | --- |
| 1D DBF spectra | Removed progress sliders and made the orange true-angle guide line draggable for manual scan positioning. |
| 2D DBF heatmap | Removed azimuth/elevation progress sliders and made the heatmap crosshair draggable to set both true-angle coordinates. |
| Interaction clarity | Kept play/pause/stop buttons, with manual dragging pausing active scan playback at the selected angle. |

## Hover And Import Affordance Pass

| Area | Improvement |
| --- | --- |
| 2D DBF heatmap | Added a hover tooltip that reports the nearest azimuth, elevation, and normalized gain value. |
| Drag affordance | Added hand cursors when hovering near the 1D true-angle guide or 2D true-angle crosshair. |
| 1T2R channel phase import | Allowed RX-only summary files so two data columns map to Rx1/Rx2 while three data columns map to Tx1/Rx1/Rx2. |

## Dialog Readability Pass

| Area | Improvement |
| --- | --- |
| Angle evaluation | Reduced metric typography, removed forced label wrapping, and shortened long cut-reason text so values are less likely to wrap. |
| Secondary dialogs | Enlarged default channel-pattern and DBF-dictionary dialogs so tables, preview panes, and action rows have readable space. |
| Dialog buttons | Unified same-row dialog actions to white Codex-style buttons with gray hover states, reserving danger only for red text. |
| Help manual | Rewrote the manual as a plain-language guide to modules, menu commands, and the typical workflow instead of mirroring the layout. |

## Not Integrated Yet

| Skill | Reason |
| --- | --- |
| Full design-system component migration | The app is now a PySide6 desktop tool with a retained ttk-style compatibility layer, so a wholesale Carbon or Material component migration would add churn without matching the current stack. |
| Icon-library toolbar | The current project has no icon dependency, and the safest product-level improvement was to preserve text controls while improving placement, state, and spacing. |
| Automated visual regression screenshots | The GUI can be instantiated and size-checked in Tk, but full screenshot comparison is not yet part of the test suite. |

## Verification

- `python -m compileall src tests GUI.py`
- `python -m pytest`
- Tk smoke check: instantiate `VirtualArrayGui`, complete first render, inspect side-panel and 2D DBF widget dimensions, then destroy the window.
