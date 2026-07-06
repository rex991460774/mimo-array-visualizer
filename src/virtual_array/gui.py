from __future__ import annotations

import json
import logging
import math
import re
import tkinter as tk
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import numpy as np
from matplotlib import rcParams
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from matplotlib.widgets import Button as MplButton

from .app_state import load_state, save_state, state_path
from .dbf_dictionary import (
    DBF_DICT_CHANNEL_PATTERN,
    DBF_DICT_CHANNEL_PATTERN_ZERO_REF,
    DBF_DICT_CUSTOM,
    DBF_DICT_IDEAL,
    DBF_DICT_IDEAL_REVERSED,
    DbfDictionaryConfig,
    DbfDictionaryTable,
    dictionary_phase_preview,
    load_dbf_dictionary_table,
)
from .analysis import (
    AZIMUTH_FOV,
    DBF_AMBIGUITY_MARGIN_DB,
    DBF_SCAN_FOV,
    DBF_SCAN_GRID_SIZE,
    DBF_SCAN_STEP_DEG,
    DbfAngleMetrics,
    ELEVATION_FOV,
    MAINLOBE_GUARD_AZ,
    MAINLOBE_GUARD_EL,
    ArrayMetrics,
    calculate_metrics_and_psf,
    dbf_angle_metrics_from_spectra,
    dbf_2d_spectrum,
    dbf_2d_normalization_reference,
    dbf_azimuth_spectrum_bank,
    dbf_elevation_spectrum_bank,
    local_peak_indices,
)
from .element_pattern import (
    PATTERN_KIND_AMPLITUDE,
    PATTERN_KIND_PHASE,
    PATTERN_PLANE_ELEVATION,
    PATTERN_PLANE_HORIZONTAL,
    ChannelPatternSet,
    ElementPattern,
    format_pattern_cut_metrics,
    load_hfss_pattern_series,
    load_hfss_summary_pattern,
    load_element_pattern,
    pattern_cut_metrics,
)
from .geometry import AntennaArray, ArrayPoint
from .grid import GRID_STEP, snap_to_grid
from .logging_config import configure_logging, current_log_path, install_excepthook
from .version import APP_VERSION


LOGGER = logging.getLogger(__name__)

rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun", "DejaVu Sans"]
rcParams["axes.unicode_minus"] = False

# ── Global constants ──────────────────────────────────────────────────
ROUND_DECIMALS = 9
LAYOUT_CONFIG_VERSION = 1
LOCAL_STATE_VERSION = 1
LAYOUT_UNIT = "lambda"
LAYOUT_UNITS_LAMBDA = {"lambda", "λ"}
LEGACY_LAYOUT_UNITS_HALF_LAMBDA = {"lambda/2", "λ/2"}
MAX_TX_COUNT = 16
MAX_RX_COUNT = 16
MAX_HISTORY_STATES = 50
AUTO_LAYOUT_SPACING = 2.0
AUTO_LAYOUT_TX_Y = 4.0
AUTO_LAYOUT_RX_Y = -4.0
TITLE_SIZE = 13
RESPONSE_MODE_AZIMUTH = "az"
RESPONSE_MODE_ELEVATION = "el"
RESPONSE_SIDELOBE_PROMINENCE_DB = 0.5
RESPONSE_SIDELOBE_GUARD_CLEARANCE_DB = 0.5
DBF_SCAN_INTERVAL_MS = 55
LANGUAGE_ZH = "zh"
LANGUAGE_EN = "en"
LANGUAGE_JA = "ja"
SUPPORTED_LANGUAGES = (LANGUAGE_ZH, LANGUAGE_EN, LANGUAGE_JA)
LANGUAGE_LABELS = {
    LANGUAGE_ZH: "中文",
    LANGUAGE_EN: "English",
    LANGUAGE_JA: "日本語",
}

DEFAULT_FREQUENCY_GHZ = 77.0
LIGHT_SPEED_MM_PER_NS = 299.792458  # mm/ns = GHz·mm

DISPLAY_SCALE_LAMBDA = 0.5
DISPLAY_GRID_STEP_LAMBDA = 0.5
PHYSICAL_MAJOR_GRID_STEP_LAMBDA = 1.0
PHYSICAL_AXIS_MIN_SPAN_LAMBDA = 4.0
PHYSICAL_AXIS_PADDING_LAMBDA = 2.0

# Window geometry
WINDOW_WIDTH = 1720
WINDOW_HEIGHT = 1060
WINDOW_MIN_WIDTH = 1280
WINDOW_MIN_HEIGHT = 860
WINDOW_GEOMETRY_RE = re.compile(
    r"^(?P<width>\d+)x(?P<height>\d+)(?:(?P<x>[+-]\d+)(?P<y>[+-]\d+))?$"
)

# Figure DPI (fixed for consistent rendering across displays)
FIG_DPI = 100

# Figure sizes (inches → pixels at FIG_DPI)
PHYS_FIG_W = 6.8
PHYS_FIG_H = 3.2
VIRT_FIG_W = 6.8
VIRT_FIG_H = 3.2
RESPONSE_FIG_W = 6.8
RESPONSE_FIG_H = 2.8
PLOT_COLUMN_MIN_WIDTH = 430
EVAL_PANEL_MIN_WIDTH = 370
DBF2D_CANVAS_SIZE = 345
DBF2D_FIG_SIZE = DBF2D_CANVAS_SIZE / FIG_DPI

NOTE_STYLES = {
    "duplicate": ("WARN", "#c2410c"),
    "windowing": ("TAPER", "#a16207"),
    "ambiguity high": ("RISK", "#b91c1c"),
    "ambiguity medium": ("WATCH", "#a16207"),
    "none": ("OK", "#15803d"),
}

UI_TEXT = {
    "app_title": {
        "zh": "MIMO阵列可视化工具 V{version}",
        "en": "MIMO Array Visualizer V{version}",
        "ja": "MIMOアレイ可視化ツール V{version}",
    },
    "app_name": {
        "zh": "MIMO阵列工作台",
        "en": "MIMO Array Workbench",
        "ja": "MIMOアレイワークベンチ",
    },
    "app_subtitle": {
        "zh": "阵列布局、虚拟孔径、响应曲线与DBF扫描",
        "en": "Array layout, virtual aperture, response curves, and DBF scan",
        "ja": "アレイ配置、仮想開口、応答曲線、DBFスキャン",
    },
    "chip_frequency": {"zh": "频率", "en": "Frequency", "ja": "周波数"},
    "chip_dictionary": {"zh": "DBF字典", "en": "DBF Dictionary", "ja": "DBF辞書"},
    "chip_pattern": {"zh": "方向图", "en": "Pattern", "ja": "パターン"},
    "chip_virtual_channels": {"zh": "虚拟通道", "en": "Virtual", "ja": "仮想"},
    "chip_az_resolution": {"zh": "方位分辨率", "en": "Az Res", "ja": "方位分解能"},
    "chip_el_resolution": {"zh": "俯仰分辨率", "en": "El Res", "ja": "仰角分解能"},
    "chip_peak_margin": {"zh": "峰值裕量", "en": "Peak Margin", "ja": "ピーク余裕"},
    "status_initial": {
        "zh": "拖动TX/RX通道调整物理阵列，松开后自动刷新虚拟阵列和响应。",
        "en": "Drag Tx/Rx channels in the physical array. Release to refresh the virtual array and responses.",
        "ja": "物理アレイ上のTX/RXチャネルをドラッグします。離すと仮想アレイと応答を更新します。",
    },
    "status_ready": {"zh": "就绪", "en": "Ready", "ja": "準備完了"},
    "menu_config": {"zh": "配置", "en": "Configuration", "ja": "設定"},
    "menu_import_layout": {
        "zh": "导入阵面JSON",
        "en": "Import Array JSON",
        "ja": "アレイJSONを読み込み",
    },
    "menu_export_layout": {
        "zh": "导出阵面JSON",
        "en": "Export Array JSON",
        "ja": "アレイJSONを書き出し",
    },
    "menu_channel_patterns": {
        "zh": "设置通道幅相CSV",
        "en": "Set Channel Amp/Phase CSV",
        "ja": "チャネル振幅/位相CSVを設定",
    },
    "menu_dbf_dictionary": {
        "zh": "配置DBF字典",
        "en": "Configure DBF Dictionary",
        "ja": "DBF辞書を設定",
    },
    "menu_language": {"zh": "语言", "en": "Language", "ja": "言語"},
    "menu_file": {"zh": "文件", "en": "File", "ja": "ファイル"},
    "menu_edit": {"zh": "编辑", "en": "Edit", "ja": "編集"},
    "menu_view": {"zh": "视图", "en": "View", "ja": "表示"},
    "menu_help": {"zh": "帮助", "en": "Help", "ja": "ヘルプ"},
    "menu_undo": {"zh": "撤销阵列编辑", "en": "Undo layout edit", "ja": "配置編集を元に戻す"},
    "menu_redo": {"zh": "重做阵列编辑", "en": "Redo layout edit", "ja": "配置編集をやり直す"},
    "menu_about": {"zh": "关于", "en": "About", "ja": "このアプリについて"},
    "menu_user_manual": {"zh": "使用说明", "en": "User Manual", "ja": "使用説明"},
    "manual_title": {"zh": "MIMO阵列可视化工具使用说明", "en": "MIMO Array Visualizer User Manual", "ja": "MIMOアレイ可視化ツール使用説明"},
    "manual_body": {
        "zh": (
            "MIMO阵列可视化工具使用说明\n\n"
            "这个程序用来快速搭建 TX/RX 阵列，观察虚拟孔径，并检查 DBF 测角是否容易出现模糊、跳变或旁瓣竞争。\n\n"
            "一、主要子模块\n"
            "物理阵列：这里是真实 TX/RX 的位置。可以添加、删除、拖动通道，坐标单位按波长显示。物理位置改变后，后面的虚拟阵列和角谱都会重新计算。\n"
            "虚拟阵列：显示 TX 与 RX 组合后的等效采样点。点越分散，通常角分辨率越好；点重合越多，可用虚拟通道越少。\n"
            "方位/俯仰 1D 角谱：看某一个真实角下，DBF 字典会把峰值打到哪里。橙色线是真实角，叉号是估计峰值。拖动橙色线可以手动检查不同真实角。\n"
            "总览与测角评估：总览看通道数、虚拟通道、口径和分辨率；测角评估看不模糊范围、范围内最大误差、竞争峰裕量和截断原因。\n"
            "2D DBF 热图：同时看方位和俯仰。颜色越亮表示归一化增益越高，白色十字是真实角，叉号是峰值位置。拖动十字可以同时改变真实方位和真实俯仰。\n"
            "底部参数：频率影响物理尺寸换算；竞争峰裕量用于判断峰值是否可靠；自动排阵可以快速生成指定数量的 T/R 通道。\n\n"
            "二、顶部二级菜单\n"
            "文件 > 导入阵面 JSON：读取之前保存的 TX/RX 布局。\n"
            "文件 > 导出阵面 JSON：保存当前布局、评估结果和当前配置，方便复现实验。\n"
            "编辑 > 撤销/重做阵列编辑：回退或恢复最近的阵列位置、添加、删除操作。\n"
            "编辑 > 设置通道幅相 CSV：给每个物理通道加载 HFSS 等工具导出的幅度/相位方向图。不加载时，该通道按理想通道处理。汇总 CSV 可以一次加载多通道；1T2R 相位文件如果只有两列数据，会按 Rx1、Rx2 读取，三列则按 Tx1、Rx1、Rx2 读取。\n"
            "编辑 > 配置 DBF 字典：选择测角时使用哪种字典。理想几何字典只按阵列几何算相位；理想反向相位用于快速检查符号约定；通道幅相校准字典会叠加已导入的通道方向图；导入 CSV/XLSX 字典用于使用外部仿真或实测字典。\n"
            "视图 > 中文/英文/日文：切换界面语言。\n"
            "帮助 > 使用说明：打开本说明。帮助 > 关于：查看版本和日志路径。\n\n"
            "三、常见使用顺序\n"
            "先摆放或导入阵列，再设置频率和竞争峰裕量；如果有通道幅相或外部字典，再从编辑菜单导入；最后看 1D 角谱、2D 热图和测角评估，确认峰值是否跟随真实角、误差是否可接受。"
        ),
        "en": (
            "MIMO Array Visualizer User Manual\n\n"
            "This tool helps you build a TX/RX array, inspect the virtual aperture, and check whether DBF angle estimation is likely to suffer from ambiguity, jumps, or competing sidelobes.\n\n"
            "Main modules\n"
            "Physical array: the real TX/RX positions. Add, delete, or drag channels. Coordinates are displayed in wavelengths, and every layout change recalculates the virtual array and spectra.\n"
            "Virtual array: the equivalent sampling points created by TX/RX combinations. Wider spread usually improves resolution; duplicate points reduce usable virtual channels.\n"
            "Az/El 1D spectra: show where the DBF dictionary peaks for a selected true angle. The orange line is the true angle and the cross is the estimated peak. Drag the orange line to inspect other angles.\n"
            "Overview and angle evaluation: overview reports channel count, virtual channels, aperture, and resolution; angle evaluation reports no-fold range, max error, peak margin, and why the valid range stops.\n"
            "2D DBF heatmap: shows azimuth and elevation together. Brighter color means stronger normalized gain, the white crosshair is the true angle, and the cross marker is the peak. Drag the crosshair to change both true angles.\n"
            "Footer parameters: frequency controls size conversion; peak margin controls reliability checks; Auto Array quickly creates a requested T/R count.\n\n"
            "Top menu items\n"
            "File > Import Array JSON: load a saved TX/RX layout.\n"
            "File > Export Array JSON: save the current layout, evaluation, and configuration.\n"
            "Edit > Undo/Redo: step backward or forward through recent layout edits.\n"
            "Edit > Set Channel Amp/Phase CSV: load per-channel amplitude or phase patterns from HFSS-like exports. Missing channels stay ideal. Summary CSV files can load several channels at once; for 1T2R phase data, two data columns map to Rx1/Rx2 and three data columns map to Tx1/Rx1/Rx2.\n"
            "Edit > Configure DBF Dictionary: choose the dictionary used for angle estimation. Ideal geometric uses only array geometry; ideal reversed phase checks sign convention; channel amp/phase uses imported channel data; imported CSV/XLSX uses an external simulated or measured dictionary.\n"
            "View: switch language. Help: open this manual or the About dialog.\n\n"
            "Typical flow\n"
            "Place or import the array, set frequency and peak margin, import channel data or dictionaries if available, then check the 1D spectra, 2D heatmap, and angle evaluation to confirm that peaks track the true angle."
        ),
        "ja": (
            "MIMOアレイ可視化ツール使用説明\n\n"
            "このツールは TX/RX アレイを作成し、仮想開口を確認し、DBF 測角で曖昧性、ジャンプ、競合サイドローブが起きやすいかを見るためのものです。\n\n"
            "主なモジュール\n"
            "物理アレイ：実際の TX/RX 位置です。チャネルの追加、削除、ドラッグができ、座標は波長単位で表示されます。\n"
            "仮想アレイ：TX/RX の組み合わせでできる等価サンプル点です。広がりが大きいほど分解能は良くなりやすく、重複点が多いほど有効チャネルは減ります。\n"
            "方位/仰角 1D スペクトル：選んだ真角度に対して DBF 辞書のピークがどこに出るかを示します。オレンジ線が真角度、× が推定ピークです。\n"
            "概要と測角評価：概要はチャネル数、仮想チャネル、開口、分解能を表示します。測角評価は非曖昧範囲、最大誤差、ピーク余裕、範囲が止まる理由を表示します。\n"
            "2D DBF ヒートマップ：方位と仰角を同時に見ます。明るいほど正規化利得が高く、白い十字が真角度、× がピークです。\n"
            "下部パラメータ：周波数は寸法換算に使います。ピーク余裕は信頼性判定に使います。自動配置は指定した T/R 数を素早く作成します。\n\n"
            "上部メニュー\n"
            "ファイル > アレイ JSON 読み込み：保存済みの TX/RX 配置を読み込みます。\n"
            "ファイル > アレイ JSON 書き出し：現在の配置、評価、設定を保存します。\n"
            "編集 > 元に戻す/やり直し：最近の配置編集を戻す、または復元します。\n"
            "編集 > チャネル振幅/位相 CSV：HFSS などのチャネル振幅/位相データを読み込みます。未設定チャネルは理想として扱います。1T2R 位相データでは、2 列は Rx1/Rx2、3 列は Tx1/Rx1/Rx2 として読みます。\n"
            "編集 > DBF 辞書設定：測角に使う辞書を選びます。理想幾何、逆位相確認、チャネル振幅/位相、外部 CSV/XLSX 辞書を選択できます。\n"
            "表示：言語を切り替えます。ヘルプ：この説明書またはバージョン情報を開きます。\n\n"
            "基本の流れ\n"
            "アレイを配置または読み込み、周波数とピーク余裕を設定し、必要ならチャネルデータや辞書を読み込み、1D スペクトル、2D ヒートマップ、測角評価を確認します。"
        ),
    },
    "about_title": {"zh": "关于 MIMO阵列工作台", "en": "About MIMO Array Workbench", "ja": "MIMOアレイワークベンチについて"},
    "about_message": {
        "zh": "MIMO阵列工作台 V{version}\n日志文件：{log_path}",
        "en": "MIMO Array Workbench V{version}\nLog file: {log_path}",
        "ja": "MIMOアレイワークベンチ V{version}\nログファイル：{log_path}",
    },
    "language_zh": {"zh": "中文", "en": "Chinese", "ja": "中国語"},
    "language_en": {"zh": "英文", "en": "English", "ja": "英語"},
    "language_ja": {"zh": "日语", "en": "Japanese", "ja": "日本語"},
    "freq_label": {"zh": "频率(GHz)", "en": "Freq (GHz)", "ja": "周波数(GHz)"},
    "margin_label": {"zh": "竞争峰裕量(dB)", "en": "Peak margin (dB)", "ja": "競合ピーク余裕(dB)"},
    "auto_label": {"zh": "自动排阵", "en": "Auto Array", "ja": "自動配置"},
    "auto_apply": {"zh": "应用阵列", "en": "Apply Array", "ja": "配置を適用"},
    "physical_add_tx": {"zh": "+TX", "en": "+TX", "ja": "+TX"},
    "physical_add_rx": {"zh": "+RX", "en": "+RX", "ja": "+RX"},
    "physical_delete": {"zh": "删除", "en": "Delete", "ja": "削除"},
    "physical_clear": {"zh": "清空", "en": "Clear", "ja": "クリア"},
    "dbf_play_compact": {"zh": "播放", "en": "Play", "ja": "再生"},
    "dbf_pause_compact": {"zh": "暂停", "en": "Pause", "ja": "一時停止"},
    "dbf_resume_compact": {"zh": "继续", "en": "Resume", "ja": "再開"},
    "dbf_stop_compact": {"zh": "停止", "en": "Stop", "ja": "停止"},
    "pattern_ideal": {"zh": "方向图：理想", "en": "Patterns: ideal", "ja": "パターン：理想"},
    "pattern_legacy": {
        "zh": "方向图：旧版单元",
        "en": "Patterns: legacy element",
        "ja": "パターン：旧要素",
    },
    "pattern_element_summary": {
        "zh": "方向图：{name}",
        "en": "Pattern: {name}",
        "ja": "パターン：{name}",
    },
    "pattern_summary": {
        "zh": "方向图：{channels}通道 / {series}文件",
        "en": "Patterns: {channels} ch / {series} files",
        "ja": "パターン：{channels}ch / {series}ファイル",
    },
    "overview_title": {"zh": "  阵列概览  ", "en": "  Array Overview  ", "ja": "  アレイ概要  "},
    "angle_eval_title": {"zh": "  测角评估  ", "en": "  Angle Evaluation  ", "ja": "  測角評価  "},
    "eval_tab_overview": {"zh": "总览", "en": "Overview", "ja": "概要"},
    "eval_tab_angle": {"zh": "测角", "en": "Angle", "ja": "測角"},
    "eval_tab_dbf2d": {"zh": "2D DBF", "en": "2D DBF", "ja": "2D DBF"},
    "physical_title": {"zh": "物理阵列布局", "en": "Physical Array", "ja": "物理アレイ配置"},
    "virtual_title": {"zh": "虚拟阵列", "en": "Virtual Array", "ja": "仮想アレイ"},
    "virtual_info": {
        "zh": "虚拟 {unique}/{total} | 重复 {duplicate} | X {x} | Y {y}",
        "en": "Virtual {unique}/{total} | Dup {duplicate} | X {x} | Y {y}",
        "ja": "仮想 {unique}/{total} | 重複 {duplicate} | X {x} | Y {y}",
    },
    "virtual_pairs_more": {"zh": ", ...（共{count}组）", "en": ", ... ({count} pairs)", "ja": ", ...（計{count}組）"},
    "virtual_hover": {
        "zh": "({x:g} λ, {y:g} λ)\n重合数量：{count}\n{pairs}",
        "en": "({x:g} λ, {y:g} λ)\nMultiplicity: {count}\n{pairs}",
        "ja": "({x:g} λ, {y:g} λ)\n重複数：{count}\n{pairs}",
    },
    "unique_point": {"zh": "唯一点", "en": "unique point", "ja": "一意点"},
    "duplicate_point": {"zh": "重复点", "en": "duplicate point", "ja": "重複点"},
    "response_title": {"zh": "{mode}响应", "en": "{mode} Response", "ja": "{mode}応答"},
    "pattern_cut_label": {"zh": "{mode}方向图", "en": "{mode} pattern", "ja": "{mode}パターン"},
    "dbf_title": {
        "zh": "{mode}DBF字典角谱",
        "en": "{mode} DBF Dictionary Spectrum",
        "ja": "{mode}DBF辞書角度スペクトル",
    },
    "axis_az_angle": {"zh": "方位角(°)", "en": "Azimuth angle (deg)", "ja": "方位角(°)"},
    "axis_el_angle": {"zh": "俯仰角(°)", "en": "Elevation angle (deg)", "ja": "仰角(°)"},
    "axis_gain": {"zh": "归一化增益(dB)", "en": "Normalized gain (dB)", "ja": "正規化利得(dB)"},
    "max_sidelobe": {"zh": "最大旁瓣", "en": "Max sidelobe", "ja": "最大サイドローブ"},
    "guard_edge_max": {"zh": "保护区边界最大值", "en": "Guard-edge max", "ja": "ガード端最大値"},
    "grating_lobe": {"zh": "栅瓣", "en": "Grating lobe", "ja": "グレーティングローブ"},
    "grating_lobe_max": {
        "zh": "栅瓣=最大旁瓣",
        "en": "Grating lobe = max sidelobe",
        "ja": "グレーティングローブ=最大サイドローブ",
    },
    "gain_value": {"zh": "增益 = {value:.2f} dB", "en": "Gain = {value:.2f} dB", "ja": "利得 = {value:.2f} dB"},
    "dbf2d_hover": {
        "zh": "方位 = {az:+.1f}°\n俯仰 = {el:+.1f}°\n增益 = {gain:.2f} dB",
        "en": "Az = {az:+.1f} deg\nEl = {el:+.1f} deg\nGain = {gain:.2f} dB",
        "ja": "方位 = {az:+.1f}°\n仰角 = {el:+.1f}°\n利得 = {gain:.2f} dB",
    },
    "psl_label": {"zh": "{mode} PSL：{value:.2f} dB", "en": "{mode} PSL: {value:.2f} dB", "ja": "{mode} PSL：{value:.2f} dB"},
    "az": {"zh": "方位", "en": "Azimuth", "ja": "方位"},
    "el": {"zh": "俯仰", "en": "Elevation", "ja": "仰角"},
    "az_short": {"zh": "方位", "en": "Az", "ja": "方位"},
    "el_short": {"zh": "俯仰", "en": "El", "ja": "仰角"},
    "legend_true_angle": {"zh": "真实角", "en": "true angle", "ja": "真角度"},
    "legend_peak": {"zh": "峰值", "en": "peak", "ja": "ピーク"},
    "dbf_info": {
        "zh": "真实角：{true:+.1f}°\n峰值角：{peak:+.1f}°\n{frame}",
        "en": "True angle: {true:+.1f} deg\nPeak angle: {peak:+.1f} deg\n{frame}",
        "ja": "真角度：{true:+.1f}°\nピーク角：{peak:+.1f}°\n{frame}",
    },
    "reference_frame": {"zh": "参考：0°", "en": "Reference: 0 deg", "ja": "基準：0°"},
    "frame_label": {"zh": "帧：{frame}/{total}", "en": "Frame: {frame}/{total}", "ja": "フレーム：{frame}/{total}"},
    "dbf_play_status": {
        "zh": "正在播放{mode}DBF角谱：-90°到+90°。",
        "en": "Playing {mode} DBF spectra from -90 deg to +90 deg.",
        "ja": "{mode}DBF角度スペクトルを再生中：-90°から+90°。",
    },
    "dbf_play_status_invalid": {
        "zh": "频率输入已恢复，正在播放{mode}DBF角谱。",
        "en": "Invalid frequency restored. Playing {mode} DBF spectra.",
        "ja": "無効な周波数を復元し、{mode}DBF角度スペクトルを再生中。",
    },
    "dbf_pause_status": {
        "zh": "{mode}DBF角谱已暂停在{angle:+.1f}°。",
        "en": "Paused {mode} DBF spectrum at {angle:+.1f} deg.",
        "ja": "{mode}DBF角度スペクトルを{angle:+.1f}°で一時停止。",
    },
    "dbf_resume_status": {
        "zh": "继续播放{mode}DBF角谱动画。",
        "en": "Resumed {mode} DBF spectrum animation.",
        "ja": "{mode}DBF角度スペクトルアニメーションを再開。",
    },
    "dbf_complete_status": {
        "zh": "{mode}DBF角谱动画播放完成。",
        "en": "{mode} DBF spectrum animation complete.",
        "ja": "{mode}DBF角度スペクトルアニメーションが完了。",
    },
    "dbf2d_title": {"zh": "  2D DBF热图  ", "en": "  2D DBF Heatmap  ", "ja": "  2D DBFヒートマップ  "},
    "dbf2d_plot_title": {"zh": "2D DBF角谱", "en": "2D DBF Spectrum", "ja": "2D DBF角度スペクトル"},
    "dbf2d_play_az": {"zh": "播放方位", "en": "Play Az", "ja": "方位再生"},
    "dbf2d_pause_az": {"zh": "暂停方位", "en": "Pause Az", "ja": "方位一時停止"},
    "dbf2d_play_el": {"zh": "播放俯仰", "en": "Play El", "ja": "仰角再生"},
    "dbf2d_pause_el": {"zh": "暂停俯仰", "en": "Pause El", "ja": "仰角一時停止"},
    "dbf2d_stop": {"zh": "停止2D", "en": "Stop 2D", "ja": "2D停止"},
    "dbf2d_status": {
        "zh": "方位{az:+.0f}°  俯仰{el:+.0f}°  {frame}/{total}",
        "en": "Az {az:+.0f} deg  El {el:+.0f} deg  {frame}/{total}",
        "ja": "方位{az:+.0f}°  仰角{el:+.0f}°  {frame}/{total}",
    },
    "dbf2d_heatmap_info": {
        "zh": "真值：方位 {az:+.0f}°，俯仰 {el:+.0f}°\n峰值：方位 {peak_az:+.0f}°，俯仰 {peak_el:+.0f}°",
        "en": "True: Az {az:+.0f} deg, El {el:+.0f} deg\nPeak: Az {peak_az:+.0f} deg, El {peak_el:+.0f} deg",
        "ja": "真値：方位 {az:+.0f}°，仰角 {el:+.0f}°\nピーク：方位 {peak_az:+.0f}°，仰角 {peak_el:+.0f}°",
    },
    "dbf2d_peak_delta": {
        "zh": "峰值偏差\n方位 {az:+.0f}° | 俯仰 {el:+.0f}°",
        "en": "Peak delta\nAz {az:+.0f} deg | El {el:+.0f} deg",
        "ja": "ピーク偏差\n方位 {az:+.0f}° | 仰角 {el:+.0f}°",
    },
    "dbf2d_colorbar_label": {"zh": "归一化增益(dB)", "en": "Normalized gain (dB)", "ja": "正規化利得(dB)"},
    "dbf2d_running": {
        "zh": "正在播放2D DBF：{axes}。",
        "en": "Playing 2D DBF: {axes}.",
        "ja": "2D DBF再生中：{axes}。",
    },
    "dbf2d_paused_axis": {
        "zh": "已暂停2D DBF的{axis}扫描。",
        "en": "Paused 2D DBF {axis} scan.",
        "ja": "2D DBFの{axis}走査を一時停止。",
    },
    "dbf2d_dragged": {
        "zh": "已拖动2D DBF真实角：方位 {az:+.0f}°，俯仰 {el:+.0f}°。",
        "en": "Moved 2D DBF true angle: Az {az:+.0f} deg, El {el:+.0f} deg.",
        "ja": "2D DBF真角度を移動：方位 {az:+.0f}°，仰角 {el:+.0f}°。",
    },
    "dbf2d_stopped": {
        "zh": "已停止2D DBF扫描。",
        "en": "Stopped 2D DBF scan.",
        "ja": "2D DBF走査を停止しました。",
    },
    "dbf_dictionary_title": {
        "zh": "DBF字典配置",
        "en": "DBF Dictionary",
        "ja": "DBF辞書設定",
    },
    "dbf_dictionary_mode_title": {"zh": "  字典模式  ", "en": "  Dictionary Mode  ", "ja": "  辞書モード  "},
    "dbf_dictionary_preview_title": {"zh": "  字典预览  ", "en": "  Dictionary Preview  ", "ja": "  辞書プレビュー  "},
    "dbf_dict_ideal": {"zh": "理想几何字典", "en": "Ideal geometric", "ja": "理想幾何辞書"},
    "dbf_dict_reversed": {"zh": "理想反向相位字典", "en": "Ideal reversed phase", "ja": "理想逆位相辞書"},
    "dbf_dict_channel": {"zh": "通道幅相校准字典", "en": "Channel amp/phase dictionary", "ja": "チャネル振幅/位相辞書"},
    "dbf_dict_custom": {"zh": "导入CSV/XLSX字典", "en": "Imported CSV/XLSX", "ja": "CSV/XLSX辞書"},
    "dbf_dict_custom_options": {"zh": "导入字典选项", "en": "Imported Options", "ja": "読込辞書オプション"},
    "dbf_dict_phase_reverse": {
        "zh": "导入字典相位反向",
        "en": "Reverse imported phase",
        "ja": "読込位相を反転",
    },
    "dbf_dict_zero_calibrate": {
        "zh": "导入字典按0°相位校准",
        "en": "0 deg phase calibrate imported",
        "ja": "読込辞書を0°位相校正",
    },
    "dbf_dict_axis": {"zh": "预览轴", "en": "Preview axis", "ja": "プレビュー軸"},
    "dbf_dict_load": {"zh": "加载CSV/XLSX", "en": "Load CSV/XLSX", "ja": "CSV/XLSX読込"},
    "dbf_dict_load_az": {"zh": "加载方位字典", "en": "Load Az Dictionary", "ja": "方位辞書読込"},
    "dbf_dict_load_el": {"zh": "加载俯仰字典", "en": "Load El Dictionary", "ja": "仰角辞書読込"},
    "dbf_dict_clear": {"zh": "清除导入字典", "en": "Clear imported", "ja": "読込辞書をクリア"},
    "dbf_dict_clear_az": {"zh": "清除方位", "en": "Clear Az", "ja": "方位クリア"},
    "dbf_dict_clear_el": {"zh": "清除俯仰", "en": "Clear El", "ja": "仰角クリア"},
    "dbf_dict_apply": {"zh": "应用字典", "en": "Apply Dictionary", "ja": "辞書を適用"},
    "dbf_dict_preview_phase": {"zh": "字典相位矩阵", "en": "Dictionary phase matrix", "ja": "辞書位相行列"},
    "dbf_dict_preview_status": {
        "zh": "{mode} | {rows}角度 × {cols}通道",
        "en": "{mode} | {rows} angles × {cols} channels",
        "ja": "{mode} | {rows}角度 × {cols}チャネル",
    },
    "dbf_dict_file_status": {
        "zh": "{axis}：{file}",
        "en": "{axis}: {file}",
        "ja": "{axis}：{file}",
    },
    "dbf_dict_no_file": {"zh": "未加载", "en": "not loaded", "ja": "未読込"},
    "dbf_dict_custom_loaded": {
        "zh": "已加载{axis}DBF字典：{file}。",
        "en": "Loaded {axis} DBF dictionary: {file}.",
        "ja": "{axis}DBF辞書を読み込みました：{file}。",
    },
    "dbf_dict_custom_failed": {
        "zh": "加载DBF字典失败",
        "en": "Load DBF dictionary failed",
        "ja": "DBF辞書の読み込みに失敗",
    },
    "dbf_dict_applied": {
        "zh": "已应用DBF字典：{mode}。",
        "en": "Applied DBF dictionary: {mode}.",
        "ja": "DBF辞書を適用しました：{mode}。",
    },
    "dbf_dict_need_file": {
        "zh": "请先加载当前预览轴的CSV/XLSX字典文件。",
        "en": "Load the CSV/XLSX dictionary for the current preview axis first.",
        "ja": "現在のプレビュー軸のCSV/XLSX辞書ファイルを先に読み込んでください。",
    },
    "dbf_dict_need_axis_files": {
        "zh": "自定义DBF字典至少需要加载方位或俯仰其中一个文件。",
        "en": "Custom DBF dictionary requires at least one azimuth or elevation file.",
        "ja": "カスタムDBF辞書には方位または仰角の少なくとも1ファイルが必要です。",
    },
    "channel_dialog_title": {
        "zh": "通道幅度/相位方向图设置",
        "en": "Channel Amplitude/Phase Patterns",
        "ja": "チャネル振幅/位相パターン設定",
    },
    "summary_csv_title": {"zh": "  汇总CSV  ", "en": "  Summary CSV  ", "ja": "  集約CSV  "},
    "physical_channels_title": {
        "zh": "  物理通道  ",
        "en": "  Physical Channels  ",
        "ja": "  物理チャネル  ",
    },
    "load_summary": {"zh": "加载{label}汇总", "en": "Load {label} Summary", "ja": "{label}集約を読み込み"},
    "set_pattern": {"zh": "设置{label}", "en": "Set {label}", "ja": "{label}を設定"},
    "clear_all": {"zh": "全部清空", "en": "Clear All", "ja": "すべてクリア"},
    "clear_channel": {"zh": "清空通道", "en": "Clear Channel", "ja": "チャネルをクリア"},
    "done": {"zh": "完成", "en": "Done", "ja": "完了"},
    "column_channel": {"zh": "通道", "en": "Channel", "ja": "チャネル"},
    "select_channel_first": {
        "zh": "请先选择一个物理通道。",
        "en": "Select one physical channel first.",
        "ja": "先に物理チャネルを1つ選択してください。",
    },
    "channel_patterns_title": {"zh": "通道方向图", "en": "Channel patterns", "ja": "チャネルパターン"},
    "channel_cleared": {
        "zh": "已清空通道方向图：{channel}。",
        "en": "Cleared channel patterns: {channel}.",
        "ja": "チャネルパターンをクリア：{channel}。",
    },
    "channel_already_ideal": {
        "zh": "通道方向图已经是理想状态。",
        "en": "Channel patterns already ideal.",
        "ja": "チャネルパターンは既に理想状態です。",
    },
    "channel_all_cleared": {
        "zh": "已清空所有通道方向图。",
        "en": "Cleared all channel patterns.",
        "ja": "すべてのチャネルパターンをクリアしました。",
    },
    "load_summary_title": {
        "zh": "加载{label}汇总CSV",
        "en": "Load {label} summary CSV",
        "ja": "{label}集約CSVを読み込み",
    },
    "load_channel_title": {
        "zh": "加载{channel}的{label}",
        "en": "Load {label} for {channel}",
        "ja": "{channel}の{label}を読み込み",
    },
    "summary_loaded": {
        "zh": "已加载{label}汇总：{file}。",
        "en": "Loaded {label} summary: {file}.",
        "ja": "{label}集約を読み込みました：{file}。",
    },
    "channel_loaded": {
        "zh": "已加载{channel}的{label}：{file}。",
        "en": "Loaded {label} for {channel}: {file}.",
        "ja": "{channel}の{label}を読み込みました：{file}。",
    },
    "load_summary_failed": {
        "zh": "加载通道汇总CSV失败",
        "en": "Load channel pattern summary failed",
        "ja": "チャネル集約CSVの読み込みに失敗",
    },
    "load_channel_failed": {
        "zh": "加载通道CSV失败",
        "en": "Load channel pattern failed",
        "ja": "チャネルCSVの読み込みに失敗",
    },
    "ideal": {"zh": "理想", "en": "ideal", "ja": "理想"},
    "amp": {"zh": "幅度", "en": "Amp", "ja": "振幅"},
    "phase": {"zh": "相位", "en": "Phase", "ja": "位相"},
    "row_channel_count": {"zh": "通道数量", "en": "Channels", "ja": "チャネル数"},
    "row_virtual_channels": {"zh": "虚拟通道", "en": "Virtual Channels", "ja": "仮想チャネル"},
    "row_az_aperture": {"zh": "方位口径", "en": "Az Aperture", "ja": "方位開口"},
    "row_el_aperture": {"zh": "俯仰口径", "en": "El Aperture", "ja": "仰角開口"},
    "row_az_resolution": {"zh": "方位分辨率", "en": "Az Resolution", "ja": "方位分解能"},
    "row_el_resolution": {"zh": "俯仰分辨率", "en": "El Resolution", "ja": "仰角分解能"},
    "row_az_no_fold": {"zh": "方位不模糊范围", "en": "Az No-Fold Range", "ja": "方位非曖昧範囲"},
    "row_az_no_fold_error": {"zh": "方位范围内最大误差", "en": "Az Max Error in Range", "ja": "方位範囲内最大誤差"},
    "row_az_margin": {"zh": "方位竞争峰裕量", "en": "Az Peak Margin", "ja": "方位競合ピーク余裕"},
    "row_az_cut": {"zh": "方位截断原因", "en": "Az Cut Reason", "ja": "方位打切り理由"},
    "row_el_no_fold": {"zh": "俯仰不模糊范围", "en": "El No-Fold Range", "ja": "仰角非曖昧範囲"},
    "row_el_no_fold_error": {"zh": "俯仰范围内最大误差", "en": "El Max Error in Range", "ja": "仰角範囲内最大誤差"},
    "row_el_margin": {"zh": "俯仰竞争峰裕量", "en": "El Peak Margin", "ja": "仰角競合ピーク余裕"},
    "row_el_cut": {"zh": "俯仰截断原因", "en": "El Cut Reason", "ja": "仰角打切り理由"},
    "metric_no_fold": {"zh": "不模糊范围", "en": "No-Fold Range", "ja": "非曖昧範囲"},
    "metric_max_error": {"zh": "最大误差", "en": "Max Error", "ja": "最大誤差"},
    "metric_peak_margin": {"zh": "竞争峰裕量", "en": "Peak Margin", "ja": "競合ピーク余裕"},
    "metric_cut_reason": {"zh": "截断原因", "en": "Cut Reason", "ja": "打切り理由"},
    "undo_empty": {"zh": "没有可撤销的操作。", "en": "Nothing to undo.", "ja": "元に戻す操作はありません。"},
    "undo_done": {"zh": "已撤销阵列编辑。", "en": "Undid layout edit.", "ja": "アレイ編集を元に戻しました。"},
    "redo_empty": {"zh": "没有可重做的操作。", "en": "Nothing to redo.", "ja": "やり直す操作はありません。"},
    "redo_done": {"zh": "已重做阵列编辑。", "en": "Redid layout edit.", "ja": "アレイ編集をやり直しました。"},
    "limit_reached": {"zh": "{prefix}数量已达上限({max_count})。", "en": "{prefix} limit reached ({max_count}).", "ja": "{prefix}数が上限({max_count})に達しました。"},
    "antenna_limit_title": {"zh": "天线数量限制", "en": "Antenna limit", "ja": "アンテナ数制限"},
    "count_limit_detail": {"zh": "{prefix}数量最多为{max_count}。", "en": "{prefix} count is limited to {max_count}.", "ja": "{prefix}数は最大{max_count}です。"},
    "added_element": {"zh": "已添加{element} | x={x:g} λ | y={y:g} λ", "en": "Added {element} | x={x:g} λ | y={y:g} λ", "ja": "{element}を追加 | x={x:g} λ | y={y:g} λ"},
    "delete_mode_on": {"zh": "删除模式：点击TX/RX通道即可删除，按Esc退出。", "en": "Delete mode: click Tx/Rx elements to remove them. Press Esc to exit.", "ja": "削除モード：TX/RXチャネルをクリックして削除、Escで終了。"},
    "delete_mode_off": {"zh": "已退出删除模式。", "en": "Delete mode off.", "ja": "削除モードを終了しました。"},
    "layout_already_clear": {"zh": "阵列已经是初始布局。", "en": "Layout already clear.", "ja": "アレイは既に初期配置です。"},
    "layout_cleared": {"zh": "已清空阵列，保留1T1R初始通道。", "en": "Cleared layout to 1T1R starter points.", "ja": "アレイをクリアし、1T1R初期チャネルを残しました。"},
    "auto_layout_title": {"zh": "自动排阵", "en": "Auto array layout", "ja": "自動アレイ配置"},
    "auto_layout_already": {"zh": "自动排阵已是{tx}T{rx}R。", "en": "Auto layout already applied: {tx}T{rx}R.", "ja": "自動配置は既に{tx}T{rx}Rです。"},
    "auto_layout_done": {"zh": "已应用自动排阵：{tx}T{rx}R。", "en": "Auto layout applied: {tx}T{rx}R.", "ja": "自動配置を適用：{tx}T{rx}R。"},
    "delete_last": {"zh": "不能删除最后一个{prefix}通道。", "en": "Cannot delete the last {prefix} element.", "ja": "最後の{prefix}チャネルは削除できません。"},
    "delete_last_detail": {"zh": "测角分析至少需要一个{prefix}通道。", "en": "At least one {prefix} element is required for analysis.", "ja": "解析には少なくとも1つの{prefix}チャネルが必要です。"},
    "deleted_element": {"zh": "已删除{element}，TX/RX编号已自动对齐。{suffix}", "en": "Deleted {element}. Tx/Rx numbering aligned.{suffix}", "ja": "{element}を削除し、TX/RX番号を整列しました。{suffix}"},
    "delete_mode_suffix": {"zh": " 删除模式保持开启。", "en": " Delete mode remains on.", "ja": " 削除モードは継続中。"},
    "frequency_set": {"zh": "频率已设置为{frequency} GHz。", "en": "Frequency set to {frequency} GHz.", "ja": "周波数を{frequency} GHzに設定しました。"},
    "frequency_invalid": {"zh": "频率输入无效，已恢复为{frequency} GHz。", "en": "Invalid frequency. Restored {frequency} GHz.", "ja": "無効な周波数です。{frequency} GHzに戻しました。"},
    "margin_set": {"zh": "竞争峰裕量阈值已设置为{value} dB。", "en": "Peak margin threshold set to {value} dB.", "ja": "競合ピーク余裕しきい値を{value} dBに設定しました。"},
    "margin_invalid": {"zh": "竞争峰裕量输入无效，已恢复为{value} dB。", "en": "Invalid peak margin. Restored {value} dB.", "ja": "競合ピーク余裕の入力が無効です。{value} dBに戻しました。"},
    "refreshed": {"zh": "已刷新。", "en": "Refreshed.", "ja": "更新しました。"},
    "refresh_invalid": {"zh": "频率输入无效，已恢复并刷新。", "en": "Invalid frequency restored and refreshed.", "ja": "無効な周波数を復元して更新しました。"},
    "drag_cancel": {"zh": "已取消拖动。", "en": "Drag canceled.", "ja": "ドラッグをキャンセルしました。"},
    "no_selection": {"zh": "当前没有选中通道。", "en": "No selection.", "ja": "選択中のチャネルはありません。"},
    "selection_cleared": {"zh": "已清除选择。", "en": "Selection cleared.", "ja": "選択を解除しました。"},
    "select_element_hint": {"zh": "已清除选择。点击一个天线通道可重新选择。", "en": "Selection cleared. Click an antenna element to select.", "ja": "選択を解除しました。アンテナチャネルをクリックして再選択できます。"},
    "delete_click_element": {"zh": "删除模式：请直接点击TX/RX通道。", "en": "Delete mode: click directly on a Tx/Rx element.", "ja": "削除モード：TX/RXチャネルを直接クリックしてください。"},
    "selected_element": {"zh": "已选中{element} | x={x:g} λ | y={y:g} λ", "en": "Selected {element} | x={x:g} λ | y={y:g} λ", "ja": "{element}を選択 | x={x:g} λ | y={y:g} λ"},
    "snap_element": {"zh": "吸附{element}：x={x:g} λ, y={y:g} λ", "en": "Snap {element}: x={x:g} λ, y={y:g} λ", "ja": "{element}をスナップ：x={x:g} λ, y={y:g} λ"},
    "placed_element": {"zh": "{element}：x={x:g} λ, y={y:g} λ", "en": "{element}: x={x:g} λ, y={y:g} λ", "ja": "{element}：x={x:g} λ, y={y:g} λ"},
    "export_layout_title": {"zh": "导出阵面布局", "en": "Export antenna layout", "ja": "アレイ配置を書き出し"},
    "import_layout_title": {"zh": "导入阵面布局", "en": "Import antenna layout", "ja": "アレイ配置を読み込み"},
    "layout_json_type": {"zh": "阵面布局JSON", "en": "Antenna layout JSON", "ja": "アレイ配置JSON"},
    "all_files_type": {"zh": "所有文件", "en": "All files", "ja": "すべてのファイル"},
    "hfss_csv_type": {"zh": "HFSS CSV/TSV/XLSX", "en": "HFSS CSV/TSV/XLSX", "ja": "HFSS CSV/TSV/XLSX"},
    "csv_type": {"zh": "CSV文件", "en": "CSV files", "ja": "CSVファイル"},
    "tsv_type": {"zh": "TSV文件", "en": "TSV files", "ja": "TSVファイル"},
    "element_pattern_import_title": {
        "zh": "导入单元方向图",
        "en": "Import element pattern",
        "ja": "要素パターンを読み込み",
    },
    "element_pattern_file_type": {
        "zh": "方向图CSV/TSV",
        "en": "Pattern CSV/TSV",
        "ja": "パターンCSV/TSV",
    },
    "element_pattern_import_failed": {
        "zh": "导入单元方向图失败",
        "en": "Import element pattern failed",
        "ja": "要素パターンの読み込みに失敗",
    },
    "element_pattern_import_canceled": {
        "zh": "已取消导入单元方向图。",
        "en": "Element pattern import canceled.",
        "ja": "要素パターンの読み込みをキャンセルしました。",
    },
    "element_pattern_loaded": {
        "zh": "已加载单元方向图：{name}",
        "en": "Element pattern loaded: {name}",
        "ja": "要素パターンを読み込みました：{name}",
    },
    "element_pattern_already_isotropic": {
        "zh": "当前已使用理想各向同性单元。",
        "en": "Element pattern already isotropic.",
        "ja": "要素パターンはすでに等方性です。",
    },
    "element_pattern_cleared": {
        "zh": "已清除单元方向图，改用理想各向同性单元。",
        "en": "Element pattern cleared. Using isotropic elements.",
        "ja": "要素パターンをクリアし、等方性要素を使用します。",
    },
    "element_pattern_confirm_title": {
        "zh": "确认单元方向图",
        "en": "Confirm Element Pattern",
        "ja": "要素パターンを確認",
    },
    "element_pattern_preview_columns": {
        "zh": "角度：{angle} | H：{horizontal}{elevation}",
        "en": "Angle: {angle} | H: {horizontal}{elevation}",
        "ja": "角度：{angle} | H：{horizontal}{elevation}",
    },
    "element_pattern_preview_elevation_column": {
        "zh": " | V：{column}",
        "en": " | V: {column}",
        "ja": " | V：{column}",
    },
    "element_pattern_horizontal_metrics": {
        "zh": "水平：{metrics}",
        "en": "Horizontal: {metrics}",
        "ja": "水平：{metrics}",
    },
    "element_pattern_elevation_metrics": {
        "zh": "俯仰：{metrics}",
        "en": "Elevation: {metrics}",
        "ja": "仰角：{metrics}",
    },
    "element_pattern_horizontal_title": {
        "zh": "水平方向图",
        "en": "Horizontal pattern",
        "ja": "水平パターン",
    },
    "element_pattern_elevation_title": {
        "zh": "俯仰方向图",
        "en": "Elevation pattern",
        "ja": "仰角パターン",
    },
    "element_pattern_no_elevation": {
        "zh": "未检测到独立俯仰列，将复用水平方向图。",
        "en": "No separate elevation column. Horizontal pattern will be reused.",
        "ja": "個別の仰角列がないため、水平パターンを再利用します。",
    },
    "element_pattern_elevation_reuse": {
        "zh": "俯仰：复用水平方向图",
        "en": "Elevation: reuses horizontal pattern",
        "ja": "仰角：水平パターンを再利用",
    },
    "element_pattern_axis_angle": {"zh": "角度(°)", "en": "Angle (deg)", "ja": "角度(°)"},
    "element_pattern_axis_gain": {"zh": "增益(dB)", "en": "Gain (dB)", "ja": "利得(dB)"},
    "element_pattern_import_button": {"zh": "导入", "en": "Import", "ja": "読み込み"},
    "element_pattern_cancel_button": {"zh": "取消", "en": "Cancel", "ja": "キャンセル"},
    "element_pattern_swap_button": {"zh": "交换H/V", "en": "Swap H/V", "ja": "H/V入替"},
    "exported_layout": {"zh": "已导出阵面布局：{file}", "en": "Exported layout: {file}", "ja": "アレイ配置を書き出しました：{file}"},
    "import_layout_failed": {"zh": "导入阵面布局失败", "en": "Import layout failed", "ja": "アレイ配置の読み込みに失敗"},
    "imported_layout": {
        "zh": "已导入：{file} | {tx}=({tx_x:g},{tx_y:g}) λ | {rx}=({rx_x:g},{rx_y:g}) λ | x {x_min:g}..{x_max:g} λ, y {y_min:g}..{y_max:g} λ",
        "en": "Imported: {file} | {tx}=({tx_x:g},{tx_y:g}) λ | {rx}=({rx_x:g},{rx_y:g}) λ | x {x_min:g}..{x_max:g} λ, y {y_min:g}..{y_max:g} λ",
        "ja": "読み込み完了：{file} | {tx}=({tx_x:g},{tx_y:g}) λ | {rx}=({rx_x:g},{rx_y:g}) λ | x {x_min:g}..{x_max:g} λ, y {y_min:g}..{y_max:g} λ",
    },
}


