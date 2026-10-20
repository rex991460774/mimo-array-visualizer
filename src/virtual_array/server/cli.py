"""``mimo-array-server`` command: run the web workbench on a local server."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from ..version import APP_VERSION
from .app import DATA_DIR_ENV, configure_server_logging, create_app, default_data_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mimo-array-server",
        description="Serve the MIMO Array Visualizer web workbench.",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("MIMO_HOST", "127.0.0.1"),
        help="Bind address (default 127.0.0.1; use 0.0.0.0 to allow other machines).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MIMO_PORT", "8000")),
        help="TCP port (default 8000).",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help=f"Directory for projects, uploaded files and exports (env {DATA_DIR_ENV}; default ./data).",
    )
    parser.add_argument(
        "--static-dir",
        type=Path,
        default=None,
        help="Built web client directory (default: the copy bundled in the package).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {APP_VERSION}")
    return parser


def data_dir_problem(data_dir: Path) -> str | None:
    """Why the data directory cannot be used, or None; checked before startup."""
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        probe = data_dir / ".write-test"
        probe.write_bytes(b"ok")
        probe.unlink()
    except OSError as exc:
        return exc.strerror or str(exc)
    return None


def main(argv: list[str] | None = None) -> None:
    import uvicorn

    args = build_parser().parse_args(argv)
    data_dir = (args.data_dir or default_data_dir()).expanduser().resolve()
    problem = data_dir_problem(data_dir)
    if problem:
        print(f"Cannot use data directory {data_dir}: {problem}", file=sys.stderr)
        print("Pass --data-dir with a writable directory (or set MIMO_DATA_DIR), or fix its permissions.", file=sys.stderr)
        raise SystemExit(2)
    log_path = configure_server_logging(data_dir)
    logging.getLogger(__name__).info(
        "Starting MIMO Array Visualizer %s on %s:%s (data: %s)",
        APP_VERSION,
        args.host,
        args.port,
        data_dir,
    )
    print(f"MIMO Array Visualizer {APP_VERSION}")
    print(f"  URL:      http://{'localhost' if args.host in {'127.0.0.1', '0.0.0.0'} else args.host}:{args.port}/")
    print(f"  Data dir: {data_dir}")
    print(f"  Log file: {log_path}")
    app = create_app(data_dir=data_dir, static_dir=args.static_dir)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
