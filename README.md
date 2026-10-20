# MIMO Array Visualizer

**中文** | [English](#english)

MIMO 阵列工作台：评估 60 GHz / 77 GHz / 92 GHz 毫米波 FMCW 雷达的 MIMO Tx/Rx 天线阵列性能。部署在本地服务器上，局域网内用浏览器即可使用，无需在每台电脑上安装软件。

可计算虚拟阵列几何、阵列方向图指标（实测 3 dB 分辨率、PSL、ISLR、栅瓣），以及基于 DBF 字典、限定在雷达视场内的测角性能（不模糊范围、亚度级测角误差、竞争峰裕量），并给出频段内性能、规格检查和多方案对比，输出多页 PDF 性能报告。

---

## 功能

### 界面

- **阵列布局**：SVG 编辑器，可拖拽 Tx/Rx，松开后吸附到 λ/2 网格；支持滚轮缩放、平移、方向键微调、删除模式、撤销/重做（50 步）、自动排阵（T/R 数量），坐标表可批量精确编辑（同时显示 mm）。拖动时虚拟阵列实时预览；选中物理通道时，与之相关的虚拟点会高亮。
- **1D DBF**：方位/俯仰字典角谱，共 181 帧真实角（−90°～+90°）。播放、拖动、点击图上任意位置都可跳转；实时显示峰值、误差、竞争峰裕量和峰质量。
- **2D DBF**：方位 × 俯仰相关热图。点击热图设定真实角；方位、俯仰可分别或同时扫描，服务器端预取后续帧。
- **测角性能**：逐帧测角误差和竞争峰裕量曲线，标注不模糊范围和裕量阈值，可导出出版级 PNG。
- **阵列概览**：通道数、虚拟通道利用率、口径（mm/λ）、分辨率、测角评估、方向图指标和提示。
- 中文 / English / 日本語界面，浅色 / 深色 / 跟随系统主题，桌面和手机宽度均可用。

### 雷达评估

- **频段**：60G（57–64 GHz）、77G（76–81 GHz）、92G（默认 90–94 GHz，需按芯片修改）预设，可自定义扫频范围；阵列坐标以设计频率下的 λ 保存。
- **评估视场**：测角评估与方向图指标都限定在雷达视场内（DBF 搜索外扩 10°），视场外栅瓣不计入视场内模糊。
- **频段内性能**：天线物理位置固定，在扫频起止与设计频率处重新评估分辨率、不模糊范围、误差、裕量和 PSL。
- **规格检查**：分辨率、视场内不模糊、视场内最大误差、竞争峰裕量、2D 峰值旁瓣逐项判定通过/未通过。
- **方案对比**：从项目库选取多个方案（如 60/77/92 GHz 各自的阵列）与当前项目并排比较。
- **布局检查**：阵元重合、间距小于 λ/2（可能物理重叠）、设计频率不在扫频范围内时给出提示。

### 功能

- **DBF 字典**：理想几何、理想反向相位、通道幅相校准、导入 CSV/XLSX 字典（方位/俯仰分别导入，支持虚拟或物理通道列，可选相位取反和 0° 校准）；附相位矩阵预览和质量提示。
- **通道幅相**：导入 HFSS 汇总文件（物理或虚拟通道），或为单个通道导入幅度/相位 × 水平/俯仰；支持 dB、度数、复数（`1+2j`、`2∠40`）。
- **单元方向图**：导入 CSV/TSV，可预览 H/V 切面并交换。
- **项目库**：项目保存在服务器数据目录，同一服务器的用户共享；浏览器会自动保留当前草稿。
- **导入导出**：阵面 JSON 与桌面版兼容（version 1，单位 λ，含评估信息）；项目包 `.mimo.zip` 包含配置和全部导入数据，可在服务器之间迁移。
- **性能报告**：服务器后台生成多页 PDF，可选附带 CSV/JSON 可复现数据包，显示进度、可取消，完成后自动下载。
- **HTTP API**：全部功能均可通过 REST API 调用，方便脚本批量评估。接口文档见 `/api/docs`。

---

## 部署

### 方式一：Docker（推荐）

```bash
git clone https://github.com/rex991460774/mimo-array-visualizer.git
cd mimo-array-visualizer
docker compose up -d --build
```

浏览器打开 `http://<服务器IP>:8000/`。数据（项目库、导入文件、报告任务、日志）保存在 Docker 卷 `mimo-data` 中，升级镜像不会丢失。

- 改端口：编辑 `docker-compose.yml` 中的 `"8000:8000"`，例如改为 `"8080:8000"`。
- 升级：`git pull && docker compose up -d --build`。
- 备份：`docker run --rm -v mimo-array-visualizer_mimo-data:/data -v "$PWD":/backup alpine tar czf /backup/mimo-data.tgz -C /data .`

镜像已内置 Noto CJK 字体，中文/日文 PDF 报告可直接生成。

### 方式二：Linux 裸机

需要 Python 3.10+ 和 Node.js 20+（仅构建前端时需要）。

```bash
scripts/setup_server.sh                       # 创建 .venv、安装依赖、构建前端
.venv/bin/mimo-array-server --host 0.0.0.0 --port 8000 --data-dir ./data
```

开机自启可参考 `deploy/mimo-array.service`（systemd）。中文报告需要系统安装 CJK 字体（如 `apt install fonts-noto-cjk`）。

### 方式三：Windows 服务器

```powershell
.\scripts\setup_server.ps1     # 需要 Python 3.10+ 与 Node.js 20+
.\scripts\run_server.ps1       # 默认 0.0.0.0:8000，数据目录 .\data
```

其他电脑访问前，需要在 Windows 防火墙中放行该端口。

### 安全说明

服务没有内置登录鉴权，适合在可信的实验室局域网内使用。命令行方式默认只监听 `127.0.0.1`；需要局域网访问时显式指定 `--host 0.0.0.0`。如需暴露到更大范围，请在前面加一层带认证的反向代理（如 Nginx Basic Auth）。上传文件限制为 CSV/TSV/TXT/XLSX/XLSM，单个不超过 32 MB。

---

## 开发

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/mimo-array-server --port 8000       # 后端

cd web && npm ci && npm run dev               # 前端热更新：http://localhost:5173（/api 代理到 :8000）
```

```bash
.venv/bin/python -m pytest -q                 # 后端测试（计算核心 + API）
.venv/bin/ruff check src tests                # Python lint
cd web && npm test && npx tsc -b              # 前端单元测试 + 类型检查
cd web && npm run build                       # 构建到 src/virtual_array/server/static
```

### 架构

```
浏览器（React + TypeScript）
  │  项目文档 JSON（坐标单位 λ）
  ▼
FastAPI 服务（virtual_array.server）
  ├─ project.py   项目模型、v1 阵面 JSON 兼容
  ├─ engine.py    项目 → 计算核心，按依赖字段做 LRU 缓存
  ├─ assets.py    导入文件按 SHA-256 存储
  └─ jobs.py      报告后台任务
  ▼
计算核心（无 UI 依赖，坐标单位 λ/2）
  geometry · analysis · dbf_dictionary · element_pattern · performance_report
```

- 1D DBF 一次请求返回完整的 181 × 181 角谱（base64 float32），播放全部在浏览器中完成，不需要逐帧请求。
- 2D DBF 使用 `Dbf2dScanner` 复用扫描字典，单帧约 30 ms，前端按批预取。
- 阵列因子计算改为矩阵乘法后约快 2 倍，数值结果与原实现一致（测试锁定）。

### 项目结构

```
src/virtual_array/
  geometry.py, analysis.py, dbf_dictionary.py, element_pattern.py,
  table_io.py, performance_report.py, phasor.py   计算核心
  project.py, assets.py, engine.py                服务层
  server/                                          FastAPI 应用、项目库、任务、CLI
  examples/                                        参考阵列（case4 8T8R）
web/                                               React 前端
tests/                                             pytest
deploy/, scripts/, Dockerfile, docker-compose.yml  部署
```

### 评估方法说明

| 项目 | 做法 | 原因 |
| --- | --- | --- |
| 分辨率 | 阵列响应 0° 切面的实测 3 dB 波束宽度；0.886/D 公式仅作参考 | 公式对稀疏/小阵列不准（case4 公式 1.35°，实测 1.72°） |
| PSL 主瓣区 | 主峰两侧至第一零点（至少下降 3 dB） | 固定 ±2°/±6° 保护区会把小阵列（如 60 GHz 3T4R）的主瓣算成旁瓣 |
| 测角范围 | 真实角在视场内 1° 步进；搜索范围外扩 10° | 实际雷达只在视场内搜索；全 ±90° 搜索会把视场外栅瓣误判为模糊 |
| 测角误差 | 1° 网格取峰后，在峰附近重新计算相关细化到 0.002° | 只用 1° 网格时误差只能是整数度，无法评估 HFSS 实测数据的亚度级误差 |
| 频段内性能 | 物理坐标固定，电长度按 f/f<sub>设计</sub> 缩放；字典按工作频率匹配 | 反映 FMCW 扫频内栅瓣起始角和分辨率的漂移 |
| 自动排阵 | Rx 间距 λ/2、Tx 间距 N<sub>Rx</sub>·λ/2 | 得到无重复、无栅瓣的 λ/2 虚拟 ULA（标准 MIMO 布局） |

导入的 HFSS 通道相位和自定义字典是单频点数据，频段内评估只缩放几何、不改变这些数据，界面会给出提示。

### 从桌面版迁移

桌面版（PySide6）已由 Web 版取代，代码保留在 git 历史中。桌面版导出的阵面 JSON 可直接通过「导入 → 导入阵面 JSON」打开，频率和裕量设置会一并读取。桌面版中按本地路径引用的字典和方向图文件，需要在 Web 版中重新上传一次；之后会保存在服务器上，也可以随项目包一起迁移。

---

## English

MIMO Array Visualizer is a web workbench for editing and evaluating MIMO radar Tx/Rx antenna layouts. Run it on a local server and use it from any browser on the LAN.

- **UI**: drag-and-snap SVG array editor with undo/redo, live virtual-array preview, 1D DBF spectrum playback, 2D DBF heatmap, angle-error/peak-margin view, overview panel; Chinese/English/Japanese; light/dark themes.
- **Analysis** for 60/77/92 GHz FMCW radars: band presets with sweep ranges, FOV-bounded DBF angle evaluation with sub-degree peak refinement, measured 3 dB resolution, first-null PSL, in-band performance at the sweep edges, requirement pass/fail, design comparison, layout overlap checks; ideal, reversed, channel-calibrated or imported dictionaries, HFSS channel amp/phase and element patterns.
- **Workflow**: shared server-side project library, desktop-compatible layout JSON, portable `.mimo.zip` bundles, background PDF reports with CSV/JSON data packages, REST API at `/api/docs`.

**Deploy with Docker**: `docker compose up -d --build`, then open `http://<server>:8000/`.
**Bare metal**: `scripts/setup_server.sh` (or `scripts\setup_server.ps1` on Windows), then `mimo-array-server --host 0.0.0.0 --port 8000 --data-dir ./data`.
The server has no built-in authentication; use it on a trusted network or behind an authenticating reverse proxy.

## License

MIT, see [LICENSE](LICENSE).
