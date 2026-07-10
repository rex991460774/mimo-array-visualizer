# Design QA — PySide6 Fluent 2 migration

**Source visual truth**

- `C:\Users\junzhe.yu\AppData\Local\Temp\mimo-array-ui-audit-20260710\02-gui-mod-physical-virtual.png`
- `C:\Users\junzhe.yu\AppData\Local\Temp\mimo-array-ui-audit-20260710\03-gui-mod-1d-dbf.png`
- `C:\Users\junzhe.yu\AppData\Local\Temp\mimo-array-ui-audit-20260710\04-gui-mod-2d-dbf.png`
- `C:\Users\junzhe.yu\AppData\Local\Temp\mimo-array-ui-audit-20260710\05-gui-mod-dbf-dictionary-dialog.png`

**Rendered implementation**

- `D:\HFSS数据整理\mimo-array-visualizer\outputs\ui-review-final\01-physical-virtual.png`
- `D:\HFSS数据整理\mimo-array-visualizer\outputs\ui-review-final\02-1d-dbf.png`
- `D:\HFSS数据整理\mimo-array-visualizer\outputs\ui-review-final\03-2d-dbf.png`
- `D:\HFSS数据整理\mimo-array-visualizer\outputs\ui-review-final\04-dbf-dictionary.png`
- Dialog evidence continues through `07-user-manual.png` in the same directory.

**Comparison setup**

- Viewport: 1366×768 logical pixels; Windows 125% capture is 1708×960 physical pixels.
- Dialog viewport: 1120×700 logical pixels; 1400×875 physical pixels.
- State: Fluent 2 light theme, Simplified Chinese, first-run 1T1R, ideal geometric DBF dictionary.
- Full-view comparison: `D:\HFSS数据整理\mimo-array-visualizer\outputs\design-qa\comparison-full.png`.
- Focused comparison: `D:\HFSS数据整理\mimo-array-visualizer\outputs\design-qa\comparison-focused.png`.
- Additional responsive evidence: `outputs\ui-review-1100-final`, `outputs\ui-review-1920`, `outputs\dpi-native-100`, and `outputs\dpi-native-150-final`.
- Additional state evidence: `outputs\lang-en-final`, `outputs\lang-ja-final`, `outputs\scenario-2t2r`, `outputs\scenario-8t8r`, and `outputs\scenario-full-2d`.

**Findings**

- No actionable P0, P1, or P2 visual differences remain. The implementation intentionally improves the audited source rather than reproducing its misleading capability states.
- Fonts and typography: common UI and plot text is at least 9 pt, CJK/system fallbacks remain sharp at 100%/125%/150%, headings have clear weight hierarchy, and long global status text is elided with a full tooltip.
- Spacing and layout rhythm: the 8 px rhythm, 6 px control radius, 8 px card radius, draggable 78:22 splitter, compact command bar, and stacked Overview groups remain coherent from 1100×650 through 1920×1080.
- Colors and tokens: the implementation consistently uses the Fluent canvas/surface/text/MAV-blue tokens. Neutral capability gaps are gray-blue, capability/quality cautions are amber, and red is reserved for destructive or genuinely dangerous states. Focus and interactive borders meet the specified semantic contrast intent.
- Image quality and assets: the repository MAV raster asset is used directly, remains crisp at 150%, and is also embedded as the packaged executable icon. No visible asset was replaced with text, emoji, CSS art, or a handcrafted substitute.
- Copy and content: all three page labels, empty states, global status, evaluation values, menus, and dialog actions were checked in Chinese, English, and Japanese. The numerical content is unchanged from the calculation layer.

**Open Questions**

- None blocking. Screen-reader output and a hardware-assisted accessibility pass remain useful release checks, but the native accessible names/descriptions and keyboard focus paths are present and covered by smoke assertions.

**Comparison History**

1. Initial comparison found a P1 misleading-state issue: 1T1R rendered flat 1D spectra and a full yellow 2D heatmap. Fixed with localized neutral capability overlays, disabled playback, and no generated 2D heatmap when either aperture is absent. Post-fix evidence: `outputs\ui-review-final\02-1d-dbf.png` and `03-2d-dbf.png`.
2. Initial comparison found P2 hierarchy and density issues: duplicate header KPIs, undersized plot/status text, untranslated tabs, and a fixed-size shell. Fixed with three global chips, visible localized native tabs, minimum 9 pt text, a native splitter, and exact 1100×650 resizing. Post-fix evidence: `outputs\ui-review-1100-final\01-physical-virtual.png` and `tests\test_qt_gui_smoke.py`.
3. Initial comparison found a P2 dialog issue: the ideal one-channel dictionary used an alarming red callout, weak action hierarchy, and a widget-backed table. Fixed with severity-aware neutral/amber/risk callouts, a visible blue primary Apply button, `QDialogButtonBox`, and `QTableView` plus `QAbstractTableModel`. Post-fix evidence: `outputs\ui-review-final\04-dbf-dictionary.png`.
4. Responsive comparison found P2 clipping at 1100×650 and language-dependent minimum widths up to 1309 px. Fixed by removing fixed plot minima, compacting the Overview rhythm, shortening command-bar copy, and allowing locale-aware intrinsic widths. Post-fix evidence: `outputs\ui-review-1100-final` and the exact-size smoke test.
5. Focused comparison found P2 polish regressions: plot axes peeking around empty overlays, English/Japanese evaluation values remaining Chinese, a high-DPI logo capture gap, and duplicate-point legend overlap. Fixed with full-canvas overlays, localized dynamic metric values, device-pixel-ratio-aware logo rendering, and separated legend placement. Post-fix evidence: `outputs\lang-en-final`, `outputs\lang-ja-final`, `outputs\dpi-native-150-final`, and `outputs\scenario-full-2d`.

**Implementation Checklist**

- [x] Canonical implementation lives in `virtual_array.gui`; legacy module and root launcher are aliases.
- [x] Native menu bar, splitter, tabs, status bar, dialogs, table models, standard icons, and Qt canvas are present.
- [x] 1T1R, one-axis-only, complete 2D, repeated virtual point, 2T2R, and 8T8R states render without misleading data.
- [x] 1100×650, 1366×768, 1920×1080 and Windows 100%/125%/150% captures have no clipping or persistent overflow.
- [x] Chinese, English, and Japanese labels and dynamic states are localized.
- [x] Automated screenshots and native Qt smoke tests cover the three pages and four custom dialogs.

**Follow-up Polish**

- [P3] A future release may add OS-level screen-reader and keyboard-only test automation beyond the current native accessibility metadata and focus-policy smoke checks.

final result: passed
