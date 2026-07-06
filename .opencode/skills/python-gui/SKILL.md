---
name: python-gui
description: Tkinter + Matplotlib GUI patterns, THEME conventions, figure sizing, font handling for desktop Python apps
---
## Tkinter layout patterns

- 使用 `grid()` 做比例布局：`grid_columnconfigure(col, weight=N)` 控制列宽比
- 固定比例用 `place()` + `<Configure>` 事件（grid weight 受内容 min size 干扰时）
- `ttk.Notebook` 做多子页，`ttk.PanedWindow` 做可拖拽分割，但用户已明确不要拖拽线
- `ttk.LabelFrame` 做分组卡片，`ttk.Frame(padding=(L,T,R,B))` 控制内边距
- 面板间距统一：左右面板内侧 padding 各 2px，总间隙 4px
- `TkDefaultFont` / `TkFixedFont` 跨平台系统字体
- macOS Tk 使用 Cocoa 后端，`geometry("WxH")` 单位是逻辑点

## Matplotlib embedding

- `Figure(figsize=(w, h), dpi=FIG_DPI)` 创建 figure，`FIG_DPI=100`
- `FigureCanvasTkAgg(fig, master=parent)` 嵌入 Tk
- `canvas.get_tk_widget().grid(row, col, sticky="nsew")` 放置 canvas
- 不要设置 canvas widget 的固定 `width/height`，用 `sticky="nsew"` 自动填充
- `_configure_axis_chrome(ax)` 统一设置 spine/tick 颜色和字体
- `fig.subplots_adjust(top, left, right, bottom)` 控制图表边距
- 中文跨平台字体链：`["PingFang SC", "Heiti SC", "STHeiti", "Microsoft YaHei", "SimHei", "WenQuanYi Micro Hei", "Noto Sans CJK SC", "DejaVu Sans"]`
- `rcParams["axes.unicode_minus"] = False` 避免负号乱码

## THEME conventions

- THEME dict 集中所有颜色/字体/间距，构建时用 `_f = THEME["font_family"]` 引用
- style 用 ttk.Style + `style.configure("Name.TFrame", ...)` 定义
- 按钮用 `style.map()` 控制 hover/pressed/disabled 状态
- 不要用 `tk` 原生 widget（用 `ttk`），除非 matplotlib canvas

## Figure size guideline

- 窗口宽度 / 100 DPI / 列数 ≈ 每个 figure 的英寸宽度
- 物理/虚拟阵列图：~0.35×窗口宽度/100 英寸宽
- 响应曲线图：比上面略高
- 2D DBF 热图：方图，约 100 + 窗口剩余/100 英寸
