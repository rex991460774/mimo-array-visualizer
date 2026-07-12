# MIMO Array Visualizer

**English** | [中文](#中文) | [日本語](#日本語)

Desktop tool for interactively editing and evaluating MIMO Tx/Rx antenna array
layouts. Computes virtual array geometry, 2D array factor, and radar-performance
metrics (PSL, beamwidth, ISLR, grating lobes, elevation ambiguity).

The desktop UI is a native **PySide6 / pyqtgraph** application with a Fluent 2
light theme. It has one maintained implementation, `virtual_array.gui`, and a
resizable three-page workspace. `GUI.py`, `GUI_mod.py`, and the installed
console command all start this same interface; `GUI_mod.py` remains only as a
compatibility alias for existing shortcuts.

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
- Header **Channel Amp/Phase** status reports amplitude and phase separately
  as ideal, imported, or mixed; imported element patterns count as imported
  amplitude.
- Polished channel-pattern UI: centered channel table values, top-layer hover
  tooltips, compact transparent Tx/Rx legend, and aligned bottom toolbar inputs.
- Readable JSON layout import/export with optional evaluation metadata.
- Current-configuration performance report export to a multi-page PDF, with
  selectable Az/El focus and frame-hold ranges, independent dB/magnitude
  spectrum pages, and optional CSV/JSON audit data.
- Local state persistence (last paths, frequency, window geometry, layout).
- PyInstaller onedir packaging for Windows.

### Fluent 2 Desktop Interface

- Resizable window: **1366 × 768** default, **1100 × 650** minimum, clamped to
  the available screen area when restored.
- Three localized tab pages:
  - **Physical & Virtual** — Physical and virtual array side by side (1:1).
  - **1D DBF** — Azimuth and elevation response spectra side by side (1:1).
  - **2D DBF** — Full-tab 2D heatmap with playback controls.
- Draggable workspace/overview splitter, with the side panel kept in a readable
  280–360 px range:
  - Channel count, virtual channels, aperture, resolution.
  - Angle evaluation: no-fold range, max error, peak margin, cut reason.
- Native Qt menus, dialogs, tables, status bar, keyboard focus, and standard
  action icons, styled through one Fluent 2 token/QSS theme.
- Neutral capability guidance replaces misleading flat spectra or heatmaps when
  an array has no usable aperture in one or both axes.
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
# Canonical launcher
python GUI.py

# Compatibility alias; opens the same interface
python GUI_mod.py

# Installed console entry point
mimo-array-visualizer
```

Windows:

```powershell
.\scripts\run_gui.ps1
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

### Current-Configuration Performance Report

Use **File → Export Current Performance Report…** to choose the PDF path,
the Az/El performance focus ranges, and the true-angle frame ranges included
in the spectrum hold plots. The report can include dB plots, normalized
correlation-magnitude plots, or both. Each axis/unit combination gets a full
page containing one spectrum chart, and every selected 1° frame is retained in
its overlay. Both units come from the same per-frame signal-to-1D-dictionary
normalized correlation (`magnitude = 10^(dB/20)`); they are display forms of
one calculation rather than separate DBF algorithms. An optional data package
exports the exact configuration plus per-frame and spectrum CSV files.

Angle-error pages scale their vertical axes from finite errors inside the
selected performance focus range, following the HFSS report plotting rule.
Folded errors outside that range may be visually clipped so useful small-error
detail remains readable; the complete values remain in the exported CSV data.

For a 2D-capable array, these Az/El pages are explicitly reported as orthogonal
main-plane diagnostics: the azimuth sweep fixes true elevation at 0°, and the
elevation sweep fixes true azimuth at 0°. They are not presented as a full
joint 2D error-volume validation.

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

Repeatable visual review (isolated state, three pages plus four dialogs):

```bash
python scripts/capture_ui_review.py --output-dir outputs/ui-review
python scripts/capture_ui_review.py --output-dir outputs/ui-review-8t8r --skip-dialogs --auto-tx 8 --auto-rx 8
```

Entry points:

```bash
mimo-array-visualizer
mimo-array-case4
```

---

## Project Structure

```
GUI.py              → Canonical launcher for virtual_array.gui
GUI_mod.py          → Compatibility alias for the same interface
src/virtual_array/
  gui.py            → Single native PySide6 GUI (resizable, three-page layout)
  geometry.py       → ArrayPoint, VirtualPoint, AntennaArray
  analysis.py       → Metrics, PSF, DBF spectra
  performance_report.py → PDF report, focus statistics, Hold data package
  performance_report_dialog.py → Native report configuration dialog
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

桌面端采用原生 **PySide6 / pyqtgraph** 和 Fluent 2 浅色主题，并只维护
`virtual_array.gui` 一套实现。`GUI.py`、`GUI_mod.py` 与安装后的控制台命令
均打开同一个三页界面；`GUI_mod.py` 仅用于兼容已有快捷方式。

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
- 顶部 **通道幅相** 状态分别显示幅度、相位为理想、导入或混合；导入单元方向图时幅度视为导入。
- 通道方向图界面细节优化：通道表内容居中、悬停信息置顶、Tx/Rx 图例紧凑透明、底部工具条输入框对齐。
- 可读的 JSON 布局导入/导出（含评估元数据）。
- 当前配置性能报告：可选方位/俯仰关注范围、逐帧 Hold 真实角范围以及
  dB/归一化模值角谱，输出多页 PDF 及可选 CSV/JSON 可复现数据包。
- 本地状态持久化（最近路径、频率、窗口几何、布局）。
- PyInstaller onedir Windows 打包。

### Fluent 2 桌面界面

- 可缩放窗口：默认 **1366 × 768**，最小 **1100 × 650**；恢复窗口时自动限制在屏幕可用区域内。
- 三个已本地化的子页面：
  - **Physical & Virtual** — 物理阵列与虚拟阵列左右并排（1:1）。
  - **1D DBF** — 方位与俯仰响应曲线左右并排（1:1）。
  - **2D DBF** — 全页 2D 热图及播放控件。
- 主工作区与右侧 **Overview** 通过可拖动分隔条布局，侧栏保持 280–360 px 的可读宽度：
  - 通道数、虚拟通道、口径、分辨率。
  - 测角评估：不模糊范围、最大误差、竞争峰裕量、截断原因。
- 原生 Qt 菜单、弹窗、表格、状态栏、键盘焦点和标准操作图标，统一由 Fluent 2 token/QSS 主题控制。
- 阵列在某方向无有效孔径时显示中性能力提示，不再显示误导性的平直角谱或整片热图。
- 跨平台中文字体（macOS / Windows / Linux）。
- 预配置 OpenCode 技能和 ruff/pyright 工具。

### 当前配置性能报告

从 **文件 → 输出当前配置性能报告…** 进入配置对话框，可选报告路径、
方位/俯仰测角性能关注范围、角谱逐帧 Hold 的真实角范围，以及 dB、
归一化模值两种纵坐标（可单选或同时输出）。每个“维度 × 纵坐标”组合
独占一整页且只放一张角谱图，所选 1° 帧全部进入叠加曲线，不会抽帧。
dB 与模值来自同一套逐帧“信号—1D DBF 字典”归一化相关结果，模值按
`10^(dB/20)` 转换，并不是另一套测角算法。

测角误差页按所选“性能关注范围”内的有限误差自适应纵轴，遵循 HFSS 报告
绘图口径；关注范围外的折返误差可能在图上被裁切，以保留小误差细节，
完整原始值仍保存在可选 CSV 数据包中。

对于具备二维孔径的阵列，报告中两个 1D DBF 页明确定义为正交主平面诊断：
方位扫描时真实俯仰固定为 0°，俯仰扫描时真实方位固定为 0°；
它们不会被表述为完整的联合二维误差体验证。

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
python GUI.py       # 正式入口
python GUI_mod.py   # 兼容别名，打开同一界面
mimo-array-visualizer
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

可重复视觉验收（隔离状态，批量生成三页和四个弹窗）：

```bash
python scripts/capture_ui_review.py --output-dir outputs/ui-review
python scripts/capture_ui_review.py --output-dir outputs/ui-review-8t8r --skip-dialogs --auto-tx 8 --auto-rx 8
```

---

# 日本語

MIMOアレイ可視化ツール — MIMO送信/受信アンテナアレイ配置を対話的に編集・評価するデスクトップアプリです。仮想アレイ形状、2Dアレイファクタ、レーダ性能指標（PSL、ビーム幅、ISLR、グレーティングローブ、仰角曖昧性）を計算します。

デスクトップ UI はネイティブ **PySide6 / pyqtgraph** と Fluent 2 のライトテーマを採用し、`virtual_array.gui` の 1 実装だけを保守します。`GUI.py`、`GUI_mod.py`、インストール済みコンソールコマンドはすべて同じ 3 ページ画面を起動し、`GUI_mod.py` は既存ショートカット用の互換エイリアスです。

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
- ヘッダーの **チャネル振幅/位相** ステータスで、振幅と位相をそれぞれ理想・読込・混在として表示。要素パターン読み込み時は振幅を読込扱いにします。
- チャネルパターン UI を調整：表の値を中央揃え、ホバー情報を最前面表示、Tx/Rx 凡例を小さく透明化、下部ツールバー入力欄を整列。
- 可読 JSON 配置の読み込み/書き出し（評価メタデータ付き）
- 現在設定の性能レポート（Az/El 評価範囲、全選択フレーム Hold、
  複数ページ PDF、任意の CSV/JSON 再現データ）
- ローカル状態の永続化
- PyInstaller onedir Windows パッケージ

### Fluent 2 デスクトップ UI

- リサイズ可能：既定 **1366 × 768**、最小 **1100 × 650**。復元時は利用可能な画面領域内に収めます。
- ローカライズ済みの 3 ページ：
  - **Physical & Virtual** — 物理/仮想アレイ左右 1:1
  - **1D DBF** — 方位/仰角応答スペクトル左右 1:1
  - **2D DBF** — タブ全体の 2D ヒートマップ
- メイン領域と右側 **Overview** はドラッグ可能なスプリッターで構成し、側面パネルは 280–360 px の読みやすい幅を維持
- ネイティブ Qt のメニュー、ダイアログ、テーブル、ステータスバー、キーボードフォーカス、標準アクションアイコンを単一の Fluent 2 token/QSS テーマで統一
- 有効な開口がない軸では、誤解を招く平坦スペクトルやヒートマップの代わりに中立的な案内を表示
- クロスプラットフォーム中国語フォント対応
- OpenCode スキル・ruff/pyright ツール設定済み

## クイックスタート

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python GUI.py        # 正式エントリ
python GUI_mod.py    # 同じ画面を開く互換エイリアス
mimo-array-visualizer
```

## 開発

```bash
pytest tests/ -x -q   # テスト実行
ruff check .          # リント
ruff format .         # フォーマット
```

再現可能なビジュアル確認（状態を分離し、3 ページと 4 ダイアログを一括生成）：

```bash
python scripts/capture_ui_review.py --output-dir outputs/ui-review
python scripts/capture_ui_review.py --output-dir outputs/ui-review-8t8r --skip-dialogs --auto-tx 8 --auto-rx 8
```
