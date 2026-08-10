# Contributing

Thanks for helping improve MIMO Array Visualizer.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Before opening a pull request, run:

```bash
pytest tests/ -x -q
ruff check .
pyright
```

## Pull requests

- Keep changes focused and explain the user or engineering problem they solve.
- Add or update tests for behavior changes.
- For GUI changes, describe the affected platform and include a screenshot when it helps review.
- Do not commit local state, generated `outputs/`, `build/`, or `dist/` files.
- Preserve the existing layout JSON format and the public console entry points unless the change explicitly updates them.

For larger changes, open an issue first so the scope and intended behavior can be discussed.
