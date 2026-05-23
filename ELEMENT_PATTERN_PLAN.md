# 单元方向图输入功能 — 开发方案

> 创建日期：2026-05-14

---

## 一档：基础功能（建议首轮完成）

### 1.1 方向图数据输入

- 界面加一块区域，标题 **Element Pattern**
- 两个输入通道：**Tx Pattern** 和 **Rx Pattern**（可各自载入文件或共用）
- 输入方式：
  - 文件选择按钮 + 路径显示，支持 `.csv` / `.tsv`
  - 附一个 **Clear** 按钮，清空后恢复默认全向假设
- 文件格式约定：

  ```
  # Angle(deg)  Gain(dBi)
  -90            -12.5
  -75            -6.3
  ...
    0             5.2
  ...
   75            -6.3
   90            -12.5
  ```

  - 两列：角度（deg）、增益（dBi 或线性值）
  - 自动检测列序（先找 header 关键词 angle / azimuth / gain / dBi）
  - 角度范围不必对称，代码自动插值

### 1.2 内部存储和插值

- 加载后存为 `np.interp` 可用的一维 `(angles, gains)` 数组
- 计算阵列因子时，对每个方位角 `az` 查询对应的单元增益 `g_tx(az)` 和 `g_rx(az)`
- 第一版仅支持一维 azimuth-only 方向图（elevation=0° 切片）

### 1.3 计算结果变化

修改 `_calculate_metrics_and_psf()` 中的阵列因子计算：

```
当前：AF = |Σ exp(j·phase)|
加载后：AF = |Σ g_tx(az) · g_rx(az) · exp(j·phase)|
```

- 如果 Tx 和 Rx 用同一天线，只加载一次即可
- 如果有 2D 方向图则在后续版本扩展到 (az, el) 二维查询

### 1.4 显示反馈

- 加载成功后在 PSF 图上叠加一条**半透明虚线**显示单元方向图（归一化到 0 dB 峰值）
- 图例标注 "Tx pattern" / "Rx pattern"
- Array Evaluation 的 NOTES 区域追加一行：
  - `"Element pattern: loaded (Tx: xxx.csv, Rx: xxx.csv)"`
  - 或 `"Element pattern: isotropic"`（未加载时）

---

## 二档：增强功能（后续迭代）

### 2.1 俯仰向方向图支持

- 输入文件扩展为三列：`Az(deg), El(deg), Gain(dBi)`，支持完整 2D 方向图
- 计算 (az, el) 二维阵列因子时用 `scipy.interpolate.RegularGridInterpolator` 做二维查询

### 2.2 相位方向图

- 支持复增益格式 (Re, Im) 或 (Mag, Phase)
- 单元复增益直接乘入复阵列因子，同时影响幅度和相位

### 2.3 方向图预览窗口

- 单独弹一个小 Figure 查看加载的方向图形状
- 方便确认导入数据正确

### 2.4 方向图对指标影响的对比显示

- Array Evaluation 里并列显示 "With pattern" / "Isotropic" 的关键指标对比
- 或加一个 toggle 按钮切换，实时刷新

---

## 三档：可选扩展（按需添加）

### 3.1 方向图归一化选项

- 是否把最大增益归一化到 0 dBi（有些数据自带绝对增益，有些需要归一化）

### 3.2 波束扫描场景的方向图加权

- 当前固定 Steering = 0°，若后续要仿真扫描场景，方向图查询角需加上扫描角偏移

### 3.3 常见仿真软件导出格式

- HFSS `.csv`、CST `.txt` 的自动解析
