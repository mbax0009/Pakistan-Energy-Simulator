from __future__ import annotations

import json
import math
import statistics

from datetime import date, datetime, timezone
from pathlib import Path

from analysis.generation_scenarios import GenerationBasis
from analysis.project_evaluation import evaluate_standard_resource_cases
from analysis.wave_resource_analysis import assess_long_term_wave_resource
from core.models import (
    FinancialInputs,
    Location,
    ProjectScenario,
    Technology,
    WaveConfig,
)
from data.cache import JsonResourceCache
from data.wave_loader import OpenMeteoMarineWaveProvider, WaveDataRequest
from physics.wave import calculate_wave_power_flux_kw_per_m


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "reports" / "generated" / "karachi_offshore_wave_validation.json"


def main() -> int:
    location = Location(
        name="Arabian Sea offshore Karachi",
        latitude=24.5,
        longitude=66.5,
    )
    config = WaveConfig(
        conversion_efficiency=0.30,
        capture_width_m=20.0,
        device_rated_power_mw=1.0,
        availability=0.90,
    )
    project = ProjectScenario(
        scenario_id="WAVE_KARACHI_OFFSHORE_VALIDATION",
        technology=Technology.WAVE,
        location=location,
        capacity_mw=100.0,
        lifetime_years=25,
        annual_degradation_rate=0.01,
        finance=FinancialInputs(
            capex_per_kw=5000.0,
            fixed_opex_per_kw_year=150.0,
            variable_opex_per_mwh=0.0,
            electricity_price_per_mwh=60.0,
            discount_rate=0.10,
        ),
        technology_config=config,
    )
    cache = JsonResourceCache(ROOT / "cache" / "resources")
    resource = OpenMeteoMarineWaveProvider(
        timeout_seconds=120.0,
        max_retries=3,
        cache=cache,
    ).fetch(
        WaveDataRequest(
            location=location,
            start_date=date(2015, 1, 1),
            end_date=date(2024, 12, 31),
            include_bathymetry=False,
        )
    )
    assessment = assess_long_term_wave_resource(project, resource)
    evaluations = evaluate_standard_resource_cases(project, assessment)
    p50 = evaluations[GenerationBasis.P50]

    exact_flux_values = tuple(
        calculate_wave_power_flux_kw_per_m(
            point.significant_wave_height_m,
            point.energy_period_s,
        )
        for point in resource.points
    )
    approximate_flux_values = tuple(
        0.49
        * point.significant_wave_height_m**2
        * point.energy_period_s
        for point in resource.points
    )
    positive_pairs = tuple(
        (exact, approximate)
        for exact, approximate in zip(exact_flux_values, approximate_flux_values)
        if exact > 0
    )
    maximum_relative_formula_difference = max(
        abs(approximate / exact - 1.0)
        for exact, approximate in positive_pairs
    )

    report = {
        "case": "100 MW wave-energy research scenario offshore Karachi",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": {
            "scenario_id": project.scenario_id,
            "latitude": location.latitude,
            "longitude": location.longitude,
            "capacity_mw": project.capacity_mw,
            "conversion_efficiency": config.conversion_efficiency,
            "effective_capture_width_m": config.capture_width_m,
            "device_rated_power_mw": config.device_rated_power_mw,
            "availability": config.availability,
            "historical_period": ["2015-01-01", "2024-12-31"],
            "economics_classification": "explicit pre-commercial research scenario",
        },
        "resource": {
            "source": resource.metadata.source_name,
            "dataset": resource.metadata.dataset_name,
            "sample_count": resource.sample_count,
            "resolved_latitude": resource.metadata.resolved_latitude,
            "resolved_longitude": resource.metadata.resolved_longitude,
            "mean_significant_wave_height_m": statistics.fmean(
                point.significant_wave_height_m for point in resource.points
            ),
            "mean_period_proxy_s": statistics.fmean(
                point.energy_period_s for point in resource.points
            ),
            "mean_deep_water_flux_kw_per_m": statistics.fmean(exact_flux_values),
            "accepted_years": [year.year for year in assessment.years],
            "excluded_years": list(assessment.excluded_years),
            "water_depth_m": resource.water_depth_m,
        },
        "generation": {
            "p90_mwh": assessment.p90_generation_mwh,
            "p50_mwh": assessment.p50_generation_mwh,
            "p10_mwh": assessment.p10_generation_mwh,
            "p50_capacity_factor": p50.equivalent_first_year_capacity_factor,
        },
        "economics_p50": {
            "lcoe_usd_per_mwh": p50.lcoe_usd_per_mwh,
            "npv_usd": p50.npv_usd,
            "project_irr": p50.irr,
            "simple_payback_years": p50.simple_payback_years,
            "discounted_payback_years": p50.discounted_payback_years,
        },
        "independent_formula_validation": {
            "reference": "J approximately 0.49 * Hs^2 * Te kW/m",
            "exact_coefficient_kw_per_m": (
                calculate_wave_power_flux_kw_per_m(1.0, 1.0)
            ),
            "approximate_coefficient_kw_per_m": 0.49,
            "maximum_relative_difference": maximum_relative_formula_difference,
            "within_1_percent": maximum_relative_formula_difference <= 0.01,
        },
        "warnings": list(assessment.warnings),
        "method_notes": [
            "Open-Meteo ERA5-Ocean wave_period is used as a proxy for energy period.",
            "Copernicus WAVERYS VTM10 remains the preferred production variable.",
            (
                "Copernicus cross-validation is pending user credentials; "
                "credentials are never bundled."
            ),
            "Bathymetry is unavailable in this fallback, so deep-water validity is not checked.",
            (
                "The device model uses assumed capture width and efficiency, "
                "not a device power matrix."
            ),
            "CAPEX and OPEX are scenario inputs, not claims about a mature Pakistan wave market.",
        ],
    }
    if not math.isfinite(maximum_relative_formula_difference):
        raise ValueError("Wave formula validation produced a non-finite difference.")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"REPORT_PATH={REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
