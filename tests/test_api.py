from __future__ import annotations

import math

from datetime import date, datetime, timedelta, timezone

import pytest

from fastapi.testclient import TestClient

from core.resources import (
    ResourceMetadata,
    SolarResourcePoint,
    SolarResourceSeries,
    WaveResourcePoint,
    WaveResourceSeries,
    WindResourcePoint,
    WindResourceSeries,
)
from simulator_api.main import app
from simulator_api.schemas import (
    AnalysisRequest,
    BreakEvenRequest,
    ComparisonRequest,
    JointUncertaintyRequest,
    OneWaySensitivityRequest,
    RiskAnalysisRequest,
    TwoWaySensitivityRequest,
)
from simulator_api.service import (
    run_analysis,
    run_break_even_analysis,
    run_comparison,
    run_joint_risk_analysis,
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


class _SyntheticWindProvider:
    def fetch(self, request):
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        return WindResourceSeries(
            location=request.location,
            metadata=ResourceMetadata(
                source_name="Synthetic test provider",
                dataset_name="Deterministic hourly fixture",
                retrieved_at=datetime.now(timezone.utc),
                resolved_latitude=request.location.latitude,
                resolved_longitude=request.location.longitude,
                provider_timezone="UTC",
            ),
            measurement_height_m=request.measurement_height_m,
            points=tuple(
                WindResourcePoint(
                    timestamp=start + timedelta(hours=index),
                    wind_speed_ms=speed,
                )
                for index, speed in enumerate((4.0, 6.0, 8.0, 10.0))
            ),
        )


class _SyntheticWaveProvider:
    def fetch(self, request):
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        return WaveResourceSeries(
            location=request.location,
            metadata=ResourceMetadata(
                source_name="Synthetic test provider",
                dataset_name="Deterministic hourly fixture",
                retrieved_at=datetime.now(timezone.utc),
                resolved_latitude=request.location.latitude,
                resolved_longitude=request.location.longitude,
                provider_timezone="UTC",
            ),
            points=tuple(
                WaveResourcePoint(
                    timestamp=start + timedelta(hours=index),
                    significant_wave_height_m=height,
                    energy_period_s=6.0,
                )
                for index, height in enumerate((0.8, 1.0, 1.2, 1.4))
            ),
            water_depth_m=50.0,
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


def _three_requests() -> list[AnalysisRequest]:
    solar = _request()
    shared = solar.model_dump(mode="json")
    wind = AnalysisRequest.model_validate(
        {
            **shared,
            "scenario_id": "API_WIND_TEST",
            "technology": "wind",
            "solar": None,
            "wind": {},
        }
    )
    wave = AnalysisRequest.model_validate(
        {
            **shared,
            "scenario_id": "API_WAVE_TEST",
            "technology": "wave",
            "location": {
                "name": "Synthetic offshore site",
                "latitude": 24.5,
                "longitude": 66.5,
            },
            "solar": None,
            "wave": {},
        }
    )
    return [solar, wind, wave]


def test_health_endpoint_exposes_versions():
    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["software_version"]
    assert response.json()["methodology_version"]
    assert "/api/v1/risk/joint" in TestClient(app).get("/openapi.json").json()["paths"]


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


def test_joint_risk_uses_aligned_worlds_and_is_reproducible():
    analyses = _three_requests()
    request = JointUncertaintyRequest.model_validate(
        {
            "technologies": [
                {
                    "analysis": analysis.model_dump(mode="json"),
                    "variables": [
                        {
                            "name": "capex_per_kw",
                            "distribution": "uniform",
                            "minimum_value": 600.0,
                            "maximum_value": 800.0,
                        }
                    ],
                }
                for analysis in analyses
            ],
            "shared_variables": [
                {
                    "name": "electricity_price_per_mwh",
                    "distribution": "uniform",
                    "minimum_value": 50.0,
                    "maximum_value": 80.0,
                }
            ],
            "metrics": ["npv", "lcoe"],
            "sample_count": 12,
            "random_seed": 19,
            "resource_resampling_mode": "none",
        }
    )
    providers = [
        _SyntheticSolarProvider(),
        _SyntheticWindProvider(),
        _SyntheticWaveProvider(),
    ]

    first = run_joint_risk_analysis(request, provider_overrides=providers)
    second = run_joint_risk_analysis(
        request,
        provider_overrides=[
            _SyntheticSolarProvider(),
            _SyntheticWindProvider(),
            _SyntheticWaveProvider(),
        ],
    )

    assert first == second
    assert first.sample_count == 12
    assert len(first.iterations) == 12
    assert all(len(world.technology_results) == 3 for world in first.iterations)
    assert len(first.comparisons) == 6
    assert all(comparison.valid_pair_count == 12 for comparison in first.comparisons)
    assert all(
        comparison.probability_a_better
        + comparison.probability_b_better
        + comparison.probability_tie
        == pytest.approx(1.0)
        for comparison in first.comparisons
    )
    solar_wind_npv = next(
        comparison
        for comparison in first.comparisons
        if comparison.metric == "npv"
        and {comparison.technology_a.value, comparison.technology_b.value}
        == {"solar", "wind"}
    )
    direct_wins = 0
    for world in first.iterations:
        values = {
            result.technology.value: result.npv_usd
            for result in world.technology_results
        }
        if values["solar"] > values["wind"] and not math.isclose(
            values["solar"], values["wind"], rel_tol=0, abs_tol=1e-9
        ):
            direct_wins += 1
    expected_solar_probability = direct_wins / first.sample_count
    reported_solar_probability = (
        solar_wind_npv.probability_a_better
        if solar_wind_npv.technology_a.value == "solar"
        else solar_wind_npv.probability_b_better
    )
    assert reported_solar_probability == pytest.approx(expected_solar_probability)


def test_joint_risk_schema_requires_one_of_each_technology():
    solar = _request().model_dump(mode="json")
    with pytest.raises(ValueError, match="exactly one Solar"):
        JointUncertaintyRequest.model_validate(
            {
                "technologies": [
                    {"analysis": {**solar, "scenario_id": f"SOLAR_{index}"}}
                    for index in range(3)
                ],
                "shared_variables": [
                    {
                        "name": "electricity_price_per_mwh",
                        "distribution": "uniform",
                        "minimum_value": 50.0,
                        "maximum_value": 80.0,
                    }
                ],
            }
        )


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
