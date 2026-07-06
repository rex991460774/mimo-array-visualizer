---
name: mimo-project
description: MIMO Array Visualizer project conventions - file structure, test commands, naming, data flow
---
## Project layout

```
GUI.py              → 启动器 (import virtual_array.gui.main)
GUI_mod.py          → 启动器 (import virtual_array.gui_mod.main) — 重构版
src/virtual_array/
  gui.py            → 原版 GUI (~7700 行)
  gui_mod.py        → 重构版 GUI (1200×800 固定窗口，三子页 Notebook)
  geometry.py       → ArrayPoint, VirtualPoint, AntennaArray
  analysis.py       → calculate_metrics_and_psf, dbf_*_spectrum
  element_pattern.py → ElementPattern, ChannelPatternSet
  dbf_dictionary.py → DBF 字典配置
  app_state.py      → JSON 持久化到 ~/Library/Application Support/antenna-array/
  logging_config.py → 日志配置
  grid.py           → GRID_STEP=1.0, snap_to_grid()
  version.py        → APP_VERSION
```

## 运行命令

```bash
python GUI.py         # 原版
python GUI_mod.py     # 重构版
pytest tests/ -x -q   # 测试
```

## 重构版 (gui_mod.py) 关键布局

- 窗口：1366×768，`resizable(False, False)`
- 主布局：`main_panel` grid 4:1 (notebook : overview)
- Notebook 三个子页（Tab 1 Physical&Virtual 1:1, Tab 2 1D DBF 1:1, Tab 3 2D DBF）
- Overview 面板在右侧，primary 指标左右排列（name col 0, value col 1, padx=2）
- angle 指标 az/el 上下堆叠单列
- 字体：matplotlib 优先链 macOS→Windows→Linux，Tkinter `TkDefaultFont`/`TkFixedFont`
- `_load_local_state()` 会从 state.json 覆盖 geometry，`main()` 里需要二次 `root.geometry()` 确保覆盖

## Tab 3 (2D DBF) 通过 `_build_dbf2d_widget()` 创建

- 返回 dbf2d_frame，由调用方 `pack(fill=BOTH, expand=True)` 放置
- 创建 Figure、canvas、play/stop 按钮、status label
- 不要设置 canvas 固定宽高

## 修改注意事项

- 所有坐标用 λ (wavelength) 单位，显示时乘 DISPLAY_SCALE_LAMBDA
- 修改 figure 尺寸后同步调整 `subplots_adjust` 参数
- `_build_response_chart` 方法签名是 `(parent, row, col, padding, mode)`，frame.grid 里不要额外 padx
- `_build_evaluation_panel(parent)` 创建 eval_frame 并用 grid 填充 parent
- 修改布局后检查 `_refresh_language_texts` 和 `generate_virtual_array` 里的引用
