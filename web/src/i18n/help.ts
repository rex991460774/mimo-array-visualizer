import type { Language } from "../state/store";

export interface HelpSection {
  id: string;
  title: string;
  paragraphs?: string[];
  steps?: string[];
  bullets?: string[];
}

export const SHORTCUTS: { keys: string[]; zh: string; en: string; ja: string }[] = [
  { keys: ["Ctrl", "Z"], zh: "撤销阵列编辑", en: "Undo layout edit", ja: "配置編集を元に戻す" },
  { keys: ["Ctrl", "Y"], zh: "重做阵列编辑（也可 Ctrl+Shift+Z）", en: "Redo layout edit (or Ctrl+Shift+Z)", ja: "配置編集をやり直す（Ctrl+Shift+Z も可）" },
  { keys: ["Ctrl", "S"], zh: "保存到项目库", en: "Save to the project library", ja: "プロジェクトライブラリに保存" },
  { keys: ["Ctrl", "O"], zh: "导入阵面 JSON / 项目包", en: "Import array JSON / bundle", ja: "配置 JSON / パッケージを読み込む" },
  { keys: ["Ctrl", "E"], zh: "导出阵面 JSON", en: "Export array JSON", ja: "配置 JSON を書き出す" },
  { keys: ["1", "–", "4"], zh: "切换视图（阵列 / 1D / 2D / 测角）", en: "Switch view (array / 1D / 2D / angle)", ja: "表示切替（配置 / 1D / 2D / 測角）" },
  { keys: ["Delete"], zh: "删除选中通道", en: "Delete the selected channel", ja: "選択チャネルを削除" },
  { keys: ["←", "→", "↑", "↓"], zh: "微调选中通道 0.5 λ（Shift：2.5 λ）", en: "Nudge selection by 0.5 λ (Shift: 2.5 λ)", ja: "選択を 0.5 λ 移動（Shift：2.5 λ）" },
  { keys: ["Esc"], zh: "取消拖动 / 退出删除模式 / 清除选择", en: "Cancel drag / exit delete mode / clear selection", ja: "ドラッグ取消 / 削除モード終了 / 選択解除" },
];

