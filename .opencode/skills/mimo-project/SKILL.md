---
name: mimo-project
description: MIMO Array Visualizer project conventions - web architecture, units, test commands, data flow
---
## Project layout

```
src/virtual_array/          Python package
  geometry.py, analysis.py, dbf_dictionary.py, element_pattern.py,
  table_io.py, performance_report.py   → 计算核心（无 UI 依赖，单位 λ/2）
  project.py                → v2 项目文档（Pydantic，单位 λ），兼容 v1 阵面 JSON
  assets.py                 → 导入文件按 SHA-256 存储
  engine.py                 → Project → 核心对象，带 LRU 缓存的计算服务
  server/                   → FastAPI：app.py（API + 静态前端）、store.py、jobs.py、cli.py
web/                        React + TypeScript + Vite 前端（构建到 server/static）
```

## 运行命令

```bash
pip install -e ".[dev]"                 # 后端依赖
cd web && npm ci && npm run build       # 前端构建
mimo-array-server --port 8000           # 启动服务
cd web && npm run dev                   # 前端开发（/api 代理到 :8000）
pytest -q && (cd web && npm test)       # 测试
ruff check src tests
```

## 关键约定

- 项目文档与 API 坐标单位是 λ，编辑网格 0.5 λ；核心计算单位是 λ/2，只在 `project_array()` 中换算。
- 通道名由列表顺序决定（Tx1…、Rx1…）；前端每次编辑后按 (x, y) 重新排序编号。
- 导入文件通过 asset ID 引用，项目文档不含本地路径；`engine.py` 按依赖字段的 JSON 摘要做缓存键。
- 大矩阵用 base64 float32 传输（`encode_array`），±inf 以字符串 "Infinity"/"-Infinity" 传输。
- UI 文案在 `web/src/i18n/messages.ts`，zh 为基准，en/ja 必须同 key、同占位符（有单元测试校验）。
- 修改计算核心时保持现有测试的数值结果不变。
