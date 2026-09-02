from __future__ import annotations

import bisect
import csv
import json
import statistics

from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from analysis.generation_scenarios import GenerationBasis
from analysis.project_evaluation import evaluate_standard_resource_cases
from analysis.wind_resource_analysis import (
    assess_long_term_wind_resource,
    calculate_exceedance_generation_mwh,
)
from core.models import (
    FinancialInputs,
    Location,
    ProjectScenario,
    Technology,
    WindConfig,
)
from data.cache import JsonResourceCache
from data.wind_loader import OpenMeteoWindProvider, WindDataRequest


ROOT = Path(__file__).resolve().parents[1]
CURVE_PATH = ROOT / "data" / "reference" / "turbines" / "IEA_Reference_3.4MW_130.csv"
REPORT_PATH = ROOT / "reports" / "generated" / "jhimpir_wind_validation.json"


def _load_reference_curve() -> tuple[tuple[float, float], ...]:
    with CURVE_PATH.open(newline="", encoding="utf-8") as handle:
        return tuple(
            (
                float(row["Wind Speed [m/s]"]),
                float(row["Power [kW]"]) / 1000.0,
            )
            for row in csv.DictReader(handle)
        )


def _interpolate_reference_power_mw(
    wind_speed_ms: float,
    curve: tuple[tuple[float, float], ...],
) -> float:
    speeds = tuple(point[0] for point in curve)
    if wind_speed_ms < speeds[0] or wind_speed_ms >= 25.01:
        return 0.0
    if wind_speed_ms >= speeds[-1]:
        return curve[-1][1]

    upper_index = bisect.bisect_right(speeds, wind_speed_ms)
    lower_speed, lower_power = curve[upper_index - 1]
    upper_speed, upper_power = curve[upper_index]
    fraction = (wind_speed_ms - lower_speed) / (upper_speed - lower_speed)
    return lower_power + fraction * (upper_power - lower_power)


def _reference_annual_generation(
    *,
    resource,
    curve: tuple[tuple[float, float], ...],
    project_capacity_mw: float,
    turbine_rated_power_mw: float,
    availability: float,
) -> dict[int, float]:
    time_step_hours = resource.time_step_hours
    if time_step_hours is None:
        raise ValueError("Wind resource must contain a regular time step.")

    project_scale = project_capacity_mw / turbine_rated_power_mw
    generation_by_year: dict[int, list[float]] = defaultdict(list)
    for point in resource.points:
        power_mw = _interpolate_reference_power_mw(point.wind_speed_ms, curve)
        generation_by_year[point.timestamp.year].append(
            min(project_capacity_mw, power_mw * project_scale * availability)
            * time_step_hours
        )
    return {
        year: sum(interval_energy)
        for year, interval_energy in generation_by_year.items()
    }


def main() -> int:
    location = Location(
        name="Jhimpir, Sindh",
        latitude=25.025,
        longitude=67.95,
    )
    config = WindConfig(
        hub_height_m=100.0,
        cut_in_speed_ms=3.0,
        rated_speed_ms=9.8127,
        cut_out_speed_ms=25.01,
        turbine_rated_power_mw=3.37,
        availability=0.95,
        wind_shear_exponent=1.0 / 7.0,
    )
    project = ProjectScenario(
        scenario_id="WIND_JHIMPIR_VALIDATION",
        technology=Technology.WIND,
        location=location,
        capacity_mw=100.0,
        lifetime_years=30,
        annual_degradation_rate=0.0,
        finance=FinancialInputs(
            capex_per_kw=976.0,
            fixed_opex_per_kw_year=44.0,
            variable_opex_per_mwh=0.0,
            electricity_price_per_mwh=60.0,
            discount_rate=0.10,
        ),
        technology_config=config,
    )
    cache = JsonResourceCache(ROOT / "cache" / "resources")
    resource = OpenMeteoWindProvider(
        timeout_seconds=120.0,
        max_retries=3,
        cache=cache,
    ).fetch(
        WindDataRequest(
            location=location,
            start_date=date(2015, 1, 1),
            end_date=date(2024, 12, 31),
            measurement_height_m=100.0,
        )
    )
    assessment = assess_long_term_wind_resource(project, resource)
    evaluations = evaluate_standard_resource_cases(project, assessment)
    p50 = evaluations[GenerationBasis.P50]

    curve = _load_reference_curve()
    reference_by_year = _reference_annual_generation(
        resource=resource,
        curve=curve,
        project_capacity_mw=project.capacity_mw,
        turbine_rated_power_mw=config.turbine_rated_power_mw,
        availability=config.availability,
    )
    accepted_years = tuple(year.year for year in assessment.years)
    reference_values = tuple(reference_by_year[year] for year in accepted_years)
    reference_p50 = calculate_exceedance_generation_mwh(
        reference_values,
        exceedance_probability=0.50,
    )
    difference_fraction = assessment.p50_generation_mwh / reference_p50 - 1.0
    mean_wind_speed_ms = statistics.fmean(
        point.wind_speed_ms for point in resource.points
    )

    report = {
        "case": "100 MW onshore wind at Jhimpir, Sindh",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": {
            "scenario_id": project.scenario_id,
            "latitude": location.latitude,
            "longitude": location.longitude,
            "capacity_mw": project.capacity_mw,
            "hub_height_m": config.hub_height_m,
            "turbine_rated_power_mw": config.turbine_rated_power_mw,
            "cut_in_speed_ms": config.cut_in_speed_ms,
            "rated_speed_ms": config.rated_speed_ms,
            "cut_out_speed_ms": config.cut_out_speed_ms,
            "availability": config.availability,
            "historical_period": ["2015-01-01", "2024-12-31"],
        },
        "resource": {
            "source": resource.metadata.source_name,
            "dataset": resource.metadata.dataset_name,
            "sample_count": resource.sample_count,
            "measurement_height_m": resource.measurement_height_m,
            "resolved_latitude": resource.metadata.resolved_latitude,
            "resolved_longitude": resource.metadata.resolved_longitude,
            "mean_wind_speed_ms": mean_wind_speed_ms,
            "accepted_years": list(accepted_years),
            "excluded_years": list(assessment.excluded_years),
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
        "reference_curve_parity": {
            "source": "NLR Wind Turbine Power Curve Archive",
            "reference_curve": "IEA Reference 3.4 MW, 130 m rotor",
            "reference_p50_generation_mwh": reference_p50,
            "simulator_minus_reference_fraction": difference_fraction,
            "absolute_difference_fraction": abs(difference_fraction),
            "within_15_percent": abs(difference_fraction) <= 0.15,
        },
        "warnings": list(assessment.warnings),
        "method_notes": [
            "Both models use identical hourly Open-Meteo ERA5 100 m wind speeds.",
            "The reference curve is linearly interpolated between NLR archive points.",
            "This is an implementation-parity check, not independent turbine validation.",
            "Both models apply the same 95% availability and equivalent fractional turbine count.",
            (
                "Wake, electrical, icing, curtailment, and terrain-flow losses "
                "are not separately modelled."
            ),
            "Air-density correction is omitted because hub-height density is unavailable.",
        ],
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"REPORT_PATH={REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
