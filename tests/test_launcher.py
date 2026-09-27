from __future__ import annotations

from urllib.error import URLError

from simulator_api import launcher


class _ReadyResponse:
    status = 200

    def __enter__(self) -> _ReadyResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def test_browser_opens_after_local_server_is_ready(monkeypatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr(launcher, "urlopen", lambda *_args, **_kwargs: _ReadyResponse())
    monkeypatch.setattr(launcher.webbrowser, "open", opened.append)

    launcher._open_browser_when_ready("http://127.0.0.1:8765")

    assert opened == ["http://127.0.0.1:8765"]


def test_browser_still_opens_after_readiness_timeout(monkeypatch) -> None:
    opened: list[str] = []
    monotonic_values = iter([0.0, 0.0, 21.0])

    def unavailable(*_args, **_kwargs):
        raise URLError("not ready")

    monkeypatch.setattr(launcher, "urlopen", unavailable)
    monkeypatch.setattr(launcher.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(launcher.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(launcher.webbrowser, "open", opened.append)

    launcher._open_browser_when_ready("http://127.0.0.1:8765")

    assert opened == ["http://127.0.0.1:8765"]