const zh: HelpSection[] = [
  {
    id: "start",
    title: "快速开始",
    steps: [
      "在「阵列布局」中添加、拖动或用「自动排阵」生成 Tx/Rx，坐标统一以 λ 表示，松开后吸附到 λ/2 网格。",
      "在顶部输入工作频率（GHz）和竞争峰裕量（dB），按 Enter 或移出输入框生效。",
      "右侧「阵列概览」实时显示通道数、虚拟通道利用率、口径和分辨率，以及方位/俯仰的测角评估。",
      "切换到「1D DBF」播放或拖动真实角，确认峰值是否连续跟随；「测角性能」给出逐帧误差和竞争峰裕量。",
      "满意后点击「保存」存入项目库，或「导出」为阵面 JSON / 项目包，再用「性能报告」生成 PDF。",
    ],
  },
  {
    id: "layout",
    title: "阵列编辑",
    bullets: [
      "▲ 红色为 Tx，● 蓝色为 Rx。拖动时保持抓取偏移，虚拟阵列同步预览，松开才吸附网格并刷新计算。",
      "删除模式下点击通道即删除；每种通道至少保留 1 个，最多 16 个。编辑后通道按 (x, y) 自动重新编号。",
      "选中通道后可在面板底部精确输入 X/Y，或打开「坐标表」批量编辑并查看 mm 值（随频率换算）。",
      "滚轮缩放、拖动空白处平移，「适配视图」恢复自动缩放。撤销/重做最多保留 50 步。",
    ],
  },
  {
    id: "virtual",
    title: "虚拟阵列与概览",
    bullets: [
      "虚拟位置 = Tx 位置 + Rx 位置。黄色为重复点（数字为重合数量），悬停查看 Tx-Rx 组合。",
      "选中某个物理通道时，与其相关的虚拟点高亮，其余变暗，便于检查单个通道的贡献。",
      "「阵列方向图指标」折叠区给出 PSL、ISLR、3 dB 波束宽度、栅瓣等指标；导入单元方向图后按方向图加权。",
    ],
  },
  {
    id: "dbf1d",
    title: "1D DBF 角谱",
    paragraphs: [
      "每个方向有 181 帧，模拟真实角 −90°～+90°（1° 步进）的信号与 DBF 字典的归一化相关。",
    ],
    bullets: [
      "「播放」从当前帧开始，播放到 +90° 自动停止；拖动滑条或点击图中任意位置跳转到该真实角。",
      "黄色竖线为真实角，红色 × 为峰值角；底部读数给出误差、竞争峰裕量和峰质量标记。",
      "顶部「角谱显示」可在 dB 与相关系数模值之间切换，两者是同一计算结果的不同显示形式。",
    ],
  },
  {
    id: "dbf2d",
    title: "2D DBF 热图",
    bullets: [
      "点击热图设定真实方位/俯仰；两个方向可分别扫描，也可同时扫描。",
      "白色十字为真实角，蓝色 × 为峰值；顶部读数给出峰值位置与偏差。",
      "2D 计算在服务器端完成并预取后续帧，首次进入或修改阵列后需要短暂计算。",
    ],
  },
  {
    id: "angle",
    title: "测角性能",
    bullets: [
      "误差图按「不模糊范围」（浅蓝底色）内的误差自适应纵轴；范围外的折返误差可能被裁切。",
      "裕量图中红色虚线为竞争峰裕量阈值；无竞争峰的帧画在图顶部。",
      "「导出误差图 PNG」生成与报告一致的出版级图片。",
    ],
  },
  {
    id: "dictionary",
    title: "DBF 字典",
    bullets: [
      "理想几何：按阵列几何生成导向矢量并自动选择相位符号；理想反向相位用于核对相位约定。",
      "通道幅相校准：使用已导入的通道幅相数据，并以 0° 方向为相位参考。",
      "导入字典：上传 CSV/XLSX，可分别指定方位与俯仰；列可对应虚拟通道（Tx×Rx）或物理通道（Tx + Rx）。值可以是相位（度）或复数（1+2j、2∠40）。",
      "预览区显示字典相位矩阵和质量提示（竞争峰模糊行、零范数行、非近邻有效秩），仅供参考。",
    ],
  },
  {
    id: "patterns",
    title: "通道幅相与单元方向图",
    bullets: [
      "汇总文件：HFSS 导出的 CSV/TSV/XLSX，角度列之后的数据列按通道顺序从左到右对应；列名包含通道名时按名称匹配。",
      "也可以在表格中为单个通道导入某一项（幅度/相位 × 水平/俯仰）。相位以 0° 行做校准。",
      "幅度支持 dB 实数或复数（按 20·log10|z| 换算）；相位支持度数或复数（取相角）。",
      "单元方向图用于阵列方向图指标，可交换 H/V；没有独立俯仰列时俯仰面复用水平面。",
    ],
  },
  {
    id: "files",
    title: "文件、报告与项目库",
    bullets: [
      "阵面 JSON 与桌面版格式兼容（version 1，单位 λ），导出时附带评估信息。",
      "项目包（.mimo.zip）包含项目配置和全部导入的数据文件，适合在不同服务器之间迁移。",
      "项目库保存在服务器数据目录，同一服务器的用户都能看到；浏览器也会自动保留当前草稿。",
      "性能报告在服务器端生成多页 PDF，可选附带 CSV/JSON 可复现数据包，生成期间可以继续编辑。",
    ],
  },
];

