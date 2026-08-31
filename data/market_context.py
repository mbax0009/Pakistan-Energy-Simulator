from __future__ import annotations

import os

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Callable

import requests

from core.models import Technology
from data.assumptions.assumptions import get_reference_case, get_source


DEFAULT_FX_ENDPOINT = "https://open.er-api.com/v6/latest/USD"
SBP_REFERENCE_URL = "https://www.sbp.org.pk/ecodata/rates/m2m/Months.asp"
FALLBACK_RATE = 277.50
FALLBACK_AS_OF = datetime(2026, 8, 28, tzinfo=timezone.utc)
FALLBACK_SOURCE_URL = "https://www.brecorder.com/markets/currency/3198"


def _is_stale(as_of: datetime, now: datetime) -> bool:
    return now - as_of > timedelta(days=3)


def _parse_live_fx(payload: dict[str, Any], *, now: datetime) -> dict[str, Any]:
    if payload.get("result") != "success":
        raise ValueError("The indicative FX provider did not return success.")

    try:
        rate = float(payload["rates"]["PKR"])
        updated_unix = int(payload["time_last_update_unix"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("The indicative FX response is missing USD/PKR data.") from exc

    if rate <= 0:
        raise ValueError("The indicative USD/PKR rate must be positive.")

    as_of = datetime.fromtimestamp(updated_unix, tz=timezone.utc)
    return {
        "base_currency": "USD",
        "quote_currency": "PKR",
        "rate": rate,
        "as_of": as_of,
        "source_name": "ExchangeRate-API open feed",
        "source_url": DEFAULT_FX_ENDPOINT,
        "official_reference_url": SBP_REFERENCE_URL,
        "is_live": True,
        "is_stale": _is_stale(as_of, now),
        "warning": (
            "Indicative display conversion only. Confirm settlement and regulatory "
            "rates against the State Bank of Pakistan before investment use."
        ),
    }


def _fallback_fx(*, now: datetime, reason: str) -> dict[str, Any]:
    return {
        "base_currency": "USD",
        "quote_currency": "PKR",
        "rate": FALLBACK_RATE,
        "as_of": FALLBACK_AS_OF,
        "source_name": "Published Pakistan interbank close (bundled fallback)",
        "source_url": FALLBACK_SOURCE_URL,
        "official_reference_url": SBP_REFERENCE_URL,
        "is_live": False,
        "is_stale": _is_stale(FALLBACK_AS_OF, now),
        "warning": (
            "Live FX retrieval failed; a dated fallback is shown. "
            f"Reason: {reason}. Verify the latest official rate before use."
        ),
    }


def _fetch_fx(
    *,
    now: datetime,
    http_get: Callable[..., Any] = requests.get,
) -> dict[str, Any]:
    endpoint = os.getenv("PAK_ENERGY_FX_ENDPOINT", DEFAULT_FX_ENDPOINT)
    try:
        response = http_get(endpoint, timeout=8)
        response.raise_for_status()
        payload = response.json()
        result = _parse_live_fx(payload, now=now)
        result["source_url"] = endpoint
        return result
    except (requests.RequestException, ValueError, TypeError) as exc:
        return _fallback_fx(now=now, reason=str(exc))


@lru_cache(maxsize=8)
def _cached_fx(day_bucket: str) -> dict[str, Any]:
    del day_bucket
    return _fetch_fx(now=datetime.now(timezone.utc))


def build_market_context(*, now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    fx = _cached_fx(current.date().isoformat()) if now is None else _fetch_fx(now=current)

    benchmarks = []
    for technology in (Technology.SOLAR, Technology.WIND, Technology.WAVE):
        reference = get_reference_case(technology)
        assumption = reference.capex_per_kw
        if assumption is None:
            benchmarks.append(
                {
                    "technology": technology.value,
                    "capex_per_kw": None,
                    "unit": None,
                    "basis_year": None,
                    "source_name": None,
                    "source_url": None,
                    "evidence_level": "unresolved",
                    "note": "No defensible mature-market generic CAPEX benchmark.",
                }
            )
            continue

        source = get_source(assumption.source_id)
        benchmarks.append(
            {
                "technology": technology.value,
                "capex_per_kw": assumption.value,
                "unit": assumption.unit,
                "basis_year": 2025,
                "source_name": f"{source.organization} — {source.title}",
                "source_url": source.source_url,
                "evidence_level": assumption.evidence_level.value,
                "note": assumption.notes,
            }
        )

    return {
        "generated_at": current,
        "default_currency": "USD",
        "resource_period": "2015–2024",
        "cost_basis_label": "IRENA 2025 global benchmarks (2025 USD)",
        "cost_benchmarks": benchmarks,
        "fx": fx,
        "electricity_price_policy": (
            "Project-specific user input. Any benchmark must retain its source "
            "and exact as-of date."
        ),
    }
