# 封装为可执行文件 (.exe) 方案

> 创建日期：2026-05-14

---

## 方案选择：PyInstaller（推荐）

PySide6 + pyqtgraph 组合下继续使用 PyInstaller 打包；项目已在
`MIMOArrayVisualizer.spec` 中显式包含 Qt 绑定与 pyqtgraph。

| 工具 | 难度 | .exe 大小 | 启动速度 | 推荐度 |
|------|------|-----------|----------|--------|
| **PyInstaller** | 低 | 80~120 MB | 3~5 秒 | ★★★ |
| Nuitka | 中 | 40~80 MB | 1~2 秒 | ★★ |
| cx_Freeze | 低 | 类似 | 类似 | ★ |

---

## 实施步骤

### 1. 确保入口可用

`GUI.py` 位于项目根目录，`pip install -e .` 已完成即可。

### 2. 推荐打包命令

```powershell
cd E:\WORK\antenna_layout

# 测试版（带控制台，方便排查问题）
pyinstaller --onedir --console --name "MIMOArrayVisualizer" --paths src GUI.py

# 发布版（无控制台）
pyinstaller --onedir --noconsole --name "MIMOArrayVisualizer" --paths src GUI.py
```

### 3. spec 文件关键配置

如需精细控制，写 `.spec` 文件：

```python
a = Analysis(
    ['GUI.py'],
    pathex=['src'],                              # 让 PyInstaller 找到 virtual_array
    hiddenimports=[
        'virtual_array',
        'virtual_array.gui',
        'virtual_array.geometry',
        'virtual_array.grid',
        'virtual_array.plotting',
        'virtual_array.examples',
        'virtual_array.examples.case4_5tx7rx_sel',
        'openpyxl',
        'openpyxl.cell._writer',
        'PySide6',
        'pyqtgraph',
    ],
    datas=[
        ('src/virtual_array/examples/*.py', 'virtual_array/examples/'),  # 示例数据
        # 中文字体（按实际路径调整）
    ],
    excludes=['pytest', 'unittest'],
)
```

### 4. 常见问题及解法

| 问题 | 原因 | 解法 |
|------|------|------|
| `ModuleNotFoundError: virtual_array` | PyInstaller 不扫描 `-e` 安装路径 | 用 `--paths src` 或 spec 中 `pathex=['src']` |
| `Reading XLSX ... requires openpyxl` | `openpyxl` 是动态导入，PyInstaller 可能漏收 | 在 spec 的 `hiddenimports` 加入 `openpyxl` 和 `openpyxl.cell._writer` |
| 中文字体丢失 | Matplotlib 找不到 `Microsoft YaHei` | 把 `C:/Windows/Fonts/msyh.ttc` 打包进 datas |
| exe 闪退 | Qt 插件、Matplotlib 后端或资源路径未被打包 | 先用 `--console` 版本测试 |
| 杀软误报 | 单文件模式解压行为触发 | 用 `--onedir`（文件夹模式），误报率极低 |

---

## 分发方式

| 模式 | 用户体验 | 启动速度 | 杀软友好 | 推荐场景 |
|------|----------|----------|----------|----------|
| `--onefile` | 一个 .exe | 慢（解压） | 差 | 只发一个文件 |
| `--onedir` | 文件夹压缩包 | 快 | 好 | 推荐 |

建议：先调通 `--onedir`，把输出文件夹打成 `.zip` 发给同事。

---

## 预估

| 维度 | 数值 |
|------|------|
| 首次调通耗时 | 30 分钟 |
| 字体/路径踩坑 | 30 分钟 |
| .exe 大小 (`--onedir`) | ~100 MB |
| 首次启动 | 3~5 秒 |
| 同事所需环境 | 无，Windows 10/11 直接运行 |
