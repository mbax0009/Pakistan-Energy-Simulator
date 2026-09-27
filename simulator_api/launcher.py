from __future__ import annotations

import os
import sys
import time
import webbrowser

from pathlib import Path
from threading import Thread
from urllib.error import URLError
from urllib.request import urlopen

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


def _open_browser_when_ready(url: str, timeout_seconds: float = 20.0) -> None:
    """Open the UI only after the local server starts accepting requests."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=0.5) as response:  # noqa: S310 - loopback URL only
                if 200 <= response.status < 500:
                    webbrowser.open(url)
                    return
        except (OSError, URLError):
            time.sleep(0.1)

    # Preserve the old behavior if startup diagnostics take longer than expected.
    webbrowser.open(url)


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
        browser_thread = Thread(
            target=_open_browser_when_ready,
            args=(url,),
            name="pak-energy-browser-launch",
            daemon=True,
        )
        browser_thread.start()

    from simulator_api.main import app

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
