# 参与贡献

感谢参与改进 MIMO Array Visualizer。

## 开发环境

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cd web && npm ci
```

后端：`.venv/bin/mimo-array-server --port 8000`；前端热更新：`cd web && npm run dev`。

提交 PR 前请运行：

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests
cd web && npm test && npx tsc -b && npm run build
```

## Pull Request

- 改动保持聚焦，说明它解决的用户或工程问题。
- 行为变化需要补充或更新测试；修改计算核心时，不得改变现有测试锁定的数值结果。
- 界面改动请附截图，并说明在哪些浏览器/宽度下验证过。
- 新增 UI 文案时，`web/src/i18n/messages.ts` 中 zh/en/ja 三种语言都要补齐（有单元测试校验）。
- 不要提交本地数据（`data/`）、构建产物（`src/virtual_array/server/static/`、`web/node_modules/`）。
- 保持 v1 阵面 JSON 格式和 `/api` 接口兼容，除非改动明确是要升级它们。

较大的改动请先开 issue，讨论范围和预期行为。
