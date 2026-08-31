from __future__ import annotations

import json

from datetime import date, datetime, timezone
from pathlib import Path

import requests

from analysis.generation_scenarios import GenerationBasis
from analysis.project_evaluation import evaluate_standard_resource_cases
from analysis.solar_resource_analysis import assess_long_term_solar_resource
from core.models import (
    FinancialInputs,
    Location,
    ProjectScenario,
    SolarConfig,
    Technology,
)
from data.cache import JsonResourceCache
from data.solar_loader import OpenMeteoSolarProvider, SolarDataRequest


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "reports" / "generated" / "jhimpir_solar_validation.json"


def _fetch_pvgis_specific_yield(
    *,
    location: Location,
    tilt_deg: float,
    system_losses: float,
    cache: JsonResourceCache,
) -> dict:
    endpoint = "https://re.jrc.ec.europa.eu/api/v5_3/PVcalc"
    params = {
        "lat": location.latitude,
        "lon": location.longitude,
        "peakpower": 1.0,
        "loss": round(system_losses * 100.0, 3),
        "angle": tilt_deg,
        "aspect": 0.0,
        "pvtechchoice": "crystSi",
        "mountingplace": "free",
        "raddatabase": "PVGIS-ERA5",
        "outputformat": "json",
    }
    material = {"endpoint": endpoint, "params": params}
    cached = cache.get(
        "pvgis-validation",
        material,
        max_age_seconds=30 * 24 * 60 * 60,
    )
    if cached is not None:
        return cached.payload

    response = requests.get(endpoint, params=params, timeout=120)
    response.raise_for_status()
    payload = response.json()
    cache.put("pvgis-validation", material, payload)
    return payload


def main() -> int:
    location = Location(
        name="Jhimpir, Sindh",
        latitude=25.025,
        longitude=67.95,
    )
    config = SolarConfig(
        tilt_deg=25.0,
        azimuth_deg=180.0,
        system_losses=0.141,
    )
    project = ProjectScenario(
        scenario_id="SOLAR_JHIMPIR_VALIDATION",
        technology=Technology.SOLAR,
        location=location,
        capacity_mw=100.0,
        lifetime_years=30,
        annual_degradation_rate=0.007,
        finance=FinancialInputs(
            capex_per_kw=667.0,
            fixed_opex_per_kw_year=22.0,
            variable_opex_per_mwh=0.0,
            electricity_price_per_mwh=60.0,
            discount_rate=0.10,
        ),
        technology_config=config,
    )
    cache = JsonResourceCache(ROOT / "cache" / "resources")
    request = SolarDataRequest(
        location=location,
        solar_config=config,
        start_date=date(2015, 1, 1),
        end_date=date(2024, 12, 31),
    )
    resource = OpenMeteoSolarProvider(
        timeout_seconds=120.0,
        max_retries=3,
        cache=cache,
    ).fetch(request)
    assessment = assess_long_term_solar_resource(project, resource)
    evaluations = evaluate_standard_resource_cases(project, assessment)
    p50 = evaluations[GenerationBasis.P50]

    pvgis_payload = _fetch_pvgis_specific_yield(
        location=location,
        tilt_deg=config.tilt_deg,
        system_losses=config.system_losses,
        cache=cache,
    )
    pvgis_totals = pvgis_payload["outputs"]["totals"]["fixed"]
    pvgis_specific_yield_kwh_per_kwp = float(pvgis_totals["E_y"])
    simulator_specific_yield_kwh_per_kwp = (
        assessment.p50_generation_mwh / project.capacity_mw
    )
    difference_fraction = (
        simulator_specific_yield_kwh_per_kwp
        / pvgis_specific_yield_kwh_per_kwp
        - 1.0
    )

    report = {
        "case": "100 MW fixed-tilt utility solar at Jhimpir, Sindh",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": {
            "scenario_id": project.scenario_id,
            "latitude": location.latitude,
            "longitude": location.longitude,
            "capacity_mw": project.capacity_mw,
            "tilt_deg": config.tilt_deg,
            "azimuth_deg_internal": config.azimuth_deg,
            "system_losses": config.system_losses,
            "historical_period": ["2015-01-01", "2024-12-31"],
        },
        "resource": {
            "source": resource.metadata.source_name,
            "dataset": resource.metadata.dataset_name,
            "sample_count": resource.sample_count,
            "resolved_latitude": resource.metadata.resolved_latitude,
            "resolved_longitude": resource.metadata.resolved_longitude,
            "accepted_years": [year.year for year in assessment.years],
            "excluded_years": list(assessment.excluded_years),
        },
        "generation": {
            "p90_mwh": assessment.p90_generation_mwh,
            "p50_mwh": assessment.p50_generation_mwh,
            "p10_mwh": assessment.p10_generation_mwh,
            "p50_capacity_factor": p50.equivalent_first_year_capacity_factor,
            "p50_specific_yield_kwh_per_kwp": simulator_specific_yield_kwh_per_kwp,
        },
        "economics_p50": {
            "lcoe_usd_per_mwh": p50.lcoe_usd_per_mwh,
            "npv_usd": p50.npv_usd,
            "project_irr": p50.irr,
            "simple_payback_years": p50.simple_payback_years,
            "discounted_payback_years": p50.discounted_payback_years,
        },
        "independent_validation": {
            "source": "European Commission JRC PVGIS 5.3 PVcalc",
            "radiation_database": "PVGIS-ERA5",
            "pvgis_specific_yield_kwh_per_kwp": pvgis_specific_yield_kwh_per_kwp,
            "simulator_minus_pvgis_fraction": difference_fraction,
            "absolute_difference_fraction": abs(difference_fraction),
            "within_15_percent": abs(difference_fraction) <= 0.15,
        },
        "warnings": list(dict.fromkeys((*assessment.warnings, *p50.warnings))),
        "method_notes": [
            "Open-Meteo ERA5 global tilted irradiance is used interval by interval.",
            "Open-Meteo ambient temperature is not treated as PV cell temperature.",
            (
                "PVGIS is an independent implementation cross-check over ERA5, "
                "not a calibration target."
            ),
            "PVGIS-SARAH3 rejected this longitude as outside its spatial coverage.",
        ],
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"REPORT_PATH={REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
