# Design QA — Carbon-led native PySide6 workbench

> 当前视觉方向是 Carbon-led 工作台，并保留 Apple 的直接操控与可中断反馈原则；2026-07-30 Apple-inspired 版本作为历史基线保留。当前实机截图位于 `outputs/carbon-apple-v1-final-20260731`，最终 Logo 检查位于 `outputs/logo-review-20260731`。

## Current review target (2026-07-31)

The current product direction uses Carbon's dense neutral hierarchy and Blue 60
state language while translating the
[apple-design skill](https://github.com/emilkowalski/skills/tree/main/skills/apple-design)
into direct manipulation, immediate feedback, visible focus, interruptibility,
and restrained motion. It retains native PySide6/Qt controls and does not
recreate a macOS window shell on Windows.

The previous Fluent 2 and Apple-inspired screenshots below remain historical
baseline evidence. Current screenshots are generated with
`scripts/capture_ui_review.py`; do not relabel an older capture as current
Carbon-led evidence.

**Accepted current evidence**

- Carbon-led native Qt, Simplified Chinese, 1366×768: `outputs/carbon-apple-v1-final-20260731` (three pages and five custom dialogs).
- Responsive and localized follow-up evidence: `outputs/responsive-audit-20260731`, `outputs/ui-fix-20260731-title-dbf`, and `outputs/radio-dialog-layout-fix-20260731-final-native`.
- Performance-report angle controls, enabled 2T2R state: `outputs/ui-review-report-angle-20260731-enabled/08-performance-report.png` (Simplified Chinese) and `outputs/ui-review-report-angle-20260731-en/08-performance-report.png` (English).
- Final black-and-white MAV Logo in the real Header: `outputs/logo-review-20260731/01-physical-virtual.png`; an isolated PyInstaller build confirmed the packaged PNG/ICO/ICNS assets match their sources.
- Functional verification: `253 passed` from the complete `tests` suite with Qt's offscreen platform; native captures above separately verify real Windows font and layout rendering.

**Current acceptance criteria**

- Theme uses centralized Carbon-led canvas, surface, typography, separator,
  control-border, Blue 60 primary/focus, radius, and state tokens.
- Header state labels remain compact and readable at supported widths; line tabs
  use a clear selected underline without fake platform chrome.
- Pressing a physical element preserves its grab offset instead of centering it
  under the pointer.
- Pointer capture keeps physical-element, 1D guide, and 2D crosshair drags
  reliable outside the originating plot, and every release/cancel path returns
  capture. Esc and unexpected OS `UngrabMouse` events use explicit cancellation
  paths so the app cannot remain mouse-grabbed.
- Physical movement stays continuous during the gesture, redraws are coalesced
  to about 16 ms, and grid snap happens once on release.
- No decorative bounce, inertia, ambient animation, or large translucent
  overlay obscures plots. User-controlled DBF playback remains interruptible.
- Keyboard focus is visible, control boundaries preserve non-text contrast,
  localized accessible names/tooltips remain present, and status is not encoded
  by color alone.
- Calculated values, imported formats, state compatibility, and plot color
  semantics are unchanged.

## Historical Fluent 2 baseline (2026-07-15)

**Original source visual truth**

- `C:\Users\junzhe.yu\AppData\Local\Temp\mimo-array-ui-audit-20260710\02-gui-mod-physical-virtual.png`
- `C:\Users\junzhe.yu\AppData\Local\Temp\mimo-array-ui-audit-20260710\03-gui-mod-1d-dbf.png`
- `C:\Users\junzhe.yu\AppData\Local\Temp\mimo-array-ui-audit-20260710\04-gui-mod-2d-dbf.png`
- `C:\Users\junzhe.yu\AppData\Local\Temp\mimo-array-ui-audit-20260710\05-gui-mod-dbf-dictionary-dialog.png`

**Fluent 2 rendered implementation**

- `D:\HFSS数据整理\mimo-array-visualizer\outputs\ui-modern-pass-20260715\after-final-1366-native\01-physical-virtual.png`
- `D:\HFSS数据整理\mimo-array-visualizer\outputs\ui-modern-pass-20260715\after-final-1366-native\02-1d-dbf.png`
- `D:\HFSS数据整理\mimo-array-visualizer\outputs\ui-modern-pass-20260715\after-final-1366-native\03-2d-dbf.png`
- Dialog evidence continues through `07-user-manual.png` in the same directory.
- Minimum-size 2T2R evidence: `outputs\ui-modern-pass-20260715\after-final-1100-2t2r`.
- Minimum-size English evidence: `outputs\ui-modern-pass-20260715\english-1100-after-fix`.
- Chaptered manual evidence at 1100×650: `outputs\manual-chapters-20260715-1100\07-user-manual.png`, with corresponding English and Japanese folders.

**Previous rendered implementation**

- `D:\HFSS数据整理\mimo-array-visualizer\outputs\ui-review-final\01-physical-virtual.png`
- `D:\HFSS数据整理\mimo-array-visualizer\outputs\ui-review-final\02-1d-dbf.png`
- `D:\HFSS数据整理\mimo-array-visualizer\outputs\ui-review-final\03-2d-dbf.png`
- `D:\HFSS数据整理\mimo-array-visualizer\outputs\ui-review-final\04-dbf-dictionary.png`
- Dialog evidence continues through `07-user-manual.png` in the same directory.

**Historical comparison setup**

- Viewport: 1366×768 logical pixels; Windows 125% capture is 1708×960 physical pixels.
- Dialog viewport: 1120×700 logical pixels; 1400×875 physical pixels.
- State: Fluent 2 light theme, Simplified Chinese, first-run 1T1R, ideal geometric DBF dictionary.
- Full-view comparison: `D:\HFSS数据整理\mimo-array-visualizer\outputs\design-qa\comparison-full.png`.
- Focused comparison: `D:\HFSS数据整理\mimo-array-visualizer\outputs\design-qa\comparison-focused.png`.
- Additional responsive evidence: `outputs\ui-review-1100-final`, `outputs\ui-review-1920`, `outputs\dpi-native-100`, and `outputs\dpi-native-150-final`.
- Additional state evidence: `outputs\lang-en-final`, `outputs\lang-ja-final`, `outputs\scenario-2t2r`, `outputs\scenario-8t8r`, and `outputs\scenario-full-2d`.

**Historical findings**

- No actionable P0, P1, or P2 visual differences remain. The implementation intentionally improves the audited source rather than reproducing its misleading capability states.
- Fonts and typography: common UI and plot text is at least 9 pt, CJK/system fallbacks remain sharp at 100%/125%/150%, headings have clear weight hierarchy, and long global status text is elided with a full tooltip.
- Spacing and layout rhythm: the 8 px rhythm, 8 px control radius, 12 px card radius, draggable 78:22 splitter, compact command bar, and stacked Overview groups remain coherent from 1100×650 through 1920×1080.
- Colors and tokens: the implementation consistently uses the Fluent canvas/surface/text/MAV-blue tokens. Neutral capability gaps are gray-blue, capability/quality cautions are amber, and red is reserved for destructive or genuinely dangerous states. Focus and interactive borders meet the specified semantic contrast intent.
- Image quality and assets: the repository MAV raster asset is used directly, remains crisp at 150%, and is also embedded as the packaged executable icon. No visible asset was replaced with text, emoji, CSS art, or a handcrafted substitute.
- Copy and content: all three page labels, empty states, global status, evaluation values, menus, and dialog actions were checked in Chinese, English, and Japanese. The numerical content is unchanged from the calculation layer.

**Historical open questions**

- None blocking. Screen-reader output and a hardware-assisted accessibility pass remain useful release checks, but the native accessible names/descriptions and keyboard focus paths are present and covered by smoke assertions.

**Comparison history**

1. Initial comparison found a P1 misleading-state issue: 1T1R rendered flat 1D spectra and a full yellow 2D heatmap. Fixed with localized neutral capability overlays, disabled playback, and no generated 2D heatmap when either aperture is absent. Post-fix evidence: `outputs\ui-review-final\02-1d-dbf.png` and `03-2d-dbf.png`.
2. Initial comparison found P2 hierarchy and density issues: duplicate header KPIs, undersized plot/status text, untranslated tabs, and a fixed-size shell. Fixed with three global chips, visible localized native tabs, minimum 9 pt text, a native splitter, and exact 1100×650 resizing. Post-fix evidence: `outputs\ui-review-1100-final\01-physical-virtual.png` and `tests\test_qt_gui_smoke.py`.
3. Initial comparison found a P2 dialog issue: the ideal one-channel dictionary used an alarming red callout, weak action hierarchy, and a widget-backed table. Fixed with severity-aware neutral/amber/risk callouts, a visible blue primary Apply button, `QDialogButtonBox`, and `QTableView` plus `QAbstractTableModel`. Post-fix evidence: `outputs\ui-review-final\04-dbf-dictionary.png`.
4. Responsive comparison found P2 clipping at 1100×650 and language-dependent minimum widths up to 1309 px. Fixed by removing fixed plot minima, compacting the Overview rhythm, shortening command-bar copy, and allowing locale-aware intrinsic widths. Post-fix evidence: `outputs\ui-review-1100-final` and the exact-size smoke test.
5. Focused comparison found P2 polish regressions: plot axes peeking around empty overlays, English/Japanese evaluation values remaining Chinese, a high-DPI logo capture gap, and duplicate-point legend overlap. Fixed with full-canvas overlays, localized dynamic metric values, device-pixel-ratio-aware logo rendering, and separated legend placement. Post-fix evidence: `outputs\lang-en-final`, `outputs\lang-ja-final`, `outputs\dpi-native-150-final`, and `outputs\scenario-full-2d`.
6. The 2026-07-15 desktop-app pass reduced P1 engineering-tool density: tabs now use a quiet pivot treatment, nested metric borders are flattened, controls expose hover/focus/checked states, capability overlays hide meaningless transport controls, dialogs clamp to the parent work area, tables and scrollbars use the shared Fluent tokens, and the manual is searchable HTML. A follow-up English 1100×650 audit then fixed header/action truncation, narrow-dialog action reflow and its safe resize breakpoint, virtual-plot legend overlap, 3:1 interactive borders, danger checked-state semantics, localized accessibility names, and repeated callout-QSS growth. Post-fix evidence: `outputs\ui-modern-pass-20260715\after-final-1366-native`, `outputs\ui-modern-pass-20260715\after-final-1100-2t2r`, and `outputs\ui-modern-pass-20260715\english-1100-after-fix`.
7. The help manual now uses 12 stable task-oriented chapters in Chinese, English, and Japanese. Help exposes direct chapter entries plus an F1 full-manual action; the dialog adds a resizable contents pane, cross-chapter search, result navigation, explicit no-result feedback, and keyboard-safe Enter handling. Content focuses on procedures, expected feedback, limits, persistence boundaries, and recovery rather than formulas. Post-fix evidence: `outputs\manual-chapters-20260715-1100`, `outputs\manual-chapters-20260715-en-1100-retry`, and `outputs\manual-chapters-20260715-ja-1100`.

**Historical implementation checklist**

- [x] Canonical implementation lives in `virtual_array.gui`; legacy module and root launcher are aliases.
- [x] Native menu bar, splitter, tabs, status bar, dialogs, table models, standard icons, and Qt canvas are present.
- [x] 1T1R, one-axis-only, complete 2D, repeated virtual point, 2T2R, and 8T8R states render without misleading data.
- [x] 1100×650, 1366×768, 1920×1080 and Windows 100%/125%/150% captures have no clipping or persistent overflow.
- [x] Chinese, English, and Japanese labels and dynamic states are localized.
- [x] Automated screenshots and native Qt smoke tests cover the three pages and five custom dialogs, including the performance-report settings window.
- [x] The help manual has stable multilingual chapters, direct menu navigation, full-text chapter search, and content/schema regression tests.

**Follow-up Polish**

- [P3] A future release may add OS-level screen-reader and keyboard-only test automation beyond the current native accessibility metadata and focus-policy smoke checks.

Historical Fluent 2 result: passed.

Current Carbon-led native Windows visual QA result: **passed**. Functional,
interaction, asset, responsive-layout, and packaging coverage also passed in
the repository-wide validation run.