def _text_for_language(key: str, language: str = LANGUAGE_ZH, **kwargs) -> str:
    language = language if language in SUPPORTED_LANGUAGES else LANGUAGE_ZH
    translations = UI_TEXT.get(key, {})
    template = translations.get(language) or translations.get(LANGUAGE_ZH) or key
    return template.format(**kwargs) if kwargs else template


def _pattern_slot_label_for_language(kind: str, plane: str, language: str) -> str:
    kind_key = "amp" if kind == PATTERN_KIND_AMPLITUDE else "phase"
    plane_text = "E" if plane == PATTERN_PLANE_ELEVATION else "H"
    return f"{_text_for_language(kind_key, language)} {plane_text}"


PRIMARY_EVAL_ROWS = (
    "row_channel_count",
    "row_virtual_channels",
    "row_az_aperture",
    "row_el_aperture",
    "row_az_resolution",
    "row_el_resolution",
)
ANGLE_EVAL_GROUPS = (
    (
        "az",
        (
            ("row_az_no_fold", "metric_no_fold"),
            ("row_az_no_fold_error", "metric_max_error"),
            ("row_az_margin", "metric_peak_margin"),
            ("row_az_cut", "metric_cut_reason"),
        ),
    ),
    (
        "el",
        (
            ("row_el_no_fold", "metric_no_fold"),
            ("row_el_no_fold_error", "metric_max_error"),
            ("row_el_margin", "metric_peak_margin"),
            ("row_el_cut", "metric_cut_reason"),
        ),
    ),
)

# ── Theme ─────────────────────────────────────────────────────────────
THEME = {
    # Base
    "bg": "#eef3f8",
    "card_bg": "#ffffff",
    "metric_bg": "#f8fbff",
    "panel_bg": "#f5f8fc",
    "panel_alt_bg": "#edf3f8",
    "card_border": "#d7e0ea",
    "metric_border": "#cfdbe7",
    "status_bar_bg": "#f7fafc",
    "toolbar_group_bg": "#ffffff",
    "input_bg": "#ffffff",
    "disabled_bg": "#edf2f7",
    "app_menu_bg": "#171a16",
    "app_menu_hover": "#2b2f2c",
    "app_menu_text": "#a5aaa3",
    "app_menu_text_active": "#f3f4f1",
    "header_bg": "#101722",
    "header_panel_bg": "#172233",
    "header_border": "#253449",
    "chip_bg": "#1d2b3c",
    "chip_border": "#2f4157",
    # Accent
    "accent": "#0f172a",
    "accent_hover": "#1f2937",
    "accent_pressed": "#020617",
    "accent_light": "#e0f2fe",
    "secondary_accent": "#0f9f9a",
    "secondary_light": "#d5fbf6",
    "danger": "#e11d48",
    "danger_hover": "#f43f5e",
    "danger_pressed": "#be123c",
    "danger_light": "#fff1f3",
    "danger_border": "#fecdd8",
    "warning": "#b7791f",
    "warning_light": "#fffbeb",
    "success": "#047857",
    "success_light": "#ecfdf5",
    # Text
    "text_primary": "#111827",
    "text_secondary": "#526070",
    "text_muted": "#8793a2",
    "text_inverse": "#ffffff",
    "text_inverse_muted": "#a9b6c7",
    # Typography
    "font_family": "Segoe UI",
    "font_family_mono": "Cascadia Code",
    "font_size_sm": 9,
    "font_size_base": 10,
    "font_size_lg": 13,
    # Matplotlib
    "plot_bg": "#fbfdff",
    "grid_color": "#d7e1ec",
    "grid_major_color": "#b7c6d6",
    "grid_minor_color": "#edf2f8",
    "grid_alpha": 0.34,
    "axis_spine": "#c9d4e0",
    "tx_color": "#f05261",
    "tx_edge": "#9f1239",
    "rx_color": "#2563eb",
    "rx_edge": "#1d4ed8",
    "selection": "#0891b2",
    "selection_fill": "#cffafe",
    "hover_fill": "#ecfeff",
    "response_line": "#0ea5e9",
    "response_secondary_line": "#64748b",
    "sidelobe": "#f59e0b",
    # MplButton
    "mpl_btn_bg": "#ffffff",
    "mpl_btn_hover": "#eef4ff",
    "mpl_btn_text": "#171717",
    "mpl_btn_border": "#d9dde3",
    # ttk buttons
    "button_bg": "#ffffff",
    "button_hover": "#f0f7ff",
    "button_pressed": "#e0f2fe",
    "button_border": "#cbd7e3",
    "dialog_button_hover": "#f0f1ee",
    "dialog_button_pressed": "#e5e7e2",
    "menu_hover": "#e0f2fe",
    "focus": "#0891b2",
    "focus_soft": "#a5f3fc",
}


# ── Data classes ──────────────────────────────────────────────────────
@dataclass
class EditableElement:
    kind: str
    index: int
    name: str
    x: float
    y: float


@dataclass(frozen=True)
class LayoutSnapshot:
    elements: tuple[tuple[str, int, str, float, float], ...]
    selected_key: tuple[str, int, str] | None


@dataclass(frozen=True)
class ResponseCut:
    mode: str
    label: str
    angles: np.ndarray
    gains_db: np.ndarray
    fov: tuple[float, float]
    mainlobe_guard: float
    x_label: str
    pattern_label: str


@dataclass
class ResponseChart:
    """Encapsulates per-axis response chart state (fig, axes, canvas, hover, buttons)."""

    fig: Figure
    ax: any  # matplotlib Axes
    canvas: FigureCanvasTkAgg
    progress_label: ttk.Label | None = None
    play_button: ttk.Button | None = None
    stop_button: ttk.Button | None = None
    hover_annotation: any = None  # matplotlib Annotation
    hover_marker: any = None
    hover_db: np.ndarray = None
    hover_angles: np.ndarray = None
    true_angle: float | None = None
    buttons: list = None
    button_callbacks: list = None

    def __post_init__(self) -> None:
        if self.hover_db is None:
            self.hover_db = np.empty(0, dtype=float)
        if self.hover_angles is None:
            self.hover_angles = np.empty(0, dtype=float)
        if self.buttons is None:
            self.buttons = []
        if self.button_callbacks is None:
            self.button_callbacks = []


def _response_cut_for_mode(
    af_db: np.ndarray,
    azimuths: np.ndarray,
    elevations: np.ndarray,
    mode: str,
    language: str = LANGUAGE_ZH,
) -> ResponseCut:
    if mode == RESPONSE_MODE_ELEVATION:
        az0_index = int(np.argmin(np.abs(azimuths)))
        return ResponseCut(
            mode=RESPONSE_MODE_ELEVATION,
            label=_text_for_language("el_short", language),
            angles=elevations,
            gains_db=af_db[:, az0_index],
            fov=ELEVATION_FOV,
            mainlobe_guard=MAINLOBE_GUARD_EL,
            x_label=_text_for_language("axis_el_angle", language),
            pattern_label=_text_for_language(
                "pattern_cut_label", language, mode=_text_for_language("el", language)
            ),
        )

    el0_index = int(np.argmin(np.abs(elevations)))
    return ResponseCut(
        mode=RESPONSE_MODE_AZIMUTH,
        label=_text_for_language("az_short", language),
        angles=azimuths,
        gains_db=af_db[el0_index, :],
        fov=AZIMUTH_FOV,
        mainlobe_guard=MAINLOBE_GUARD_AZ,
        x_label=_text_for_language("axis_az_angle", language),
        pattern_label=_text_for_language(
            "pattern_cut_label", language, mode=_text_for_language("az", language)
        ),
    )


def _response_sidelobe_marker(
    angles: np.ndarray,
    gains_db: np.ndarray,
    guard: float,
    min_prominence_db: float = RESPONSE_SIDELOBE_PROMINENCE_DB,
    min_guard_clearance_db: float = RESPONSE_SIDELOBE_GUARD_CLEARANCE_DB,
) -> tuple[int, bool]:
    peak_indices = local_peak_indices(gains_db)
    sidelobe_mask = np.abs(angles) > guard
    sidelobe_peak_indices = np.array(
        [
            index
            for index in peak_indices[sidelobe_mask[peak_indices]]
            if _peak_prominence_db(gains_db, int(index)) >= min_prominence_db
            and _peak_guard_clearance_db(angles, gains_db, guard, int(index))
            >= min_guard_clearance_db
        ],
        dtype=int,
    )
    if len(sidelobe_peak_indices):
        index = int(sidelobe_peak_indices[np.argmax(gains_db[sidelobe_peak_indices])])
        return index, True
    if np.any(sidelobe_mask):
        return int(np.argmax(np.where(sidelobe_mask, gains_db, -np.inf))), False
    return int(np.argmax(gains_db)), False


def _peak_prominence_db(values_db: np.ndarray, peak_index: int) -> float:
    peak_db = float(values_db[peak_index])
    left_min = peak_db
    for index in range(peak_index - 1, -1, -1):
        value = float(values_db[index])
        if value > peak_db:
            break
        left_min = min(left_min, value)

    right_min = peak_db
    for index in range(peak_index + 1, len(values_db)):
        value = float(values_db[index])
        if value > peak_db:
            break
        right_min = min(right_min, value)

    return peak_db - max(left_min, right_min)


def _peak_guard_clearance_db(
    angles: np.ndarray,
    gains_db: np.ndarray,
    guard: float,
    peak_index: int,
) -> float:
    peak_angle = float(angles[peak_index])
    if peak_angle < 0.0:
        side_indices = np.flatnonzero(angles < -guard)
        if len(side_indices) == 0:
            return 0.0
        guard_index = int(side_indices[np.argmax(angles[side_indices])])
    else:
        side_indices = np.flatnonzero(angles > guard)
        if len(side_indices) == 0:
            return 0.0
        guard_index = int(side_indices[np.argmin(angles[side_indices])])
    return float(gains_db[peak_index] - gains_db[guard_index])


# ── Formatting helpers ────────────────────────────────────────────────
def _format_float(value: float | None, unit: str = "") -> str:
    if value is None or not np.isfinite(value):
        return "N/A"
    return f"{value:.2f}{unit}"


def _format_db(value: float | None) -> str:
    if value is None or not np.isfinite(value):
        return "N/A"
    return f"{value:.2f} dB"


def _format_db_at_az(value: float | None, angle: float | None) -> str:
    if value is None or angle is None or not np.isfinite(value) or not np.isfinite(angle):
        return "N/A"
    return f"{value:.2f} dB @ Az {angle:.1f}°"


def _format_signed_degree(value: float, digits: int = 0) -> str:
    if abs(value) < 0.05:
        return "0°"
    text = f"{value:+.{digits}f}"
    if digits == 0:
        text = text.replace(".0", "")
    return f"{text}°"


def _format_angle_error(value: float | None) -> str:
    if value is None or not np.isfinite(value):
        return "N/A"
    return f"{value:.1f}°"


def _format_angle_range(metrics: DbfAngleMetrics | None) -> str:
    if (
        metrics is None
        or metrics.no_fold_left is None
        or metrics.no_fold_right is None
        or not np.isfinite(metrics.no_fold_left)
        or not np.isfinite(metrics.no_fold_right)
    ):
        return "N/A"
    width = metrics.no_fold_width
    width_text = "N/A" if width is None else f"{width:.0f}°"
    return (
        f"{_format_signed_degree(metrics.no_fold_left)}~"
        f"{_format_signed_degree(metrics.no_fold_right)} / {width_text}"
    )


def _format_peak_margin(value: float | None) -> str:
    if value is None:
        return "N/A"
    if np.isposinf(value):
        return "无竞争峰"
    if not np.isfinite(value):
        return "N/A"
    return f"{value:.1f} dB"


def _format_axis_angle_metrics(metrics: DbfAngleMetrics | None, field: str) -> str:
    if metrics is None:
        return "N/A"
    if field == "no_fold_error":
        return _format_angle_error(metrics.no_fold_max_abs_error)
    if field == "focus_error":
        return _format_angle_error(metrics.focus_max_abs_error)
    if field == "margin":
        if (
            (metrics.no_fold_width or 0.0) <= 0.0
            and (
                metrics.negative_cut_reason in {"边界受限", "谱不可靠"}
                or metrics.positive_cut_reason in {"边界受限", "谱不可靠"}
            )
        ):
            return "不可用"
        return _format_peak_margin(metrics.min_peak_margin_db)
    raise ValueError(f"Unknown DBF angle metric field: {field!r}")


def _format_mm(value: float) -> str:
    return f"{value:.1f} mm"