const en: HelpSection[] = [
  {
    id: "start",
    title: "Quick start",
    steps: [
      "In Array layout, add or drag Tx/Rx channels or use Auto layout. Coordinates are in λ and snap to the λ/2 grid on release.",
      "Enter the frequency (GHz) and the competitor-peak margin (dB) in the top bar; press Enter or leave the field to apply.",
      "The Overview on the right shows channel counts, virtual utilization, aperture, resolution and the azimuth/elevation angle evaluation.",
      "Open 1D DBF to play or drag the true angle and check that the peak follows; Angle performance shows per-frame error and margin.",
      "Save to the project library, export array JSON or a project bundle, and use Report to generate a PDF.",
    ],
  },
  {
    id: "layout",
    title: "Editing the array",
    bullets: [
      "Red ▲ marks Tx, blue ● marks Rx. Dragging keeps the grab offset and previews the virtual array; it snaps and recomputes on release.",
      "In delete mode, click a channel to remove it. Each kind needs 1 to 16 channels. Channels are renumbered by (x, y) after edits.",
      "Edit X/Y of the selection in the panel footer, or open Coordinates for a table with mm values (from the frequency).",
      "Scroll to zoom, drag the background to pan, Fit view restores auto-zoom. Undo/redo keeps 50 steps.",
    ],
  },
  {
    id: "virtual",
    title: "Virtual array and overview",
    bullets: [
      "Virtual position = Tx + Rx. Amber points are duplicates (the number is the multiplicity); hover to see the Tx-Rx pairs.",
      "Selecting a physical channel highlights the virtual points it forms and dims the rest.",
      "The Array pattern metrics section lists PSL, ISLR, 3 dB beamwidth and grating lobes; an imported element pattern weights them.",
    ],
  },
  {
    id: "dbf1d",
    title: "1D DBF spectra",
    paragraphs: [
      "Each axis has 181 frames simulating true angles from −90° to +90° (1° steps), correlated with the DBF dictionary.",
    ],
    bullets: [
      "Play starts from the current frame and stops at +90°. Drag the slider or click anywhere in the chart to jump.",
      "The amber line is the true angle and the red × is the peak; the readout shows error, peak margin and peak-quality flags.",
      "Spectrum display switches between dB and correlation magnitude; both are views of the same calculation.",
    ],
  },
  {
    id: "dbf2d",
    title: "2D DBF heatmap",
    bullets: [
      "Click the heatmap to set the true azimuth/elevation; scan the axes separately or together.",
      "The white cross is the true angle, the blue × the peak; the header shows peak position and offset.",
      "2D spectra are computed on the server and prefetched during playback.",
    ],
  },
  {
    id: "angle",
    title: "Angle performance",
    bullets: [
      "The error chart scales to errors inside the no-fold range (shaded); folded errors outside it may clip.",
      "The red dashed line in the margin chart is the margin threshold; frames without a competitor are drawn at the top.",
      "Export error PNG renders the publication-quality image used in reports.",
    ],
  },
  {
    id: "dictionary",
    title: "DBF dictionary",
    bullets: [
      "Ideal geometric builds steering vectors from the geometry with automatic sign selection; Ideal reversed phase checks conventions.",
      "Channel amp/phase uses the imported channel data, phase-referenced to 0°.",
      "Imported loads CSV/XLSX for azimuth and/or elevation; columns map to virtual (Tx×Rx) or physical (Tx + Rx) channels. Values may be phase in degrees or complex (1+2j, 2∠40).",
      "The preview shows the dictionary phase matrix and an advisory quality note.",
    ],
  },
  {
    id: "patterns",
    title: "Channel amp/phase and element pattern",
    bullets: [
      "Summary files are HFSS CSV/TSV/XLSX exports; data columns after the angle column map to channels left to right, or by name.",
      "You can also import one slot (amplitude/phase × horizontal/elevation) for a single channel. Phase is calibrated to the 0° row.",
      "Amplitude accepts dB or complex values (20·log10|z|); phase accepts degrees or complex values (angle).",
      "The element pattern weights the array-pattern metrics; swap H/V if needed. Without an elevation column the horizontal cut is reused.",
    ],
  },
  {
    id: "files",
    title: "Files, reports and the library",
    bullets: [
      "Array JSON is compatible with the desktop tool (version 1, unit λ) and includes an evaluation block on export.",
      "A project bundle (.mimo.zip) contains the project and all imported data files, for moving between servers.",
      "The project library lives in the server data directory and is shared by its users; the browser also keeps your draft.",
      "Reports are rendered on the server as multi-page PDFs with an optional CSV/JSON reproducibility package.",
    ],
  },
];

