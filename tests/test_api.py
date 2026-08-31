from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from fastapi.testclient import TestClient

from core.resources import ResourceMetadata, SolarResourcePoint, SolarResourceSeries
from simulator_api.main import app
from simulator_api.schemas import (
    AnalysisRequest,
    BreakEvenRequest,
    ComparisonRequest,
    OneWaySensitivityRequest,
    RiskAnalysisRequest,
    TwoWaySensitivityRequest,
)
from simulator_api.service import (
    run_analysis,
    run_break_even_analysis,
    run_comparison,
    run_one_way_analysis,
    run_risk_analysis,
    run_two_way_analysis,
)


class _SyntheticSolarProvider:
    def fetch(self, request):
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        points = tuple(
            SolarResourcePoint(
                timestamp=start + timedelta(hours=index),
                ghi_wm2=irradiance,
                poa_irradiance_wm2=irradiance,
                ambient_temperature_c=25.0,
                cell_temperature_c=None,
            )
            for index, irradiance in enumerate((0.0, 500.0, 1000.0, 0.0))
        )
        return SolarResourceSeries(
            location=request.location,
            metadata=ResourceMetadata(
                source_name="Synthetic test provider",
                dataset_name="Deterministic hourly fixture",
                retrieved_at=datetime.now(timezone.utc),
                resolved_latitude=request.location.latitude,
                resolved_longitude=request.location.longitude,
                provider_timezone="UTC",
            ),
            points=points,
        )


def _request() -> AnalysisRequest:
    return AnalysisRequest.model_validate(
        {
            "scenario_id": "API_SOLAR_TEST",
            "technology": "solar",
            "location": {
                "name": "Jhimpir",
                "latitude": 25.025,
                "longitude": 67.95,
            },
            "capacity_mw": 100,
            "lifetime_years": 30,
            "annual_degradation_rate": 0.007,
            "financial": {
                "capex_per_kw": 691,
                "fixed_opex_per_kw_year": 22,
                "electricity_price_per_mwh": 60,
                "discount_rate": 0.10,
            },
            "resource": {
                "start_date": date(2020, 1, 1),
                "end_date": date(2020, 1, 1),
                "minimum_year_completeness": 0.0001,
            },
            "solar": {
                "tilt_deg": 25,
                "azimuth_deg": 180,
                "system_losses": 0.141,
            },
        }
    )


def test_health_endpoint_exposes_versions():
    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["software_version"]
    assert response.json()["methodology_version"]


def test_analysis_service_returns_typed_reproducible_result():
    result = run_analysis(
        _request(),
        provider_override=_SyntheticSolarProvider(),
    )

    assert result.scenario_id == "API_SOLAR_TEST"
    assert result.resource.sample_count == 4
    assert result.resource.source_name == "Synthetic test provider"
    assert result.generation_statistics.p90_mwh <= result.generation_statistics.p50_mwh
    assert result.generation_statistics.p50_mwh <= result.generation_statistics.p10_mwh
    assert set(result.evaluations) >= {"p90", "p50", "p10"}
    assert result.evaluations["p50"].lcoe_usd_per_mwh is not None
    assert any("temperature" in warning.lower() for warning in result.warnings)
    assert result.reproducibility.software_version
    assert result.reproducibility.methodology_version


def test_one_way_and_two_way_sensitivity_reuse_baseline_resource():
    provider = _SyntheticSolarProvider()
    one_way = run_one_way_analysis(
        OneWaySensitivityRequest(
            analysis=_request(),
            parameter="capex_per_kw",
            metric="lcoe",
            values=[500.0, 691.0, 900.0],
        ),
        provider_override=provider,
    )
    two_way = run_two_way_analysis(
        TwoWaySensitivityRequest(
            analysis=_request(),
            x_parameter="capex_per_kw",
            x_values=[500.0, 900.0],
            y_parameter="electricity_price_per_mwh",
            y_values=[50.0, 70.0],
            metric="npv",
            benchmark_value=0.0,
        ),
        provider_override=provider,
    )

    assert len(one_way.points) == 3
    assert one_way.points[0].metric_value < one_way.points[-1].metric_value
    assert len(two_way.points) == 4
    assert two_way.lower_is_better is False


def test_risk_analysis_is_reproducible_with_fixed_seed():
    request = RiskAnalysisRequest.model_validate(
        {
            "analysis": _request().model_dump(mode="json"),
            "variables": [
                {
                    "name": "capex_per_kw",
                    "distribution": "uniform",
                    "minimum_value": 600.0,
                    "maximum_value": 800.0,
                    "units": "USD/kW",
                }
            ],
            "sample_count": 20,
            "random_seed": 42,
            "resource_resampling_mode": "none",
        }
    )

    first = run_risk_analysis(request, provider_override=_SyntheticSolarProvider())
    second = run_risk_analysis(request, provider_override=_SyntheticSolarProvider())

    assert first.samples == second.samples
    assert first.sample_count == 20
    assert 0 <= first.probability_npv_positive <= 1


def test_comparison_ranks_projects_without_overall_score():
    baseline = _request()
    higher_capex = baseline.model_copy(
        update={
            "scenario_id": "API_SOLAR_TEST_HIGH_CAPEX",
            "location": baseline.location.model_copy(
                update={
                    "name": "Lahore test site",
                    "latitude": 31.5204,
                    "longitude": 74.3587,
                }
            ),
            "financial": baseline.financial.model_copy(
                update={"capex_per_kw": 900.0}
            ),
        }
    )
    result = run_comparison(
        ComparisonRequest(analyses=[baseline, higher_capex]),
        provider_overrides=[_SyntheticSolarProvider(), _SyntheticSolarProvider()],
    )

    assert len(result.rows) == 2
    custom_site = next(
        row for row in result.rows if row.scenario_id == "API_SOLAR_TEST_HIGH_CAPEX"
    )
    assert custom_site.location_name == "Lahore test site"
    assert custom_site.requested_latitude == pytest.approx(31.5204)
    assert custom_site.requested_longitude == pytest.approx(74.3587)
    assert custom_site.resolved_latitude == pytest.approx(31.5204)
    assert custom_site.resolved_longitude == pytest.approx(74.3587)
    assert result.rankings
    assert all(ranking.metric != "overall_score" for ranking in result.rankings)


def test_break_even_recovers_baseline_capex_for_baseline_lcoe():
    provider = _SyntheticSolarProvider()
    baseline = run_analysis(_request(), provider_override=provider)
    target_lcoe = baseline.evaluations["p50"].lcoe_usd_per_mwh
    assert target_lcoe is not None

    result = run_break_even_analysis(
        BreakEvenRequest(
            analysis=_request(),
            parameter="capex_per_kw",
            metric="lcoe",
            target_metric_value=target_lcoe,
            lower_bound=500.0,
            upper_bound=900.0,
        ),
        provider_override=provider,
    )

    assert result.converged
    assert result.break_even_parameter_value == pytest.approx(691.0, abs=1e-3)
