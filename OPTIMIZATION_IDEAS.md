# 项目优化建议

> 创建日期：2026-05-15
> 基于对全部源码的完整阅读

---

## 项目现状概述

| 维度 | 评价 |
|------|------|
| **核心算法** | 扎实。天线阵列、虚拟阵列、阵列因子、波束指标计算准确 |
| **数据模型** | 清晰。`geometry.py` 简洁精炼，类职责单一 |
| **GUI 重建** | 已完成。Matplotlib 只管图、Tkinter 管文本面板，分工明确 |
| **测试** | 薄弱。仅 68 行，只测了 `geometry.py` 和 `snap_to_grid` |
| **可扩展性** | 当前硬编码偏多，加新功能需要较多改动 |

---

## 一、架构优化

### 1.1 拆分 `gui.py`（1812 行 → 多个模块）

当前 `gui.py` 承担了所有职责，建议拆为：

```
src/virtual_array/
├── gui.py          (~400 行)  只用 Tkinter 布局和事件绑定
├── plots.py        (~400 行)  三个 Figure 的绘制逻辑
├── analysis.py     (~300 行)  阵列因子计算 + 指标提取（从 gui.py 迁出）
├── widgets.py      (~200 行)  Array Evaluation 面板构建
└── events.py       (~300 行)  拖拽、hover、键盘事件
```

好处：每个文件职责明确，加功能时不会在 1800 行里翻找。

### 1.2 提取 `analysis.py`

把 `_calculate_metrics_and_psf()`、`_azimuth_cut_metrics()`、`_azimuth_first_sidelobe()`、`_evaluate_front_radar()` 等函数从 `gui.py` 移到一个独立模块。这些是纯计算逻辑，不依赖 Tkinter/Matplotlib，天然可单测。

---

## 二、功能扩展

### 2.1 布局管理（高优先级）

| 功能 | 现状 | 建议 |
|------|------|------|
| 新建空白布局 | 不支持 | 加 "New Layout" 按钮，输入 Tx/Rx 数量 |
| 增加/删除阵元 | 不支持 | 右键菜单：Remove element |
| 预设配置切换 | 只有一个 case4 | 下拉菜单选择预设，内置 3~5 个典型阵列 |
| 多布局对比 | 不支持 | 加一个 "Compare" 标签页，并列显示两套指标 |

**实现难度**：中。核心数据结构已准备好，主要是 UI 工作量。

### 2.2 自定义频率

当前只有 77/92/60 GHz 三个选项。建议在 Combobox 末尾加一项 "Custom..."，弹出输入框让用户输入任意频率（GHz），自动换算波长。

### 2.3 波束扫描（Steering）

当前固定 Az=0°、El=0°。扫描场景下需要在阵列因子计算中引入线性相位偏移：

```
phase = π × [virtual_xy[:, 0] × (u - sin(θ_scan)×cos(φ_scan))
           + virtual_xy[:, 1] × (v - sin(φ_scan))]
```

界面上加两个 Spinbox：Azimuth Steering (°) 和 Elevation Steering (°)。

### 2.4 批处理导出

加一个 "Batch Export" 面板：
- 选一个目录，批量导入 `.json` 布局文件
- 对每个布局计算全套指标
- 导出为单个 CSV/Excel 汇总表（排名、对比）

这正好对接你之前做的 Import/Export Layout 功能。

---

## 三、交互体验

### 3.1 撤销 / 重做

拖拽阵元后 `Ctrl+Z` 撤销、`Ctrl+Y` 重做。实现方式：维护一个 `deque` 存最近 50 个 `elements` 快照。

### 3.2 实时刷新开关

当前拖拽释放后才刷新虚拟阵列。加一个 Checkbutton "Auto-refresh"，勾选后拖拽过程中实时更新右侧面板和 PSF 图。

**注意**：这会显著增加计算负载。可加节流（throttle）：移动过程中每 200ms 最多刷新一次。