const ja: HelpSection[] = [
  {
    id: "start",
    title: "クイックスタート",
    steps: [
      "「アレイ配置」で Tx/Rx を追加・ドラッグするか自動配置を使います。座標は λ 単位で、離すと λ/2 グリッドにスナップします。",
      "上部で周波数（GHz）と競合ピークマージン（dB）を入力し、Enter またはフォーカス移動で確定します。",
      "右側の「アレイ概要」にチャネル数、仮想チャネル利用率、開口、分解能、方位/仰角の測角評価が表示されます。",
      "「1D DBF」で真の角度を再生・ドラッグしてピーク追従を確認し、「測角性能」でフレームごとの誤差とマージンを確認します。",
      "プロジェクトライブラリに保存するか、配置 JSON / パッケージを書き出し、「性能レポート」で PDF を生成します。",
    ],
  },
  {
    id: "layout",
    title: "アレイ編集",
    bullets: [
      "赤 ▲ が Tx、青 ● が Rx です。ドラッグ中はつかみ位置を保ったまま仮想アレイをプレビューし、離すとスナップして再計算します。",
      "削除モードではチャネルをクリックで削除します。各種 1〜16 個。編集後は (x, y) 順に番号が振り直されます。",
      "選択チャネルの X/Y はパネル下部で直接入力でき、「座標表」では mm 値（周波数から換算）も確認できます。",
      "ホイールでズーム、背景ドラッグでパン、「全体表示」で自動ズームに戻ります。元に戻す/やり直しは 50 手まで。",
    ],
  },
  {
    id: "virtual",
    title: "仮想アレイと概要",
    bullets: [
      "仮想位置 = Tx + Rx。黄色は重複点（数字は重なり数）で、ホバーで Tx-Rx の組を確認できます。",
      "物理チャネルを選択すると、そのチャネルが作る仮想点が強調表示されます。",
      "「アレイパターン指標」に PSL、ISLR、3 dB ビーム幅、グレーティングローブを表示します。素子パターン読込時は重み付けされます。",
    ],
  },
  {
    id: "dbf1d",
    title: "1D DBF スペクトル",
    paragraphs: ["各軸 181 フレームで、真の角度 −90°〜+90°（1° 刻み）の信号と DBF 辞書の正規化相関を示します。"],
    bullets: [
      "再生は現在のフレームから始まり +90° で停止します。スライダーまたはグラフのクリックで移動できます。",
      "黄色の線が真の角度、赤い × がピークです。下部に誤差、競合ピークマージン、ピーク品質を表示します。",
      "スペクトル表示で dB と相関係数の振幅を切り替えられます。どちらも同じ計算結果の表示形式です。",
    ],
  },
  {
    id: "dbf2d",
    title: "2D DBF ヒートマップ",
    bullets: [
      "ヒートマップをクリックして真の方位/仰角を設定します。方位・仰角は個別または同時にスキャンできます。",
      "白い十字が真の角度、青い × がピークです。上部にピーク位置とずれを表示します。",
      "2D スペクトルはサーバーで計算し、再生中は先読みします。",
    ],
  },
  {
    id: "angle",
    title: "測角性能",
    bullets: [
      "誤差グラフは折り返しなし範囲（網掛け）内の誤差に合わせて縦軸を調整します。範囲外の折り返し誤差は切れることがあります。",
      "マージングラフの赤い破線がしきい値です。競合ピークのないフレームは上端に描画します。",
      "「誤差図 PNG を書き出す」でレポートと同じ品質の画像を出力します。",
    ],
  },
  {
    id: "dictionary",
    title: "DBF 辞書",
    bullets: [
      "理想幾何は形状からステアリングベクトルを生成し位相符号を自動選択します。理想逆位相は規約確認用です。",
      "チャネル振幅/位相校正は読み込んだチャネルデータを 0° 基準で使用します。",
      "読込辞書は CSV/XLSX を方位・仰角ごとに読み込みます。列は仮想（Tx×Rx）または物理（Tx + Rx）チャネルに対応します。値は位相（度）または複素数（1+2j、2∠40）です。",
      "プレビューに辞書位相行列と参考用の品質表示を示します。",
    ],
  },
  {
    id: "patterns",
    title: "チャネル振幅/位相と素子パターン",
    bullets: [
      "サマリーファイルは HFSS の CSV/TSV/XLSX 出力です。角度列以降の列を左から順に、または名前でチャネルに対応させます。",
      "表から単一チャネルの 1 項目（振幅/位相 × 水平/仰角）も読み込めます。位相は 0° 行で校正されます。",
      "振幅は dB または複素数（20·log10|z|）、位相は度または複素数（偏角）に対応します。",
      "素子パターンはアレイパターン指標の重み付けに使われ、H/V を入れ替えられます。",
    ],
  },
  {
    id: "files",
    title: "ファイル、レポート、ライブラリ",
    bullets: [
      "配置 JSON はデスクトップ版と互換（version 1、単位 λ）で、書き出し時に評価情報を含みます。",
      "プロジェクトパッケージ（.mimo.zip）は設定と読み込んだデータファイルをすべて含み、サーバー間の移行に使えます。",
      "プロジェクトライブラリはサーバーのデータディレクトリに保存され、利用者間で共有されます。ブラウザも下書きを保持します。",
      "レポートはサーバーで複数ページの PDF として生成され、CSV/JSON の再現用データを含められます。",
    ],
  },
];

export const HELP: Record<Language, HelpSection[]> = { zh, en, ja };
