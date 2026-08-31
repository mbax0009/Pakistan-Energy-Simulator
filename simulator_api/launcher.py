from __future__ import annotations

import os
import sys
import webbrowser

from pathlib import Path
from threading import Timer

import uvicorn


def _ensure_standard_streams() -> None:
    """Provide sinks for libraries that inspect streams in a windowed build."""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")


def _runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "runtime-data"
    return Path(__file__).resolve().parents[1] / ".runtime"


def main() -> None:
    _ensure_standard_streams()
    runtime_root = _runtime_root()
    temp_root = runtime_root / "tmp"
    cache_root = runtime_root / "cache" / "resources"
    temp_root.mkdir(parents=True, exist_ok=True)
    cache_root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("TEMP", str(temp_root))
    os.environ.setdefault("TMP", str(temp_root))
    os.environ.setdefault("PAK_ENERGY_CACHE_DIR", str(cache_root))

    host = os.getenv("PAK_ENERGY_HOST", "127.0.0.1")
    port = int(os.getenv("PAK_ENERGY_PORT", "8765"))
    url = f"http://{host}:{port}"
    open_browser = os.getenv("PAK_ENERGY_OPEN_BROWSER", "1").strip().lower()
    if open_browser not in {"0", "false", "no"}:
        Timer(1.25, lambda: webbrowser.open(url)).start()

    from simulator_api.main import app

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