### 3.3 键盘快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+Z` | 撤销 |
| `Ctrl+Y` | 重做 |
| `Ctrl+S` | 导出布局 |
| `Ctrl+E` | 导出图片 |
| `Ctrl+G` | 刷新虚拟阵列 |
| `Delete` | 删除选中单元 |
| `Escape` | 取消选中 |

### 3.4 窗口状态记忆

退出时保存窗口位置和大小到 `%APPDATA%/antenna-array/layout.ini`，下次启动恢复。用 `tkinter` 的 `winfo_geometry()` + `protocol("WM_DELETE_WINDOW")` 实现，不需要额外依赖。

### 3.5 标签重叠处理

当物理阵列中阵元间距很小时，姓名标签会重叠。可加一个简单的贪心避让算法，或在标签重叠时自动隐藏部分标签，hover 时才显示。

---

## 四、工程健壮性

### 4.1 补充测试（高优先级）

当前只有 68 行测试。建议至少补齐：

| 测试对象 | 优先级 |
|----------|--------|
| `geometry.py` 的 `unique_virtual_xy` 边界情况（全重叠、零重叠） | 高 |
| `analysis.py` 提取后的所有指标计算函数 | 高 |
| 方向图计算（含已知结果的校验案例） | 高 |
| Import/Export Layout 的 JSON 解析 | 中 |
| 坐标吸附加密测试（边界、负值） | 低 |

### 4.2 日志系统

当前异常直接弹 `messagebox` 或 `print`。建议引入 `logging` 模块，输出到 `%APPDATA%/antenna-array/logs/`，方便排查用户环境中偶发问题。

### 4.3 `.gitignore`

当前缺少 `.gitignore`，建议添加排除 `__pycache__/`、`.pytest_cache/`、`*.egg-info/`、`outputs/`、`.venv/`。

---

## 五、数值/算法增强

### 5.1 二维 PSF 预览

当前 Azimuth Response 只画一维方向切面。可考虑在 PSF 图旁边加一个小二维 heatmap（Az × El），直观展示栅瓣和旁瓣的二维分布。这会增加计算量但视觉收益大。

### 5.2 峰值旁瓣角度可视化

在二维 heatmap 上标记最差旁瓣的位置（叉号 + 坐标标注），比纯数字直观。

### 5.3 D/λ 比值显示

在 Array Evaluation 或信息栏中显示阵元平均间距（以波长计），方便判断是否会出现栅瓣（经验值 `d/λ < 0.5`）。

### 5.4 幅度加权

当前假设所有阵元等幅同相。可加一组权重输入（每个 Tx/Rx 独立幅值），模拟幅度加权对旁瓣的影响（如 Chebyshev、Taylor 加权）。

---

## 六、文件组织

### 6.1 清理

| 文件/目录 | 状态 | 建议 |
|-----------|------|------|
| `examples/case4_5tx7rx_sel.py` | 与 `src/virtual_array/examples/` 重复 | 删除外层，统一从包内引用 |
| `src/virtual_array/examples/__init__.py` | 空文件 | 可删除 |
| `__pycache__/` (多个) | 缓存 | 加入 `.gitignore` |
| `.venv/` | 旧虚拟环境 | 清理或加入 `.gitignore` |

### 6.2 README 更新

当前 README 描述了安装和运行，但落后于代码实际。建议补充：
- GUI 各区域的截图和标注说明
- 指标含义速查表
- 拖拽操作的 GIF 演示

---

## 优先级排序（建议顺序）

```
第一轮（质量基础）：
  ├─ 补充核心测试
  ├─ 加 .gitignore
  ├─ 提取 analysis.py
  └─ 日志系统

第二轮（功能完善）：
  ├─ 布局管理（新建/删除阵元）
  ├─ 自定义频率
  ├─ 撤销/重做
  └─ 实时刷新开关

第三轮（体验提升）：
  ├─ 键盘快捷键
  ├─ 窗口状态记忆
  ├─ 二维 PSF heatmap
  └─ 标签重叠处理

第四轮（深度扩展）：
  ├─ 波束扫描
  ├─ 幅度加权
  ├─ 批处理导出
  └─ 多布局对比
```