def _parse_frequency_ghz(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        frequency = float(value)
    elif isinstance(value, str):
        text = value.strip().lower().replace(",", ".")
        if text.endswith("ghz"):
            text = text[:-3].strip()
        elif text.endswith("g"):
            text = text[:-1].strip()
        if not text:
            return None
        try:
            frequency = float(text)
        except ValueError:
            return None
    else:
        return None
    return frequency if math.isfinite(frequency) and frequency > 0 else None


def _format_frequency_ghz(frequency: float) -> str:
    if abs(frequency - round(frequency)) < 1e-9:
        return str(int(round(frequency)))
    return f"{frequency:.6f}".rstrip("0").rstrip(".")


def _parse_margin_db(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        margin = float(value)
    elif isinstance(value, str):
        text = value.strip().lower().replace(",", ".")
        if text.endswith("db"):
            text = text[:-2].strip()
        if not text:
            return None
        try:
            margin = float(text)
        except ValueError:
            return None
    else:
        return None
    return margin if math.isfinite(margin) and margin >= 0.0 else None


def _format_margin_db(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _validated_window_geometry(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    geometry = value.strip()
    match = WINDOW_GEOMETRY_RE.fullmatch(geometry)
    if match is None:
        return None
    width = int(match.group("width"))
    height = int(match.group("height"))
    return geometry if width > 0 and height > 0 else None


def _json_number(value: float | None, digits: int = 6) -> float | int | None:
    if value is None or not np.isfinite(value):
        return None
    rounded = round(float(value), digits)
    if abs(rounded - round(rounded)) < 10 ** -digits:
        return int(round(rounded))
    return rounded


def _layout_config_to_json(config: dict[str, object]) -> str:
    lines = [
        "{",
        f'  "version": {json.dumps(config["version"], ensure_ascii=False)},',
        f'  "unit": {json.dumps(config["unit"], ensure_ascii=False)},',
        '  "tx": [',
    ]
    tx_points = config["tx"]
    rx_points = config["rx"]
    if not isinstance(tx_points, list) or not isinstance(rx_points, list):
        raise ValueError("Layout config tx/rx must be lists.")

    for index, point in enumerate(tx_points):
        suffix = "," if index < len(tx_points) - 1 else ""
        lines.append(
            "    "
            + json.dumps(point, ensure_ascii=False, separators=(", ", ": "))
            + suffix
        )
    lines.extend(['  ],', '  "rx": ['])
    for index, point in enumerate(rx_points):
        suffix = "," if index < len(rx_points) - 1 else ""
        lines.append(
            "    "
            + json.dumps(point, ensure_ascii=False, separators=(", ", ": "))
            + suffix
        )
    lines.append("  ],")

    evaluation = json.dumps(config["evaluation"], ensure_ascii=False, indent=2)
    evaluation_lines = evaluation.splitlines()
    lines.append('  "evaluation": ' + evaluation_lines[0])
    lines.extend("  " + line for line in evaluation_lines[1:])
    lines.append("}")
    return "\n".join(lines) + "\n"


def _show_unhandled_tk_exception(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback,
) -> None:  # noqa: ANN001
    LOGGER.critical(
        "Unhandled Tk callback exception",
        exc_info=(exc_type, exc_value, exc_traceback),
    )
    log_path = current_log_path()
    details = f"{exc_value}"
    if log_path is not None:
        details += f"\n\nDetails were saved to:\n{log_path}"
    try:
        messagebox.showerror("Application error", details)
    except Exception:
        LOGGER.exception("Failed to show Tk exception dialog")


def _to_display_lambda(values):  # noqa: ANN001
    return np.asarray(values, dtype=float) * DISPLAY_SCALE_LAMBDA


def _to_internal_half_lambda(value: float) -> float:
    return value / DISPLAY_SCALE_LAMBDA


def _clip_to_bounds(value: float, low: float, high: float) -> float:
    return float(min(max(value, low), high))


def _axes_boxes_overlap(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
    margin: float = 0.015,
) -> bool:
    first_left, first_bottom, first_right, first_top = first
    second_left, second_bottom, second_right, second_top = second
    return not (
        first_right + margin < second_left
        or second_right + margin < first_left
        or first_top + margin < second_bottom
        or second_top + margin < first_bottom
    )


def _style_toplevel(window: tk.Toplevel) -> None:
    window.configure(bg=THEME["bg"])


def _style_popup_menu(menu: tk.Menu) -> None:
    try:
        menu.configure(
            background=THEME["card_bg"],
            foreground=THEME["text_primary"],
            activebackground=THEME["menu_hover"],
            activeforeground=THEME["text_primary"],
            disabledforeground=THEME["text_muted"],
            selectcolor=THEME["focus"],
            borderwidth=1,
            activeborderwidth=0,
            relief=tk.SOLID,
            font=(THEME["font_family"], THEME["font_size_base"]),
        )
        try:
            menu.configure(cursor="hand2")
        except tk.TclError:
            pass
    except tk.TclError:
        LOGGER.debug("Menu did not accept all themed options", exc_info=True)

    end_index = menu.index(tk.END)
    if end_index is None:
        return
    for index in range(end_index + 1):
        entry_type = menu.type(index)
        try:
            if entry_type == "separator":
                menu.entryconfigure(index, background=THEME["card_border"])
            else:
                menu.entryconfigure(
                    index,
                    background=THEME["card_bg"],
                    foreground=THEME["text_primary"],
                    activebackground=THEME["menu_hover"],
                    activeforeground=THEME["text_primary"],
                )
                if entry_type == "cascade":
                    submenu_name = menu.entrycget(index, "menu")
                    submenu = menu.nametowidget(submenu_name)
                    if isinstance(submenu, tk.Menu):
                        _style_popup_menu(submenu)
        except (tk.TclError, KeyError):
            LOGGER.debug("Menu entry did not accept themed options", exc_info=True)


def _build_popup_menu(parent: tk.Widget) -> tk.Menu:
    menu = tk.Menu(parent, tearoff=False)
    _style_popup_menu(menu)
    return menu


def _apply_interactive_cursors(widget: tk.Widget) -> None:
    for child in widget.winfo_children():
        if isinstance(
            child,
            (
                ttk.Button,
                ttk.Checkbutton,
                ttk.Combobox,
                ttk.Menubutton,
                ttk.Radiobutton,
                ttk.Scale,
            ),
        ):
            try:
                child.configure(cursor="hand2")
            except tk.TclError:
                LOGGER.debug("Interactive widget did not accept cursor option", exc_info=True)
        _apply_interactive_cursors(child)


def _style_canvas_widget(widget: tk.Widget) -> None:
    try:
        widget.configure(
            background=THEME["card_bg"],
            highlightthickness=1,
            highlightbackground=THEME["card_border"],
            highlightcolor=THEME["card_border"],
            takefocus=0,
        )
    except tk.TclError:
        LOGGER.debug("Canvas widget did not accept themed border options", exc_info=True)


def _configure_axis_chrome(ax) -> None:  # noqa: ANN001
    ax.set_facecolor(THEME["plot_bg"])
    for spine in ax.spines.values():
        spine.set_color(THEME["axis_spine"])
        spine.set_linewidth(0.8)
    ax.tick_params(colors=THEME["text_secondary"], labelsize=8, width=0.8)


def _style_legend(legend) -> None:  # noqa: ANN001
    if legend is None:
        return
    frame = legend.get_frame()
    frame.set_facecolor(THEME["card_bg"])
    frame.set_edgecolor(THEME["card_border"])
    frame.set_alpha(0.92)


def _new_response_hover_annotation(ax):  # noqa: ANN001
    annotation = ax.annotate(
        "",
        xy=(0, 0),
        xytext=(12, 12),
        textcoords="offset points",
        bbox={
            "boxstyle": "round,pad=0.35",
            "facecolor": THEME["card_bg"],
            "edgecolor": THEME["focus_soft"],
            "alpha": 1.0,
            "linewidth": 0.8,
        },
        fontsize=8,
        color=THEME["text_primary"],
        annotation_clip=False,
        zorder=30,
    )
    annotation.set_clip_on(False)
    annotation.set_visible(False)
    return annotation


def _configure_pattern_preview_axis(ax) -> None:  # noqa: ANN001
    _configure_axis_chrome(ax)
    ax.set_xlim(-180.0, 180.0)
    ax.set_xticks(np.arange(-180.0, 181.0, 30.0))
    ax.set_xticks(np.arange(-180.0, 181.0, 10.0), minor=True)
    ax.grid(True, which="major", alpha=0.32, color=THEME["grid_major_color"], linewidth=0.6)
    ax.grid(True, which="minor", alpha=0.18, color=THEME["grid_minor_color"], linewidth=0.45)


def _element_prefix(kind: str) -> str:
    if kind == "tx":
        return "Tx"
    if kind == "rx":
        return "Rx"
    raise ValueError(f"Unknown element kind: {kind!r}")


def _max_elements_for_kind(kind: str) -> int:
    if kind == "tx":
        return MAX_TX_COUNT
    if kind == "rx":
        return MAX_RX_COUNT
    raise ValueError(f"Unknown element kind: {kind!r}")


def _validate_element_count(raw_value, kind: str) -> int:  # noqa: ANN001
    prefix = _element_prefix(kind)
    max_count = _max_elements_for_kind(kind)
    try:
        count = int(str(raw_value).strip())
    except (TypeError, ValueError):
        raise ValueError(f"{prefix} count must be an integer from 1 to {max_count}.")
    if count < 1 or count > max_count:
        raise ValueError(f"{prefix} count must be from 1 to {max_count}.")
    return count


def _centered_auto_positions(count: int) -> list[float]:
    offset = (count - 1) * AUTO_LAYOUT_SPACING / 2.0
    return [
        float(snap_to_grid(index * AUTO_LAYOUT_SPACING - offset))
        for index in range(count)
    ]


def _build_auto_layout_elements(tx_count: int, rx_count: int) -> list[EditableElement]:
    tx_x = _centered_auto_positions(tx_count)
    rx_x = _centered_auto_positions(rx_count)
    return [
        *[
            EditableElement(
                kind="tx",
                index=index,
                name=f"Tx{index + 1}",
                x=x,
                y=AUTO_LAYOUT_TX_Y,
            )
            for index, x in enumerate(tx_x)
        ],
        *[
            EditableElement(
                kind="rx",
                index=index,
                name=f"Rx{index + 1}",
                x=x,
                y=AUTO_LAYOUT_RX_Y,
            )
            for index, x in enumerate(rx_x)
        ],
    ]


def _starter_layout_elements() -> list[EditableElement]:
    return [
        EditableElement(kind="tx", index=0, name="Tx1", x=0.0, y=AUTO_LAYOUT_TX_Y),
        EditableElement(kind="rx", index=0, name="Rx1", x=0.0, y=AUTO_LAYOUT_RX_Y),
    ]


def _snap_to_grid_inside(value: float, low: float, high: float) -> float:
    snapped = snap_to_grid(value)
    if snapped < low:
        snapped = np.ceil(low / GRID_STEP) * GRID_STEP
    elif snapped > high:
        snapped = np.floor(high / GRID_STEP) * GRID_STEP
    return _clip_to_bounds(float(snapped), low, high)


def _event_widget_is_text_input(event) -> bool:  # noqa: ANN001
    widget = getattr(event, "widget", None)
    if widget is None:
        return False
    try:
        widget_class = widget.winfo_class()
    except tk.TclError:
        return False
    return widget_class in {
        "Entry",
        "TEntry",
        "Text",
        "Combobox",
        "TCombobox",
        "Spinbox",
        "TSpinbox",
    }


def _axis_limits(
    values: list[float] | np.ndarray,
    minimum_span: float = 20.0,
    padding: float = 6.0,
) -> tuple[float, float]:
    value_array = np.asarray(values, dtype=float)
    low = float(value_array.min())
    high = float(value_array.max())
    if high - low < minimum_span:
        center = (low + high) / 2.0
        low = center - minimum_span / 2.0
        high = center + minimum_span / 2.0
    return low - padding, high + padding


def _axis_ticks_within(limits: tuple[float, float], step: float) -> np.ndarray:
    low, high = limits
    start = np.ceil(low / step) * step
    stop = np.floor(high / step) * step
    return np.arange(start, stop + step / 2.0, step)


def _square_axis_limits(
    x_values: list[float] | np.ndarray,
    y_values: list[float] | np.ndarray,
    minimum_span: float,
    padding: float,
) -> tuple[tuple[float, float], tuple[float, float]]:
    x_low, x_high = _axis_limits(x_values, minimum_span=minimum_span, padding=padding)
    y_low, y_high = _axis_limits(y_values, minimum_span=minimum_span, padding=padding)
    x_span = x_high - x_low
    y_span = y_high - y_low
    target_span = max(x_span, y_span)

    if x_span < target_span:
        x_center = (x_low + x_high) / 2.0
        x_low = x_center - target_span / 2.0
        x_high = x_center + target_span / 2.0
    if y_span < target_span:
        y_center = (y_low + y_high) / 2.0
        y_low = y_center - target_span / 2.0
        y_high = y_center + target_span / 2.0
    return (x_low, x_high), (y_low, y_high)


def _fixed_box_equal_limits(
    x_values: list[float] | np.ndarray,
    y_values: list[float] | np.ndarray,
    fig_width_in: float,
    fig_height_in: float,
    x_padding: float = 6.0,
    y_padding: float = 6.0,
    minimum_span: float = 20.0,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Compute equal-aspect axis limits given a standalone Figure size."""
    x_low, x_high = _axis_limits(x_values, minimum_span=minimum_span, padding=x_padding)
    y_low, y_high = _axis_limits(y_values, minimum_span=minimum_span, padding=y_padding)
    x_span = x_high - x_low
    y_span = y_high - y_low
    box_ratio = fig_width_in / fig_height_in
    data_ratio = x_span / y_span if y_span else box_ratio

    if data_ratio < box_ratio:
        target_x_span = y_span * box_ratio
        center = (x_low + x_high) / 2.0
        x_low = center - target_x_span / 2.0
        x_high = center + target_x_span / 2.0
    elif data_ratio > box_ratio:
        target_y_span = x_span / box_ratio
        center = (y_low + y_high) / 2.0
        y_low = center - target_y_span / 2.0
        y_high = center + target_y_span / 2.0

    return (x_low, x_high), (y_low, y_high)


def _azimuth_status_label(metrics: ArrayMetrics) -> str:
    labels = {
        "Good": "方位良好",
        "Acceptable": "方位可用",
        "Risky": "方位风险",
        "Bad": "方位较差",
    }
    return labels.get(metrics.front_radar_status, f"方位{metrics.front_radar_status}")


def _ambiguity_level_label(value: str) -> str:
    labels = {"High": "高", "Medium": "中", "Low": "低"}
    return labels.get(value, value)


def _angle_cut_reason_summary(metrics: DbfAngleMetrics | None) -> str:
    if metrics is None:
        return "N/A"
    reason_labels = {
        "竞争峰模糊": "峰模糊",
        "到达数据边界": "边界",
        "边界受限": "边界受限",
        "误差跳变": "误差跳变",
        "谱不可靠": "谱不可靠",
        "正常": "正常",
    }
    negative = reason_labels.get(metrics.negative_cut_reason, metrics.negative_cut_reason) or "N/A"
    positive = reason_labels.get(metrics.positive_cut_reason, metrics.positive_cut_reason) or "N/A"
    if negative == positive:
        return negative
    return f"负:{negative} / 正:{positive}"


def _legacy_note_key(note: str) -> str:
    note_lower = note.lower()
    if "duplicate" in note_lower or "重复" in note:
        return "duplicate"
    if "windowing" in note_lower or "加窗" in note or "旁瓣" in note:
        return "windowing"
    if "ambiguity high" in note_lower or "模糊风险高" in note:
        return "ambiguity high"
    if "ambiguity medium" in note_lower or "模糊风险中" in note:
        return "ambiguity medium"
    if "不可用" in note or "未覆盖" in note:
        return "ambiguity high"
    return "none"


def _note_display(note: str) -> tuple[str, str]:
    key = _legacy_note_key(note)
    icon, color = NOTE_STYLES[key]
    return f"{icon}  {note}", color


def _dbf_mode_label(mode: str | None, language: str = LANGUAGE_ZH) -> str:
    if mode == "elevation":
        return _text_for_language("el", language)
    return _text_for_language("az", language)


def _dbf_short_label(mode: str | None, language: str = LANGUAGE_ZH) -> str:
    if mode == "elevation":
        return _text_for_language("el_short", language)
    return _text_for_language("az_short", language)


def _dbf_dictionary_mode_label(mode: str, language: str = LANGUAGE_ZH) -> str:
    labels = {
        DBF_DICT_IDEAL: "dbf_dict_ideal",
        DBF_DICT_IDEAL_REVERSED: "dbf_dict_reversed",
        DBF_DICT_CHANNEL_PATTERN: "dbf_dict_channel",
        DBF_DICT_CHANNEL_PATTERN_ZERO_REF: "dbf_dict_channel",
        DBF_DICT_CUSTOM: "dbf_dict_custom",
    }
    return _text_for_language(labels.get(mode, "dbf_dict_ideal"), language)


def _format_dbf_angle_label(angle: float, language: str = LANGUAGE_ZH) -> str:
    if abs(angle) < 0.05:
        return "0°" if language != LANGUAGE_EN else "0 deg"
    return f"{angle:+.0f}°" if language != LANGUAGE_EN else f"{angle:+.0f} deg"


def _series_table_label(series, language: str = LANGUAGE_ZH) -> str:  # noqa: ANN001
    if series is None:
        return _text_for_language("ideal", language)
    return series.short_label()


def _pattern_slot_label(kind: str, plane: str, language: str = LANGUAGE_ZH) -> str:
    kind_label = _text_for_language(
        "amp" if kind == PATTERN_KIND_AMPLITUDE else "phase", language
    )
    plane_label = "E" if plane == PATTERN_PLANE_ELEVATION else "H"
    return f"{kind_label} {plane_label}"


def _dbf_frame_index_for_angle(angle: float) -> int:
    frame = int(round((angle - DBF_SCAN_FOV[0]) / DBF_SCAN_STEP_DEG))
    return max(0, min(DBF_SCAN_GRID_SIZE - 1, frame))


def _dbf_peak_index(
    scan_angles: np.ndarray,
    spectrum_db: np.ndarray,
    true_angle: float,
    tolerance_db: float = 1e-6,
) -> int:
    peak_gain = float(np.max(spectrum_db))
    candidate_indices = np.flatnonzero(spectrum_db >= peak_gain - tolerance_db)
    if len(candidate_indices) == 0:
        return int(np.argmax(spectrum_db))
    return int(
        candidate_indices[
            int(np.argmin(np.abs(scan_angles[candidate_indices] - true_angle)))
        ]
    )


# ═══════════════════════════════════════════════════════════════════════
#  Main GUI class
# ═══════════════════════════════════════════════════════════════════════
class VirtualArrayGui:
    """MIMO antenna virtual-array visualizer.

    Layout (Tkinter grid):
      ┌─────────────┬──────────────┬────────────────┐
      │  Physical   │  Virtual     │                │
      │  Array      │  Array       │  Array         │
      │  (Mpl Fig)  │  (Mpl Fig)   │  Evaluation    │
      ├─────────────┼──────────────┤  (Tkinter)     │
      │  Azimuth    │  Elevation   │                │
      │  Response   │  Response    │                │
      │  (Mpl Fig)  │  (Mpl Fig)   │                │
      ├─────────────┴──────────────┴────────────────┤
      │              Controls (buttons)             │
      └─────────────────────────────────────────────┘
    """

    def _t(self, key: str, **kwargs) -> str:
        return _text_for_language(key, getattr(self, "language", LANGUAGE_ZH), **kwargs)

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.language = LANGUAGE_ZH
        self.language_var = tk.StringVar(value=LANGUAGE_LABELS[self.language])
        self.root.title(self._t("app_title", version=APP_VERSION))
        self.root.configure(bg=THEME["bg"])

        # Data state
        self.elements = self._build_elements()
        self.dragging: EditableElement | None = None
        self.drag_bounds: tuple[float, float, float, float] | None = None
        self.drag_axis_limits: tuple[tuple[float, float], tuple[float, float]] | None = None
        self.drag_start_snapshot: LayoutSnapshot | None = None
        self.selected_element: EditableElement | None = None
        self.delete_mode = False
        self.undo_stack: deque[LayoutSnapshot] = deque(maxlen=MAX_HISTORY_STATES)
        self.redo_stack: deque[LayoutSnapshot] = deque(maxlen=MAX_HISTORY_STATES)

        # Hover state
        self.physical_hover_annotation = None
        self.physical_hover_marker = None
        self.virtual_hover_annotation = None
        self.virtual_hover_marker = None
        self.virtual_hover_xy = np.empty((0, 2), dtype=float)
        self.virtual_hover_counts = np.empty(0, dtype=int)
        self.virtual_hover_text: list[str] = []
        self.physical_buttons: list[MplButton] = []
        self.physical_button_callbacks: list[int] = []
        self.physical_action_buttons: dict[str, ttk.Button] = {}
        self.dbf_scan_active = False
        self.dbf_scan_paused = False
        self.dbf_scan_mode: str | None = None
        self.dbf_scan_after_id: str | None = None
        self.dbf_true_angles = np.empty(0, dtype=float)
        self.dbf_scan_angles = np.empty(0, dtype=float)
        self.dbf_spectra_db = np.empty((0, 0), dtype=float)
        self.dbf_scan_frame = 0
        self.dbf_drag_mode: str | None = None
        self.dbf2d_az_frame = _dbf_frame_index_for_angle(0.0)
        self.dbf2d_el_frame = _dbf_frame_index_for_angle(0.0)
        self.dbf2d_az_playing = False
        self.dbf2d_el_playing = False
        self.dbf2d_after_id: str | None = None
        self.dbf2d_progress_updating = False
        self.dbf2d_dragging = False
        self.dbf2d_az_var: tk.DoubleVar | None = None
        self.dbf2d_el_var: tk.DoubleVar | None = None
        self.dbf2d_az_button: ttk.Button | None = None
        self.dbf2d_el_button: ttk.Button | None = None
        self.dbf2d_stop_button: ttk.Button | None = None
        self.dbf2d_status_label: ttk.Label | None = None
        self.dbf2d_fig: Figure | None = None
        self.dbf2d_ax = None
        self.dbf2d_cbar_ax = None
        self.dbf2d_canvas: FigureCanvasTkAgg | None = None
        self.dbf2d_normalization_max: float | None = None
        self.dbf2d_hover_annotation = None
        self.dbf2d_hover_marker = None
        self.dbf2d_hover_azimuths = np.empty(0, dtype=float)
        self.dbf2d_hover_elevations = np.empty(0, dtype=float)
        self.dbf2d_hover_db = np.empty((0, 0), dtype=float)
        self.workspace_pane: ttk.PanedWindow | None = None
        self.eval_notebook: ttk.Notebook | None = None
        self.config_menu_button: ttk.Menubutton | None = None
        self.language_menu_button: ttk.Menubutton | None = None
        self.edit_menu_button: ttk.Menubutton | None = None
        self.help_menu_button: ttk.Menubutton | None = None
        self.config_menu: tk.Menu | None = None
        self.language_menu: tk.Menu | None = None
        self.edit_menu: tk.Menu | None = None
        self.help_menu: tk.Menu | None = None
        self.eval_summary_tab: ttk.Frame | None = None

        self.element_pattern: ElementPattern | None = None
        self.channel_patterns = ChannelPatternSet()
        self.dbf_dictionary = DbfDictionaryConfig()
        self.auto_tx_count = tk.StringVar(value="1")
        self.auto_rx_count = tk.StringVar(value="1")
        self.last_valid_frequency_ghz = DEFAULT_FREQUENCY_GHZ
        self.frequency_ghz = tk.StringVar(
            value=_format_frequency_ghz(DEFAULT_FREQUENCY_GHZ)
        )
        self.frequency_entry: ttk.Entry | None = None
        self.pattern_status = tk.StringVar(value=self._t("pattern_ideal"))
        self.status = tk.StringVar(
            value=self._t("status_initial")
        )
        self.header_frequency_text = tk.StringVar()
        self.header_dictionary_text = tk.StringVar()
        self.header_pattern_text = tk.StringVar()
        self.header_kpi_texts: dict[str, tk.StringVar] = {
            "chip_virtual_channels": tk.StringVar(value="N/A"),
            "chip_az_resolution": tk.StringVar(value="N/A"),
            "chip_el_resolution": tk.StringVar(value="N/A"),
            "chip_peak_margin": tk.StringVar(value="N/A"),
        }
        self.header_title_label: ttk.Label | None = None
        self.header_subtitle_label: ttk.Label | None = None
        self.header_chip_labels: dict[str, ttk.Label] = {}
        self.last_layout_dir = Path("outputs").resolve()
        self.last_pattern_dir = Path.home()
        self.last_valid_margin_db = DBF_AMBIGUITY_MARGIN_DB
        self.margin_db = tk.StringVar(value=_format_margin_db(DBF_AMBIGUITY_MARGIN_DB))
        self.margin_entry: ttk.Entry | None = None
        self._load_local_state()
        self._sync_auto_count_inputs()

        # ── Build the grid layout ─────────────────────────────────
        root.grid_rowconfigure(0, weight=0)  # Codex-style menu
        root.grid_rowconfigure(1, weight=0)  # Workspace header
        root.grid_rowconfigure(2, weight=1, minsize=650)  # Draggable workspace
        root.grid_rowconfigure(3, weight=0)  # Controls
        root.grid_columnconfigure(0, weight=1, minsize=PLOT_COLUMN_MIN_WIDTH * 2)
        root.grid_columnconfigure(1, weight=0)
        root.grid_columnconfigure(2, weight=0)
        style = ttk.Style(self.root)
        style.theme_use("clam")

        # ── Refined ttk styles ─────────────────────────────────────
        _f = THEME["font_family"]
        _fm = THEME["font_family_mono"]
        root.option_add("*Font", f"{{{_f}}} {THEME['font_size_base']}")
        root.option_add("*Menu.Font", f"{{{_f}}} {THEME['font_size_base']}")
        root.option_add("*Menu.background", THEME["card_bg"])
        root.option_add("*Menu.foreground", THEME["text_primary"])
        root.option_add("*Menu.activeBackground", THEME["menu_hover"])
        root.option_add("*Menu.activeForeground", THEME["text_primary"])
        root.option_add("*Menu.disabledForeground", THEME["text_muted"])
        root.option_add("*Menu.selectColor", THEME["focus"])
        root.option_add("*Menu.borderWidth", 1)
        root.option_add("*Menu.activeBorderWidth", 0)
        root.option_add("*Menu.relief", "solid")
        root.option_add("*selectBackground", THEME["selection_fill"])
        root.option_add("*selectForeground", THEME["text_primary"])

        style.configure("TFrame", background=THEME["bg"])
        style.configure("Panel.TFrame", background=THEME["panel_bg"], borderwidth=0)
        style.configure(
            "PlotPanel.TFrame",
            background=THEME["card_bg"],
            bordercolor=THEME["card_border"],
            lightcolor=THEME["card_bg"],
            darkcolor=THEME["card_border"],
            relief="solid",
            borderwidth=1,
        )
        style.configure("Card.TFrame", background=THEME["card_bg"])
        style.configure("Dialog.TFrame", background=THEME["bg"])
        style.configure("Toolbar.TFrame", background=THEME["status_bar_bg"])
        style.configure("AppMenu.TFrame", background=THEME["app_menu_bg"])
        style.configure("Header.TFrame", background=THEME["header_bg"])
        style.configure("Workspace.TPanedwindow", background=THEME["bg"])
        style.configure(
            "HeaderChip.TFrame",
            background=THEME["chip_bg"],
            bordercolor=THEME["chip_border"],
            lightcolor=THEME["chip_bg"],
            darkcolor=THEME["chip_border"],
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "ToolbarGroup.TFrame",
            background=THEME["toolbar_group_bg"],
            bordercolor=THEME["card_border"],
            lightcolor=THEME["toolbar_group_bg"],
            darkcolor=THEME["card_border"],
        )
        style.configure("ChartFooter.TFrame", background=THEME["panel_alt_bg"])
        style.configure("Status.TFrame", background=THEME["status_bar_bg"])
        style.configure("StatusInner.TFrame", background=THEME["status_bar_bg"])

        style.configure(
            "TLabel",
            background=THEME["bg"],
            foreground=THEME["text_primary"],
            font=(_f, THEME["font_size_base"]),
        )
        style.configure(
            "Toolbar.TLabel",
            background=THEME["toolbar_group_bg"],
            foreground=THEME["text_secondary"],
            font=(_f, THEME["font_size_sm"], "bold"),
        )
        style.configure(
            "Status.TLabel",
            background=THEME["status_bar_bg"],
            foreground=THEME["text_secondary"],
            font=(_f, THEME["font_size_sm"]),
        )
        style.configure(
            "HeaderTitle.TLabel",
            background=THEME["header_bg"],
            foreground=THEME["text_inverse"],
            font=(_f, 12, "bold"),
        )
        style.configure(
            "HeaderSubtitle.TLabel",
            background=THEME["header_bg"],
            foreground=THEME["text_inverse_muted"],
            font=(_f, THEME["font_size_sm"]),
        )
        style.configure(
            "HeaderChipName.TLabel",
            background=THEME["chip_bg"],
            foreground=THEME["text_inverse_muted"],
            font=(_f, 8, "bold"),
        )
        style.configure(
            "HeaderChipValue.TLabel",
            background=THEME["chip_bg"],
            foreground=THEME["text_inverse"],
            font=(_fm, THEME["font_size_sm"], "bold"),
        )
        style.configure(
            "Muted.TLabel",
            background=THEME["toolbar_group_bg"],
            foreground=THEME["text_muted"],
            font=(_f, THEME["font_size_sm"]),
        )
        style.configure(
            "ChartFooter.TLabel",
            background=THEME["panel_alt_bg"],
            foreground=THEME["text_secondary"],
            font=(_f, THEME["font_size_sm"]),
        )
        style.configure(
            "Card.TLabel",
            background=THEME["card_bg"],
            foreground=THEME["text_primary"],
            font=(_f, THEME["font_size_base"]),
        )
        style.configure(
            "CardMono.TLabel",
            background=THEME["card_bg"],
            foreground=THEME["text_primary"],
            font=(_fm, THEME["font_size_base"]),
        )
        style.configure(
            "CardHeader.TLabel",
            background=THEME["card_bg"],
            foreground=THEME["text_primary"],
            font=(_fm, THEME["font_size_base"], "bold"),
        )
        style.configure(
            "SectionTitle.TLabel",
            background=THEME["card_bg"],
            foreground=THEME["text_secondary"],
            font=(_f, THEME["font_size_sm"], "bold"),
        )
        style.configure(
            "Badge.TLabel",
            background=THEME["card_bg"],
            foreground=THEME["text_primary"],
            font=(_f, THEME["font_size_lg"], "bold"),
        )
        style.configure(
            "Metric.TFrame",
            background=THEME["metric_bg"],
            bordercolor=THEME["metric_border"],
            lightcolor=THEME["metric_bg"],
            darkcolor=THEME["metric_border"],
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "MetricName.TLabel",
            background=THEME["metric_bg"],
            foreground=THEME["text_secondary"],
            font=(_f, THEME["font_size_sm"]),
        )
        style.configure(
            "MetricSection.TLabel",
            background=THEME["metric_bg"],
            foreground=THEME["text_primary"],
            font=(_f, THEME["font_size_base"], "bold"),
        )
        style.configure(
            "MetricValue.TLabel",
            background=THEME["metric_bg"],
            foreground=THEME["text_primary"],
            font=(_fm, THEME["font_size_sm"], "bold"),
        )
        style.configure(
            "MetricValueGood.TLabel",
            background=THEME["metric_bg"],
            foreground=THEME["success"],
            font=(_fm, THEME["font_size_sm"], "bold"),
        )
        style.configure(
            "MetricValueWarn.TLabel",
            background=THEME["metric_bg"],
            foreground=THEME["warning"],
            font=(_fm, THEME["font_size_sm"], "bold"),
        )
        style.configure(
            "MetricValueRisk.TLabel",
            background=THEME["metric_bg"],
            foreground=THEME["danger"],
            font=(_fm, THEME["font_size_sm"], "bold"),
        )

        button_base = {
            "padding": (12, 7),
            "relief": "flat",
            "borderwidth": 1,
            "focuscolor": THEME["focus"],
        }
        button_font = (_f, THEME["font_size_base"])
        style.configure(
            "TButton",
            **button_base,
            font=button_font,
            background=THEME["button_bg"],
            foreground=THEME["text_primary"],
            bordercolor=THEME["button_border"],
            lightcolor=THEME["button_bg"],
            darkcolor=THEME["button_border"],
        )
        style.map(
            "TButton",
            background=[
                ("disabled", THEME["disabled_bg"]),
                ("pressed", THEME["button_pressed"]),
                ("active", THEME["button_hover"]),
            ],
            foreground=[
                ("disabled", THEME["text_muted"]),
                ("active", THEME["text_primary"]),
            ],
            bordercolor=[
                ("pressed", THEME["focus"]),
                ("focus", THEME["focus"]),
                ("active", THEME["focus_soft"]),
            ],
            lightcolor=[("pressed", THEME["button_pressed"]), ("active", THEME["button_hover"])],
            darkcolor=[("pressed", THEME["button_pressed"]), ("active", THEME["button_hover"])],
        )
        style.configure(
            "Accent.TButton",
            **button_base,
            font=(_f, THEME["font_size_base"], "bold"),
            background=THEME["accent"],
            foreground=THEME["text_inverse"],
            bordercolor=THEME["accent"],
            lightcolor=THEME["accent"],
            darkcolor=THEME["accent_pressed"],
        )
        style.map(
            "Accent.TButton",
            background=[
                ("disabled", "#9ca3af"),
                ("pressed", THEME["accent_pressed"]),
                ("active", THEME["accent_hover"]),
            ],
            foreground=[("disabled", "#f8fafc"), ("active", THEME["text_inverse"])],
            bordercolor=[("focus", THEME["focus"]), ("active", THEME["accent_hover"])],
            lightcolor=[("pressed", THEME["accent_pressed"]), ("active", THEME["accent_hover"])],
            darkcolor=[("pressed", THEME["accent_pressed"]), ("active", THEME["accent_hover"])],
        )
        large_button_map = {
            "background": [
                ("disabled", THEME["disabled_bg"]),
                ("pressed", THEME["button_pressed"]),
                ("active", THEME["button_hover"]),
            ],
            "foreground": [
                ("disabled", THEME["text_muted"]),
                ("active", THEME["text_primary"]),
            ],
            "bordercolor": [
                ("pressed", THEME["focus"]),
                ("focus", THEME["focus"]),
                ("active", THEME["focus_soft"]),
            ],
            "lightcolor": [
                ("pressed", THEME["button_pressed"]),
                ("active", THEME["button_hover"]),
            ],
            "darkcolor": [
                ("pressed", THEME["button_pressed"]),
                ("active", THEME["button_hover"]),
            ],
        }
        style.configure(
            "Large.TButton",
            **{**button_base, "relief": "solid"},
            font=button_font,
            background=THEME["button_bg"],
            foreground=THEME["text_primary"],
            bordercolor=THEME["button_border"],
            lightcolor=THEME["button_bg"],
            darkcolor=THEME["button_border"],
        )
        style.map("Large.TButton", **large_button_map)
        compact_button_base = {
            **button_base,
            "padding": (8, 4),
        }
        style.configure(
            "Compact.TButton",
            **compact_button_base,
            font=(_f, THEME["font_size_sm"], "bold"),
            background=THEME["button_bg"],
            foreground=THEME["text_primary"],
            bordercolor=THEME["button_border"],
            lightcolor=THEME["button_bg"],
            darkcolor=THEME["button_border"],
        )
        style.map("Compact.TButton", **large_button_map)
        style.configure(
            "CompactPlay.TButton",
            **compact_button_base,
            font=(_f, THEME["font_size_sm"], "bold"),
            background=THEME["button_bg"],
            foreground=THEME["focus"],
            bordercolor=THEME["focus_soft"],
            lightcolor=THEME["button_bg"],
            darkcolor=THEME["focus_soft"],
        )
        style.map(
            "CompactPlay.TButton",
            background=[
                ("disabled", THEME["disabled_bg"]),
                ("pressed", THEME["button_pressed"]),
                ("active", THEME["button_hover"]),
            ],
            foreground=[
                ("disabled", THEME["text_muted"]),
                ("pressed", THEME["focus"]),
                ("active", THEME["focus"]),
            ],
            bordercolor=[
                ("disabled", THEME["button_border"]),
                ("focus", THEME["focus"]),
                ("active", THEME["focus"]),
            ],
            lightcolor=[
                ("pressed", THEME["button_pressed"]),
                ("active", THEME["button_hover"]),
            ],
            darkcolor=[
                ("pressed", THEME["button_pressed"]),
                ("active", THEME["button_hover"]),
            ],
        )
        style.configure(
            "CompactPlayActive.TButton",
            **compact_button_base,
            font=(_f, THEME["font_size_sm"], "bold"),
            background=THEME["button_bg"],
            foreground=THEME["focus"],
            bordercolor=THEME["focus"],
            lightcolor=THEME["button_bg"],
            darkcolor=THEME["focus"],
        )
        style.map(
            "CompactPlayActive.TButton",
            background=[
                ("disabled", THEME["disabled_bg"]),
                ("pressed", THEME["button_pressed"]),
                ("active", THEME["button_hover"]),
            ],
            foreground=[
                ("disabled", THEME["text_muted"]),
                ("active", THEME["focus"]),
            ],
            bordercolor=[
                ("disabled", THEME["button_border"]),
                ("focus", THEME["focus"]),
                ("active", THEME["focus"]),
            ],
            lightcolor=[
                ("pressed", THEME["button_pressed"]),
                ("active", THEME["button_hover"]),
            ],
            darkcolor=[
                ("pressed", THEME["button_pressed"]),
                ("active", THEME["button_hover"]),
            ],
        )
        style.configure(
            "CompactStop.TButton",
            **compact_button_base,
            font=(_f, THEME["font_size_sm"], "bold"),
            background=THEME["button_bg"],
            foreground=THEME["danger"],
            bordercolor=THEME["danger_border"],
            lightcolor=THEME["button_bg"],
            darkcolor=THEME["danger_border"],
        )
        style.map(
            "CompactStop.TButton",
            background=[
                ("disabled", THEME["disabled_bg"]),
                ("pressed", THEME["button_pressed"]),
                ("active", THEME["button_hover"]),
            ],
            foreground=[
                ("disabled", THEME["text_muted"]),
                ("pressed", THEME["danger_pressed"]),
                ("active", THEME["danger_pressed"]),
            ],
            bordercolor=[
                ("disabled", THEME["button_border"]),
                ("focus", THEME["danger"]),
                ("active", THEME["danger"]),
            ],
            lightcolor=[
                ("pressed", THEME["button_pressed"]),
                ("active", THEME["button_hover"]),
            ],
            darkcolor=[
                ("pressed", THEME["button_pressed"]),
                ("active", THEME["button_hover"]),
            ],
        )
        style.configure(
            "CompactAccent.TButton",
            **compact_button_base,
            font=(_f, THEME["font_size_sm"], "bold"),
            background=THEME["button_bg"],
            foreground=THEME["text_primary"],
            bordercolor=THEME["button_border"],
            lightcolor=THEME["button_bg"],
            darkcolor=THEME["button_border"],
        )
        style.map(
            "CompactAccent.TButton",
            background=[
                ("disabled", THEME["disabled_bg"]),
                ("pressed", THEME["button_pressed"]),
                ("active", THEME["button_hover"]),
            ],
            foreground=[("disabled", THEME["text_muted"]), ("active", THEME["text_primary"])],
            bordercolor=[("focus", THEME["focus"]), ("active", THEME["focus_soft"])],
            lightcolor=[("pressed", THEME["button_pressed"]), ("active", THEME["button_hover"])],
            darkcolor=[("pressed", THEME["button_pressed"]), ("active", THEME["button_hover"])],
        )
        style.configure(
            "CompactDanger.TButton",
            **compact_button_base,
            font=(_f, THEME["font_size_sm"], "bold"),
            background=THEME["button_bg"],
            foreground=THEME["danger"],
            bordercolor=THEME["danger"],
            lightcolor=THEME["button_bg"],
            darkcolor=THEME["danger_border"],
        )
        style.map(
            "CompactDanger.TButton",
            background=[("pressed", THEME["button_pressed"]), ("active", THEME["button_hover"])],
            foreground=[("active", THEME["danger_pressed"])],
            bordercolor=[("pressed", THEME["danger_pressed"]), ("active", THEME["danger"])],
            lightcolor=[("pressed", THEME["button_pressed"]), ("active", THEME["button_hover"])],
            darkcolor=[("pressed", THEME["button_pressed"]), ("active", THEME["button_hover"])],
        )
        style.configure(
            "Toolbar.TMenubutton",
            **button_base,
            font=(_f, THEME["font_size_base"], "bold"),
            background=THEME["button_bg"],
            foreground=THEME["text_primary"],
            bordercolor=THEME["button_border"],
            lightcolor=THEME["button_bg"],
            darkcolor=THEME["button_border"],
        )
        style.map(
            "Toolbar.TMenubutton",
            background=[
                ("pressed", THEME["button_pressed"]),
                ("active", THEME["button_hover"]),
            ],
            foreground=[("active", THEME["text_primary"])],
            bordercolor=[
                ("pressed", THEME["focus"]),
                ("focus", THEME["focus"]),
                ("active", THEME["focus_soft"]),
            ],
            lightcolor=[("pressed", THEME["button_pressed"]), ("active", THEME["button_hover"])],
            darkcolor=[("pressed", THEME["button_pressed"]), ("active", THEME["button_hover"])],
        )
        style.configure(
            "TopMenu.TMenubutton",
            padding=(14, 5),
            relief="flat",
            borderwidth=0,
            font=(_f, THEME["font_size_base"], "bold"),
            background=THEME["app_menu_bg"],
            foreground=THEME["app_menu_text"],
            bordercolor=THEME["app_menu_bg"],
            lightcolor=THEME["app_menu_bg"],
            darkcolor=THEME["app_menu_bg"],
            arrowcolor=THEME["app_menu_text"],
        )
        style.map(
            "TopMenu.TMenubutton",
            background=[
                ("pressed", THEME["app_menu_hover"]),
                ("active", THEME["app_menu_hover"]),
            ],
            foreground=[
                ("pressed", THEME["app_menu_text_active"]),
                ("active", THEME["app_menu_text_active"]),
            ],
            bordercolor=[
                ("pressed", THEME["app_menu_hover"]),
                ("active", THEME["app_menu_hover"]),
            ],
            lightcolor=[
                ("pressed", THEME["app_menu_hover"]),
                ("active", THEME["app_menu_hover"]),
            ],
            darkcolor=[
                ("pressed", THEME["app_menu_hover"]),
                ("active", THEME["app_menu_hover"]),
            ],
            arrowcolor=[
                ("pressed", THEME["app_menu_text_active"]),
                ("active", THEME["app_menu_text_active"]),
            ],
        )
        style.configure(
            "AppMenuArrow.TLabel",
            background=THEME["app_menu_bg"],
            foreground=THEME["app_menu_text"],
            font=(_f, THEME["font_size_base"], "bold"),
        )
        style.configure(
            "Danger.TButton",
            **{**button_base, "relief": "solid"},
            font=button_font,
            background=THEME["danger_light"],
            foreground=THEME["danger"],
            bordercolor=THEME["danger"],
            lightcolor=THEME["danger_light"],
            darkcolor=THEME["danger_border"],
        )
        style.map(
            "Danger.TButton",
            background=[
                ("disabled", THEME["disabled_bg"]),
                ("pressed", "#fee2e2"),
                ("active", THEME["danger_light"]),
            ],
            foreground=[
                ("disabled", THEME["text_muted"]),
                ("pressed", THEME["danger_pressed"]),
                ("active", THEME["danger_pressed"]),
            ],
            bordercolor=[
                ("disabled", THEME["button_border"]),
                ("focus", THEME["danger"]),
                ("active", THEME["danger"]),
            ],
            lightcolor=[("pressed", "#fee2e2"), ("active", THEME["danger_light"])],
            darkcolor=[("pressed", "#fee2e2"), ("active", THEME["danger_light"])],
        )
        dialog_button_base = {
            **button_base,
            "padding": (12, 7),
            "relief": "solid",
        }
        dialog_button_map = {
            "background": [
                ("disabled", THEME["disabled_bg"]),
                ("pressed", THEME["dialog_button_pressed"]),
                ("active", THEME["dialog_button_hover"]),
            ],
            "foreground": [
                ("disabled", THEME["text_muted"]),
                ("active", THEME["text_primary"]),
            ],
            "bordercolor": [
                ("disabled", THEME["button_border"]),
                ("focus", THEME["button_border"]),
                ("active", THEME["button_border"]),
            ],
            "lightcolor": [
                ("pressed", THEME["dialog_button_pressed"]),
                ("active", THEME["dialog_button_hover"]),
            ],
            "darkcolor": [
                ("pressed", THEME["dialog_button_pressed"]),
                ("active", THEME["dialog_button_hover"]),
            ],
        }
        style.configure(
            "DialogButton.TButton",
            **dialog_button_base,
            font=button_font,
            background=THEME["button_bg"],
            foreground=THEME["text_primary"],
            bordercolor=THEME["button_border"],
            lightcolor=THEME["button_bg"],
            darkcolor=THEME["button_border"],
        )
        style.map("DialogButton.TButton", **dialog_button_map)
        style.configure(
            "DialogDanger.TButton",
            **dialog_button_base,
            font=button_font,
            background=THEME["button_bg"],
            foreground=THEME["danger"],
            bordercolor=THEME["button_border"],
            lightcolor=THEME["button_bg"],
            darkcolor=THEME["button_border"],
        )
        danger_dialog_map = {
            **dialog_button_map,
            "foreground": [
                ("disabled", THEME["text_muted"]),
                ("pressed", THEME["danger_pressed"]),
                ("active", THEME["danger_pressed"]),
            ],
        }
        style.map("DialogDanger.TButton", **danger_dialog_map)

        style.configure(
            "TLabelframe",
            background=THEME["card_bg"],
            foreground=THEME["text_secondary"],
            bordercolor=THEME["card_border"],
            lightcolor=THEME["card_bg"],
            darkcolor=THEME["card_border"],
            relief="solid",
            borderwidth=1,
            font=(_f, THEME["font_size_sm"], "bold"),
        )
        style.configure(
            "TLabelframe.Label",
            background=THEME["card_bg"],
            foreground=THEME["text_secondary"],
            font=(_f, THEME["font_size_sm"], "bold"),
        )

        style.configure(
            "TEntry",
            font=(_f, THEME["font_size_base"]),
            padding=(6, 4),
            fieldbackground=THEME["input_bg"],
            background=THEME["input_bg"],
            foreground=THEME["text_primary"],
            bordercolor=THEME["button_border"],
            lightcolor=THEME["input_bg"],
            darkcolor=THEME["button_border"],
            insertcolor=THEME["text_primary"],
            selectbackground=THEME["selection_fill"],
            selectforeground=THEME["text_primary"],
        )
        style.map(
            "TEntry",
            bordercolor=[
                ("focus", THEME["focus"]),
                ("active", THEME["focus_soft"]),
            ],
            fieldbackground=[
                ("disabled", THEME["disabled_bg"]),
                ("focus", THEME["input_bg"]),
            ],
        )
        style.configure(
            "TCombobox",
            font=(_f, THEME["font_size_base"]),
            fieldbackground=THEME["input_bg"],
            background=THEME["button_bg"],
            foreground=THEME["text_primary"],
            bordercolor=THEME["button_border"],
            arrowcolor=THEME["text_secondary"],
            selectbackground=THEME["selection_fill"],
            selectforeground=THEME["text_primary"],
        )
        style.map(
            "TCombobox",
            bordercolor=[
                ("focus", THEME["focus"]),
                ("active", THEME["focus_soft"]),
            ],
            fieldbackground=[
                ("readonly", THEME["input_bg"]),
                ("disabled", THEME["disabled_bg"]),
            ],
            arrowcolor=[("active", THEME["focus"]), ("disabled", THEME["text_muted"])],
        )
        for selector_style in ("TRadiobutton", "TCheckbutton"):
            style.configure(
                selector_style,
                background=THEME["card_bg"],
                foreground=THEME["text_primary"],
                font=(_f, THEME["font_size_base"]),
                focuscolor=THEME["focus_soft"],
                indicatorbackground=THEME["input_bg"],
                indicatorforeground=THEME["focus"],
                indicatorcolor=THEME["selection_fill"],
                bordercolor=THEME["button_border"],
                lightcolor=THEME["input_bg"],
                darkcolor=THEME["button_border"],
            )
            style.map(
                selector_style,
                background=[
                    ("pressed", THEME["button_pressed"]),
                    ("active", THEME["button_hover"]),
                ],
                indicatorbackground=[
                    ("pressed", THEME["button_pressed"]),
                    ("active", THEME["hover_fill"]),
                    ("selected", THEME["selection_fill"]),
                ],
                indicatorcolor=[
                    ("pressed", THEME["button_pressed"]),
                    ("active", THEME["hover_fill"]),
                    ("selected", THEME["selection_fill"]),
                ],
                foreground=[
                    ("disabled", THEME["text_muted"]),
                    ("active", THEME["text_primary"]),
                    ("selected", THEME["text_primary"]),
                ],
            )
        style.configure(
            "Horizontal.TScale",
            background=THEME["panel_alt_bg"],
            troughcolor="#e2e6ec",
            bordercolor=THEME["panel_alt_bg"],
            lightcolor=THEME["accent"],
            darkcolor=THEME["accent"],
        )
        style.configure(
            "Vertical.TScale",
            background=THEME["panel_alt_bg"],
            troughcolor="#e2e6ec",
            bordercolor=THEME["panel_alt_bg"],
            lightcolor=THEME["accent"],
            darkcolor=THEME["accent"],
        )
        style.configure(
            "Treeview",
            background=THEME["card_bg"],
            fieldbackground=THEME["card_bg"],
            foreground=THEME["text_primary"],
            rowheight=27,
            bordercolor=THEME["card_border"],
            borderwidth=0,
            font=(_f, THEME["font_size_base"]),
        )
        style.map(
            "Treeview",
            background=[("selected", THEME["selection_fill"])],
            foreground=[("selected", THEME["text_primary"])],
        )
        style.configure(
            "Treeview.Heading",
            background=THEME["panel_alt_bg"],
            foreground=THEME["text_secondary"],
            font=(_f, THEME["font_size_sm"], "bold"),
            relief="flat",
            padding=(6, 5),
        )
        style.map(
            "Treeview.Heading",
            background=[("active", THEME["button_hover"])],
            foreground=[("active", THEME["text_primary"])],
        )
        style.configure(
            "Eval.TNotebook",
            background=THEME["card_bg"],
            borderwidth=0,
            tabmargins=(0, 0, 0, 0),
        )
        style.configure(
            "Eval.TNotebook.Tab",
            background=THEME["panel_alt_bg"],
            foreground=THEME["text_secondary"],
            font=(_f, THEME["font_size_sm"], "bold"),
            padding=(10, 6),
        )
        style.map(
            "Eval.TNotebook.Tab",
            background=[
                ("selected", THEME["card_bg"]),
                ("active", THEME["button_hover"]),
            ],
            foreground=[
                ("selected", THEME["text_primary"]),
                ("active", THEME["text_primary"]),
            ],
        )

        self._build_app_menu(root)
        self._build_workspace_header(root)

        # ── Row 1: draggable plot workspace + evaluation panel ────
        self.workspace_pane = ttk.PanedWindow(
            root,
            orient=tk.HORIZONTAL,
            style="Workspace.TPanedwindow",
        )
        self.workspace_pane.grid(row=2, column=0, columnspan=3, sticky="nsew")

        plot_workspace = ttk.Frame(
            self.workspace_pane,
            style="Panel.TFrame",
            padding=(10, 10, 5, 10),
            width=max(PLOT_COLUMN_MIN_WIDTH * 2, WINDOW_WIDTH - EVAL_PANEL_MIN_WIDTH - 40),
            height=650,
        )
        plot_workspace.grid_propagate(False)
        plot_workspace.grid_rowconfigure(0, weight=1, minsize=280, uniform="plot_rows")
        plot_workspace.grid_rowconfigure(1, weight=1, minsize=280, uniform="plot_rows")
        plot_workspace.grid_columnconfigure(0, weight=1, uniform="plot")
        plot_workspace.grid_columnconfigure(1, weight=1, uniform="plot")

        left_frame = ttk.Frame(
            plot_workspace,
            style="PlotPanel.TFrame",
            padding=(10, 10, 10, 8),
        )
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=(0, 5))
        left_frame.grid_rowconfigure(0, weight=0)
        left_frame.grid_rowconfigure(1, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)
        self._build_physical_toolbar(left_frame)

        right_frame = ttk.Frame(
            plot_workspace,
            style="PlotPanel.TFrame",
            padding=(10, 10, 10, 8),
        )
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=(0, 5))
        right_frame.grid_rowconfigure(0, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)

        eval_info_frame = ttk.Frame(
            self.workspace_pane,
            style="Panel.TFrame",
            padding=(5, 10, 10, 10),
            width=EVAL_PANEL_MIN_WIDTH,
            height=650,
        )
        eval_info_frame.grid_propagate(False)
        eval_info_frame.grid_rowconfigure(0, weight=1)
        eval_info_frame.grid_columnconfigure(0, weight=1)
        self.workspace_pane.add(plot_workspace, weight=1)
        self.workspace_pane.add(eval_info_frame, weight=0)
        self._build_evaluation_panel(eval_info_frame)
        self.root.after_idle(self._set_default_workspace_sash)
        self.root.after(100, self._set_default_workspace_sash)
        self.root.after(300, self._stabilize_default_workspace_sash)

        # Physical Array figure
        self.phys_fig = Figure(figsize=(PHYS_FIG_W, PHYS_FIG_H), dpi=FIG_DPI)
        self.phys_fig.set_facecolor(THEME["card_bg"])
        self.physical_ax = self.phys_fig.add_subplot(111)
        self.physical_ax.set_facecolor(THEME["plot_bg"])
        self.phys_fig.subplots_adjust(top=0.87, left=0.10, right=0.97, bottom=0.17)
        self.phys_canvas = FigureCanvasTkAgg(self.phys_fig, master=left_frame)
        phys_widget = self.phys_canvas.get_tk_widget()
        _style_canvas_widget(phys_widget)
        phys_widget.grid(row=1, column=0, sticky="nsew")

        # Virtual Array figure
        self.virt_fig = Figure(figsize=(VIRT_FIG_W, VIRT_FIG_H), dpi=FIG_DPI)
        self.virt_fig.set_facecolor(THEME["card_bg"])
        self.virtual_ax = self.virt_fig.add_subplot(111)
        self.virtual_ax.set_facecolor(THEME["plot_bg"])
        self.virt_canvas = FigureCanvasTkAgg(self.virt_fig, master=right_frame)
        virt_widget = self.virt_canvas.get_tk_widget()
        _style_canvas_widget(virt_widget)
        virt_widget.grid(row=0, column=0, sticky="nsew")

        # ── Bottom row: Azimuth Response + Elevation Response ─────
        self.az_chart = self._build_response_chart(
            plot_workspace, row=1, col=0, padding=(6, 3, 3, 6), mode="azimuth"
        )
        self.el_chart = self._build_response_chart(
            plot_workspace, row=1, col=1, padding=(3, 3, 6, 6), mode="elevation"
        )

        # ── Row 2: Controls ───────────────────────────────────────
        controls_outer = ttk.Frame(root, style="Status.TFrame")
        controls_outer.grid(row=3, column=0, columnspan=3, sticky="ew")
        controls = ttk.Frame(controls_outer, style="Status.TFrame", padding=(12, 8, 12, 4))
        controls.pack(fill=tk.X)
        status_row = ttk.Frame(controls_outer, style="Status.TFrame", padding=(12, 0, 12, 8))
        status_row.pack(fill=tk.X)

        controls.grid_columnconfigure(3, weight=1)

        def toolbar_group(
            column: int,
            *,
            sticky: str = "w",
            padx: tuple[int, int] = (0, 8),
        ) -> ttk.Frame:
            group = ttk.Frame(
                controls,
                style="ToolbarGroup.TFrame",
                padding=(8, 5),
                borderwidth=1,
                relief="solid",
            )
            group.grid(row=0, column=column, sticky=sticky, padx=padx, pady=(0, 4))
            return group

        freq_group = toolbar_group(0)
        self.freq_toolbar_label = ttk.Label(
            freq_group, text=self._t("freq_label"), style="Toolbar.TLabel"
        )
        self.freq_toolbar_label.pack(side=tk.LEFT, padx=(0, 4))
        freq_entry = ttk.Entry(
            freq_group,
            textvariable=self.frequency_ghz,
            width=8,
            justify="right",
        )
        self.frequency_entry = freq_entry
        freq_entry.pack(side=tk.LEFT)
        freq_entry.bind("<Return>", self.on_frequency_changed)
        freq_entry.bind("<FocusOut>", self.on_frequency_changed)

        margin_group = toolbar_group(1)
        self.margin_toolbar_label = ttk.Label(
            margin_group, text=self._t("margin_label"), style="Toolbar.TLabel"
        )
        self.margin_toolbar_label.pack(side=tk.LEFT, padx=(0, 4))
        margin_entry = ttk.Entry(
            margin_group,
            textvariable=self.margin_db,
            width=5,
            justify="right",
        )
        self.margin_entry = margin_entry
        margin_entry.pack(side=tk.LEFT)
        margin_entry.bind("<Return>", self.on_margin_changed)
        margin_entry.bind("<FocusOut>", self.on_margin_changed)

        auto_group = toolbar_group(2)
        self.auto_toolbar_label = ttk.Label(
            auto_group, text=self._t("auto_label"), style="Toolbar.TLabel"
        )
        self.auto_toolbar_label.pack(side=tk.LEFT, padx=(0, 4))
        auto_tx_entry = ttk.Entry(
            auto_group,
            textvariable=self.auto_tx_count,
            width=3,
            justify="right",
        )
        auto_tx_entry.pack(side=tk.LEFT)
        auto_tx_entry.bind("<Return>", self.apply_auto_array_layout)
        ttk.Label(
            auto_group, text="T", style="Toolbar.TLabel"
        ).pack(side=tk.LEFT, padx=(2, 4))
        auto_rx_entry = ttk.Entry(
            auto_group,
            textvariable=self.auto_rx_count,
            width=3,
            justify="right",
        )
        auto_rx_entry.pack(side=tk.LEFT)
        auto_rx_entry.bind("<Return>", self.apply_auto_array_layout)
        ttk.Label(
            auto_group, text="R", style="Toolbar.TLabel"
        ).pack(side=tk.LEFT, padx=(2, 6))
        self.auto_apply_button = ttk.Button(
            auto_group,
            text=self._t("auto_apply"),
            command=self.apply_auto_array_layout,
            style="Large.TButton",
        )
        self.auto_apply_button.pack(side=tk.LEFT)

        pattern_group = toolbar_group(3, sticky="ew", padx=(0, 0))
        # Pattern indicator and controls
        self.pattern_canvas = tk.Canvas(
            pattern_group,
            width=12,
            height=12,
            highlightthickness=0,
            bg=THEME["toolbar_group_bg"],
        )
        self.pattern_canvas.pack(side=tk.LEFT, padx=(0, 4))
        self.pattern_dot = self.pattern_canvas.create_oval(
            1, 1, 11, 11, fill=THEME["text_muted"], outline=""
        )

        ttk.Label(
            pattern_group,
            textvariable=self.pattern_status,
            style="Muted.TLabel",
        ).pack(side=tk.LEFT)

        ttk.Label(
            status_row,
            textvariable=self.status,
            style="Status.TLabel",
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # ── Event bindings ────────────────────────────────────────
        # Physical array: press, motion, release (drag + hover)
        self.phys_canvas.mpl_connect("button_press_event", self.on_press)
        self.phys_canvas.mpl_connect("motion_notify_event", self.on_motion)
        self.phys_canvas.mpl_connect("button_release_event", self.on_release)
        # Virtual array: hover only
        self.virt_canvas.mpl_connect("motion_notify_event", self.on_motion)
        # Az/El response: hover only
        for mode, chart in (
            ("azimuth", self.az_chart),
            ("elevation", self.el_chart),
        ):
            chart.canvas.mpl_connect(
                "button_press_event",
                lambda event, chart_mode=mode: self.on_dbf_true_line_press(
                    event, chart_mode
                ),
            )
            chart.canvas.mpl_connect("motion_notify_event", self.on_motion)
            chart.canvas.mpl_connect(
                "button_release_event",
                lambda event, chart_mode=mode: self.on_dbf_true_line_release(
                    event, chart_mode
                ),
            )
            chart.canvas.mpl_connect(
                "figure_leave_event",
                lambda _event, response_chart=chart: self._on_response_figure_leave(
                    response_chart
                ),
            )
        if self.dbf2d_canvas is not None:
            self.dbf2d_canvas.mpl_connect("button_press_event", self.on_dbf2d_crosshair_press)
            self.dbf2d_canvas.mpl_connect("motion_notify_event", self.on_dbf2d_crosshair_motion)
            self.dbf2d_canvas.mpl_connect("button_release_event", self.on_dbf2d_crosshair_release)
            self.dbf2d_canvas.mpl_connect("figure_leave_event", self.on_dbf2d_figure_leave)

        self.root.bind("<Left>", self.on_arrow_key)
        self.root.bind("<Right>", self.on_arrow_key)
        self.root.bind("<Up>", self.on_arrow_key)
        self.root.bind("<Down>", self.on_arrow_key)
        self.root.bind("<Delete>", self.on_delete_key)
        self._bind_keyboard_shortcuts()

        _apply_interactive_cursors(self.root)
        self._refresh_language_texts()
        self.generate_virtual_array()

    # ── Response chart helpers ──────────────────────────────────────────

    def _build_app_menu(self, parent: tk.Widget) -> None:
        menu_bar = ttk.Frame(parent, style="AppMenu.TFrame", padding=(6, 2, 8, 2))
        menu_bar.grid(row=0, column=0, columnspan=3, sticky="ew")
        menu_bar.grid_columnconfigure(5, weight=1)

        ttk.Label(
            menu_bar,
            text=">",
            style="AppMenuArrow.TLabel",
            anchor="center",
            width=1,
        ).grid(row=0, column=0, sticky="w", padx=(0, 6))

        menu_specs = (
            ("config_menu_button", "config_menu", "menu_file", 1),
            ("edit_menu_button", "edit_menu", "menu_edit", 2),
            ("language_menu_button", "language_menu", "menu_view", 3),
            ("help_menu_button", "help_menu", "menu_help", 4),
        )
        for button_attr, menu_attr, label_key, column in menu_specs:
            button = ttk.Menubutton(
                menu_bar,
                text=self._t(label_key),
                style="TopMenu.TMenubutton",
                width=5,
            )
            button.grid(row=0, column=column, sticky="w", padx=(0, 6))
            menu = _build_popup_menu(button)
            button.configure(menu=menu)
            setattr(self, button_attr, button)
            setattr(self, menu_attr, menu)

        self._refresh_app_menus()

    def _refresh_app_menus(self) -> None:
        if self.config_menu_button is not None:
            self.config_menu_button.configure(text=self._t("menu_file"))
        if self.edit_menu_button is not None:
            self.edit_menu_button.configure(text=self._t("menu_edit"))
        if self.language_menu_button is not None:
            self.language_menu_button.configure(text=self._t("menu_view"))
        if self.help_menu_button is not None:
            self.help_menu_button.configure(text=self._t("menu_help"))

        if self.config_menu is not None:
            self.config_menu.delete(0, tk.END)
            self.config_menu.add_command(
                label=self._t("menu_import_layout"),
                command=self.import_layout_config,
            )
            self.config_menu.add_command(
                label=self._t("menu_export_layout"),
                command=self.export_layout_config,
            )
            _style_popup_menu(self.config_menu)

        if self.edit_menu is not None:
            self.edit_menu.delete(0, tk.END)
            self.edit_menu.add_command(
                label=self._t("menu_undo"),
                command=self.undo_layout_change,
            )
            self.edit_menu.add_command(
                label=self._t("menu_redo"),
                command=self.redo_layout_change,
            )
            self.edit_menu.add_separator()
            self.edit_menu.add_command(
                label=self._t("menu_channel_patterns"),
                command=self.open_channel_patterns_dialog,
            )
            self.edit_menu.add_command(
                label=self._t("menu_dbf_dictionary"),
                command=self.open_dbf_dictionary_dialog,
            )
            _style_popup_menu(self.edit_menu)

        if self.language_menu is not None:
            self.language_menu.delete(0, tk.END)
            for language, label_key in (
                (LANGUAGE_ZH, "language_zh"),
                (LANGUAGE_EN, "language_en"),
                (LANGUAGE_JA, "language_ja"),
            ):
                prefix = "✓ " if language == self.language else ""
                self.language_menu.add_command(
                    label=f"{prefix}{self._t(label_key)}",
                    command=lambda lang=language: self.set_language(lang),
                )
            _style_popup_menu(self.language_menu)

        if self.help_menu is not None:
            self.help_menu.delete(0, tk.END)
            self.help_menu.add_command(
                label=self._t("menu_user_manual"),
                command=self._show_user_manual_dialog,
            )
            self.help_menu.add_separator()
            self.help_menu.add_command(
                label=self._t("menu_about"),
                command=self._show_about_dialog,
            )
            _style_popup_menu(self.help_menu)

    def _show_user_manual_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        _style_toplevel(dialog)
        dialog.title(self._t("manual_title"))
        dialog.geometry("760x620")
        dialog.minsize(620, 480)
        dialog.transient(self.root)

        frame = ttk.Frame(dialog, style="Dialog.TFrame", padding=(14, 12))
        frame.pack(fill=tk.BOTH, expand=True)
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        ttk.Label(
            frame,
            text=self._t("manual_title"),
            style="CardHeader.TLabel",
            background=THEME["bg"],
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        text = tk.Text(
            frame,
            wrap=tk.WORD,
            height=24,
            relief=tk.SOLID,
            borderwidth=1,
            bg=THEME["card_bg"],
            fg=THEME["text_primary"],
            insertbackground=THEME["text_primary"],
            selectbackground=THEME["selection_fill"],
            selectforeground=THEME["text_primary"],
            font=(THEME["font_family"], THEME["font_size_base"]),
            padx=12,
            pady=10,
        )
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.grid(row=1, column=0, sticky="nsew")
        scrollbar.grid(row=1, column=1, sticky="ns")
        text.insert("1.0", self._t("manual_body"))
        text.configure(state=tk.DISABLED)

        ttk.Button(
            frame,
            text=self._t("element_pattern_cancel_button"),
            command=dialog.destroy,
            style="Large.TButton",
        ).grid(row=2, column=0, columnspan=2, sticky="e", pady=(10, 0))
        _apply_interactive_cursors(dialog)

    def _show_about_dialog(self) -> None:
        log_path = current_log_path()
        messagebox.showinfo(
            self._t("about_title"),
            self._t(
                "about_message",
                version=APP_VERSION,
                log_path=str(log_path) if log_path is not None else "N/A",
            ),
        )

    def _build_workspace_header(self, parent: tk.Widget) -> None:
        header = ttk.Frame(parent, style="Header.TFrame", padding=(10, 5, 10, 5))
        header.grid(row=1, column=0, columnspan=3, sticky="ew")
        header.grid_columnconfigure(0, weight=0)
        header.grid_columnconfigure(1, weight=1)

        title_group = ttk.Frame(header, style="Header.TFrame")
        title_group.grid(row=0, column=0, sticky="w", padx=(0, 12))
        title_group.grid_columnconfigure(0, weight=1)
        self.header_title_label = ttk.Label(
            title_group,
            text=self._t("app_name"),
            style="HeaderTitle.TLabel",
            anchor="w",
        )
        self.header_title_label.grid(row=0, column=0, sticky="ew")

        chip_row = ttk.Frame(header, style="Header.TFrame")
        chip_row.grid(row=0, column=1, sticky="w")
        chip_specs = (
            ("chip_frequency", self.header_frequency_text, 8),
            ("chip_dictionary", self.header_dictionary_text, 13),
            ("chip_pattern", self.header_pattern_text, 13),
            ("chip_virtual_channels", self.header_kpi_texts["chip_virtual_channels"], 11),
            ("chip_az_resolution", self.header_kpi_texts["chip_az_resolution"], 8),
            ("chip_el_resolution", self.header_kpi_texts["chip_el_resolution"], 8),
            ("chip_peak_margin", self.header_kpi_texts["chip_peak_margin"], 18),
        )
        for column, (label_key, value_var, value_width) in enumerate(chip_specs):
            self._build_header_chip(
                chip_row,
                column,
                label_key,
                value_var,
                value_width=value_width,
                compact=True,
            )

    def _build_header_chip(
        self,
        parent: ttk.Frame,
        column: int,
        label_key: str,
        value_var: tk.StringVar,
        *,
        value_width: int = 20,
        compact: bool = False,
    ) -> None:
        chip = ttk.Frame(
            parent,
            style="HeaderChip.TFrame",
            padding=(6, 3) if compact else (8, 5),
        )
        chip.grid(row=0, column=column, sticky="w", padx=(0 if column == 0 else 6, 0))
        label = ttk.Label(
            chip,
            text=self._t(label_key),
            style="HeaderChipName.TLabel",
            anchor="w",
        )
        label.grid(row=0, column=0, sticky="ew")
        ttk.Label(
            chip,
            textvariable=value_var,
            style="HeaderChipValue.TLabel",
            anchor="w",
            width=value_width,
        ).grid(row=1, column=0, sticky="ew", pady=(2, 0))
        self.header_chip_labels[label_key] = label

    def _refresh_workspace_header(self) -> None:
        if self.header_title_label is not None:
            self.header_title_label.configure(text=self._t("app_name"))
        for key, label in self.header_chip_labels.items():
            label.configure(text=self._t(key))

        self.header_frequency_text.set(
            f"{_format_frequency_ghz(self.current_frequency_ghz())} GHz"
        )
        self.header_dictionary_text.set(
            _dbf_dictionary_mode_label(self.dbf_dictionary.mode, self.language)
        )
        self.header_pattern_text.set(self.pattern_status.get())

    def _set_default_workspace_sash(self) -> None:
        if self.workspace_pane is None:
            return
        width = self.workspace_pane.winfo_width()
        if width <= 1:
            return
        plot_width = max(PLOT_COLUMN_MIN_WIDTH * 2, width // 2)
        if width - plot_width < EVAL_PANEL_MIN_WIDTH:
            plot_width = max(PLOT_COLUMN_MIN_WIDTH * 2, width - EVAL_PANEL_MIN_WIDTH)
        try:
            self.workspace_pane.sashpos(0, plot_width)
        except tk.TclError:
            return

    def _stabilize_default_workspace_sash(self) -> None:
        if self.workspace_pane is None:
            return
        try:
            self.root.update_idletasks()
        except tk.TclError:
            return
        self._set_default_workspace_sash()

    def _bind_keyboard_shortcuts(self) -> None:
        for sequence in ("<Control-z>", "<Control-Z>"):
            self.root.bind(sequence, self.undo_layout_change)
        for sequence in ("<Control-y>", "<Control-Y>", "<Control-Shift-Z>", "<Control-Shift-z>"):
            self.root.bind(sequence, self.redo_layout_change)
        self.root.bind("<Control-s>", self.on_save_shortcut)
        self.root.bind("<Control-S>", self.on_save_shortcut)
        self.root.bind("<Control-o>", self.on_import_shortcut)
        self.root.bind("<Control-O>", self.on_import_shortcut)
        self.root.bind("<Control-g>", self.on_refresh_shortcut)
        self.root.bind("<Control-G>", self.on_refresh_shortcut)
        self.root.bind("<Control-r>", self.on_refresh_shortcut)
        self.root.bind("<Control-R>", self.on_refresh_shortcut)
        self.root.bind("<Control-f>", self.on_focus_frequency_shortcut)
        self.root.bind("<Control-F>", self.on_focus_frequency_shortcut)
        self.root.bind("<Escape>", self.on_escape_key)

    def set_language(self, language: str) -> None:
        if language not in SUPPORTED_LANGUAGES:
            return
        self.language = language
        self.language_var.set(LANGUAGE_LABELS[language])
        self._refresh_language_texts()
        if hasattr(self, "phys_canvas"):
            self.generate_virtual_array()

    def _refresh_language_texts(self) -> None:
        self.root.title(self._t("app_title", version=APP_VERSION))
        self._refresh_app_menus()
        if getattr(self, "freq_toolbar_label", None) is not None:
            self.freq_toolbar_label.configure(text=self._t("freq_label"))
        if getattr(self, "margin_toolbar_label", None) is not None:
            self.margin_toolbar_label.configure(text=self._t("margin_label"))
        if getattr(self, "auto_toolbar_label", None) is not None:
            self.auto_toolbar_label.configure(text=self._t("auto_label"))
        if getattr(self, "auto_apply_button", None) is not None:
            self.auto_apply_button.configure(text=self._t("auto_apply"))
        for key, button in self.physical_action_buttons.items():
            button.configure(text=self._t(key))
        self._update_delete_button_state()
        for button, key in zip(
            self.physical_buttons,
            (
                "physical_add_tx",
                "physical_add_rx",
                "physical_delete",
                "physical_clear",
            ),
        ):
                button.label.set_text(self._t(key))
        if getattr(self, "eval_frame", None) is not None:
            if self.eval_notebook is not None:
                self.eval_notebook.tab(self.eval_summary_tab, text=self._t("eval_tab_overview"))
                self.eval_notebook.tab(self.dbf2d_frame, text=self._t("eval_tab_dbf2d"))
            self.overview_frame.configure(text=self._t("overview_title"))
            self.angle_eval_frame.configure(text=self._t("angle_eval_title"))
            for key, label in self.primary_name_labels.items():
                label.configure(text=self._t(key))
            for key, label in self.secondary_name_labels.items():
                label_key = getattr(self, "secondary_name_label_keys", {}).get(key, key)
                label.configure(text=self._t(label_key))
        self._update_dbf_scan_controls()
        self._update_dbf2d_controls()
        self._update_channel_pattern_status()
        self._refresh_workspace_header()

    def _build_response_chart(
        self,
        parent: tk.Widget,
        row: int,
        col: int,
        padding: tuple[int, int, int, int],
        mode: str,
    ) -> ResponseChart:
        """Create a response chart (Az or El) and embed it in the grid."""
        frame = ttk.Frame(parent, style="PlotPanel.TFrame", padding=padding)
        frame.grid(
            row=row,
            column=col,
            sticky="nsew",
            padx=(0, 5) if col == 0 else (5, 0),
            pady=(5, 0),
        )
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=0)
        frame.grid_columnconfigure(0, weight=1)

        fig = Figure(figsize=(RESPONSE_FIG_W, RESPONSE_FIG_H), dpi=FIG_DPI)
        fig.set_facecolor(THEME["card_bg"])
        ax = fig.add_subplot(111)
        ax.set_facecolor(THEME["plot_bg"])
        fig.subplots_adjust(top=0.82, left=0.13, right=0.97, bottom=0.18)
        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas_widget = canvas.get_tk_widget()
        _style_canvas_widget(canvas_widget)
        canvas_widget.grid(row=0, column=0, sticky="nsew")

        progress_frame = ttk.Frame(frame, style="ChartFooter.TFrame", padding=(6, 5))
        progress_frame.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        progress_frame.grid_columnconfigure(0, weight=1)

        control_row = ttk.Frame(progress_frame, style="ChartFooter.TFrame")
        control_row.grid(row=0, column=0, sticky="ew")
        control_row.grid_columnconfigure(0, weight=1)
        progress_label = ttk.Label(
            control_row,
            text=f"{_dbf_short_label(mode, self.language)} {_format_dbf_angle_label(0.0, self.language)}",
            style="ChartFooter.TLabel",
            anchor="w",
        )
        progress_label.grid(row=0, column=0, sticky="ew")
        play_button = ttk.Button(
            control_row,
            text=self._t("dbf_play_compact"),
            command=(
                self.toggle_az_dbf_animation
                if mode == "azimuth"
                else self.toggle_el_dbf_animation
            ),
            style="CompactPlay.TButton",
            width=6,
        )
        play_button.grid(row=0, column=1, sticky="e", padx=(8, 5))
        stop_button = ttk.Button(
            control_row,
            text=self._t("dbf_stop_compact"),
            command=self.stop_dbf_scan_animation,
            style="CompactStop.TButton",
            width=6,
        )
        stop_button.grid(row=0, column=2, sticky="e")
        stop_button.configure(state=tk.DISABLED)
        return ResponseChart(
            fig=fig,
            ax=ax,
            canvas=canvas,
            progress_label=progress_label,
            play_button=play_button,
            stop_button=stop_button,
        )

    def _build_physical_toolbar(self, parent: ttk.Frame) -> None:
        toolbar = ttk.Frame(parent, style="Card.TFrame", padding=(0, 0, 0, 6))
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.grid_columnconfigure(4, weight=1)

        button_specs = (
            ("physical_add_tx", self.add_tx_element, "Compact.TButton"),
            ("physical_add_rx", self.add_rx_element, "Compact.TButton"),
            ("physical_delete", self.toggle_delete_mode, "Compact.TButton"),
            ("physical_clear", self.clear_array_layout, "CompactStop.TButton"),
        )
        for column, (key, command, style_name) in enumerate(button_specs):
            button = ttk.Button(
                toolbar,
                text=self._t(key),
                command=command,
                style=style_name,
                width=8,
            )
            button.grid(row=0, column=column, sticky="w", padx=(0 if column == 0 else 6, 0))
            self.physical_action_buttons[key] = button

    def _update_delete_button_state(self) -> None:
        button = self.physical_action_buttons.get("physical_delete")
        if button is None:
            return
        button.configure(
            style="CompactDanger.TButton" if self.delete_mode else "Compact.TButton"
        )

    def _build_figure_buttons(
        self,
        fig: Figure,
        button_specs: tuple[tuple[str, list[float], callable], ...],
        buttons_list: list[MplButton],
        callbacks_list: list[int],
    ) -> None:
        """Add MplButton widgets to *fig* from *button_specs*."""
        for label, rect, callback in button_specs:
            button_ax = fig.add_axes(rect)
            button_ax.set_facecolor(THEME["mpl_btn_bg"])
            for spine in button_ax.spines.values():
                spine.set_edgecolor(THEME["mpl_btn_border"])
                spine.set_linewidth(0.8)
            button = MplButton(
                button_ax, label,
                color=THEME["mpl_btn_bg"],
                hovercolor=THEME["mpl_btn_hover"],
            )
            button.label.set_fontsize(8.5)
            button.label.set_color(THEME["mpl_btn_text"])
            button.label.set_fontweight("bold")
            button.label.set_horizontalalignment("center")
            button.label.set_verticalalignment("center")
            cid = button.on_clicked(lambda _event, action=callback: action())
            buttons_list.append(button)
            callbacks_list.append(cid)

    # ── Tkinter Evaluation Panel ──────────────────────────────────────

    def _build_primary_metric_tile(
        self,
        parent: ttk.Frame,
        key: str,
        row: int,
        column: int,
    ) -> None:
        tile = ttk.Frame(parent, style="Metric.TFrame", padding=(7, 5))
        tile.grid(
            row=row,
            column=column,
            sticky="nsew",
            padx=(0 if column == 0 else 4, 0 if column == 1 else 4),
            pady=(0, 6),
        )
        tile.grid_columnconfigure(0, weight=1)
        name_label = ttk.Label(
            tile,
            text=self._t(key),
            style="MetricName.TLabel",
            anchor="w",
            justify=tk.LEFT,
            wraplength=142,
        )
        name_label.grid(row=0, column=0, sticky="ew")
        value_label = ttk.Label(
            tile,
            text="",
            style="MetricValue.TLabel",
            anchor="w",
            justify=tk.LEFT,
            wraplength=142,
        )
        value_label.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        self.primary_name_labels[key] = name_label
        self.primary_value_labels[key] = value_label

    def _build_angle_metric_group(
        self,
        parent: ttk.Frame,
        axis_key: str,
        metric_specs: tuple[tuple[str, str], ...],
        column: int,
    ) -> None:
        group = ttk.Frame(parent, style="Metric.TFrame", padding=(7, 5))
        group.grid(
            row=0,
            column=column,
            sticky="nsew",
            padx=(0 if column == 0 else 4, 0 if column == 1 else 4),
        )
        group.grid_columnconfigure(0, weight=0, minsize=72)
        group.grid_columnconfigure(1, weight=1, minsize=150)
        title = ttk.Label(
            group,
            text=self._t(axis_key),
            style="MetricSection.TLabel",
            anchor="w",
        )
        title.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 3))
        self.secondary_name_labels[f"{axis_key}_section"] = title
        self.secondary_name_label_keys[f"{axis_key}_section"] = axis_key

        for row, (metric_key, label_key) in enumerate(metric_specs, start=1):
            name_label = ttk.Label(
                group,
                text=self._t(label_key),
                style="MetricName.TLabel",
                anchor="w",
                justify=tk.LEFT,
                wraplength=0,
            )
            name_label.grid(row=row, column=0, sticky="w", pady=(0, 1), padx=(0, 8))
            value_label = ttk.Label(
                group,
                text="",
                style="MetricValue.TLabel",
                anchor="e",
                justify=tk.RIGHT,
                wraplength=260,
            )
            value_label.grid(row=row, column=1, sticky="ew", pady=(0, 1))
            self.secondary_name_labels[metric_key] = name_label
            self.secondary_name_label_keys[metric_key] = label_key
            self.secondary_value_labels[metric_key] = value_label

    def _build_evaluation_panel(self, parent: ttk.Frame) -> None:
        """Build the Array Evaluation card using Tkinter native widgets."""
        self.eval_frame = ttk.Frame(parent, style="Card.TFrame", padding=(8, 6))
        self.eval_frame.grid(row=0, column=0, sticky="nsew")
        self.eval_frame.grid_rowconfigure(0, weight=1)
        self.eval_frame.grid_columnconfigure(0, weight=1)

        self.eval_notebook = ttk.Notebook(self.eval_frame, style="Eval.TNotebook")
        self.eval_notebook.grid(row=0, column=0, sticky="nsew")

        self.eval_summary_tab = ttk.Frame(
            self.eval_notebook,
            style="Card.TFrame",
            padding=(7, 8),
        )
        self.eval_summary_tab.grid_columnconfigure(0, weight=1)
        self.eval_notebook.add(self.eval_summary_tab, text=self._t("eval_tab_overview"))

        # PRIMARY section
        self.overview_frame = ttk.LabelFrame(
            self.eval_summary_tab,
            text=self._t("overview_title"),
            padding=(7, 6),
            style="TLabelframe",
        )
        self.overview_frame.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        for column in range(2):
            self.overview_frame.grid_columnconfigure(column, weight=1, uniform="overview_metrics")

        self.primary_name_labels: dict[str, ttk.Label] = {}
        self.secondary_name_labels: dict[str, ttk.Label] = {}
        self.secondary_name_label_keys: dict[str, str] = {}
        self.primary_value_labels: dict[str, ttk.Label] = {}
        self.secondary_value_labels: dict[str, ttk.Label] = {}

        for i, key in enumerate(PRIMARY_EVAL_ROWS):
            row = i // 2
            column = i % 2
            self._build_primary_metric_tile(self.overview_frame, key, row, column)

        # SECONDARY section
        self.angle_eval_frame = ttk.LabelFrame(
            self.eval_summary_tab,
            text=self._t("angle_eval_title"),
            padding=(7, 6),
            style="TLabelframe",
        )
        self.angle_eval_frame.grid(row=1, column=0, sticky="ew")
        for column in range(2):
            self.angle_eval_frame.grid_columnconfigure(column, weight=1, uniform="angle_metrics")

        for column, (axis_key, metric_specs) in enumerate(ANGLE_EVAL_GROUPS):
            self._build_angle_metric_group(
                self.angle_eval_frame,
                axis_key,
                metric_specs,
                column,
            )

        self._build_dbf2d_panel()
        if self.eval_notebook is not None and self.dbf2d_frame is not None:
            self.eval_notebook.select(self.dbf2d_frame)

    def _build_dbf2d_panel(self) -> None:
        if self.eval_notebook is None:
            return
        self.dbf2d_frame = ttk.Frame(
            self.eval_notebook,
            style="Card.TFrame",
            padding=(8, 8),
        )
        self.eval_notebook.add(self.dbf2d_frame, text=self._t("eval_tab_dbf2d"))
        self.dbf2d_frame.grid_columnconfigure(0, weight=1)
        self.dbf2d_frame.grid_rowconfigure(0, weight=1)

        self.dbf2d_fig = Figure(figsize=(DBF2D_FIG_SIZE, DBF2D_FIG_SIZE), dpi=FIG_DPI)
        self.dbf2d_fig.set_facecolor(THEME["card_bg"])
        self.dbf2d_ax = self.dbf2d_fig.add_axes([0.11, 0.12, 0.70, 0.78])
        self.dbf2d_cbar_ax = self.dbf2d_fig.add_axes([0.87, 0.18, 0.035, 0.64])
        self.dbf2d_ax.set_facecolor(THEME["plot_bg"])
        self.dbf2d_canvas = FigureCanvasTkAgg(self.dbf2d_fig, master=self.dbf2d_frame)
        dbf2d_widget = self.dbf2d_canvas.get_tk_widget()
        _style_canvas_widget(dbf2d_widget)
        dbf2d_widget.configure(width=DBF2D_CANVAS_SIZE, height=DBF2D_CANVAS_SIZE)
        dbf2d_widget.grid(row=0, column=0, sticky="nsew")

        button_row = ttk.Frame(self.dbf2d_frame, style="Card.TFrame")
        button_row.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        for column in range(3):
            button_row.grid_columnconfigure(column, weight=1, uniform="dbf2d_buttons")
        self.dbf2d_az_button = ttk.Button(
            button_row,
            text=self._t("dbf2d_play_az"),
            command=lambda: self.toggle_dbf2d_animation("azimuth"),
            style="CompactPlay.TButton",
            width=8,
        )
        self.dbf2d_az_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.dbf2d_el_button = ttk.Button(
            button_row,
            text=self._t("dbf2d_play_el"),
            command=lambda: self.toggle_dbf2d_animation("elevation"),
            style="CompactPlay.TButton",
            width=8,
        )
        self.dbf2d_el_button.grid(row=0, column=1, sticky="ew", padx=4)
        self.dbf2d_stop_button = ttk.Button(
            button_row,
            text=self._t("dbf2d_stop"),
            command=self.stop_dbf2d_animation,
            style="CompactStop.TButton",
            width=7,
        )
        self.dbf2d_stop_button.grid(row=0, column=2, sticky="ew", padx=(4, 0))
        self.dbf2d_stop_button.configure(state=tk.DISABLED)

        self.dbf2d_status_label = ttk.Label(
            self.dbf2d_frame,
            text="",
            style="Card.TLabel",
            font=(THEME["font_family_mono"], THEME["font_size_sm"]),
            anchor="center",
        )
        self.dbf2d_status_label.grid(row=2, column=0, sticky="ew", pady=(4, 0))

    def _metric_value_style(self, key: str, value: str) -> str:
        if value in {"不可用"}:
            return "MetricValueRisk.TLabel"
        if value == "N/A":
            return "MetricValue.TLabel"
        if key == "row_virtual_channels":
            return "MetricValueGood.TLabel" if "(100%)" in value else "MetricValueWarn.TLabel"
        if key.endswith("_margin"):
            if value == "无竞争峰":
                return "MetricValueGood.TLabel"
            match = re.match(r"^\s*(-?\d+(?:\.\d+)?)", value)
            if match is not None:
                margin = float(match.group(1))
                return (
                    "MetricValueGood.TLabel"
                    if margin >= max(self.current_margin_db(), 0.5)
                    else "MetricValueWarn.TLabel"
                )
        if key.endswith("_cut"):
            if value in {"正常", "到达数据边界"}:
                return "MetricValueGood.TLabel"
            if "谱不可靠" in value or "竞争峰模糊" in value or "不可用" in value:
                return "MetricValueRisk.TLabel"
            return "MetricValueWarn.TLabel"
        return "MetricValue.TLabel"

    def _update_evaluation_panel(self, metrics: ArrayMetrics) -> None:
        """Update the Tkinter evaluation panel with current metrics."""
        utilization = (
            metrics.unique_count / metrics.virtual_count if metrics.virtual_count else 0.0
        )
        az_dbf_metrics = self._dbf_angle_metrics_for_mode("azimuth")
        el_dbf_metrics = self._dbf_angle_metrics_for_mode("elevation")

        # PRIMARY values
        values = {
            "row_channel_count": f"{metrics.tx_count}T × {metrics.rx_count}R",
            "row_virtual_channels": f"{metrics.unique_count}/{metrics.virtual_count} ({utilization:.0%})",
            "row_az_aperture": _format_mm(self.aperture_mm(metrics.x_aperture)),
            "row_el_aperture": _format_mm(self.aperture_mm(metrics.y_aperture)),
            "row_az_resolution": _format_float(metrics.azimuth_resolution, "°"),
            "row_el_resolution": _format_float(metrics.elevation_resolution, "°"),
        }
        for key, val in values.items():
            if key in self.primary_value_labels:
                self.primary_value_labels[key].configure(
                    text=val,
                    style=self._metric_value_style(key, val),
                )

        # SECONDARY values
        sec_values = {
            "row_az_no_fold": _format_angle_range(az_dbf_metrics),
            "row_az_no_fold_error": _format_axis_angle_metrics(az_dbf_metrics, "no_fold_error"),
            "row_az_margin": _format_axis_angle_metrics(az_dbf_metrics, "margin"),
            "row_az_cut": _angle_cut_reason_summary(az_dbf_metrics),
            "row_el_no_fold": _format_angle_range(el_dbf_metrics),
            "row_el_no_fold_error": _format_axis_angle_metrics(el_dbf_metrics, "no_fold_error"),
            "row_el_margin": _format_axis_angle_metrics(el_dbf_metrics, "margin"),
            "row_el_cut": _angle_cut_reason_summary(el_dbf_metrics),
        }
        for key, val in sec_values.items():
            if key in self.secondary_value_labels:
                self.secondary_value_labels[key].configure(
                    text=val,
                    style=self._metric_value_style(key, val),
                )

        self.header_kpi_texts["chip_virtual_channels"].set(values["row_virtual_channels"])
        self.header_kpi_texts["chip_az_resolution"].set(values["row_az_resolution"])
        self.header_kpi_texts["chip_el_resolution"].set(values["row_el_resolution"])
        self.header_kpi_texts["chip_peak_margin"].set(
            f"{self._t('az_short')} {sec_values['row_az_margin']} / "
            f"{self._t('el_short')} {sec_values['row_el_margin']}"
        )

    # ── Array data ────────────────────────────────────────────────────

    def _set_frequency_ghz(self, frequency: float) -> None:
        self.last_valid_frequency_ghz = frequency
        self.frequency_ghz.set(_format_frequency_ghz(frequency))

    def _normalize_frequency_input(self) -> tuple[float, bool]:
        frequency = _parse_frequency_ghz(self.frequency_ghz.get())
        if frequency is None:
            fallback = self.last_valid_frequency_ghz
            self.frequency_ghz.set(_format_frequency_ghz(fallback))
            return fallback, False
        self._set_frequency_ghz(frequency)
        return frequency, True

    def current_frequency_ghz(self) -> float:
        frequency = _parse_frequency_ghz(self.frequency_ghz.get())
        return frequency if frequency is not None else self.last_valid_frequency_ghz

    def _set_margin_db(self, margin: float) -> None:
        self.last_valid_margin_db = margin
        self.margin_db.set(_format_margin_db(margin))

    def _normalize_margin_input(self) -> tuple[float, bool]:
        margin = _parse_margin_db(self.margin_db.get())
        if margin is None:
            fallback = self.last_valid_margin_db
            self.margin_db.set(_format_margin_db(fallback))
            return fallback, False
        self._set_margin_db(margin)
        return margin, True

    def current_margin_db(self) -> float:
        margin = _parse_margin_db(self.margin_db.get())
        return margin if margin is not None else self.last_valid_margin_db

    def wavelength_mm(self) -> float:
        return LIGHT_SPEED_MM_PER_NS / self.current_frequency_ghz()

    def half_wavelength_mm(self) -> float:
        return self.wavelength_mm() / 2.0

    def aperture_mm(self, aperture_half_lambda: float) -> float:
        return aperture_half_lambda * self.half_wavelength_mm()

    def _build_elements(self) -> list[EditableElement]:
        return _starter_layout_elements()

    def current_array(self) -> AntennaArray:
        tx = [
            ArrayPoint(name=element.name, x=element.x, y=element.y)
            for element in self.elements
            if element.kind == "tx"
        ]
        rx = [
            ArrayPoint(name=element.name, x=element.x, y=element.y)
            for element in self.elements
            if element.kind == "rx"
        ]
        return AntennaArray(tx=tx, rx=rx)

    def _elements_of_kind(self, kind: str) -> list[EditableElement]:
        return [element for element in self.elements if element.kind == kind]

    def _sync_auto_count_inputs(self) -> None:
        auto_tx_count = getattr(self, "auto_tx_count", None)
        auto_rx_count = getattr(self, "auto_rx_count", None)
        if auto_tx_count is not None:
            auto_tx_count.set(str(len(self._elements_of_kind("tx"))))
        if auto_rx_count is not None:
            auto_rx_count.set(str(len(self._elements_of_kind("rx"))))

    def _renumber_elements(self) -> None:
        selected = self.selected_element
        renumbered: list[EditableElement] = []
        for kind in ("tx", "rx"):
            prefix = _element_prefix(kind)
            sorted_elements = sorted(
                self._elements_of_kind(kind),
                key=lambda element: (element.x, element.y, element.index),
            )
            for index, element in enumerate(sorted_elements):
                element.index = index
                element.name = f"{prefix}{index + 1}"
                renumbered.append(element)
        self.elements = renumbered
        if any(element is selected for element in self.elements):
            self.selected_element = selected
        else:
            self.selected_element = None

    def _clear_interaction_state(self) -> None:
        self.delete_mode = False
        self.selected_element = None
        self.dragging = None
        self.drag_bounds = None
        self.drag_axis_limits = None
        self.drag_start_snapshot = None
        self._sync_auto_count_inputs()
        self._update_delete_button_state()

    def _layout_snapshot_for(
        self,
        elements: list[EditableElement],
        selected_element: EditableElement | None,
    ) -> LayoutSnapshot:
        selected_key = (
            (selected_element.kind, selected_element.index, selected_element.name)
            if selected_element is not None
            else None
        )
        return LayoutSnapshot(
            elements=tuple(
                (
                    element.kind,
                    int(element.index),
                    element.name,
                    round(float(element.x), ROUND_DECIMALS),
                    round(float(element.y), ROUND_DECIMALS),
                )
                for element in elements
            ),
            selected_key=selected_key,
        )

    def _capture_layout_snapshot(self) -> LayoutSnapshot:
        return self._layout_snapshot_for(self.elements, self.selected_element)

    def _push_undo_snapshot(self, snapshot: LayoutSnapshot | None = None) -> None:
        snapshot = snapshot if snapshot is not None else self._capture_layout_snapshot()
        if not self.undo_stack or self.undo_stack[-1] != snapshot:
            self.undo_stack.append(snapshot)
        self.redo_stack.clear()

    def _restore_layout_snapshot(self, snapshot: LayoutSnapshot) -> None:
        self.elements = [
            EditableElement(kind=kind, index=index, name=name, x=x, y=y)
            for kind, index, name, x, y in snapshot.elements
        ]
        self.selected_element = None
        if snapshot.selected_key is not None:
            for element in self.elements:
                key = (element.kind, element.index, element.name)
                if key == snapshot.selected_key:
                    self.selected_element = element
                    break
        self.dragging = None
        self.drag_bounds = None
        self.drag_axis_limits = None
        self.drag_start_snapshot = None

    def undo_layout_change(self, event=None) -> str | None:  # noqa: ANN001
        if event is not None and _event_widget_is_text_input(event):
            return None

        current_snapshot = self._capture_layout_snapshot()
        while self.undo_stack and self.undo_stack[-1] == current_snapshot:
            self.undo_stack.pop()
        if not self.undo_stack:
            self.status.set(self._t("undo_empty"))
            return "break"

        previous_snapshot = self.undo_stack.pop()
        self.redo_stack.append(current_snapshot)
        self._restore_layout_snapshot(previous_snapshot)
        self.generate_virtual_array()
        self.status.set(self._t("undo_done"))
        return "break"

    def redo_layout_change(self, event=None) -> str | None:  # noqa: ANN001
        if event is not None and _event_widget_is_text_input(event):
            return None

        current_snapshot = self._capture_layout_snapshot()
        while self.redo_stack and self.redo_stack[-1] == current_snapshot:
            self.redo_stack.pop()
        if not self.redo_stack:
            self.status.set(self._t("redo_empty"))
            return "break"

        next_snapshot = self.redo_stack.pop()
        if not self.undo_stack or self.undo_stack[-1] != current_snapshot:
            self.undo_stack.append(current_snapshot)
        self._restore_layout_snapshot(next_snapshot)
        self.generate_virtual_array()
        self.status.set(self._t("redo_done"))
        return "break"

    def _next_element_position(self, kind: str) -> tuple[float, float]:
        same_kind = self._elements_of_kind(kind)
        if not same_kind:
            return (0.0, 0.0 if kind == "tx" else -10.0)

        anchor = (
            self.selected_element
            if self.selected_element is not None and self.selected_element.kind == kind
            else max(same_kind, key=lambda element: (element.x, element.y))
        )
        occupied = {(element.x, element.y) for element in self.elements}
        x = snap_to_grid(anchor.x + 2 * GRID_STEP)
        y = snap_to_grid(anchor.y)
        while (x, y) in occupied:
            x = snap_to_grid(x + 2 * GRID_STEP)
        return x, y

    def add_tx_element(self) -> None:
        self._add_element("tx")

    def add_rx_element(self) -> None:
        self._add_element("rx")

    def _add_element(self, kind: str) -> None:
        current_count = len(self._elements_of_kind(kind))
        max_count = _max_elements_for_kind(kind)
        prefix = _element_prefix(kind)
        if current_count >= max_count:
            self.status.set(self._t("limit_reached", prefix=prefix, max_count=max_count))
            messagebox.showinfo(
                self._t("antenna_limit_title"),
                self._t("count_limit_detail", prefix=prefix, max_count=max_count),
            )
            return

        self._push_undo_snapshot()
        x, y = self._next_element_position(kind)
        element = EditableElement(
            kind=kind,
            index=current_count,
            name=f"{prefix}{current_count + 1}",
            x=x,
            y=y,
        )
        self.elements.append(element)
        self.selected_element = element
        self._renumber_elements()
        self.delete_mode = False
        self.dragging = None
        self.drag_bounds = None
        self.drag_axis_limits = None
        self.drag_start_snapshot = None
        self._sync_auto_count_inputs()
        self._update_delete_button_state()
        self.generate_virtual_array()
        self.status.set(
            self._t(
                "added_element",
                element=element.name,
                x=element.x * DISPLAY_SCALE_LAMBDA,
                y=element.y * DISPLAY_SCALE_LAMBDA,
            )
        )

    def _build_physical_figure_controls(self) -> None:
        self._build_figure_buttons(
            self.phys_fig,
            (
                (self._t("physical_add_tx"), [0.55, 0.91, 0.07, 0.055], self.add_tx_element),
                (self._t("physical_add_rx"), [0.625, 0.91, 0.07, 0.055], self.add_rx_element),
                (self._t("physical_delete"), [0.70, 0.91, 0.105, 0.055], self.toggle_delete_mode),
                (self._t("physical_clear"), [0.81, 0.91, 0.105, 0.055], self.clear_array_layout),
            ),
            self.physical_buttons,
            self.physical_button_callbacks,
        )

    def toggle_delete_mode(self, _event=None) -> None:  # noqa: ANN001
        self.delete_mode = not self.delete_mode
        self.dragging = None
        self.drag_bounds = None
        self.drag_axis_limits = None
        self.drag_start_snapshot = None
        if self.delete_mode:
            self.status.set(self._t("delete_mode_on"))
        else:
            self.status.set(self._t("delete_mode_off"))
        self._update_delete_button_state()

    def clear_array_layout(self, _event=None) -> None:  # noqa: ANN001
        new_elements = _starter_layout_elements()
        if self._layout_snapshot_for(new_elements, None) == self._capture_layout_snapshot():
            self.status.set(self._t("layout_already_clear"))
            return
        self._push_undo_snapshot()
        self.elements = new_elements
        self._clear_interaction_state()
        self._sync_auto_count_inputs()
        self.generate_virtual_array()
        self.status.set(self._t("layout_cleared"))

    def apply_auto_array_layout(self, _event=None) -> str:  # noqa: ANN001
        try:
            tx_count = _validate_element_count(self.auto_tx_count.get(), "tx")
            rx_count = _validate_element_count(self.auto_rx_count.get(), "rx")
        except ValueError as exc:
            self.status.set(str(exc))
            messagebox.showinfo(self._t("auto_layout_title"), str(exc))
            return "break"

        new_elements = _build_auto_layout_elements(tx_count, rx_count)
        if self._layout_snapshot_for(new_elements, None) == self._capture_layout_snapshot():
            self.status.set(self._t("auto_layout_already", tx=tx_count, rx=rx_count))
            return "break"

        self._push_undo_snapshot()
        self.elements = new_elements
        self._clear_interaction_state()
        self._sync_auto_count_inputs()
        self.generate_virtual_array()
        self.status.set(self._t("auto_layout_done", tx=tx_count, rx=rx_count))
        return "break"

    def delete_selected_element(self) -> None:
        if self.selected_element is None:
            self.toggle_delete_mode()
            return

        self._delete_element(self.selected_element)

    def _delete_element(self, element: EditableElement) -> bool:
        same_kind_count = len(self._elements_of_kind(element.kind))
        if same_kind_count <= 1:
            prefix = _element_prefix(element.kind)
            self.status.set(self._t("delete_last", prefix=prefix))
            messagebox.showinfo(
                self._t("antenna_limit_title"),
                self._t("delete_last_detail", prefix=prefix),
            )
            return False

        deleted_name = element.name
        self._push_undo_snapshot()
        self.elements = [candidate for candidate in self.elements if candidate is not element]
        self.selected_element = None
        self.dragging = None
        self.drag_bounds = None
        self.drag_axis_limits = None
        self.drag_start_snapshot = None
        self._renumber_elements()
        self._sync_auto_count_inputs()
        self.generate_virtual_array()
        mode_suffix = self._t("delete_mode_suffix") if self.delete_mode else ""
        self.status.set(self._t("deleted_element", element=deleted_name, suffix=mode_suffix))
        return True

    # ── Button handlers ───────────────────────────────────────────────

    def on_frequency_changed(self, _event=None) -> str:  # noqa: ANN001
        frequency, is_valid = self._normalize_frequency_input()
        self.generate_virtual_array()
        if is_valid:
            self.status.set(
                self._t("frequency_set", frequency=_format_frequency_ghz(frequency))
            )
        else:
            self.status.set(
                self._t("frequency_invalid", frequency=_format_frequency_ghz(frequency))
            )
        return "break"

    def on_margin_changed(self, _event=None) -> str:  # noqa: ANN001
        margin, is_valid = self._normalize_margin_input()
        self.generate_virtual_array()
        if is_valid:
            self.status.set(self._t("margin_set", value=_format_margin_db(margin)))
        else:
            self.status.set(self._t("margin_invalid", value=_format_margin_db(margin)))
        return "break"

    def on_save_shortcut(self, _event=None) -> str:  # noqa: ANN001
        self.export_layout_config()
        return "break"

    def on_import_shortcut(self, _event=None) -> str:  # noqa: ANN001
        self.import_layout_config()
        return "break"

    def on_refresh_shortcut(self, _event=None) -> str:  # noqa: ANN001
        _frequency, is_valid = self._normalize_frequency_input()
        self.generate_virtual_array()
        self.status.set(self._t("refreshed") if is_valid else self._t("refresh_invalid"))
        return "break"

    def on_focus_frequency_shortcut(self, _event=None) -> str:  # noqa: ANN001
        if self.frequency_entry is not None:
            self.frequency_entry.focus_set()
            self.frequency_entry.selection_range(0, tk.END)
        return "break"

    def on_escape_key(self, _event=None) -> str:  # noqa: ANN001
        if self.delete_mode:
            self.delete_mode = False
            self.status.set(self._t("delete_mode_off"))
            self._update_delete_button_state()
            return "break"

        if self.dragging is not None and self.drag_start_snapshot is not None:
            self._restore_layout_snapshot(self.drag_start_snapshot)
            self.generate_virtual_array()
            self.status.set(self._t("drag_cancel"))
            return "break"

        self.dragging = None
        self.drag_bounds = None
        self.drag_axis_limits = None
        self.drag_start_snapshot = None
        if self.selected_element is None:
            self.status.set(self._t("no_selection"))
            return "break"
        self.selected_element = None
        self._draw_physical_array()
        self.phys_canvas.draw_idle()
        self.status.set(self._t("selection_cleared"))
        return "break"

    def _event_dbf_angle(self, event, chart: ResponseChart) -> float | None:  # noqa: ANN001
        if event.xdata is not None:
            return float(event.xdata)
        if event.x is None or event.y is None:
            return None
        try:
            angle, _gain = chart.ax.transData.inverted().transform((event.x, event.y))
        except (TypeError, ValueError):
            return None
        return float(angle)

    def _set_chart_cursor(self, chart: ResponseChart, cursor: str) -> None:
        if chart.canvas is None or not hasattr(chart.canvas, "get_tk_widget"):
            return
        try:
            chart.canvas.get_tk_widget().configure(cursor=cursor)
        except (tk.TclError, AttributeError):
            return

    def _response_event_near_true_line(self, event, chart: ResponseChart) -> bool:  # noqa: ANN001
        if event.inaxes != chart.ax or event.xdata is None or chart.true_angle is None:
            return False
        x_low, x_high = chart.ax.get_xlim()
        tolerance = max(2.0, abs(x_high - x_low) * 0.015)
        return abs(float(event.xdata) - float(chart.true_angle)) <= tolerance

    def _update_response_cursor(self, event, chart: ResponseChart) -> None:  # noqa: ANN001
        self._set_chart_cursor(
            chart,
            "hand2" if self._response_event_near_true_line(event, chart) else "",
        )

    def _on_response_figure_leave(self, chart: ResponseChart) -> None:
        self._hide_response_hover(chart)
        self._set_chart_cursor(chart, "")

    def _set_dbf_scan_frame(self, mode: str, frame: int) -> None:
        frame = max(0, min(DBF_SCAN_GRID_SIZE - 1, int(frame)))

        if self.dbf_scan_after_id is not None:
            try:
                self.root.after_cancel(self.dbf_scan_after_id)
            except tk.TclError:
                pass
            self.dbf_scan_after_id = None

        if (
            self.dbf_scan_mode != mode
            or self.dbf_true_angles.size == 0
            or self.dbf_scan_angles.size == 0
            or self.dbf_spectra_db.size == 0
        ):
            self._normalize_frequency_input()
            self._load_dbf_spectra(mode)

        self.dbf_scan_frame = min(frame, len(self.dbf_true_angles) - 1)
        self.dbf_scan_active = True
        self.dbf_scan_paused = True
        self._draw_dbf_scan_frame()
        self._update_dbf_scan_controls()
        language = getattr(self, "language", LANGUAGE_ZH)
        label = _dbf_mode_label(mode, language)
        true_angle = self._current_dbf_true_angle()
        self.status.set(self._t("dbf_pause_status", mode=label, angle=true_angle))

    def _set_dbf_scan_angle(self, mode: str, angle: float) -> None:
        self._set_dbf_scan_frame(mode, _dbf_frame_index_for_angle(angle))

    def on_dbf_true_line_press(self, event, mode: str) -> None:  # noqa: ANN001
        chart = self._chart_for_dbf_mode(mode)
        if event.button != 1 or event.inaxes != chart.ax:
            return
        if not self._response_event_near_true_line(event, chart):
            return
        angle = self._event_dbf_angle(event, chart)
        if angle is None:
            return
        self.dbf_drag_mode = mode
        self._set_chart_cursor(chart, "hand2")
        self._hide_response_hover(chart)
        self._set_dbf_scan_angle(mode, angle)

    def _drag_dbf_true_line(self, event) -> None:  # noqa: ANN001
        mode = self.dbf_drag_mode
        if mode is None:
            return
        chart = self._chart_for_dbf_mode(mode)
        angle = self._event_dbf_angle(event, chart)
        if angle is None:
            return
        self._set_dbf_scan_angle(mode, angle)

    def on_dbf_true_line_release(self, event, mode: str) -> None:  # noqa: ANN001
        if self.dbf_drag_mode != mode:
            return
        self._drag_dbf_true_line(event)
        self.dbf_drag_mode = None
        chart = self._chart_for_dbf_mode(mode)
        self._update_response_cursor(event, chart)

    def toggle_az_dbf_animation(self, _event=None) -> None:  # noqa: ANN001
        self.toggle_dbf_scan_animation("azimuth")

    def toggle_el_dbf_animation(self, _event=None) -> None:  # noqa: ANN001
        self.toggle_dbf_scan_animation("elevation")

    def toggle_dbf_scan_animation(self, mode: str = "azimuth") -> None:
        if self.dbf_scan_active and self.dbf_scan_mode == mode:
            if self.dbf_scan_paused:
                self.resume_dbf_scan_animation()
            else:
                self.pause_dbf_scan_animation()
            return
        self.start_dbf_scan_animation(mode)

    def start_dbf_scan_animation(self, mode: str = "azimuth") -> None:
        self.stop_dbf_scan_animation(restore_response=True)
        _frequency, is_valid = self._normalize_frequency_input()
        self._load_dbf_spectra(mode)
        self.dbf_scan_frame = 0
        self.dbf_scan_active = True
        self.dbf_scan_paused = False
        self._update_dbf_scan_controls()
        self._draw_dbf_scan_frame()
        self._schedule_dbf_scan_frame()
        language = getattr(self, "language", LANGUAGE_ZH)
        label = _dbf_mode_label(mode, language)
        self.status.set(
            self._t("dbf_play_status", mode=label)
            if is_valid
            else self._t("dbf_play_status_invalid", mode=label)
        )

    def _dbf_spectrum_bank_for_mode(self, mode: str):
        if mode == "azimuth":
            return dbf_azimuth_spectrum_bank
        if mode == "elevation":
            return dbf_elevation_spectrum_bank
        raise ValueError(f"Unknown DBF animation mode: {mode!r}")

    def _dbf_angle_metrics_for_mode(self, mode: str) -> DbfAngleMetrics | None:
        try:
            spectrum_bank = self._dbf_spectrum_bank_for_mode(mode)
            true_angles, scan_angles, spectra_db = spectrum_bank(
                self.current_array(),
                tx_pattern=self.element_pattern,
                rx_pattern=self.element_pattern,
                channel_patterns=self.channel_patterns,
                dbf_dictionary=self.dbf_dictionary,
            )
            return dbf_angle_metrics_from_spectra(
                true_angles,
                scan_angles,
                spectra_db,
                ambiguity_margin_db=self.current_margin_db(),
            )
        except Exception:
            LOGGER.exception("Failed to calculate %s DBF angle metrics", mode)
            return None

    def _load_dbf_spectra(self, mode: str) -> None:
        spectrum_bank = self._dbf_spectrum_bank_for_mode(mode)
        self.dbf_true_angles, self.dbf_scan_angles, self.dbf_spectra_db = (
            spectrum_bank(
                self.current_array(),
                tx_pattern=self.element_pattern,
                rx_pattern=self.element_pattern,
                channel_patterns=self.channel_patterns,
                dbf_dictionary=self.dbf_dictionary,
            )
        )
        self.dbf_scan_mode = mode

    def pause_dbf_scan_animation(self) -> None:
        if not self.dbf_scan_active or self.dbf_scan_paused:
            return
        if self.dbf_scan_after_id is not None:
            try:
                self.root.after_cancel(self.dbf_scan_after_id)
            except tk.TclError:
                pass
        self.dbf_scan_after_id = None
        self.dbf_scan_paused = True
        self._update_dbf_scan_controls()
        language = getattr(self, "language", LANGUAGE_ZH)
        label = _dbf_mode_label(self.dbf_scan_mode, language)
        true_angle = self._current_dbf_true_angle()
        self.status.set(self._t("dbf_pause_status", mode=label, angle=true_angle))

    def resume_dbf_scan_animation(self) -> None:
        if not self.dbf_scan_active or not self.dbf_scan_paused:
            return
        self.dbf_scan_paused = False
        self._update_dbf_scan_controls()
        self._schedule_dbf_scan_frame()
        language = getattr(self, "language", LANGUAGE_ZH)
        label = _dbf_mode_label(self.dbf_scan_mode, language)
        self.status.set(self._t("dbf_resume_status", mode=label))

    def stop_dbf_scan_animation(self, restore_response: bool = True) -> None:
        had_animation = self.dbf_scan_active or self.dbf_scan_mode is not None
        if self.dbf_scan_after_id is not None:
            try:
                self.root.after_cancel(self.dbf_scan_after_id)
            except tk.TclError:
                pass
        self.dbf_scan_after_id = None
        self.dbf_scan_active = False
        self.dbf_scan_paused = False
        self.dbf_scan_mode = None
        self._update_dbf_scan_controls()
        if restore_response and had_animation:
            self.generate_virtual_array()

    def _schedule_dbf_scan_frame(self) -> None:
        self.dbf_scan_after_id = self.root.after(
            DBF_SCAN_INTERVAL_MS,
            self._advance_dbf_scan_animation,
        )

    def _advance_dbf_scan_animation(self) -> None:
        if not self.dbf_scan_active or self.dbf_scan_paused:
            return
        self.dbf_scan_frame += 1
        if self.dbf_scan_frame >= len(self.dbf_true_angles):
            self.dbf_scan_after_id = None
            self.dbf_scan_active = False
            self.dbf_scan_paused = False
            language = getattr(self, "language", LANGUAGE_ZH)
            label = _dbf_mode_label(self.dbf_scan_mode, language)
            self._update_dbf_scan_controls()
            self.status.set(self._t("dbf_complete_status", mode=label))
            return
        self._draw_dbf_scan_frame()
        self._schedule_dbf_scan_frame()

    def _update_dbf_scan_controls(self) -> None:
        for mode, chart in (
            ("azimuth", getattr(self, "az_chart", None)),
            ("elevation", getattr(self, "el_chart", None)),
        ):
            if chart is None:
                continue
            is_active_mode = self.dbf_scan_active and self.dbf_scan_mode == mode
            has_paused_mode = (
                self.dbf_scan_paused
                and self.dbf_scan_mode == mode
                and self.dbf_true_angles.size > 0
            )
            if chart.play_button is not None:
                if is_active_mode:
                    text = (
                        self._t("dbf_resume_compact")
                        if self.dbf_scan_paused
                        else self._t("dbf_pause_compact")
                    )
                elif has_paused_mode:
                    text = self._t("dbf_resume_compact")
                else:
                    text = self._t("dbf_play_compact")
                style_name = (
                    "CompactPlayActive.TButton"
                    if is_active_mode or has_paused_mode
                    else "CompactPlay.TButton"
                )
                chart.play_button.configure(text=text, style=style_name)
            if chart.stop_button is not None:
                chart.stop_button.configure(text=self._t("dbf_stop_compact"))
                state = tk.NORMAL if self.dbf_scan_mode == mode else tk.DISABLED
                chart.stop_button.configure(state=state)

    def _chart_for_dbf_mode(self, mode: str) -> ResponseChart:
        return self.el_chart if mode == "elevation" else self.az_chart

    def _set_dbf_progress(
        self, mode: str, frame_index: int, true_angle: float
    ) -> None:
        chart = self._chart_for_dbf_mode(mode)
        if chart.progress_label is not None:
            language = getattr(self, "language", LANGUAGE_ZH)
            chart.progress_label.configure(
                text=(
                    f"{_dbf_short_label(mode, language)} "
                    f"{_format_dbf_angle_label(true_angle, language)} "
                    f"({frame_index + 1}/{DBF_SCAN_GRID_SIZE})"
                )
            )

    def _current_dbf_true_angle(self) -> float:
        if self.dbf_true_angles.size == 0:
            return 0.0
        frame = min(self.dbf_scan_frame, len(self.dbf_true_angles) - 1)
        return float(self.dbf_true_angles[frame])

    def _draw_dbf_reference_spectrum(self, mode: str) -> None:
        spectrum_bank = self._dbf_spectrum_bank_for_mode(mode)
        _true_angles, scan_angles, spectra_db = spectrum_bank(
            self.current_array(),
            true_angles_deg=np.asarray([0.0], dtype=float),
            tx_pattern=self.element_pattern,
            rx_pattern=self.element_pattern,
            channel_patterns=self.channel_patterns,
            dbf_dictionary=self.dbf_dictionary,
        )
        self._draw_dbf_spectrum(
            mode=mode,
            true_angle=0.0,
            scan_angles=scan_angles,
            spectrum_db=spectra_db[0],
            frame_label=self._t("reference_frame"),
            frame_index=_dbf_frame_index_for_angle(0.0),
        )

    def _draw_dbf_scan_frame(self) -> None:
        if (
            self.dbf_true_angles.size == 0
            or self.dbf_scan_angles.size == 0
            or self.dbf_spectra_db.size == 0
        ):
            return

        frame = min(self.dbf_scan_frame, len(self.dbf_true_angles) - 1)
        true_angle = float(self.dbf_true_angles[frame])
        spectrum_db = self.dbf_spectra_db[frame]
        self._draw_dbf_spectrum(
            mode=self.dbf_scan_mode or "azimuth",
            true_angle=true_angle,
            scan_angles=self.dbf_scan_angles,
            spectrum_db=spectrum_db,
            frame_label=self._t(
                "frame_label", frame=frame + 1, total=len(self.dbf_true_angles)
            ),
            frame_index=frame,
        )

    def _draw_dbf_spectrum(
        self,
        mode: str,
        true_angle: float,
        scan_angles: np.ndarray,
        spectrum_db: np.ndarray,
        frame_label: str,
        frame_index: int | None = None,
    ) -> None:
        peak_index = _dbf_peak_index(scan_angles, spectrum_db, true_angle)
        peak_angle = float(scan_angles[peak_index])
        peak_gain = float(spectrum_db[peak_index])
        true_index = int(np.argmin(np.abs(scan_angles - true_angle)))
        true_gain = float(spectrum_db[true_index])
        language = getattr(self, "language", LANGUAGE_ZH)
        mode_label = _dbf_mode_label(mode, language)
        chart = self._chart_for_dbf_mode(mode)
        chart.true_angle = float(true_angle)
        ax = chart.ax
        ax.clear()
        _configure_axis_chrome(ax)
        if frame_index is not None:
            self._set_dbf_progress(mode, frame_index, true_angle)

        clipped_spectrum = np.clip(spectrum_db, -40.0, 0.0)
        ax.plot(
            scan_angles,
            clipped_spectrum,
            color=THEME["response_line"],
            linewidth=5.0,
            alpha=0.12,
            solid_capstyle="round",
        )
        ax.plot(
            scan_angles,
            clipped_spectrum,
            color=THEME["response_line"],
            linewidth=2.0,
            solid_capstyle="round",
        )
        ax.axvline(
            true_angle,
            color=THEME["sidelobe"],
            linewidth=1.9,
            linestyle="-",
            zorder=4,
            label=self._t("legend_true_angle"),
        )
        ax.scatter(
            [true_angle],
            [max(true_gain, -40.0)],
            marker="o",
            s=58,
            color=THEME["sidelobe"],
            edgecolors="#ffffff",
            linewidths=0.9,
            zorder=5,
        )
        ax.scatter(
            [peak_angle],
            [max(peak_gain, -40.0)],
            marker="x",
            s=70,
            color=THEME["secondary_accent"],
            linewidths=1.8,
            zorder=6,
            label=self._t("legend_peak"),
        )
        ax.set_xlim(DBF_SCAN_FOV)
        ax.set_ylim(-40.0, 1.0)
        ax.set_title(
            self._t("dbf_title", mode=mode_label),
            pad=6,
            y=1.02,
            loc="left",
            color=THEME["text_primary"],
            fontweight="bold",
        )
        axis_key = "axis_el_angle" if mode == "elevation" else "axis_az_angle"
        ax.set_xlabel(self._t(axis_key), color=THEME["text_secondary"])
        ax.set_ylabel(self._t("axis_gain"), labelpad=2, color=THEME["text_secondary"])
        ax.grid(True, alpha=THEME["grid_alpha"], color=THEME["grid_color"], linewidth=0.55)
        ax.text(
            0.02,
            0.08,
            (
                self._t(
                    "dbf_info",
                    true=true_angle,
                    peak=peak_angle,
                    frame=frame_label,
                )
            ),
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=9,
            color=THEME["text_primary"],
            bbox={
                "boxstyle": "round,pad=0.25",
                "facecolor": THEME["card_bg"],
                "edgecolor": THEME["card_border"],
                "alpha": 0.93,
                "linewidth": 0.7,
            },
        )
        _style_legend(ax.legend(loc="lower right", fontsize=7, framealpha=0.92))

        chart.hover_db = spectrum_db
        chart.hover_angles = scan_angles
        chart.hover_annotation = _new_response_hover_annotation(ax)
        chart.hover_marker = ax.scatter(
            [],
            [],
            marker="o",
            s=44,
            facecolors=THEME["hover_fill"],
            edgecolors=THEME["focus"],
            linewidths=1.0,
            zorder=8,
        )
        chart.hover_marker.set_visible(False)
        chart.canvas.draw_idle()

    def toggle_dbf2d_animation(self, axis: str) -> None:
        if axis == "azimuth":
            self.dbf2d_az_playing = not self.dbf2d_az_playing
        elif axis == "elevation":
            self.dbf2d_el_playing = not self.dbf2d_el_playing
        else:
            raise ValueError(f"Unknown 2D DBF axis: {axis!r}")
        self._update_dbf2d_controls()
        if self.dbf2d_az_playing or self.dbf2d_el_playing:
            self._schedule_dbf2d_frame()
            axes = []
            if self.dbf2d_az_playing:
                axes.append(_dbf_mode_label("azimuth", self.language))
            if self.dbf2d_el_playing:
                axes.append(_dbf_mode_label("elevation", self.language))
            self.status.set(self._t("dbf2d_running", axes=" + ".join(axes)))
        else:
            self._cancel_dbf2d_timer()

    def stop_dbf2d_animation(self, update_status: bool = True) -> None:
        self._cancel_dbf2d_timer()
        self.dbf2d_az_playing = False
        self.dbf2d_el_playing = False
        self._update_dbf2d_controls()
        if update_status:
            self.status.set(self._t("dbf2d_stopped"))

    def _cancel_dbf2d_timer(self) -> None:
        if self.dbf2d_after_id is not None:
            try:
                self.root.after_cancel(self.dbf2d_after_id)
            except tk.TclError:
                pass
        self.dbf2d_after_id = None

    def _schedule_dbf2d_frame(self) -> None:
        if self.dbf2d_after_id is None and (
            self.dbf2d_az_playing or self.dbf2d_el_playing
        ):
            self.dbf2d_after_id = self.root.after(
                DBF_SCAN_INTERVAL_MS,
                self._advance_dbf2d_animation,
            )

    def _advance_dbf2d_animation(self) -> None:
        self.dbf2d_after_id = None
        if self.dbf2d_az_playing:
            self.dbf2d_az_frame = (self.dbf2d_az_frame + 1) % DBF_SCAN_GRID_SIZE
        if self.dbf2d_el_playing:
            self.dbf2d_el_frame = (self.dbf2d_el_frame + 1) % DBF_SCAN_GRID_SIZE
        if self.dbf2d_az_playing or self.dbf2d_el_playing:
            self._draw_dbf2d_heatmap()
            self._schedule_dbf2d_frame()
        else:
            self._update_dbf2d_controls()

    def on_dbf2d_progress_changed(self, axis: str, raw_value: str) -> None:
        if self.dbf2d_progress_updating:
            return
        try:
            frame = int(round(float(raw_value)))
        except (TypeError, ValueError):
            return
        frame = max(0, min(DBF_SCAN_GRID_SIZE - 1, frame))
        if axis == "azimuth":
            self.dbf2d_az_frame = frame
            self.dbf2d_az_playing = False
        elif axis == "elevation":
            self.dbf2d_el_frame = frame
            self.dbf2d_el_playing = False
        else:
            return
        if not self.dbf2d_az_playing and not self.dbf2d_el_playing:
            self._cancel_dbf2d_timer()
        self._draw_dbf2d_heatmap()
        self._update_dbf2d_controls()
        self.status.set(
            self._t("dbf2d_paused_axis", axis=_dbf_mode_label(axis, self.language))
        )

    def _event_dbf2d_angles(self, event) -> tuple[float, float] | None:  # noqa: ANN001
        if self.dbf2d_ax is None:
            return None
        if event.xdata is not None and event.ydata is not None:
            return float(event.xdata), float(event.ydata)
        if event.x is None or event.y is None:
            return None
        try:
            azimuth, elevation = self.dbf2d_ax.transData.inverted().transform(
                (event.x, event.y)
            )
        except (TypeError, ValueError):
            return None
        return float(azimuth), float(elevation)

    def _set_dbf2d_cursor(self, cursor: str) -> None:
        if self.dbf2d_canvas is None:
            return
        try:
            self.dbf2d_canvas.get_tk_widget().configure(cursor=cursor)
        except (tk.TclError, AttributeError):
            return

    def _dbf2d_event_near_crosshair(self, event) -> bool:  # noqa: ANN001
        if event.inaxes != self.dbf2d_ax or event.xdata is None or event.ydata is None:
            return False
        azimuth, elevation = self._current_dbf2d_angles()
        x_low, x_high = self.dbf2d_ax.get_xlim()
        y_low, y_high = self.dbf2d_ax.get_ylim()
        x_tolerance = max(2.0, abs(x_high - x_low) * 0.015)
        y_tolerance = max(2.0, abs(y_high - y_low) * 0.015)
        return (
            abs(float(event.xdata) - azimuth) <= x_tolerance
            or abs(float(event.ydata) - elevation) <= y_tolerance
        )

    def _update_dbf2d_cursor(self, event) -> None:  # noqa: ANN001
        self._set_dbf2d_cursor(
            "hand2" if self._dbf2d_event_near_crosshair(event) else ""
        )

    def _set_dbf2d_angles(self, azimuth: float, elevation: float) -> None:
        self.dbf2d_az_frame = _dbf_frame_index_for_angle(azimuth)
        self.dbf2d_el_frame = _dbf_frame_index_for_angle(elevation)
        self.dbf2d_az_playing = False
        self.dbf2d_el_playing = False
        self._cancel_dbf2d_timer()
        self._draw_dbf2d_heatmap()
        self._update_dbf2d_controls()
        current_azimuth, current_elevation = self._current_dbf2d_angles()
        self.status.set(
            self._t(
                "dbf2d_dragged",
                az=current_azimuth,
                el=current_elevation,
            )
        )

    def on_dbf2d_crosshair_press(self, event) -> None:  # noqa: ANN001
        if event.button != 1 or event.inaxes != self.dbf2d_ax:
            return
        if not self._dbf2d_event_near_crosshair(event):
            return
        angles = self._event_dbf2d_angles(event)
        if angles is None:
            return
        self.dbf2d_dragging = True
        self._set_dbf2d_cursor("hand2")
        self._hide_dbf2d_hover()
        self._set_dbf2d_angles(*angles)

    def on_dbf2d_crosshair_motion(self, event) -> None:  # noqa: ANN001
        if not self.dbf2d_dragging:
            self._update_dbf2d_cursor(event)
            self._update_dbf2d_hover(event)
            return
        angles = self._event_dbf2d_angles(event)
        if angles is None:
            return
        self._set_dbf2d_cursor("hand2")
        self._set_dbf2d_angles(*angles)

    def on_dbf2d_crosshair_release(self, event) -> None:  # noqa: ANN001
        if not self.dbf2d_dragging:
            return
        angles = self._event_dbf2d_angles(event)
        if angles is not None:
            self._set_dbf2d_angles(*angles)
        self.dbf2d_dragging = False
        self._update_dbf2d_cursor(event)

    def on_dbf2d_figure_leave(self, _event) -> None:  # noqa: ANN001
        if not self.dbf2d_dragging:
            self._set_dbf2d_cursor("")
        self._hide_dbf2d_hover()

    def _current_dbf2d_angles(self) -> tuple[float, float]:
        azimuth = DBF_SCAN_FOV[0] + self.dbf2d_az_frame * DBF_SCAN_STEP_DEG
        elevation = DBF_SCAN_FOV[0] + self.dbf2d_el_frame * DBF_SCAN_STEP_DEG
        return float(azimuth), float(elevation)

    def _set_dbf2d_progress(self) -> None:
        self.dbf2d_progress_updating = True
        try:
            if self.dbf2d_az_var is not None:
                self.dbf2d_az_var.set(float(self.dbf2d_az_frame))
            if self.dbf2d_el_var is not None:
                self.dbf2d_el_var.set(float(self.dbf2d_el_frame))
        finally:
            self.dbf2d_progress_updating = False

        if self.dbf2d_status_label is not None:
            azimuth, elevation = self._current_dbf2d_angles()
            frame_index = self.dbf2d_el_frame * DBF_SCAN_GRID_SIZE + self.dbf2d_az_frame + 1
            total = DBF_SCAN_GRID_SIZE * DBF_SCAN_GRID_SIZE
            self.dbf2d_status_label.configure(
                text=self._t(
                    "dbf2d_status",
                    az=azimuth,
                    el=elevation,
                    frame=frame_index,
                    total=total,
                )
            )

    def _update_dbf2d_controls(self) -> None:
        if self.dbf2d_az_button is not None:
            self.dbf2d_az_button.configure(
                text=self._t("dbf2d_pause_az")
                if self.dbf2d_az_playing
                else self._t("dbf2d_play_az"),
                style=(
                    "CompactPlayActive.TButton"
                    if self.dbf2d_az_playing
                    else "CompactPlay.TButton"
                ),
            )
        if self.dbf2d_el_button is not None:
            self.dbf2d_el_button.configure(
                text=self._t("dbf2d_pause_el")
                if self.dbf2d_el_playing
                else self._t("dbf2d_play_el"),
                style=(
                    "CompactPlayActive.TButton"
                    if self.dbf2d_el_playing
                    else "CompactPlay.TButton"
                ),
            )
        if self.dbf2d_stop_button is not None:
            state = tk.NORMAL if self.dbf2d_az_playing or self.dbf2d_el_playing else tk.DISABLED
            self.dbf2d_stop_button.configure(text=self._t("dbf2d_stop"), state=state)
        self._set_dbf2d_progress()

    def _draw_dbf2d_heatmap(self) -> None:
        if self.dbf2d_ax is None or self.dbf2d_canvas is None:
            return
        azimuth, elevation = self._current_dbf2d_angles()
        if self.dbf2d_normalization_max is None:
            self.dbf2d_normalization_max = dbf_2d_normalization_reference(
                self.current_array(),
                tx_pattern=self.element_pattern,
                rx_pattern=self.element_pattern,
                channel_patterns=self.channel_patterns,
                dbf_dictionary=self.dbf_dictionary,
            )
        scan_azimuths, scan_elevations, spectrum_db = dbf_2d_spectrum(
            self.current_array(),
            true_azimuth_deg=azimuth,
            true_elevation_deg=elevation,
            tx_pattern=self.element_pattern,
            rx_pattern=self.element_pattern,
            channel_patterns=self.channel_patterns,
            dbf_dictionary=self.dbf_dictionary,
            normalization_max=self.dbf2d_normalization_max,
        )
        self.dbf2d_hover_azimuths = scan_azimuths
        self.dbf2d_hover_elevations = scan_elevations
        self.dbf2d_hover_db = spectrum_db
        peak_el_index, peak_az_index = np.unravel_index(
            int(np.argmax(spectrum_db)), spectrum_db.shape
        )
        peak_az = float(scan_azimuths[peak_az_index])
        peak_el = float(scan_elevations[peak_el_index])
        peak_az_error = peak_az - azimuth
        peak_el_error = peak_el - elevation

        ax = self.dbf2d_ax
        ax.clear()
        _configure_axis_chrome(ax)
        image = ax.imshow(
            np.clip(spectrum_db, -40.0, 0.0),
            origin="lower",
            extent=(
                float(scan_azimuths[0]),
                float(scan_azimuths[-1]),
                float(scan_elevations[0]),
                float(scan_elevations[-1]),
            ),
            aspect="auto",
            cmap="magma",
            vmin=-40.0,
            vmax=0.0,
            interpolation="nearest",
        )
        if self.dbf2d_cbar_ax is not None and self.dbf2d_fig is not None:
            self.dbf2d_cbar_ax.clear()
            colorbar = self.dbf2d_fig.colorbar(image, cax=self.dbf2d_cbar_ax)
            colorbar.set_label(
                self._t("dbf2d_colorbar_label"),
                color=THEME["text_secondary"],
                fontsize=7.5,
            )
            colorbar.ax.tick_params(
                labelsize=7,
                colors=THEME["text_secondary"],
                length=2.5,
                width=0.6,
            )
            colorbar.outline.set_edgecolor(THEME["axis_spine"])
            colorbar.outline.set_linewidth(0.6)
            self.dbf2d_cbar_ax.set_facecolor(THEME["card_bg"])
        ax.set_aspect("auto")
        ax.axvline(azimuth, color="#ffffff", linewidth=1.0, alpha=0.82)
        ax.axhline(elevation, color="#ffffff", linewidth=1.0, alpha=0.82)
        ax.scatter(
            [peak_az],
            [peak_el],
            marker="x",
            s=48,
            color=THEME["secondary_light"],
            linewidths=1.5,
            zorder=5,
        )
        ax.set_title(
            self._t("dbf2d_plot_title"),
            loc="left",
            pad=5,
            color=THEME["text_primary"],
            fontweight="bold",
        )
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.text(
            0.99,
            0.02,
            f"{self._t('az_short')}(°)",
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=7.5,
            color=THEME["text_secondary"],
            bbox={
                "boxstyle": "round,pad=0.18",
                "facecolor": THEME["plot_bg"],
                "edgecolor": THEME["axis_spine"],
                "alpha": 0.78,
                "linewidth": 0.4,
            },
        )
        ax.text(
            0.02,
            0.52,
            f"{self._t('el_short')}(°)",
            transform=ax.transAxes,
            ha="left",
            va="center",
            rotation=90,
            fontsize=7.5,
            color=THEME["text_secondary"],
            bbox={
                "boxstyle": "round,pad=0.18",
                "facecolor": THEME["plot_bg"],
                "edgecolor": THEME["axis_spine"],
                "alpha": 0.78,
                "linewidth": 0.4,
            },
        )
        ax.text(
            0.02,
            0.96,
            self._t(
                "dbf2d_heatmap_info",
                az=azimuth,
                el=elevation,
                peak_az=peak_az,
                peak_el=peak_el,
            ),
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=7.5,
            color=THEME["text_inverse"],
            bbox={
                "boxstyle": "round,pad=0.25",
                "facecolor": "#111827",
                "edgecolor": "#111827",
                "alpha": 0.74,
                "linewidth": 0.0,
            },
        )
        ax.text(
            0.98,
            0.96,
            self._t(
                "dbf2d_peak_delta",
                az=peak_az_error,
                el=peak_el_error,
            ),
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=7.5,
            color=THEME["text_inverse"],
            bbox={
                "boxstyle": "round,pad=0.25",
                "facecolor": THEME["secondary_accent"],
                "edgecolor": THEME["secondary_accent"],
                "alpha": 0.82,
                "linewidth": 0.0,
            },
        )
        self.dbf2d_hover_annotation = _new_response_hover_annotation(ax)
        self.dbf2d_hover_marker = ax.scatter(
            [],
            [],
            marker="o",
            s=46,
            facecolors=THEME["hover_fill"],
            edgecolors=THEME["focus"],
            linewidths=1.0,
            zorder=8,
        )
        self.dbf2d_hover_marker.set_visible(False)
        self._set_dbf2d_progress()
        self.dbf2d_canvas.draw_idle()

    def open_dbf_dictionary_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        _style_toplevel(dialog)
        dialog.title(self._t("dbf_dictionary_title"))
        dialog.transient(self.root)
        dialog.geometry("1120x700")
        dialog.minsize(1040, 640)

        root_frame = ttk.Frame(dialog, style="Dialog.TFrame", padding=12)
        root_frame.pack(fill=tk.BOTH, expand=True)
        root_frame.grid_columnconfigure(0, weight=0, minsize=380)
        root_frame.grid_columnconfigure(1, weight=1)
        root_frame.grid_rowconfigure(0, weight=1)

        initial_mode = self.dbf_dictionary.mode
        if initial_mode == DBF_DICT_CHANNEL_PATTERN_ZERO_REF:
            initial_mode = DBF_DICT_CHANNEL_PATTERN
        mode_var = tk.StringVar(value=initial_mode)
        axis_var = tk.StringVar(value="azimuth")
        phase_reverse_var = tk.BooleanVar(value=self.dbf_dictionary.custom_phase_reversed)
        zero_calibrate_var = tk.BooleanVar(
            value=self.dbf_dictionary.custom_zero_phase_calibrated
        )
        custom_holder: dict[str, DbfDictionaryTable | None] = {
            "azimuth": self.dbf_dictionary.custom_azimuth_table,
            "elevation": self.dbf_dictionary.custom_elevation_table,
        }
        az_file_var = tk.StringVar()
        el_file_var = tk.StringVar()

        mode_frame = ttk.LabelFrame(
            root_frame,
            text=self._t("dbf_dictionary_mode_title"),
            padding=(8, 6),
        )
        mode_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        for column in range(2):
            mode_frame.grid_columnconfigure(
                column, weight=1, uniform="dbf_dictionary_buttons"
            )
        mode_row = 0
        for mode in (
            DBF_DICT_IDEAL,
            DBF_DICT_IDEAL_REVERSED,
            DBF_DICT_CHANNEL_PATTERN,
            DBF_DICT_CUSTOM,
        ):
            ttk.Radiobutton(
                mode_frame,
                text=_dbf_dictionary_mode_label(mode, self.language),
                variable=mode_var,
                value=mode,
                command=lambda: redraw_preview(),
            ).grid(row=mode_row, column=0, sticky="w", pady=(0, 5))
            mode_row += 1

        ttk.Separator(mode_frame).grid(row=mode_row, column=0, sticky="ew", pady=6)
        mode_row += 1
        ttk.Label(
            mode_frame,
            text=self._t("dbf_dict_axis"),
            style="Muted.TLabel",
        ).grid(row=mode_row, column=0, sticky="w")
        mode_row += 1
        ttk.Radiobutton(
            mode_frame,
            text=self._t("az_short"),
            variable=axis_var,
            value="azimuth",
            command=lambda: redraw_preview(),
        ).grid(row=mode_row, column=0, sticky="w", pady=(4, 0))
        mode_row += 1
        ttk.Radiobutton(
            mode_frame,
            text=self._t("el_short"),
            variable=axis_var,
            value="elevation",
            command=lambda: redraw_preview(),
        ).grid(row=mode_row, column=0, sticky="w", pady=(2, 0))
        mode_row += 1

        ttk.Separator(mode_frame).grid(row=mode_row, column=0, columnspan=2, sticky="ew", pady=8)
        mode_row += 1
        ttk.Label(mode_frame, textvariable=az_file_var, style="Muted.TLabel").grid(
            row=mode_row, column=0, columnspan=2, sticky="ew", pady=(0, 3)
        )
        mode_row += 1
        ttk.Button(
            mode_frame,
            text=self._t("dbf_dict_load_az"),
            command=lambda: load_custom_dictionary("azimuth"),
            style="DialogButton.TButton",
        ).grid(row=mode_row, column=0, sticky="ew", pady=(0, 4))
        ttk.Button(
            mode_frame,
            text=self._t("dbf_dict_clear_az"),
            command=lambda: clear_custom_dictionary("azimuth"),
            style="DialogButton.TButton",
        ).grid(row=mode_row, column=1, sticky="ew", padx=(6, 0), pady=(0, 4))
        mode_row += 1
        ttk.Label(mode_frame, textvariable=el_file_var, style="Muted.TLabel").grid(
            row=mode_row, column=0, columnspan=2, sticky="ew", pady=(3, 3)
        )
        mode_row += 1
        ttk.Button(
            mode_frame,
            text=self._t("dbf_dict_load_el"),
            command=lambda: load_custom_dictionary("elevation"),
            style="DialogButton.TButton",
        ).grid(row=mode_row, column=0, sticky="ew")
        ttk.Button(
            mode_frame,
            text=self._t("dbf_dict_clear_el"),
            command=lambda: clear_custom_dictionary("elevation"),
            style="DialogButton.TButton",
        ).grid(row=mode_row, column=1, sticky="ew", padx=(6, 0))
        mode_row += 1

        ttk.Separator(mode_frame).grid(row=mode_row, column=0, columnspan=2, sticky="ew", pady=8)
        mode_row += 1
        ttk.Label(
            mode_frame,
            text=self._t("dbf_dict_custom_options"),
            style="Muted.TLabel",
        ).grid(row=mode_row, column=0, columnspan=2, sticky="w")
        mode_row += 1
        ttk.Checkbutton(
            mode_frame,
            text=self._t("dbf_dict_phase_reverse"),
            variable=phase_reverse_var,
            command=lambda: redraw_preview(),
        ).grid(row=mode_row, column=0, columnspan=2, sticky="w", pady=(4, 0))
        mode_row += 1
        ttk.Checkbutton(
            mode_frame,
            text=self._t("dbf_dict_zero_calibrate"),
            variable=zero_calibrate_var,
            command=lambda: redraw_preview(),
        ).grid(row=mode_row, column=0, columnspan=2, sticky="w", pady=(2, 0))

        preview_frame = ttk.LabelFrame(
            root_frame,
            text=self._t("dbf_dictionary_preview_title"),
            padding=(8, 6),
        )
        preview_frame.grid(row=0, column=1, sticky="nsew")
        preview_frame.grid_rowconfigure(0, weight=1)
        preview_frame.grid_columnconfigure(0, weight=1)

        matrix_area = ttk.Frame(preview_frame, style="Card.TFrame")
        matrix_area.grid(row=0, column=0, sticky="nsew")
        matrix_area.grid_rowconfigure(0, weight=1)
        matrix_area.grid_columnconfigure(0, weight=1)
        matrix_tree = ttk.Treeview(matrix_area, show="headings", height=18)
        matrix_tree.grid(row=0, column=0, sticky="nsew")
        matrix_y_scroll = ttk.Scrollbar(
            matrix_area, orient=tk.VERTICAL, command=matrix_tree.yview
        )
        matrix_y_scroll.grid(row=0, column=1, sticky="ns")
        matrix_x_scroll = ttk.Scrollbar(
            matrix_area, orient=tk.HORIZONTAL, command=matrix_tree.xview
        )
        matrix_x_scroll.grid(row=1, column=0, sticky="ew")
        matrix_tree.configure(
            yscrollcommand=matrix_y_scroll.set,
            xscrollcommand=matrix_x_scroll.set,
        )

        preview_status = ttk.Label(
            preview_frame,
            text="",
            style="Card.TLabel",
            font=(THEME["font_family_mono"], THEME["font_size_sm"]),
        )
        preview_status.grid(row=1, column=0, sticky="ew", pady=(6, 0))

        button_row = ttk.Frame(root_frame, style="Dialog.TFrame")
        button_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        button_row.grid_columnconfigure(0, weight=1)

        def refresh_file_labels() -> None:
            az_file = (
                custom_holder["azimuth"].display_name
                if custom_holder["azimuth"] is not None
                else self._t("dbf_dict_no_file")
            )
            el_file = (
                custom_holder["elevation"].display_name
                if custom_holder["elevation"] is not None
                else self._t("dbf_dict_no_file")
            )
            az_file_var.set(
                self._t(
                    "dbf_dict_file_status",
                    axis=_dbf_short_label("azimuth", self.language),
                    file=az_file,
                )
            )
            el_file_var.set(
                self._t(
                    "dbf_dict_file_status",
                    axis=_dbf_short_label("elevation", self.language),
                    file=el_file,
                )
            )

        def current_config(require_complete: bool = False) -> DbfDictionaryConfig:
            mode = mode_var.get()
            if mode == DBF_DICT_CUSTOM:
                if require_complete and (
                    custom_holder["azimuth"] is None
                    and custom_holder["elevation"] is None
                ):
                    raise ValueError(self._t("dbf_dict_need_axis_files"))
            return DbfDictionaryConfig(
                mode=mode,
                custom_azimuth_table=custom_holder["azimuth"],
                custom_elevation_table=custom_holder["elevation"],
                custom_phase_reversed=phase_reverse_var.get(),
                custom_zero_phase_calibrated=zero_calibrate_var.get(),
            )

        def show_matrix_message(message: str) -> None:
            matrix_tree.delete(*matrix_tree.get_children())
            matrix_tree.configure(columns=("message",), displaycolumns=("message",))
            matrix_tree.heading("message", text=self._t("dbf_dictionary_preview_title").strip())
            matrix_tree.column("message", width=520, anchor="center", stretch=True)
            matrix_tree.insert("", tk.END, values=(message,))
            preview_status.configure(text=message)

        def redraw_preview() -> None:
            try:
                config = current_config()
                angles = np.linspace(DBF_SCAN_FOV[0], DBF_SCAN_FOV[1], DBF_SCAN_GRID_SIZE)
                matrix = config.scan_matrix(
                    self.current_array(),
                    angles,
                    axis=axis_var.get(),
                    channel_patterns=self.channel_patterns,
                )
                phase = dictionary_phase_preview(matrix)
                columns = ("angle",) + tuple(
                    f"CH{index + 1}" for index in range(phase.shape[1])
                )
                matrix_tree.delete(*matrix_tree.get_children())
                matrix_tree.configure(columns=columns, displaycolumns=columns)
                matrix_tree.heading("angle", text="Angle")
                matrix_tree.column("angle", width=74, anchor="e", stretch=False)
                for column in columns[1:]:
                    matrix_tree.heading(column, text=column)
                    matrix_tree.column(column, width=72, anchor="e", stretch=False)
                for angle, row_values in zip(angles, phase):
                    matrix_tree.insert(
                        "",
                        tk.END,
                        values=(f"{angle:+.0f}", *[f"{value:+.1f}" for value in row_values]),
                    )
                axis_label = _dbf_short_label(axis_var.get(), self.language)
                title = f"{self._t('dbf_dict_preview_phase')} - {axis_label}"
                preview_status.configure(
                    text=f"{title} | "
                    + self._t(
                        "dbf_dict_preview_status",
                        mode=_dbf_dictionary_mode_label(config.mode, self.language),
                        rows=matrix.shape[0],
                        cols=matrix.shape[1],
                    )
                )
            except Exception as exc:
                show_matrix_message(str(exc))

        def load_custom_dictionary(axis: str) -> None:
            filename = filedialog.askopenfilename(
                title=(
                    self._t("dbf_dict_load_el")
                    if axis == "elevation"
                    else self._t("dbf_dict_load_az")
                ),
                initialdir=str(self.last_pattern_dir),
                filetypes=[
                    ("DBF Dictionary", "*.csv *.tsv *.xlsx *.xlsm"),
                    (self._t("csv_type"), "*.csv"),
                    ("Excel", "*.xlsx *.xlsm"),
                    (self._t("all_files_type"), "*.*"),
                ],
            )
            if not filename:
                return
            try:
                table = load_dbf_dictionary_table(filename, self.current_array())
            except Exception as exc:
                LOGGER.exception("Failed to load DBF dictionary from %s", filename)
                messagebox.showerror(self._t("dbf_dict_custom_failed"), str(exc))
                return
            self.last_pattern_dir = Path(filename).parent
            custom_holder[axis] = table
            mode_var.set(DBF_DICT_CUSTOM)
            axis_var.set(axis)
            refresh_file_labels()
            self.status.set(
                self._t(
                    "dbf_dict_custom_loaded",
                    axis=_dbf_short_label(axis, self.language),
                    file=Path(filename).name,
                )
            )
            redraw_preview()

        def clear_custom_dictionary(axis: str) -> None:
            custom_holder[axis] = None
            if (
                mode_var.get() == DBF_DICT_CUSTOM
                and custom_holder["azimuth"] is None
                and custom_holder["elevation"] is None
            ):
                mode_var.set(DBF_DICT_IDEAL)
            refresh_file_labels()
            redraw_preview()

        def apply_dictionary() -> None:
            try:
                config = current_config(require_complete=True)
            except Exception as exc:
                messagebox.showinfo(self._t("dbf_dictionary_title"), str(exc))
                return
            self.dbf_dictionary = config
            self.generate_virtual_array()
            self.status.set(
                self._t(
                    "dbf_dict_applied",
                    mode=_dbf_dictionary_mode_label(config.mode, self.language),
                )
            )
            dialog.destroy()

        ttk.Button(
            button_row,
            text=self._t("dbf_dict_apply"),
            command=apply_dictionary,
            style="DialogButton.TButton",
        ).grid(row=0, column=1, sticky="e", padx=(8, 0))
        ttk.Button(
            button_row,
            text=self._t("done"),
            command=dialog.destroy,
            style="DialogButton.TButton",
        ).grid(row=0, column=2, sticky="e", padx=(8, 0))

        refresh_file_labels()
        redraw_preview()
        _apply_interactive_cursors(dialog)

    def open_channel_patterns_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        _style_toplevel(dialog)
        dialog.title(self._t("channel_dialog_title"))
        dialog.transient(self.root)
        dialog.geometry("1120x680")
        dialog.minsize(1020, 600)

        root_frame = ttk.Frame(dialog, style="Dialog.TFrame", padding=12)
        root_frame.pack(fill=tk.BOTH, expand=True)
        root_frame.grid_columnconfigure(0, weight=1)
        root_frame.grid_rowconfigure(1, weight=1)

        summary_frame = ttk.LabelFrame(
            root_frame,
            text=self._t("summary_csv_title"),
            padding=(8, 6),
        )
        summary_frame.grid(row=0, column=0, sticky="ew")
        for column in range(5):
            summary_frame.grid_columnconfigure(column, weight=1, uniform="summary_buttons")

        summary_specs = (
            (_pattern_slot_label(PATTERN_KIND_AMPLITUDE, PATTERN_PLANE_HORIZONTAL, self.language), PATTERN_KIND_AMPLITUDE, PATTERN_PLANE_HORIZONTAL),
            (_pattern_slot_label(PATTERN_KIND_AMPLITUDE, PATTERN_PLANE_ELEVATION, self.language), PATTERN_KIND_AMPLITUDE, PATTERN_PLANE_ELEVATION),
            (_pattern_slot_label(PATTERN_KIND_PHASE, PATTERN_PLANE_HORIZONTAL, self.language), PATTERN_KIND_PHASE, PATTERN_PLANE_HORIZONTAL),
            (_pattern_slot_label(PATTERN_KIND_PHASE, PATTERN_PLANE_ELEVATION, self.language), PATTERN_KIND_PHASE, PATTERN_PLANE_ELEVATION),
        )
        for column, (label, kind, plane) in enumerate(summary_specs):
            ttk.Button(
                summary_frame,
                text=self._t("load_summary", label=label),
                command=lambda k=kind, p=plane: self._load_summary_channel_pattern(
                    k, p, dialog, refresh_tree
                ),
                style="DialogButton.TButton",
            ).grid(
                row=0,
                column=column,
                sticky="ew",
                padx=(0 if column == 0 else 6, 0),
            )

        ttk.Button(
            summary_frame,
            text=self._t("clear_all"),
            command=lambda: clear_all_patterns(),
            style="DialogDanger.TButton",
        ).grid(row=0, column=4, sticky="ew", padx=(6, 0))

        table_frame = ttk.LabelFrame(
            root_frame,
            text=self._t("physical_channels_title"),
            padding=(8, 6),
        )
        table_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        columns = ("channel", "amp_h", "amp_e", "phase_h", "phase_e")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        tree.tag_configure("odd", background=THEME["panel_alt_bg"])
        tree.tag_configure("even", background=THEME["card_bg"])
        headings = {
            "channel": self._t("column_channel"),
            "amp_h": summary_specs[0][0],
            "amp_e": summary_specs[1][0],
            "phase_h": summary_specs[2][0],
            "phase_e": summary_specs[3][0],
        }
        widths = {
            "channel": 90,
            "amp_h": 170,
            "amp_e": 170,
            "phase_h": 170,
            "phase_e": 170,
        }
        for column in columns:
            tree.heading(column, text=headings[column])
            tree.column(column, width=widths[column], minwidth=70, anchor="w")
        tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=scrollbar.set)

        button_row = ttk.Frame(root_frame, style="Dialog.TFrame")
        button_row.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        for column in range(6):
            button_row.grid_columnconfigure(column, weight=1, uniform="channel_buttons")
        for column, (label, kind, plane) in enumerate(summary_specs):
            ttk.Button(
                button_row,
                text=self._t("set_pattern", label=label),
                command=lambda k=kind, p=plane: self._load_single_channel_pattern(
                    tree, k, p, dialog, refresh_tree
                ),
                style="DialogButton.TButton",
            ).grid(
                row=0,
                column=column,
                sticky="ew",
                padx=(0 if column == 0 else 6, 0),
            )
        ttk.Button(
            button_row,
            text=self._t("clear_channel"),
            command=lambda: clear_selected_channel(),
            style="DialogDanger.TButton",
        ).grid(row=0, column=4, sticky="ew", padx=(6, 0))
        ttk.Button(
            button_row,
            text=self._t("done"),
            command=dialog.destroy,
            style="DialogButton.TButton",
        ).grid(row=0, column=5, sticky="ew", padx=(6, 0))

        def refresh_tree() -> None:
            selected = tree.selection()
            selected_channel = selected[0] if selected else None
            for item in tree.get_children():
                tree.delete(item)
            for row_index, channel_name in enumerate(self._physical_channel_names()):
                pattern = self.channel_patterns.pattern_for(channel_name)
                tree.insert(
                    "",
                    tk.END,
                    iid=channel_name,
                    tags=("odd" if row_index % 2 else "even",),
                    values=(
                        channel_name,
                        _series_table_label(pattern.amplitude_horizontal, self.language),
                        _series_table_label(pattern.amplitude_elevation, self.language),
                        _series_table_label(pattern.phase_horizontal, self.language),
                        _series_table_label(pattern.phase_elevation, self.language),
                    ),
                )
            if selected_channel in tree.get_children():
                tree.selection_set(selected_channel)
                tree.focus(selected_channel)

        def clear_selected_channel() -> None:
            channel_name = self._selected_pattern_channel(tree)
            if channel_name is None:
                return
            self.channel_patterns.clear_channel(channel_name)
            self._after_channel_patterns_changed(
                self._t("channel_cleared", channel=channel_name)
            )
            refresh_tree()

        def clear_all_patterns() -> None:
            if self.channel_patterns.is_empty() and self.element_pattern is None:
                self.status.set(self._t("channel_already_ideal"))
                return
            self.channel_patterns.clear()
            self.element_pattern = None
            self._after_channel_patterns_changed(self._t("channel_all_cleared"))
            refresh_tree()

        refresh_tree()
        if tree.get_children():
            first = tree.get_children()[0]
            tree.selection_set(first)
            tree.focus(first)
        _apply_interactive_cursors(dialog)

    def _physical_channel_names(self) -> list[str]:
        array = self.current_array()
        return [point.name for point in array.tx] + [point.name for point in array.rx]

    def _selected_pattern_channel(self, tree: ttk.Treeview) -> str | None:
        selected = tree.selection()
        if not selected:
            messagebox.showinfo(
                self._t("channel_patterns_title"),
                self._t("select_channel_first"),
            )
            return None
        return str(selected[0])

    def _load_summary_channel_pattern(
        self,
        kind: str,
        plane: str,
        parent: tk.Toplevel,
        refresh_callback: callable,
    ) -> None:
        filename = self._ask_channel_pattern_file(
            title=self._t(
                "load_summary_title",
                label=_pattern_slot_label(kind, plane, self.language),
            ),
            parent=parent,
        )
        if not filename:
            return
        try:
            series_by_channel = load_hfss_summary_pattern(
                filename,
                self._physical_channel_names(),
                value_kind=kind,
            )
        except Exception as exc:
            LOGGER.exception("Load channel pattern summary failed: %s", filename)
            messagebox.showerror(self._t("load_summary_failed"), str(exc))
            return

        self.channel_patterns.update_many(series_by_channel, kind, plane)
        self._after_channel_patterns_changed(
            self._t(
                "summary_loaded",
                label=_pattern_slot_label(kind, plane, self.language),
                file=Path(filename).name,
            )
        )
        refresh_callback()

    def _load_single_channel_pattern(
        self,
        tree: ttk.Treeview,
        kind: str,
        plane: str,
        parent: tk.Toplevel,
        refresh_callback: callable,
    ) -> None:
        channel_name = self._selected_pattern_channel(tree)
        if channel_name is None:
            return
        filename = self._ask_channel_pattern_file(
            title=self._t(
                "load_channel_title",
                label=_pattern_slot_label(kind, plane, self.language),
                channel=channel_name,
            ),
            parent=parent,
        )
        if not filename:
            return
        try:
            series = load_hfss_pattern_series(filename, value_kind=kind)
        except Exception as exc:
            LOGGER.exception("Load channel pattern failed: %s", filename)
            messagebox.showerror(self._t("load_channel_failed"), str(exc))
            return

        self.channel_patterns.set_series(channel_name, kind, plane, series)
        self._after_channel_patterns_changed(
            self._t(
                "channel_loaded",
                label=_pattern_slot_label(kind, plane, self.language),
                channel=channel_name,
                file=Path(filename).name,
            )
        )
        refresh_callback()

    def _ask_channel_pattern_file(
        self,
        title: str,
        parent: tk.Toplevel,
    ) -> str:
        filename = filedialog.askopenfilename(
            parent=parent,
            title=title,
            initialdir=str(self.last_pattern_dir),
            filetypes=[
                (self._t("hfss_csv_type"), "*.csv *.tsv *.xlsx *.xlsm"),
                (self._t("csv_type"), "*.csv"),
                (self._t("tsv_type"), "*.tsv"),
                ("Excel", "*.xlsx *.xlsm"),
                (self._t("all_files_type"), "*.*"),
            ],
        )
        if filename:
            self.last_pattern_dir = Path(filename).parent
        return filename

    def _after_channel_patterns_changed(self, message: str) -> None:
        self._update_channel_pattern_status()
        self.generate_virtual_array()
        self.status.set(message)

    def _update_channel_pattern_status(self) -> None:
        current_patterns = [
            self.channel_patterns.pattern_for(channel_name)
            for channel_name in self._physical_channel_names()
        ]
        channels = sum(not pattern.is_empty() for pattern in current_patterns)
        series = sum(pattern.series_count() for pattern in current_patterns)
        if channels == 0:
            if self.element_pattern is not None:
                self.pattern_status.set(
                    self._t("pattern_element_summary", name=self.element_pattern.name)
                )
                self.pattern_canvas.itemconfig(self.pattern_dot, fill=THEME["secondary_accent"])
                self._refresh_workspace_header()
                return
            self.pattern_status.set(self._t("pattern_ideal"))
            self.pattern_canvas.itemconfig(self.pattern_dot, fill=THEME["text_muted"])
            self._refresh_workspace_header()
            return
        self.pattern_status.set(
            self._t("pattern_summary", channels=channels, series=series)
        )
        self.pattern_canvas.itemconfig(self.pattern_dot, fill=THEME["secondary_accent"])
        self._refresh_workspace_header()

    def import_element_pattern(self) -> None:
        filename = filedialog.askopenfilename(
            title=self._t("element_pattern_import_title"),
            initialdir=str(self.last_pattern_dir),
            filetypes=[
                (self._t("element_pattern_file_type"), "*.csv *.tsv"),
                (self._t("csv_type"), "*.csv"),
                (self._t("tsv_type"), "*.tsv"),
                (self._t("all_files_type"), "*.*"),
            ],
        )
        if not filename:
            return
        self.last_pattern_dir = Path(filename).parent

        try:
            pattern = load_element_pattern(filename)
        except Exception as exc:
            LOGGER.exception("Import element pattern failed: %s", filename)
            messagebox.showerror(self._t("element_pattern_import_failed"), str(exc))
            return

        confirmed_pattern = self._confirm_element_pattern_import(pattern)
        if confirmed_pattern is None:
            self.status.set(self._t("element_pattern_import_canceled"))
            return

        pattern = confirmed_pattern
        self.element_pattern = pattern
        self.pattern_status.set(self._t("pattern_element_summary", name=pattern.name))
        self.pattern_canvas.itemconfig(self.pattern_dot, fill=THEME["secondary_accent"])
        self._refresh_workspace_header()
        LOGGER.info("Imported element pattern from %s", filename)
        self.generate_virtual_array()
        self.status.set(self._t("element_pattern_loaded", name=pattern.name))

    def clear_element_pattern(self) -> None:
        if self.element_pattern is None:
            self.status.set(self._t("element_pattern_already_isotropic"))
            return
        LOGGER.info("Cleared element pattern: %s", self.element_pattern.source_path)
        self.element_pattern = None
        self.pattern_status.set(self._t("pattern_ideal"))
        self.pattern_canvas.itemconfig(self.pattern_dot, fill=THEME["text_muted"])
        self._refresh_workspace_header()
        self.generate_virtual_array()
        self.status.set(self._t("element_pattern_cleared"))

    def _confirm_element_pattern_import(
        self, pattern: ElementPattern
    ) -> ElementPattern | None:
        dialog = tk.Toplevel(self.root)
        _style_toplevel(dialog)
        dialog.title(self._t("element_pattern_confirm_title"))
        dialog.transient(self.root)
        dialog.grab_set()

        title = ttk.Label(
            dialog,
            text=f"{pattern.name}",
            font=(THEME["font_family"], 10, "bold"),
            foreground=THEME["text_primary"],
            background=THEME["bg"],
        )
        title.pack(fill=tk.X, padx=10, pady=(8, 2))
        subtitle = ttk.Label(
            dialog,
            text="",
            font=(THEME["font_family"], 9),
            foreground=THEME["text_secondary"],
            background=THEME["bg"],
        )
        subtitle.pack(fill=tk.X, padx=10, pady=(0, 6))
        metrics_frame = ttk.Frame(dialog)
        metrics_frame.pack(fill=tk.X, padx=10, pady=(0, 6))
        horizontal_metrics_label = ttk.Label(
            metrics_frame,
            text="",
            font=(THEME["font_family_mono"], 9),
            foreground=THEME["response_line"],
        )
        horizontal_metrics_label.pack(anchor="w")
        elevation_metrics_label = ttk.Label(
            metrics_frame,
            text="",
            font=(THEME["font_family_mono"], 9),
            foreground=THEME["secondary_accent"],
        )
        elevation_metrics_label.pack(anchor="w")

        fig = Figure(figsize=(7.8, 5.0), dpi=FIG_DPI)
        fig.set_facecolor(THEME["card_bg"])
        horizontal_ax = fig.add_subplot(211)
        elevation_ax = fig.add_subplot(212)

        canvas = FigureCanvasTkAgg(fig, master=dialog)
        canvas_widget = canvas.get_tk_widget()
        _style_canvas_widget(canvas_widget)
        canvas_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))

        state: dict[str, ElementPattern | None] = {"pattern": pattern, "confirmed": None}

        def redraw_preview() -> None:
            current = state["pattern"]
            if current is None:
                return
            elevation_column = (
                self._t(
                    "element_pattern_preview_elevation_column",
                    column=current.elevation_column,
                )
                if current.elevation_column
                else ""
            )
            subtitle.configure(
                text=self._t(
                    "element_pattern_preview_columns",
                    angle=current.angle_column,
                    horizontal=current.horizontal_column,
                    elevation=elevation_column,
                )
            )

            horizontal_ax.clear()
            elevation_ax.clear()
            horizontal_ax.plot(
                current.angles_deg,
                current.horizontal_gain_db,
                color=THEME["response_line"],
                linewidth=1.8,
            )
            horizontal_metrics = format_pattern_cut_metrics(
                pattern_cut_metrics(current.angles_deg, current.horizontal_gain_db)
            )
            horizontal_metrics_label.configure(
                text=self._t(
                    "element_pattern_horizontal_metrics",
                    metrics=horizontal_metrics,
                )
            )
            horizontal_ax.set_title(
                self._t("element_pattern_horizontal_title"),
                loc="left",
            )
            horizontal_ax.set_ylabel(self._t("element_pattern_axis_gain"))
            _configure_pattern_preview_axis(horizontal_ax)
            horizontal_ax.grid(True, alpha=0.3, color=THEME["grid_major_color"], linewidth=0.55)

            if current.elevation_gain_db is not None:
                elevation_ax.plot(
                    current.angles_deg,
                    current.elevation_gain_db,
                    color=THEME["secondary_accent"],
                    linewidth=1.8,
                )
                elevation_metrics = format_pattern_cut_metrics(
                    pattern_cut_metrics(current.angles_deg, current.elevation_gain_db)
                )
                elevation_metrics_label.configure(
                    text=self._t(
                        "element_pattern_elevation_metrics",
                        metrics=elevation_metrics,
                    )
                )
            else:
                elevation_ax.text(
                    0.5,
                    0.5,
                    self._t("element_pattern_no_elevation"),
                    transform=elevation_ax.transAxes,
                    ha="center",
                    va="center",
                    fontsize=10,
                )
                elevation_metrics_label.configure(
                    text=self._t("element_pattern_elevation_reuse")
                )
            elevation_ax.set_title(
                self._t("element_pattern_elevation_title"),
                loc="left",
            )
            elevation_ax.set_xlabel(self._t("element_pattern_axis_angle"))
            elevation_ax.set_ylabel(self._t("element_pattern_axis_gain"))
            _configure_pattern_preview_axis(elevation_ax)
            elevation_ax.grid(True, alpha=0.3, color=THEME["grid_major_color"], linewidth=0.55)
            fig.tight_layout()
            canvas.draw_idle()

        redraw_preview()

        def confirm() -> None:
            state["confirmed"] = state["pattern"]
            dialog.destroy()

        def cancel() -> None:
            state["confirmed"] = None
            dialog.destroy()

        def swap_axes() -> None:
            current = state["pattern"]
            if current is None:
                return
            state["pattern"] = current.swapped_axes()
            redraw_preview()

        button_row = ttk.Frame(dialog)
        button_row.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(
            button_row,
            text=self._t("element_pattern_import_button"),
            command=confirm,
            style="Accent.TButton",
        ).pack(side=tk.RIGHT)
        ttk.Button(
            button_row,
            text=self._t("element_pattern_cancel_button"),
            command=cancel,
            style="Large.TButton",
        ).pack(
            side=tk.RIGHT, padx=(0, 8)
        )
        swap_button = ttk.Button(
            button_row,
            text=self._t("element_pattern_swap_button"),
            command=swap_axes,
            style="Large.TButton",
        )
        swap_button.pack(side=tk.LEFT)
        if pattern.elevation_gain_db is None:
            swap_button.configure(state=tk.DISABLED)
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        dialog.wait_window()
        return state["confirmed"]

    def export_layout_config(self) -> None:
        default_path = Path("outputs") / "antenna_layout.json"
        default_path.parent.mkdir(exist_ok=True)
        filename = filedialog.asksaveasfilename(
            title=self._t("export_layout_title"),
            initialdir=str(self.last_layout_dir),
            initialfile=default_path.name,
            defaultextension=".json",
            filetypes=[(self._t("layout_json_type"), "*.json")],
        )
        if not filename:
            return
        self.last_layout_dir = Path(filename).parent
        config = self._layout_config()
        with open(filename, "w", encoding="utf-8") as file:
            file.write(_layout_config_to_json(config))
        LOGGER.info("Exported layout config to %s", filename)
        self.status.set(self._t("exported_layout", file=filename))

    def import_layout_config(self) -> None:
        filename = filedialog.askopenfilename(
            title=self._t("import_layout_title"),
            initialdir=str(self.last_layout_dir),
            filetypes=[
                (self._t("layout_json_type"), "*.json"),
                (self._t("all_files_type"), "*.*"),
            ],
        )
        if not filename:
            return
        self.last_layout_dir = Path(filename).parent
        previous_snapshot = self._capture_layout_snapshot()
        try:
            with open(filename, "r", encoding="utf-8") as file:
                config = json.load(file)
            imported_elements = self._elements_from_layout_config(config)
        except Exception as exc:
            LOGGER.exception("Import layout failed: %s", filename)
            messagebox.showerror(self._t("import_layout_failed"), str(exc))
            return

        imported_snapshot = self._layout_snapshot_for(imported_elements, None)
        if imported_snapshot != previous_snapshot:
            self._push_undo_snapshot(previous_snapshot)
        self.elements = imported_elements
        self.dragging = None
        self.drag_bounds = None
        self.drag_axis_limits = None
        self.drag_start_snapshot = None
        self.selected_element = None
        self._sync_auto_count_inputs()
        self.generate_virtual_array()
        tx = [element for element in self.elements if element.kind == "tx"]
        rx = [element for element in self.elements if element.kind == "rx"]
        x_values = [element.x * DISPLAY_SCALE_LAMBDA for element in self.elements]
        y_values = [element.y * DISPLAY_SCALE_LAMBDA for element in self.elements]
        self.status.set(
            self._t(
                "imported_layout",
                file=Path(filename).name,
                tx=tx[0].name,
                tx_x=tx[0].x * DISPLAY_SCALE_LAMBDA,
                tx_y=tx[0].y * DISPLAY_SCALE_LAMBDA,
                rx=rx[0].name,
                rx_x=rx[0].x * DISPLAY_SCALE_LAMBDA,
                rx_y=rx[0].y * DISPLAY_SCALE_LAMBDA,
                x_min=min(x_values),
                x_max=max(x_values),
                y_min=min(y_values),
                y_max=max(y_values),
            )
        )
        LOGGER.info("Imported layout config from %s", filename)

    # ── Layout config I/O ─────────────────────────────────────────────

    def _layout_config(self) -> dict[str, object]:
        config = self._layout_coordinates_config()
        metrics = self._metrics_for_export()
        config["evaluation"] = self._layout_evaluation(metrics)
        return config

    def _layout_coordinates_config(self) -> dict[str, object]:
        tx = [element for element in self.elements if element.kind == "tx"]
        rx = [element for element in self.elements if element.kind == "rx"]
        return {
            "version": LAYOUT_CONFIG_VERSION,
            "unit": LAYOUT_UNIT,
            "tx": [
                {
                    "name": element.name,
                    "x": _json_number(element.x * DISPLAY_SCALE_LAMBDA, digits=9),
                    "y": _json_number(element.y * DISPLAY_SCALE_LAMBDA, digits=9),
                }
                for element in tx
            ],
            "rx": [
                {
                    "name": element.name,
                    "x": _json_number(element.x * DISPLAY_SCALE_LAMBDA, digits=9),
                    "y": _json_number(element.y * DISPLAY_SCALE_LAMBDA, digits=9),
                }
                for element in rx
            ],
        }

    def _elements_from_layout_config(self, config: object) -> list[EditableElement]:
        if not isinstance(config, dict):
            raise ValueError("Layout config must be a JSON object.")
        if config.get("version") != LAYOUT_CONFIG_VERSION:
            raise ValueError(f"Unsupported layout version: {config.get('version')!r}.")
        unit = config.get("unit")
        if unit not in LAYOUT_UNITS_LAMBDA | LEGACY_LAYOUT_UNITS_HALF_LAMBDA:
            raise ValueError("Layout unit must be 'lambda'.")
        coordinates_are_lambda = unit in LAYOUT_UNITS_LAMBDA

        elements: list[EditableElement] = []
        for kind in ("tx", "rx"):
            raw_points = config.get(kind)
            if not isinstance(raw_points, list) or not raw_points:
                raise ValueError(f"Layout field '{kind}' must be a non-empty list.")
            max_count = _max_elements_for_kind(kind)
            if len(raw_points) > max_count:
                prefix = _element_prefix(kind)
                raise ValueError(f"Layout has {len(raw_points)} {prefix} elements; maximum is {max_count}.")
            for index, raw_point in enumerate(raw_points):
                if not isinstance(raw_point, dict):
                    raise ValueError(f"{kind}[{index}] must be an object.")
                try:
                    name = f"{_element_prefix(kind)}{index + 1}"
                    raw_x = float(raw_point["x"])
                    raw_y = float(raw_point["y"])
                    if coordinates_are_lambda:
                        raw_x = _to_internal_half_lambda(raw_x)
                        raw_y = _to_internal_half_lambda(raw_y)
                    x = snap_to_grid(raw_x)
                    y = snap_to_grid(raw_y)
                except KeyError as exc:
                    raise ValueError(f"{kind}[{index}] is missing coordinate {exc}.") from exc
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"{kind}[{index}] has invalid coordinates.") from exc
                elements.append(EditableElement(kind=kind, index=index, name=name, x=x, y=y))
        return elements

    def _metrics_for_export(self) -> ArrayMetrics:
        array = self.current_array()
        unique, counts = array.unique_virtual_xy(decimals=ROUND_DECIMALS)
        _af_db, _azimuths, _elevations, metrics = calculate_metrics_and_psf(
            array,
            unique,
            counts,
            tx_pattern=self.element_pattern,
            rx_pattern=self.element_pattern,
            channel_patterns=self.channel_patterns,
        )
        return metrics

    def _layout_evaluation(self, metrics: ArrayMetrics) -> dict[str, object]:
        utilization = metrics.unique_count / metrics.virtual_count if metrics.virtual_count else 0.0
        return {
            "frequency_ghz": _format_frequency_ghz(self.current_frequency_ghz()),
            "ambiguity_margin_db": _json_number(self.current_margin_db(), digits=3),
            "dbf_dictionary": {
                "mode": self.dbf_dictionary.mode,
                "custom_sources": {
                    "azimuth": (
                        self.dbf_dictionary.custom_azimuth_table.source_path
                        if self.dbf_dictionary.custom_azimuth_table is not None
                        else None
                    ),
                    "elevation": (
                        self.dbf_dictionary.custom_elevation_table.source_path
                        if self.dbf_dictionary.custom_elevation_table is not None
                        else None
                    ),
                },
                "custom_phase_reversed": self.dbf_dictionary.custom_phase_reversed,
                "custom_zero_phase_calibrated": (
                    self.dbf_dictionary.custom_zero_phase_calibrated
                ),
            },
            "virtual_utilization": {
                "unique_points": metrics.unique_count,
                "virtual_channels": metrics.virtual_count,
                "ratio": _json_number(utilization, digits=6),
                "duplicate_points": metrics.duplicate_excess,
            },
            "az_aperture_mm": _json_number(self.aperture_mm(metrics.x_aperture), digits=3),
            "az_aperture_lambda": _json_number(metrics.x_aperture * DISPLAY_SCALE_LAMBDA, digits=9),
            "az_resolution_deg": _json_number(metrics.azimuth_resolution, digits=3),
            "az_3db_bw_deg": _json_number(metrics.azimuth_3db_beamwidth, digits=3),
            "az_psl_db": _json_number(metrics.azimuth_psl_db, digits=3),
            "first_sidelobe": {
                "level_db": _json_number(metrics.azimuth_first_sidelobe_db, digits=3),
                "az_deg": _json_number(metrics.azimuth_first_sidelobe_angle, digits=3),
            },
            "az_grating_lobe": {
                "level_db": _json_number(metrics.azimuth_grating_lobe_db, digits=3),
                "az_deg": _json_number(metrics.azimuth_grating_lobe_angle, digits=3),
            },
            "az_islr_db": _json_number(metrics.azimuth_islr_db, digits=3),
            "el_3db_bw_deg": _json_number(metrics.elevation_3db_beamwidth, digits=3),
            "el_psl_db": _json_number(metrics.elevation_psl_db, digits=3),
            "psl_2d_worst_db": _json_number(metrics.psl_db, digits=3),
            "psl_2d_location_deg": {
                "az": _json_number(metrics.sidelobe_azimuth, digits=3),
                "el": _json_number(metrics.sidelobe_elevation, digits=3),
            },
            "element_pattern": self._element_pattern_export_info(),
            "channel_patterns": self._channel_pattern_export_info(),
            "notes": self._notes_parts(metrics),
        }

    # ── Main generation pipeline ──────────────────────────────────────

    def generate_virtual_array(self) -> None:
        self.stop_dbf_scan_animation(restore_response=False)
        self.stop_dbf2d_animation(update_status=False)
        self.dbf2d_normalization_max = None
        array = self.current_array()
        unique, counts = array.unique_virtual_xy(decimals=ROUND_DECIMALS)
        pair_map = self._build_virtual_pair_map(array)
        af_db, azimuths, elevations, metrics = calculate_metrics_and_psf(
            array,
            unique,
            counts,
            tx_pattern=self.element_pattern,
            rx_pattern=self.element_pattern,
            channel_patterns=self.channel_patterns,
        )

        self._draw_physical_array()
        self._draw_virtual_array(unique, counts, pair_map, metrics)
        self._update_evaluation_panel(metrics)
        self._update_channel_pattern_status()
        self._draw_dbf_reference_spectrum("azimuth")
        self._draw_dbf_reference_spectrum("elevation")
        self._draw_dbf2d_heatmap()

        self.status.set(self._t("status_ready"))
        self._refresh_workspace_header()
        self.phys_canvas.draw_idle()
        self.virt_canvas.draw_idle()
        self.az_chart.canvas.draw_idle()
        self.el_chart.canvas.draw_idle()

    def _build_virtual_pair_map(
        self, array: AntennaArray
    ) -> dict[tuple[float, float], list[str]]:
        pair_map: dict[tuple[float, float], list[str]] = defaultdict(list)
        for point in array.virtual_points():
            key = (round(point.x, ROUND_DECIMALS), round(point.y, ROUND_DECIMALS))
            pair_map[key].append(f"{point.tx_name}-{point.rx_name}")
        return pair_map

    # ── Plot drawing ──────────────────────────────────────────────────

    def _draw_physical_array(self) -> None:
        self.physical_ax.clear()
        _configure_axis_chrome(self.physical_ax)
        tx = [element for element in self.elements if element.kind == "tx"]
        rx = [element for element in self.elements if element.kind == "rx"]

        self.physical_ax.scatter(
            _to_display_lambda([element.x for element in tx]),
            _to_display_lambda([element.y for element in tx]),
            marker="D",
            s=62,
            facecolors="none",
            edgecolors=THEME["tx_color"],
            linewidths=1.8,
            label="Tx",
        )
        self.physical_ax.scatter(
            _to_display_lambda([element.x for element in rx]),
            _to_display_lambda([element.y for element in rx]),
            marker="*",
            s=112,
            color=THEME["rx_color"],
            edgecolors=THEME["rx_edge"],
            linewidths=0.55,
            label="Rx",
        )
        self.physical_hover_marker = self.physical_ax.scatter(
            [],
            [],
            marker="o",
            s=260,
            facecolors=THEME["hover_fill"],
            edgecolors=THEME["focus"],
            linewidths=1.6,
            alpha=0.45,
            zorder=4,
            label="_nolegend_",
        )
        self.physical_hover_marker.set_visible(False)
        if self.selected_element is not None:
            self.physical_ax.scatter(
                _to_display_lambda([self.selected_element.x]),
                _to_display_lambda([self.selected_element.y]),
                marker="o",
                s=292,
                facecolors="none",
                edgecolors=THEME["selection"],
                linewidths=2.6,
                zorder=5,
                label="_nolegend_",
            )
        for element in self.elements:
            if self.selected_element is element:
                self.physical_ax.annotate(
                    element.name,
                    xy=(
                        element.x * DISPLAY_SCALE_LAMBDA,
                        element.y * DISPLAY_SCALE_LAMBDA,
                    ),
                    xytext=(7, 16),
                    textcoords="offset points",
                    fontsize=8.8,
                    ha="left",
                    va="bottom",
                    color=THEME["text_primary"],
                    bbox={
                        "boxstyle": "round,pad=0.18",
                        "facecolor": THEME["selection_fill"],
                        "edgecolor": THEME["focus"],
                        "alpha": 0.95,
                        "linewidth": 0.6,
                    },
                )
            else:
                dy = 1.0 if element.kind == "tx" else -1.15
                self.physical_ax.text(
                    element.x * DISPLAY_SCALE_LAMBDA,
                    element.y * DISPLAY_SCALE_LAMBDA + dy,
                    element.name,
                    fontsize=8.8,
                    ha="center",
                    va="center",
                    color=THEME["text_secondary"],
                )

        self.physical_ax.set_title(
            self._t("physical_title"), fontsize=TITLE_SIZE, pad=6, y=1.02, loc="left",
            color=THEME["text_primary"], fontweight="bold",
        )
        self.physical_ax.set_xlabel("x (λ)", color=THEME["text_secondary"])
        self.physical_ax.set_ylabel("y (λ)", color=THEME["text_secondary"])
        if self.drag_axis_limits is not None:
            x_limits, y_limits = self.drag_axis_limits
        else:
            physical_x = _to_display_lambda([element.x for element in self.elements])
            physical_y = _to_display_lambda([element.y for element in self.elements])
            x_limits, y_limits = _square_axis_limits(
                physical_x,
                physical_y,
                minimum_span=PHYSICAL_AXIS_MIN_SPAN_LAMBDA,
                padding=PHYSICAL_AXIS_PADDING_LAMBDA,
            )
        self.physical_ax.set_xlim(*x_limits)
        self.physical_ax.set_ylim(*y_limits)
        self.physical_ax.set_xticks(
            _axis_ticks_within(x_limits, PHYSICAL_MAJOR_GRID_STEP_LAMBDA)
        )
        self.physical_ax.set_yticks(
            _axis_ticks_within(y_limits, PHYSICAL_MAJOR_GRID_STEP_LAMBDA)
        )
        self.physical_ax.set_xticks(
            _axis_ticks_within(x_limits, DISPLAY_GRID_STEP_LAMBDA),
            minor=True,
        )
        self.physical_ax.set_yticks(
            _axis_ticks_within(y_limits, DISPLAY_GRID_STEP_LAMBDA),
            minor=True,
        )
        self.physical_ax.grid(
            True, which="major", color=THEME["grid_major_color"], linewidth=0.95, alpha=0.66
        )
        self.physical_ax.grid(
            True, which="minor", color=THEME["grid_minor_color"], linewidth=0.42, alpha=0.24
        )
        if self.dragging is not None:
            snap_x = self.dragging.x * DISPLAY_SCALE_LAMBDA
            snap_y = self.dragging.y * DISPLAY_SCALE_LAMBDA
            self.physical_ax.axvline(
                snap_x,
                color=THEME["selection"],
                linestyle="--",
                linewidth=1.35,
                alpha=0.86,
                zorder=3,
            )
            self.physical_ax.axhline(
                snap_y,
                color=THEME["selection"],
                linestyle="--",
                linewidth=1.35,
                alpha=0.86,
                zorder=3,
            )
            self.physical_ax.scatter(
                [snap_x],
                [snap_y],
                marker="o",
                s=430,
                facecolors="none",
                edgecolors=THEME["selection"],
                linewidths=2.8,
                zorder=6,
                label="_nolegend_",
            )
        _style_legend(self.physical_ax.legend(loc="upper right", framealpha=0.92))
        self.physical_ax.set_aspect("equal", adjustable="box", anchor="C")
        self.physical_hover_annotation = self.physical_ax.annotate(
            "",
            xy=(0, 0),
            xytext=(12, 12),
            textcoords="offset points",
            bbox={
                "boxstyle": "round,pad=0.35",
                "facecolor": THEME["card_bg"],
                "edgecolor": THEME["focus_soft"],
                "alpha": 0.95,
                "linewidth": 0.8,
            },
            arrowprops={"arrowstyle": "->", "color": THEME["focus"], "linewidth": 0.8},
            fontsize=8,
            color=THEME["text_primary"],
        )
        self.physical_hover_annotation.set_visible(False)

    def _draw_virtual_array(
        self,
        unique: np.ndarray,
        counts: np.ndarray,
        pair_map: dict[tuple[float, float], list[str]],
        metrics: ArrayMetrics,
    ) -> None:
        self.virtual_ax.clear()
        _configure_axis_chrome(self.virtual_ax)
        unique_display = _to_display_lambda(unique)
        x_min, x_max = float(unique_display[:, 0].min()), float(unique_display[:, 0].max())
        y_min, y_max = float(unique_display[:, 1].min()), float(unique_display[:, 1].max())
        self.virtual_ax.add_patch(
            Rectangle(
                (x_min, y_min),
                x_max - x_min,
                y_max - y_min,
                fill=False,
                linestyle="--",
                linewidth=1.2,
                edgecolor=THEME["text_secondary"],
                alpha=0.5,
            )
        )
        sizes = 80 + 54 * np.clip(counts - 2, 0, 6)
        single_mask = counts == 1
        duplicate_mask = counts > 1
        if np.any(single_mask):
            self.virtual_ax.scatter(
                unique_display[single_mask, 0],
                unique_display[single_mask, 1],
                s=34,
                marker="o",
                color=THEME["rx_color"],
                edgecolors=THEME["rx_edge"],
                linewidths=0.55,
                label=self._t("unique_point"),
            )
        if np.any(duplicate_mask):
            self.virtual_ax.scatter(
                unique_display[duplicate_mask, 0],
                unique_display[duplicate_mask, 1],
                s=sizes[duplicate_mask],
                color=THEME["warning"],
                marker="o",
                edgecolors="#92400e",
                linewidths=1.35,
                label=self._t("duplicate_point"),
            )
        self.virtual_hover_marker = self.virtual_ax.scatter(
            [],
            [],
            marker="o",
            s=210,
            facecolors=THEME["hover_fill"],
            edgecolors=THEME["focus"],
            linewidths=1.5,
            alpha=0.5,
            zorder=7,
            label="_nolegend_",
        )
        self.virtual_hover_marker.set_visible(False)
        for (x, y), count in zip(unique_display, counts):
            if count > 1:
                self.virtual_ax.annotate(
                    f"×{int(count)}",
                    xy=(x, y),
                    xytext=(5, 5),
                    textcoords="offset points",
                    fontsize=12,
                    color=THEME["danger"],
                    weight="bold",
                )

        # Store hover data
        self.virtual_hover_xy = unique_display
        self.virtual_hover_counts = counts.astype(int, copy=True)
        self.virtual_hover_text = []
        for x, y in unique:
            key = (round(float(x), ROUND_DECIMALS), round(float(y), ROUND_DECIMALS))
            pairs = pair_map.get(key, [])
            pair_text = ", ".join(pairs[:10])
            if len(pairs) > 10:
                pair_text += self._t("virtual_pairs_more", count=len(pairs))
            self.virtual_hover_text.append(
                self._t(
                    "virtual_hover",
                    x=x * DISPLAY_SCALE_LAMBDA,
                    y=y * DISPLAY_SCALE_LAMBDA,
                    count=len(pairs),
                    pairs=pair_text,
                )
            )

        self.virtual_hover_annotation = self.virtual_ax.annotate(
            "",
            xy=(0, 0),
            xytext=(12, 12),
            textcoords="offset points",
            bbox={
                "boxstyle": "round,pad=0.35",
                "facecolor": THEME["card_bg"],
                "edgecolor": THEME["focus_soft"],
                "alpha": 0.95,
                "linewidth": 0.8,
            },
            arrowprops={"arrowstyle": "->", "color": THEME["focus"], "linewidth": 0.8},
            fontsize=8,
        )
        self.virtual_hover_annotation.set_visible(False)

        self.virtual_ax.set_title(self._t("virtual_title"), fontsize=TITLE_SIZE, pad=8, loc="left",
                                    color=THEME["text_primary"], fontweight="bold")
        self.virtual_ax.set_xlabel("x (λ)", color=THEME["text_secondary"])
        self.virtual_ax.set_ylabel("y (λ)", color=THEME["text_secondary"])
        self.virtual_ax.grid(True, alpha=THEME["grid_alpha"], color=THEME["grid_color"], linewidth=0.55)

        # Simple padded limits — let set_aspect("equal") handle the rest
        x_limits = _axis_limits(unique_display[:, 0], minimum_span=6.0, padding=2.0)
        y_limits = _axis_limits(unique_display[:, 1], minimum_span=6.0, padding=2.0)
        self.virtual_ax.set_xlim(*x_limits)
        self.virtual_ax.set_ylim(*y_limits)
        self.virtual_ax.set_xticks(
            np.arange(
                np.floor(x_limits[0] / 5) * 5,
                np.ceil(x_limits[1] / 5) * 5 + 1,
                5,
            )
        )
        self.virtual_ax.set_yticks(
            np.arange(
                np.floor(y_limits[0] / 5) * 5,
                np.ceil(y_limits[1] / 5) * 5 + 1,
                5,
            )
        )
        self.virtual_ax.set_xticks(
            np.arange(
                np.floor(x_limits[0] / DISPLAY_GRID_STEP_LAMBDA) * DISPLAY_GRID_STEP_LAMBDA,
                x_limits[1] + DISPLAY_GRID_STEP_LAMBDA,
                DISPLAY_GRID_STEP_LAMBDA,
            ),
            minor=True,
        )
        self.virtual_ax.set_yticks(
            np.arange(
                np.floor(y_limits[0] / DISPLAY_GRID_STEP_LAMBDA) * DISPLAY_GRID_STEP_LAMBDA,
                y_limits[1] + DISPLAY_GRID_STEP_LAMBDA,
                DISPLAY_GRID_STEP_LAMBDA,
            ),
            minor=True,
        )
        self.virtual_ax.set_aspect("equal", adjustable="box")

        # Info box in upper-left corner
        self.virtual_ax.text(
            0.01,
            0.98,
            self._t(
                "virtual_info",
                unique=metrics.unique_count,
                total=metrics.virtual_count,
                duplicate=metrics.duplicate_excess,
                x=_format_mm(self.aperture_mm(metrics.x_aperture)),
                y=_format_mm(self.aperture_mm(metrics.y_aperture)),
            ),
            transform=self.virtual_ax.transAxes,
            ha="left",
            va="top",
            fontsize=8.5,
            color=THEME["text_primary"],
            bbox={
                "boxstyle": "round,pad=0.22",
                "facecolor": THEME["card_bg"],
                "edgecolor": THEME["card_border"],
                "alpha": 0.9,
            },
        )
        if counts.max() > 1:
            _style_legend(self.virtual_ax.legend(loc="best", fontsize=8))

    def _draw_response_common(
        self,
        ax,
        response_cut: ResponseCut,
        metrics: ArrayMetrics,
    ) -> None:
        """Shared drawing logic for both Az and El response figures."""
        ax.clear()
        _configure_axis_chrome(ax)
        response_db = response_cut.gains_db
        response_angles = response_cut.angles
        sidelobe_index, sidelobe_is_peak = _response_sidelobe_marker(
            response_angles, response_db, response_cut.mainlobe_guard
        )
        sidelobe_angle = float(response_angles[sidelobe_index])
        sidelobe_gain = float(response_db[sidelobe_index])
        sidelobe_label = (
            self._t("max_sidelobe") if sidelobe_is_peak else self._t("guard_edge_max")
        )
        response_ylim = (-40.0, 0.0)

        ax.plot(
            response_angles,
            response_db,
            color=THEME["response_line"],
            linewidth=5.0,
            alpha=0.12,
            solid_capstyle="round",
        )
        ax.plot(
            response_angles,
            response_db,
            color=THEME["response_line"],
            linewidth=2.0,
            solid_capstyle="round",
        )
        show_legend = False
        if self.element_pattern is not None:
            if response_cut.mode == RESPONSE_MODE_ELEVATION:
                element_pattern_cut = self.element_pattern.normalized_elevation_gain_db_at(
                    response_angles
                )
            else:
                element_pattern_cut = self.element_pattern.normalized_horizontal_gain_db_at(
                    response_angles
                )
            pattern_cut = np.clip(
                element_pattern_cut,
                response_ylim[0],
                response_ylim[1],
            )
            ax.plot(
                response_angles,
                pattern_cut,
                color=THEME["response_secondary_line"],
                linestyle="--",
                linewidth=1.3,
                alpha=0.72,
                label=response_cut.pattern_label,
            )
            show_legend = True
        ax.set_xlim(response_cut.fov)
        ax.set_ylim(response_ylim)
        ax.axvspan(
            -response_cut.mainlobe_guard,
            response_cut.mainlobe_guard,
            color=THEME["accent_light"],
            alpha=0.7,
        )
        ax.scatter(
            [0.0],
            [0.0],
            marker="+",
            s=80,
            color=THEME["text_primary"],
            linewidths=2.0,
            zorder=4,
        )
        # Max sidelobe marker
        ax.scatter(
            [sidelobe_angle],
            [sidelobe_gain],
            marker="x",
            s=70,
            color=THEME["sidelobe"],
            linewidths=2.0,
            zorder=5,
            clip_on=True,
            label=sidelobe_label,
        )

        x_low, x_high = response_cut.fov
        y_low, y_high = response_ylim
        annotation_boxes: list[tuple[float, float, float, float]] = []

        def annotation_position(angle: float, gain: float) -> tuple[float, float, str]:
            angle_axes = (angle - x_low) / (x_high - x_low)
            gain_axes = (gain - y_low) / (y_high - y_low)
            box_width = 0.18
            box_height = 0.15
            if angle >= 0:
                base_x = min(angle_axes + 0.08, 0.76)
                ha = "left"
            else:
                base_x = max(angle_axes - 0.08, 0.24)
                ha = "right"

            candidates = (0.12, -0.12, 0.25, -0.25, 0.38, -0.34, 0.0)
            for offset in candidates:
                y = float(np.clip(gain_axes + offset, 0.18, 0.82))
                if ha == "left":
                    box = (base_x, y - box_height / 2, base_x + box_width, y + box_height / 2)
                else:
                    box = (base_x - box_width, y - box_height / 2, base_x, y + box_height / 2)
                if not any(_axes_boxes_overlap(box, existing) for existing in annotation_boxes):
                    annotation_boxes.append(box)
                    return base_x, y, ha

            fallback_y = float(np.clip(gain_axes, 0.18, 0.82))
            if ha == "left":
                annotation_boxes.append(
                    (base_x, fallback_y - box_height / 2, base_x + box_width, fallback_y + box_height / 2)
                )
            else:
                annotation_boxes.append(
                    (base_x - box_width, fallback_y - box_height / 2, base_x, fallback_y + box_height / 2)
                )
            return base_x, fallback_y, ha

        annotation_x, annotation_y, annotation_ha = annotation_position(
            sidelobe_angle, sidelobe_gain
        )
        ax.annotate(
            (
                f"{sidelobe_label}\n{response_cut.label} = {sidelobe_angle:.1f}°\n"
                f"{self._t('gain_value', value=sidelobe_gain)}"
            ),
            xy=(sidelobe_angle, sidelobe_gain),
            xytext=(annotation_x, annotation_y),
            textcoords=ax.transAxes,
            ha=annotation_ha,
            va="center",
            fontsize=7.5,
            color="#7c2d12",
            bbox={
                "boxstyle": "round,pad=0.25",
                "facecolor": "#fff7ed",
                "edgecolor": "#fed7aa",
                "alpha": 0.92,
                "linewidth": 0.7,
            },
            arrowprops={"arrowstyle": "->", "color": THEME["sidelobe"], "linewidth": 0.7},
            annotation_clip=True,
        )

        # Grating lobe marker (Az only)
        if (
            response_cut.mode == RESPONSE_MODE_AZIMUTH
            and metrics.azimuth_grating_lobe_angle is not None
            and metrics.azimuth_grating_lobe_db is not None
        ):
            grating_angle = metrics.azimuth_grating_lobe_angle
            grating_gain = metrics.azimuth_grating_lobe_db
            grating_same_as_max = (
                abs(grating_angle - sidelobe_angle)
                <= float(np.diff(response_angles).mean()) / 2.0
                and abs(grating_gain - sidelobe_gain) <= 0.05
            )
            ax.scatter(
                [grating_angle],
                [grating_gain],
                marker="^",
                s=82,
                facecolors="none",
                edgecolors=THEME["secondary_accent"],
                linewidths=1.8,
                zorder=6,
                clip_on=True,
                label=(
                    self._t("grating_lobe_max")
                    if grating_same_as_max
                    else self._t("grating_lobe")
                ),
            )
            show_legend = True
            if not grating_same_as_max:
                grating_x, grating_y, grating_ha = annotation_position(
                    grating_angle, grating_gain
                )
                ax.annotate(
                    (
                        f"{self._t('grating_lobe')}\n"
                        f"{_dbf_short_label('azimuth', self.language)} = {grating_angle:.1f}°\n"
                        f"{self._t('gain_value', value=grating_gain)}"
                    ),
                    xy=(grating_angle, grating_gain),
                    xytext=(grating_x, grating_y),
                    textcoords=ax.transAxes,
                    ha=grating_ha,
                    va="center",
                    fontsize=7.5,
                    color="#134e4a",
                    bbox={
                        "boxstyle": "round,pad=0.25",
                        "facecolor": THEME["secondary_light"],
                        "edgecolor": "#5eead4",
                        "alpha": 0.92,
                        "linewidth": 0.7,
                    },
                    arrowprops={"arrowstyle": "->", "color": THEME["secondary_accent"], "linewidth": 0.7},
                    annotation_clip=True,
                )
            else:
                _style_legend(ax.legend(loc="lower right", fontsize=7, framealpha=0.92))
                show_legend = False

        ax.set_title(self._t("response_title", mode=response_cut.label), pad=6, y=1.02, loc="left",
                      color=THEME["text_primary"], fontweight="bold")
        ax.set_xlabel(response_cut.x_label, color=THEME["text_secondary"])
        ax.set_ylabel(self._t("axis_gain"), labelpad=2, color=THEME["text_secondary"])
        ax.grid(True, alpha=THEME["grid_alpha"], color=THEME["grid_color"], linewidth=0.55)
        if show_legend:
            _style_legend(ax.legend(loc="lower right", fontsize=7, framealpha=0.92))

        response_psl_db = (
            metrics.elevation_psl_db
            if response_cut.mode == RESPONSE_MODE_ELEVATION
            else metrics.azimuth_psl_db
        )
        # PSL badge in lower-left corner
        ax.text(
            0.02,
            0.08,
            self._t("psl_label", mode=response_cut.label, value=response_psl_db),
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=9,
            color=THEME["text_primary"],
            bbox={
                "boxstyle": "round,pad=0.25",
                "facecolor": THEME["card_bg"],
                "edgecolor": THEME["card_border"],
                "alpha": 0.93,
                "linewidth": 0.7,
            },
        )

        return response_db, response_angles

    def _draw_response(
        self,
        mode: str,
        chart: ResponseChart,
        af_db: np.ndarray,
        azimuths: np.ndarray,
        elevations: np.ndarray,
        metrics: ArrayMetrics,
    ) -> None:
        """Draw a response chart (Az or El) and set up hover data."""
        response_cut = _response_cut_for_mode(
            af_db, azimuths, elevations, mode, self.language
        )
        response_db, response_angles = self._draw_response_common(chart.ax, response_cut, metrics)

        chart.hover_db = response_db
        chart.hover_angles = response_angles
        chart.hover_annotation = _new_response_hover_annotation(chart.ax)
        chart.hover_marker = chart.ax.scatter(
            [],
            [],
            marker="o",
            s=42,
            facecolors=THEME["selection_fill"],
            edgecolors=THEME["focus"],
            linewidths=1.2,
            zorder=8,
            clip_on=True,
        )
        chart.hover_marker.set_visible(False)

    # ── Notes helpers ─────────────────────────────────────────────────

    def _notes_parts(self, metrics: ArrayMetrics) -> list[str]:
        notes = []
        if metrics.duplicate_excess > 0:
            notes.append("存在重复虚拟通道")
        if metrics.azimuth_psl_db > -10.0:
            notes.append("建议加窗降低旁瓣")
        if metrics.elevation_ambiguity_level == "High":
            notes.append("俯仰模糊风险高")
        elif metrics.elevation_ambiguity_level == "Medium":
            notes.append("俯仰模糊风险中")
        return notes

    def _element_pattern_export_info(self) -> dict[str, object]:
        if self.element_pattern is None:
            return {"mode": "isotropic"}
        return {
            "mode": "loaded",
            "source": self.element_pattern.source_path,
            "angle_column": self.element_pattern.angle_column,
            "horizontal_column": self.element_pattern.horizontal_column,
            "elevation_column": self.element_pattern.elevation_column,
        }

    def _channel_pattern_export_info(self) -> dict[str, object]:
        current_channels = self._physical_channel_names()
        configured = []
        for channel_name in current_channels:
            pattern = self.channel_patterns.pattern_for(channel_name)
            if pattern.is_empty():
                continue
            configured.append(
                {
                    "channel": channel_name,
                    "amplitude_h": _series_table_label(pattern.amplitude_horizontal),
                    "amplitude_e": _series_table_label(pattern.amplitude_elevation),
                    "phase_h": _series_table_label(pattern.phase_horizontal),
                    "phase_e": _series_table_label(pattern.phase_elevation),
                }
            )
        return {
            "mode": "ideal" if not configured else "channel_patterns",
            "configured_channels": len(configured),
            "configured_series": sum(
                self.channel_patterns.pattern_for(channel).series_count()
                for channel in current_channels
            ),
            "channels": configured,
        }

    def _load_local_state(self) -> None:
        try:
            state = load_state()
            if not state:
                return
            if state.get("version") != LOCAL_STATE_VERSION:
                LOGGER.info("Ignoring unsupported local state version: %r", state.get("version"))
                return

            language = state.get("language")
            if language in SUPPORTED_LANGUAGES:
                self.language = str(language)
                self.language_var.set(LANGUAGE_LABELS[self.language])

            layout_dir = state.get("last_layout_dir")
            if isinstance(layout_dir, str) and layout_dir:
                self.last_layout_dir = Path(layout_dir)

            pattern_dir = state.get("last_pattern_dir")
            if isinstance(pattern_dir, str) and pattern_dir:
                self.last_pattern_dir = Path(pattern_dir)

            frequency = state.get("frequency_ghz")
            parsed_frequency = _parse_frequency_ghz(frequency)
            if parsed_frequency is not None:
                self._set_frequency_ghz(parsed_frequency)

            margin = state.get("ambiguity_margin_db")
            parsed_margin = _parse_margin_db(margin)
            if parsed_margin is not None:
                self._set_margin_db(parsed_margin)

            window = state.get("window")
            if isinstance(window, dict):
                geometry = _validated_window_geometry(window.get("geometry"))
                if geometry is not None:
                    self.root.geometry(geometry)
                window_state = window.get("state")
                if window_state == "zoomed":
                    self.root.after(
                        0,
                        lambda: self._restore_window_state("zoomed"),
                    )

            layout = state.get("layout")
            if layout is not None:
                self.elements = self._elements_from_layout_config(layout)

            dictionary_state = state.get("dbf_dictionary")
            if isinstance(dictionary_state, dict):
                mode = str(dictionary_state.get("mode", DBF_DICT_IDEAL))
                if mode == DBF_DICT_CHANNEL_PATTERN_ZERO_REF:
                    mode = DBF_DICT_CHANNEL_PATTERN
                elif mode not in {
                    DBF_DICT_IDEAL,
                    DBF_DICT_IDEAL_REVERSED,
                    DBF_DICT_CHANNEL_PATTERN,
                    DBF_DICT_CUSTOM,
                }:
                    mode = DBF_DICT_IDEAL
                custom_phase_reversed = bool(
                    dictionary_state.get("custom_phase_reversed", False)
                )
                custom_zero_phase_calibrated = bool(
                    dictionary_state.get("custom_zero_phase_calibrated", False)
                )
                custom_azimuth_table = None
                custom_elevation_table = None
                legacy_custom_path = dictionary_state.get("custom_path")
                custom_azimuth_path = dictionary_state.get("custom_azimuth_path")
                custom_elevation_path = dictionary_state.get("custom_elevation_path")
                if not isinstance(custom_azimuth_path, str) or not custom_azimuth_path:
                    custom_azimuth_path = legacy_custom_path
                if not isinstance(custom_elevation_path, str) or not custom_elevation_path:
                    custom_elevation_path = legacy_custom_path
                if mode == DBF_DICT_CUSTOM:
                    for axis_name, custom_path in (
                        ("azimuth", custom_azimuth_path),
                        ("elevation", custom_elevation_path),
                    ):
                        if not isinstance(custom_path, str) or not custom_path:
                            continue
                        try:
                            table = load_dbf_dictionary_table(
                                custom_path, self.current_array()
                            )
                        except Exception:
                            LOGGER.warning(
                                "Failed to restore %s DBF dictionary from %s",
                                axis_name,
                                custom_path,
                            )
                            mode = DBF_DICT_IDEAL
                            continue
                        if axis_name == "azimuth":
                            custom_azimuth_table = table
                        else:
                            custom_elevation_table = table
                    if (
                        custom_azimuth_table is None
                        and custom_elevation_table is None
                    ):
                        mode = DBF_DICT_IDEAL
                self.dbf_dictionary = DbfDictionaryConfig(
                    mode=mode,
                    custom_azimuth_table=custom_azimuth_table,
                    custom_elevation_table=custom_elevation_table,
                    custom_phase_reversed=custom_phase_reversed,
                    custom_zero_phase_calibrated=custom_zero_phase_calibrated,
                )

            pattern_path = state.get("element_pattern_path")
            if isinstance(pattern_path, str) and pattern_path:
                try:
                    pattern = load_element_pattern(pattern_path)
                    self.element_pattern = pattern
                    self.pattern_status.set(
                        self._t("pattern_element_summary", name=pattern.name)
                    )
                    if getattr(self, "pattern_canvas", None) is not None:
                        self.pattern_canvas.itemconfig(
                            self.pattern_dot, fill=THEME["secondary_accent"]
                        )
                    LOGGER.info("Restored element pattern from %s", pattern_path)
                except Exception:
                    LOGGER.warning("Failed to restore element pattern from %s", pattern_path)

            LOGGER.info("Loaded local state from %s", state_path())
        except Exception:
            LOGGER.exception("Failed to load local state from %s", state_path())

    def _restore_window_state(self, window_state: str) -> None:
        try:
            self.root.state(window_state)
        except tk.TclError:
            LOGGER.warning("Failed to restore window state: %s", window_state)

    def _window_state_config(self) -> dict[str, str]:
        self.root.update_idletasks()
        window_state = self.root.state()
        if window_state == "iconic":
            window_state = "normal"
        return {
            "geometry": self.root.winfo_geometry(),
            "state": window_state,
        }

    def _save_local_state(self) -> None:
        state = {
            "version": LOCAL_STATE_VERSION,
            "language": self.language,
            "last_layout_dir": str(self.last_layout_dir),
            "last_pattern_dir": str(self.last_pattern_dir),
            "frequency_ghz": _format_frequency_ghz(self.current_frequency_ghz()),
            "ambiguity_margin_db": _format_margin_db(self.current_margin_db()),
            "dbf_dictionary": {
                "mode": self.dbf_dictionary.mode,
                "custom_azimuth_path": (
                    self.dbf_dictionary.custom_azimuth_table.source_path
                    if self.dbf_dictionary.custom_azimuth_table is not None
                    else ""
                ),
                "custom_elevation_path": (
                    self.dbf_dictionary.custom_elevation_table.source_path
                    if self.dbf_dictionary.custom_elevation_table is not None
                    else ""
                ),
                "custom_phase_reversed": self.dbf_dictionary.custom_phase_reversed,
                "custom_zero_phase_calibrated": (
                    self.dbf_dictionary.custom_zero_phase_calibrated
                ),
            },
            "layout": self._layout_coordinates_config(),
            "window": self._window_state_config(),
        }
        if self.element_pattern is not None and self.element_pattern.source_path:
            state["element_pattern_path"] = str(self.element_pattern.source_path)
        save_state(state)
        LOGGER.info("Saved local state to %s", state_path())

    def on_close(self) -> None:
        try:
            self.stop_dbf_scan_animation(restore_response=False)
            self.stop_dbf2d_animation(update_status=False)
            self._save_local_state()
        except Exception:
            LOGGER.exception("Failed to save local state")
        self.root.destroy()

    # ── Event handlers ────────────────────────────────────────────────

    def on_press(self, event) -> None:  # noqa: ANN001
        if event.inaxes != self.physical_ax or event.xdata is None or event.ydata is None:
            return
        internal_x = _to_internal_half_lambda(event.xdata)
        internal_y = _to_internal_half_lambda(event.ydata)

        if self.delete_mode:
            element = self._nearest_element(internal_x, internal_y)
            if element is None:
                self.status.set(self._t("delete_click_element"))
                return
            self._delete_element(element)
            return

        self.dragging = self._nearest_element(internal_x, internal_y)
        if self.dragging is not None:
            self.drag_start_snapshot = self._capture_layout_snapshot()
            x_limits = tuple(float(value) for value in self.physical_ax.get_xlim())
            y_limits = tuple(float(value) for value in self.physical_ax.get_ylim())
            self.drag_axis_limits = (x_limits, y_limits)
            self.drag_bounds = (
                _to_internal_half_lambda(x_limits[0]),
                _to_internal_half_lambda(x_limits[1]),
                _to_internal_half_lambda(y_limits[0]),
                _to_internal_half_lambda(y_limits[1]),
            )
            self.selected_element = self.dragging
            self.status.set(
                self._t(
                    "selected_element",
                    element=self.dragging.name,
                    x=self.dragging.x * DISPLAY_SCALE_LAMBDA,
                    y=self.dragging.y * DISPLAY_SCALE_LAMBDA,
                )
            )
            self._draw_physical_array()
            self.phys_canvas.draw()
        elif self.selected_element is not None:
            self.drag_start_snapshot = None
            self.selected_element = None
            self.status.set(self._t("select_element_hint"))
            self._draw_physical_array()
            self.phys_canvas.draw()
        else:
            self.drag_start_snapshot = None

    def on_motion(self, event) -> None:  # noqa: ANN001
        if self.dbf_drag_mode is not None:
            self._set_chart_cursor(
                self._chart_for_dbf_mode(self.dbf_drag_mode), "hand2"
            )
            self._drag_dbf_true_line(event)
            return

        if self.dragging is not None:
            if event.x is None or event.y is None:
                return
            display_x, display_y = self.physical_ax.transData.inverted().transform(
                (event.x, event.y)
            )
            internal_x = _to_internal_half_lambda(float(display_x))
            internal_y = _to_internal_half_lambda(float(display_y))
            if self.drag_bounds is not None:
                min_x, max_x, min_y, max_y = self.drag_bounds
                internal_x = _clip_to_bounds(internal_x, min_x, max_x)
                internal_y = _clip_to_bounds(internal_y, min_y, max_y)
                internal_x = _snap_to_grid_inside(internal_x, min_x, max_x)
                internal_y = _snap_to_grid_inside(internal_y, min_y, max_y)
            else:
                internal_x = snap_to_grid(internal_x)
                internal_y = snap_to_grid(internal_y)
            self.dragging.x = internal_x
            self.dragging.y = internal_y
            self.status.set(
                self._t(
                    "snap_element",
                    element=self.dragging.name,
                    x=self.dragging.x * DISPLAY_SCALE_LAMBDA,
                    y=self.dragging.y * DISPLAY_SCALE_LAMBDA,
                )
            )
            self._draw_physical_array()
            self.phys_canvas.draw()
            return

        self._update_physical_hover(event)
        self._update_virtual_hover(event)
        self._update_response_cursor(event, self.az_chart)
        self._update_response_cursor(event, self.el_chart)
        self._update_response_hover(
            event, self.az_chart, _dbf_short_label("azimuth", self.language)
        )
        self._update_response_hover(
            event, self.el_chart, _dbf_short_label("elevation", self.language)
        )

    def on_release(self, event) -> None:  # noqa: ANN001
        if self.dragging is not None:
            if self.drag_bounds is not None:
                min_x, max_x, min_y, max_y = self.drag_bounds
                self.dragging.x = _snap_to_grid_inside(
                    self.dragging.x, min_x, max_x
                )
                self.dragging.y = _snap_to_grid_inside(
                    self.dragging.y, min_y, max_y
                )
            else:
                self.dragging.x = snap_to_grid(self.dragging.x)
                self.dragging.y = snap_to_grid(self.dragging.y)
            self.status.set(
                self._t(
                    "placed_element",
                    element=self.dragging.name,
                    x=self.dragging.x * DISPLAY_SCALE_LAMBDA,
                    y=self.dragging.y * DISPLAY_SCALE_LAMBDA,
                )
            )
            current_snapshot = self._capture_layout_snapshot()
            if (
                self.drag_start_snapshot is not None
                and self.drag_start_snapshot != current_snapshot
            ):
                self._push_undo_snapshot(self.drag_start_snapshot)
            self.dragging = None
            self.drag_bounds = None
            self.drag_axis_limits = None
            self.drag_start_snapshot = None
            self.generate_virtual_array()

    def on_arrow_key(self, event) -> str | None:
        if _event_widget_is_text_input(event):
            return None
        if self.selected_element is None:
            return "break"

        dx = 0.0
        dy = 0.0
        if event.keysym == "Left":
            dx = -GRID_STEP
        elif event.keysym == "Right":
            dx = GRID_STEP
        elif event.keysym == "Up":
            dy = GRID_STEP
        elif event.keysym == "Down":
            dy = -GRID_STEP
        else:
            return "break"

        new_x = snap_to_grid(self.selected_element.x + dx)
        new_y = snap_to_grid(self.selected_element.y + dy)
        if new_x == self.selected_element.x and new_y == self.selected_element.y:
            return "break"

        self._push_undo_snapshot()
        self.selected_element.x = new_x
        self.selected_element.y = new_y
        self.generate_virtual_array()
        self.status.set(
            self._t(
                "selected_element",
                element=self.selected_element.name,
                x=self.selected_element.x * DISPLAY_SCALE_LAMBDA,
                y=self.selected_element.y * DISPLAY_SCALE_LAMBDA,
            )
        )
        return "break"

    def on_delete_key(self, event) -> str | None:  # noqa: ANN001
        if _event_widget_is_text_input(event):
            return None
        self.delete_selected_element()
        return "break"

    # ── Hover logic ───────────────────────────────────────────────────

    def _update_virtual_hover(self, event) -> None:  # noqa: ANN001
        if self.virtual_hover_annotation is None:
            return
        if (
            event.inaxes != self.virtual_ax
            or event.xdata is None
            or event.ydata is None
            or len(self.virtual_hover_xy) == 0
        ):
            needs_redraw = False
            if self.virtual_hover_annotation.get_visible():
                self.virtual_hover_annotation.set_visible(False)
                needs_redraw = True
            if self.virtual_hover_marker is not None and self.virtual_hover_marker.get_visible():
                self.virtual_hover_marker.set_visible(False)
                needs_redraw = True
            if needs_redraw:
                self.virt_canvas.draw_idle()
            return

        x_span = max(abs(np.diff(self.virtual_ax.get_xlim())[0]), 1.0)
        y_span = max(abs(np.diff(self.virtual_ax.get_ylim())[0]), 1.0)
        normalized_distance = np.hypot(
            (self.virtual_hover_xy[:, 0] - event.xdata) / x_span,
            (self.virtual_hover_xy[:, 1] - event.ydata) / y_span,
        )
        index = int(np.argmin(normalized_distance))
        if normalized_distance[index] > 0.018:
            needs_redraw = False
            if self.virtual_hover_annotation.get_visible():
                self.virtual_hover_annotation.set_visible(False)
                needs_redraw = True
            if self.virtual_hover_marker is not None and self.virtual_hover_marker.get_visible():
                self.virtual_hover_marker.set_visible(False)
                needs_redraw = True
            if needs_redraw:
                self.virt_canvas.draw_idle()
            return

        xy = self.virtual_hover_xy[index]
        if self.virtual_hover_marker is not None:
            count = (
                int(self.virtual_hover_counts[index])
                if self.virtual_hover_counts.size > index
                else 1
            )
            self.virtual_hover_marker.set_offsets([xy])
            self.virtual_hover_marker.set_sizes([210 + min(max(count - 1, 0), 6) * 36])
            self.virtual_hover_marker.set_visible(True)
        self.virtual_hover_annotation.xy = (xy[0], xy[1])
        self.virtual_hover_annotation.set_text(self.virtual_hover_text[index])
        self.virtual_hover_annotation.set_visible(True)
        self.virt_canvas.draw_idle()

    def _update_physical_hover(self, event) -> None:  # noqa: ANN001
        if self.physical_hover_annotation is None:
            return
        if event.inaxes != self.physical_ax or event.xdata is None or event.ydata is None:
            needs_redraw = False
            if self.physical_hover_annotation.get_visible():
                self.physical_hover_annotation.set_visible(False)
                needs_redraw = True
            if self.physical_hover_marker is not None and self.physical_hover_marker.get_visible():
                self.physical_hover_marker.set_visible(False)
                needs_redraw = True
            if needs_redraw:
                self.phys_canvas.draw_idle()
            return
        if not self.elements:
            needs_redraw = False
            if self.physical_hover_annotation.get_visible():
                self.physical_hover_annotation.set_visible(False)
                needs_redraw = True
            if self.physical_hover_marker is not None and self.physical_hover_marker.get_visible():
                self.physical_hover_marker.set_visible(False)
                needs_redraw = True
            if needs_redraw:
                self.phys_canvas.draw_idle()
            return

        internal_x = _to_internal_half_lambda(event.xdata)
        internal_y = _to_internal_half_lambda(event.ydata)
        distances = np.array(
            [
                (element.x - internal_x) ** 2 + (element.y - internal_y) ** 2
                for element in self.elements
            ],
            dtype=float,
        )
        index = int(np.argmin(distances))
        if distances[index] > 2.0:
            needs_redraw = False
            if self.physical_hover_annotation.get_visible():
                self.physical_hover_annotation.set_visible(False)
                needs_redraw = True
            if self.physical_hover_marker is not None and self.physical_hover_marker.get_visible():
                self.physical_hover_marker.set_visible(False)
                needs_redraw = True
            if needs_redraw:
                self.phys_canvas.draw_idle()
            return

        element = self.elements[index]
        display_x = element.x * DISPLAY_SCALE_LAMBDA
        display_y = element.y * DISPLAY_SCALE_LAMBDA
        if self.physical_hover_marker is not None:
            self.physical_hover_marker.set_offsets([[display_x, display_y]])
            self.physical_hover_marker.set_visible(True)
        self.physical_hover_annotation.xy = (display_x, display_y)
        self.physical_hover_annotation.set_text(
            f"{element.name}\nx = {display_x:g} λ\ny = {display_y:g} λ"
        )
        self.physical_hover_annotation.set_visible(True)
        self.phys_canvas.draw_idle()

    def _hide_dbf2d_hover(self) -> None:
        if self.dbf2d_hover_annotation is None:
            return
        needs_redraw = False
        if self.dbf2d_hover_annotation.get_visible():
            self.dbf2d_hover_annotation.set_visible(False)
            needs_redraw = True
        if (
            self.dbf2d_hover_marker is not None
            and self.dbf2d_hover_marker.get_visible()
        ):
            self.dbf2d_hover_marker.set_visible(False)
            needs_redraw = True
        if needs_redraw and self.dbf2d_canvas is not None:
            self.dbf2d_canvas.draw_idle()

    def _update_dbf2d_hover(self, event) -> None:  # noqa: ANN001
        if self.dbf2d_hover_annotation is None:
            return
        if (
            event.inaxes != self.dbf2d_ax
            or event.xdata is None
            or event.ydata is None
            or self.dbf2d_hover_azimuths.size == 0
            or self.dbf2d_hover_elevations.size == 0
            or self.dbf2d_hover_db.size == 0
        ):
            self._hide_dbf2d_hover()
            return

        az_index = int(np.argmin(np.abs(self.dbf2d_hover_azimuths - event.xdata)))
        el_index = int(np.argmin(np.abs(self.dbf2d_hover_elevations - event.ydata)))
        if (
            el_index >= self.dbf2d_hover_db.shape[0]
            or az_index >= self.dbf2d_hover_db.shape[1]
        ):
            self._hide_dbf2d_hover()
            return

        azimuth = float(self.dbf2d_hover_azimuths[az_index])
        elevation = float(self.dbf2d_hover_elevations[el_index])
        gain = float(self.dbf2d_hover_db[el_index, az_index])
        if self.dbf2d_hover_marker is not None:
            self.dbf2d_hover_marker.set_offsets([[azimuth, elevation]])
            self.dbf2d_hover_marker.set_visible(True)

        self.dbf2d_hover_annotation.xy = (float(event.xdata), float(event.ydata))
        x_low, x_high = self.dbf2d_ax.get_xlim()
        y_low, y_high = self.dbf2d_ax.get_ylim()
        x_frac = (float(event.xdata) - x_low) / (x_high - x_low) if x_high != x_low else 0.5
        y_frac = (float(event.ydata) - y_low) / (y_high - y_low) if y_high != y_low else 0.5
        x_offset = -12 if x_frac > 0.70 else 12
        y_offset = -30 if y_frac > 0.62 else 14
        self.dbf2d_hover_annotation.set_position((x_offset, y_offset))
        self.dbf2d_hover_annotation.set_ha("right" if x_offset < 0 else "left")
        self.dbf2d_hover_annotation.set_va("top" if y_offset < 0 else "bottom")
        self.dbf2d_hover_annotation.set_text(
            self._t("dbf2d_hover", az=azimuth, el=elevation, gain=gain)
        )
        self.dbf2d_hover_annotation.set_visible(True)
        if self.dbf2d_canvas is not None:
            self.dbf2d_canvas.draw_idle()

    def _update_response_hover(
        self, event, chart: ResponseChart, label: str  # noqa: ANN001
    ) -> None:
        """Update hover tooltip for a response chart (Az or El)."""
        if chart.hover_annotation is None:
            return
        if (
            event.inaxes != chart.ax
            or event.xdata is None
            or event.ydata is None
            or chart.hover_db.size == 0
        ):
            needs_redraw = False
            if chart.hover_annotation.get_visible():
                chart.hover_annotation.set_visible(False)
                needs_redraw = True
            if chart.hover_marker is not None and chart.hover_marker.get_visible():
                chart.hover_marker.set_visible(False)
                needs_redraw = True
            if needs_redraw:
                chart.canvas.draw_idle()
            return

        angle_index = int(np.argmin(np.abs(chart.hover_angles - event.xdata)))
        angle = float(chart.hover_angles[angle_index])
        gain = float(chart.hover_db[angle_index])
        if chart.hover_marker is not None:
            chart.hover_marker.set_offsets([[angle, gain]])
            chart.hover_marker.set_visible(True)
        chart.hover_annotation.xy = (float(event.xdata), float(event.ydata))
        x_low, x_high = chart.ax.get_xlim()
        y_low, y_high = chart.ax.get_ylim()
        x_frac = (float(event.xdata) - x_low) / (x_high - x_low) if x_high != x_low else 0.5
        y_frac = (float(event.ydata) - y_low) / (y_high - y_low) if y_high != y_low else 0.5
        x_offset = -12 if x_frac > 0.72 else 12
        y_offset = -28 if y_frac > 0.60 else 14
        chart.hover_annotation.set_position((x_offset, y_offset))
        chart.hover_annotation.set_ha("right" if x_offset < 0 else "left")
        chart.hover_annotation.set_va("top" if y_offset < 0 else "bottom")
        chart.hover_annotation.set_text(
            f"{label} = {angle:.1f}°\n{self._t('gain_value', value=gain)}"
        )
        chart.hover_annotation.set_visible(True)
        chart.canvas.draw_idle()

    def _hide_response_hover(self, chart: ResponseChart) -> None:
        if chart.hover_annotation is None:
            return
        needs_redraw = False
        if chart.hover_annotation.get_visible():
            chart.hover_annotation.set_visible(False)
            needs_redraw = True
        if chart.hover_marker is not None and chart.hover_marker.get_visible():
            chart.hover_marker.set_visible(False)
            needs_redraw = True
        if needs_redraw:
            chart.canvas.draw_idle()

    def _nearest_element(self, x: float, y: float) -> EditableElement | None:
        if not self.elements:
            return None
        distances = [
            ((element.x - x) ** 2 + (element.y - y) ** 2, element)
            for element in self.elements
        ]
        distance, element = min(distances, key=lambda item: item[0])
        return element if distance <= 4.0 else None


# ═══════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════
def main() -> None:
    log_path = configure_logging()
    install_excepthook()
    LOGGER.info("Starting MIMO Array Visualizer")
    root = tk.Tk()
    root.report_callback_exception = _show_unhandled_tk_exception
    root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
    root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
    root.resizable(True, True)
    LOGGER.info("Log file: %s", log_path)
    app = VirtualArrayGui(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    try:
        root.mainloop()
    finally:
        LOGGER.info("MIMO Array Visualizer exited")


if __name__ == "__main__":
    main()
