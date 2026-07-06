# MIMO Array Visualizer

**English** | [中文](#中文) | [日本語](#日本語)

Desktop tool for interactively editing and evaluating MIMO Tx/Rx antenna array
layouts. Computes virtual array geometry, 2D array factor, and radar-performance
metrics (PSL, beamwidth, ISLR, grating lobes, elevation ambiguity).

Two GUI variants are provided:

- **GUI.py** — Original layout: 2×2 plot grid + evaluation panel with draggable workspace splitter.
- **GUI_mod.py** — Refined layout: fixed 1366×768, three tab pages + side overview panel (4:1 split).

---

## Features

### Core Engine

- Interactive Tx/Rx layout editor with add, delete-mode, clear,
  auto-place by Tx/Rx count, drag, and snap-to-grid.
- Undo/redo for layout edits, plus keyboard shortcuts for common actions.
- Virtual-array visualization with duplicate-channel statistics.
- Array evaluation: aperture, resolution, 3 dB beamwidth, PSL, ISLR,
  grating-lobe and elevation-ambiguity indicators.
- Custom frequency input with GHz suffix parsing, plus configurable DBF
  competitor-peak margin threshold.
- DBF dictionary spectrum animation for azimuth and elevation, with draggable
  true-angle lines over 181 angles from −90° to +90° in 1° steps.
- 2D DBF heatmap with independent azimuth/elevation playback controls.
- Configurable DBF dictionary modes: ideal, phase-reversed, channel-pattern
  calibrated, and imported CSV/XLSX dictionary matrices with tabular preview.
- HFSS channel-pattern CSV/XLSX import for per-channel amplitude and phase.
- Readable JSON layout import/export with optional evaluation metadata.
- Local state persistence (last paths, frequency, window geometry, layout).
- PyInstaller onedir packaging for Windows.

### GUI_mod.py (Refined Layout)

- Fixed window: **1366 × 768**, non-resizable.
- Three tab pages with consistent 4 px inner spacing:
  - **Physical & Virtual** — Physical and virtual array side by side (1:1).
  - **1D DBF** — Azimuth and elevation response spectra side by side (1:1).
  - **2D DBF** — Full-tab 2D heatmap with playback controls.
- Right-side **Overview** panel (4:1 tab-to-overview split):
  - Channel count, virtual channels, aperture, resolution.
  - Angle evaluation: no-fold range, max error, peak margin, cut reason.
- Cross-platform Chinese font support (macOS / Windows / Linux).
- OpenCode skills and ruff/pyright tooling preconfigured.

---

## Quick Start

### Setup

```powershell
# Windows (PowerShell)
.\scripts\setup.ps1
```

**macOS / Linux**:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Run

```bash
# Original GUI
python GUI.py

# Refined GUI
python GUI_mod.py
```

Windows:

```powershell
.\.venv\Scripts\python.exe GUI.py
.\.venv\Scripts\python.exe GUI_mod.py
```

If PowerShell blocks execution:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

---

## Keyboard Shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl+Z` | Undo layout edit |
| `Ctrl+Y` / `Ctrl+Shift+Z` | Redo layout edit |
| `Ctrl+S` | Export layout JSON |
| `Ctrl+O` | Import layout JSON |
| `Ctrl+G` / `Ctrl+R` | Refresh analysis |
| `Ctrl+F` | Focus frequency input |
| `Delete` | Delete selected element / enter delete mode |
| `Escape` | Clear selection / exit delete mode / cancel drag |

---

## DBF Angle Spectra

Each 1D DBF plot has 181 frames simulating true incoming angles from −90° to
+90° in 1° steps. Use the compact **Play** button under each plot. **Pause**
freezes the current spectrum; click again to **Resume**. Drag the true-angle
line to jump to a specific angle.

The toolbar **Peak margin (dB)** input controls the competitor-peak margin
threshold for no-fold ambiguity evaluation.

### DBF Dictionary

Use **Edit → Configure DBF Dictionary** to choose the beamforming dictionary:

| Mode | Description |
| --- | --- |
| Ideal geometric | Phase-only steering from array geometry |
| Ideal reversed phase | Sign-check variant |
| Channel amp/phase | Uses imported HFSS channel data with 0° phase reference |
| Imported CSV/XLSX | External dictionary loaded per-axis (Az/El) |

### 2D DBF Heatmap

The 2D DBF panel shows a correlation heatmap over azimuth and elevation.
Each axis can play/pause independently — one axis stays fixed while the
other scans, or both axes scan simultaneously.

---

## Layout Editing

Use the Physical Array toolbar to add Tx/Rx elements, clear the layout to
1T1R, or enter delete mode. In delete mode each clicked element is removed
and remaining channels are renumbered by position.

The auto-layout inputs (`T` / `R` count) and **Apply Array** button generate
centered Tx and Rx rows for quick-start configurations.

### Layout JSON

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

---

## Channel Pattern Import

Use **Edit → Configure Channel Amp/Phase** to load HFSS amplitude/phase data
for physical or virtual channels. Summary CSV/XLSX files map columns
left-to-right by channel order. Loaded patterns are applied as complex
physical-channel weights (Tx × Rx for each virtual channel).

---

## Development

```bash
# Run tests
pytest tests/ -x -q

# Lint & format
ruff check .
ruff format .

# Build Windows EXE
.\scripts\build_exe.ps1
```

Entry points:

```bash
mimo-array-visualizer
mimo-array-case4
```

---

## Project Structure

```
GUI.py              → Launcher (original)
GUI_mod.py          → Launcher (refined)
src/virtual_array/
  gui.py            → Original GUI (~7700 lines)
  gui_mod.py        → Refined GUI (1366×768 fixed, three-tab layout)
  geometry.py       → ArrayPoint, VirtualPoint, AntennaArray
  analysis.py       → Metrics, PSF, DBF spectra
  element_pattern.py → ElementPattern, ChannelPatternSet
  dbf_dictionary.py → DBF dictionary configuration
  app_state.py      → JSON persistence
  grid.py           → Grid snap helpers
  version.py        → APP_VERSION
  examples/         → Reference array fixtures
tests/              → pytest suite
.opencode/          → OpenCode skills & tooling config
```

---

# 中文

MIMO 阵列可视化工具 — 用于交互式编辑和评估 MIMO 发射/接收天线阵列布局的桌面应用。可计算虚拟阵列几何、2D 阵列因子以及雷达性能指标（旁瓣电平、波束宽度、ISLR、栅瓣、俯仰模糊）。

提供两个 GUI 版本：

- **GUI.py** — 原始布局：2×2 图形网格 + 可拖拽分割的评估面板。
- **GUI_mod.py** — 重构布局：固定 1366×768，三子页 Notebook + 右侧概览面板（4:1）。

## 功能特性

### 核心引擎

- 交互式 Tx/Rx 布局编辑器：添加、删除模式、清空、按 T/R 数量自动排阵、拖拽、吸附网格。
- 编辑操作的撤销/重做，常用快捷键。
- 虚拟阵列可视化（含重复通道统计）。
- 阵列评估：口径尺寸、分辨率、3 dB 波束宽度、PSL、ISLR、栅瓣和俯仰模糊指标。
- 自定义频率输入（支持 GHz 后缀解析），可配置 DBF 竞争峰裕量阈值。
- 方位/俯仰 DBF 字典角谱动画，181 个真实角（−90° 到 +90°，步进 1°）。
- 2D DBF 热图，方位/俯仰轴独立播放控制。
- 可配置 DBF 字典模式：理想几何、反向相位、通道幅相校准、导入 CSV/XLSX 字典。
- HFSS 通道方向图 CSV/XLSX 导入（幅度/相位）。
- 可读的 JSON 布局导入/导出（含评估元数据）。
- 本地状态持久化（最近路径、频率、窗口几何、布局）。
- PyInstaller onedir Windows 打包。

### GUI_mod.py（重构版）

- 固定窗口：**1366 × 768**，不可缩放。
- 三个子页面，统一 4 px 内间距：
  - **Physical & Virtual** — 物理阵列与虚拟阵列左右并排（1:1）。
  - **1D DBF** — 方位与俯仰响应曲线左右并排（1:1）。
  - **2D DBF** — 全页 2D 热图及播放控件。
- 右侧 **Overview** 概览面板（子页:概览 = 4:1）：
  - 通道数、虚拟通道、口径、分辨率。
  - 测角评估：不模糊范围、最大误差、竞争峰裕量、截断原因。
- 跨平台中文字体（macOS / Windows / Linux）。
- 预配置 OpenCode 技能和 ruff/pyright 工具。

## 快速开始

### 环境配置

**Windows (PowerShell)**：

```powershell
.\scripts\setup.ps1
```

**macOS / Linux**：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 运行

```bash
python GUI.py       # 原始版
python GUI_mod.py   # 重构版
```

## 快捷键

| 快捷键 | 操作 |
| --- | --- |
| `Ctrl+Z` | 撤销布局编辑 |
| `Ctrl+Y` / `Ctrl+Shift+Z` | 重做布局编辑 |
| `Ctrl+S` | 导出布局 JSON |
| `Ctrl+O` | 导入布局 JSON |
| `Ctrl+G` / `Ctrl+R` | 刷新分析 |
| `Ctrl+F` | 聚焦频率输入框 |
| `Delete` | 删除选中通道 / 进入删除模式 |
| `Escape` | 清除选择 / 退出删除模式 / 取消拖拽 |

## 开发

```bash
pytest tests/ -x -q   # 运行测试
ruff check .          # 代码检查
ruff format .         # 代码格式化
```

---

# 日本語

MIMOアレイ可視化ツール — MIMO送信/受信アンテナアレイ配置を対話的に編集・評価するデスクトップアプリです。仮想アレイ形状、2Dアレイファクタ、レーダ性能指標（PSL、ビーム幅、ISLR、グレーティングローブ、仰角曖昧性）を計算します。

2 つの GUI バージョンを提供：

- **GUI.py** — オリジナル版：2×2 プロットグリッド + 分割可能な評価パネル。
- **GUI_mod.py** — 改良版：固定 1366×768、3 タブ Notebook + 右側概要パネル（4:1）。

## 機能

### コアエンジン

- インタラクティブな Tx/Rx 配置編集（追加、削除モード、クリア、自動配置、ドラッグ、グリッドスナップ）
- アンドゥ/リドゥ、キーボードショートカット
- 仮想アレイ表示（重複チャネル統計付き）
- アレイ評価：開口サイズ、分解能、3 dB ビーム幅、PSL、ISLR、グレーティングローブ、仰角曖昧性指標
- カスタム周波数入力（GHz サフィックス対応）、DBF 競合ピークマージン設定
- 方位/仰角 DBF 辞書角度スペクトルアニメーション（181 フレーム、−90° 〜 +90°、1° ステップ）
- 2D DBF ヒートマップ（方位/仰角の独立再生）
- 設定可能な DBF 辞書モード（理想幾何、逆位相、チャネル振幅/位相校正、CSV/XLSX 辞書読み込み）
- HFSS チャネルパターン CSV/XLSX 読み込み（振幅/位相）
- 可読 JSON 配置の読み込み/書き出し（評価メタデータ付き）
- ローカル状態の永続化
- PyInstaller onedir Windows パッケージ

### GUI_mod.py（改良版）

- 固定ウィンドウ：**1366 × 768**、リサイズ不可
- 3 タブ（統一 4 px 間隔）：
  - **Physical & Virtual** — 物理/仮想アレイ左右 1:1
  - **1D DBF** — 方位/仰角応答スペクトル左右 1:1
  - **2D DBF** — 全画面 2D ヒートマップ
- 右側 **Overview** パネル（タブ:概要 = 4:1）
- クロスプラットフォーム中国語フォント対応
- OpenCode スキル・ruff/pyright ツール設定済み

## クイックスタート

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python GUI.py        # オリジナル版
python GUI_mod.py    # 改良版
```

## 開発

```bash
pytest tests/ -x -q   # テスト実行
ruff check .          # リント
ruff format .         # フォーマット
```
