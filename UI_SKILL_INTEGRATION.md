# UI Skill Integration Notes

This note records the professional UI skills and references integrated into the
desktop GUI. The current interface is a Carbon-led native Qt application with
Apple-inspired direct-manipulation and feedback behavior;
older passes are retained below as implementation history rather than current
theme guidance.

## Current Carbon-Led Native Qt Pass (2026-07-31)

Structural reference: [Carbon Design System](https://carbondesignsystem.com/).
Interaction reference: [emilkowalski/skills — apple-design](https://github.com/emilkowalski/skills/tree/main/skills/apple-design).

The skill is installed locally for Codex reuse, but the product does not depend
on the skill at runtime. Its principles were translated into PySide6/Qt instead
of copying web animation code or drawing a fake macOS shell.

| Principle | Current implementation | Product impact |
| --- | --- | --- |
| Immediate response | Buttons, line tabs, hover, pressed, selected, disabled, and focus states come from one native token/QSS theme. | Users receive clear feedback without ornamental motion; centralized tokens keep future changes consistent. |
| Direct manipulation | A physical element keeps its pointer-to-element grab offset, captures the pointer on press, and uses one cleanup path for release, Esc, or OS capture loss. | The element no longer jumps to the cursor center, and interrupted drags cannot leave the application mouse-grabbed. |
| Continuous movement | Drag positions update continuously within bounds; grid snap runs once on release. | Removes stepwise grid jitter while preserving the exact stored, snapped layout after the gesture. |
| Efficient redraw | High-frequency physical-drag events are coalesced behind an approximately 16 ms redraw task. | Reduces redundant plot work and main-thread stalls while retaining frame-rate-level feedback. |
| Interruptibility | 1D true-angle guides and the 2D crosshair capture/release the pointer; manual movement pauses user-started playback. | Direct input remains authoritative and playback never fights the user. |
| Restrained motion | The redesign adds no bounce, inertia, ambient loops, or data-obscuring transitions. | Engineering data stays stable and reduced-motion users lose no functionality. |
| Layered hierarchy | `#F4F4F4` canvas, white work surfaces, flat header states, Carbon line tabs, and low-contrast separators replace nested rounded cards. | The interface scans more calmly without hiding dense diagnostics. |
| Accessibility | Native Qt semantics, visible `#0F62FE` keyboard focus and primary fill, localized accessible names/tooltips, contrast-aware borders, and non-color-only status cues remain required. | Keyboard and assistive-technology paths stay dependable across supported languages and DPI settings. |

Implementation rule: all current visual guidance lives in
`GUI_MOD_VISUAL_GUIDELINES.md`; the tables below describe earlier design work
that led to the same canonical `virtual_array.gui` implementation.

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

## Historical Design Passes

The following entries document earlier iterations (including the former dark
workbench and Fluent 2 directions). They are useful provenance, but they do not
override the current Carbon-led token system or Apple-inspired interaction rules.

### Earlier Product-Grade UI Pass

| Area | Improvement |
| --- | --- |
| Workspace shell | Added a dark professional workbench header with product identity and live state chips for frequency, DBF dictionary, and pattern mode. |
| Plot surfaces | Unified the physical array, virtual array, and response charts as bordered plot surfaces with consistent gutters and white chart backgrounds. |
| Curve styling | Added a subtle low-alpha underlay to response and DBF curves so the plots feel more polished while preserving exact line readability. |
| Status discipline | Removed repeated status text from the physical-array toolbar; global state now lives in the header chips and bottom status row. |
| High-DPI stability | Moved header chips below the title so they remain visible on smaller or scaled Windows displays. |

### Interaction Layout Pass

| Area | Improvement |
| --- | --- |
| Draggable workspace | Replaced the fixed plot/evaluation columns with a horizontal ttk PanedWindow so users can resize plots versus diagnostics. |
| Evaluation hierarchy | Converted the right-side evaluation stack into Overview, Angle, and 2D DBF tabs to reduce vertical crowding. |
| Header KPI rail | Added live KPI chips for virtual-channel utilization, Az/El resolution, and peak-margin status. |
| Localization cleanup | Moved element-pattern import, preview, status, and dialog strings into UI_TEXT for consistent Chinese/English/Japanese switching. |
| 2D DBF anatomy | Added a fixed normalized-gain colorbar and peak-delta badge to the DBF heatmap while reusing the same colorbar axis on redraw. |

### Codex-Style Menu Pass

| Area | Improvement |
| --- | --- |
| Top menu bar | Moved configuration and language dropdowns into a Codex-style top menu row with File, Edit, View, and Help groups. |
| Footer cleanup | Removed the bottom configuration/language dropdown groups so the footer focuses on frequency, margin, auto layout, pattern state, and status. |
| Header order | Placed the product/KPI information below the new menu bar and kept state chips right-aligned with KPI chips left-aligned. |
| Evaluation merge | Combined Overview and Angle diagnostics into one right-panel tab, leaving 2D DBF as the second tab. |

### Readability And Button Polish Pass

| Area | Improvement |
| --- | --- |
| Default split | Set the initial draggable workspace split to about 50/50 so the four plot modules and the 2D DBF heatmap are both readable. |
| Default DBF focus | Selected the 2D DBF tab by default to match the wide heatmap-oriented startup layout. |
| Button consistency | Unified same-row action buttons to white-background compact buttons with hover/focus highlighting instead of mixed filled blocks. |
| Help manual | Added a scrollable Help > User Manual window covering menus, layout, editing, DBF controls, pattern/dictionary configuration, and save/restore behavior. |

### Direct Angle Manipulation Pass

| Area | Improvement |
| --- | --- |
| 1D DBF spectra | Removed progress sliders and made the orange true-angle guide line draggable for manual scan positioning. |
| 2D DBF heatmap | Removed azimuth/elevation progress sliders and made the heatmap crosshair draggable to set both true-angle coordinates. |
| Interaction clarity | Kept play/pause/stop buttons, with manual dragging pausing active scan playback at the selected angle. |

### Hover And Import Affordance Pass

| Area | Improvement |
| --- | --- |
| 2D DBF heatmap | Added a hover tooltip that reports the nearest azimuth, elevation, and normalized gain value. |
| Drag affordance | Added hand cursors when hovering near the 1D true-angle guide or 2D true-angle crosshair. |
| 1T2R channel phase import | Allowed RX-only summary files so two data columns map to Rx1/Rx2 while three data columns map to Tx1/Rx1/Rx2. |

### Dialog Readability Pass

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
| CI pixel-diff visual regression | `scripts/capture_ui_review.py` already generates repeatable native Qt screenshots with isolated state. A fixed-threshold pixel-diff gate is intentionally not in CI because font rasterization and DPI vary by runner; human comparison remains the reliable release check. |

## Verification

- `python -m compileall src tests GUI.py`
- `python -m pytest` — current repository-wide result: `253 passed`.
- Native Qt smoke check: run with `QT_QPA_PLATFORM=offscreen`, instantiate `VirtualArrayGui`, complete first render, inspect workspace/dialog geometry and accessibility state, then close the window.
- Accepted current visual evidence: `outputs/carbon-apple-v1-final-20260731` (three pages plus five dialogs), with responsive/dialog follow-ups under `outputs/responsive-audit-20260731`, `outputs/ui-fix-20260731-title-dbf`, and `outputs/radio-dialog-layout-fix-20260731-final-native`. The earlier `outputs/apple-design-pass-20260730` captures remain historical interaction evidence only.
