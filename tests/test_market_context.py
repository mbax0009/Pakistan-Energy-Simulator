from __future__ import annotations

from datetime import datetime, timezone

from core.models import Technology
from data.assumptions.assumptions import get_reference_case
from data.market_context import _fallback_fx, _parse_live_fx, build_market_context


def test_reference_capex_uses_latest_published_2025_benchmarks():
    assert get_reference_case(Technology.SOLAR).capex_per_kw.value == 667.0
    assert get_reference_case(Technology.SOLAR).capex_per_kw.unit == "2025 USD/kW"
    assert get_reference_case(Technology.WIND).capex_per_kw.value == 976.0
    assert get_reference_case(Technology.WIND).capex_per_kw.unit == "2025 USD/kW"


def test_live_fx_payload_preserves_source_date_and_disclosure():
    now = datetime(2026, 8, 30, tzinfo=timezone.utc)
    payload = {
        "result": "success",
        "time_last_update_unix": 1787875200,
        "rates": {"PKR": 277.5},
    }

    result = _parse_live_fx(payload, now=now)

    assert result["rate"] == 277.5
    assert result["is_live"] is True
    assert result["as_of"].tzinfo is not None
    assert "State Bank of Pakistan" in result["warning"]


def test_fallback_fx_is_explicitly_dated_and_not_live():
    result = _fallback_fx(
        now=datetime(2026, 8, 30, tzinfo=timezone.utc),
        reason="offline",
    )

    assert result["rate"] == 277.50
    assert result["is_live"] is False
    assert result["as_of"].date().isoformat() == "2026-08-28"
    assert "offline" in result["warning"]


def test_market_context_keeps_resource_and_cost_periods_separate(monkeypatch):
    monkeypatch.setattr(
        "data.market_context._fetch_fx",
        lambda **_: _fallback_fx(
            now=datetime(2026, 8, 30, tzinfo=timezone.utc),
            reason="test",
        ),
    )

    context = build_market_context(now=datetime(2026, 8, 30, tzinfo=timezone.utc))

    assert context["resource_period"] == "2015–2024"
    assert context["cost_basis_label"].startswith("IRENA 2025")
    assert context["default_currency"] == "USD"
