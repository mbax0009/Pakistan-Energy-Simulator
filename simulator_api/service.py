from __future__ import annotations

import os

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from analysis.evaluators import (
    EvaluationContext,
    create_parameter_evaluator,
    evaluate_scenario_modification,
)
from analysis.comparison import compare_projects
from analysis.monte_carlo_evaluators import create_monte_carlo_evaluator
from analysis.project_evaluation import ProjectEvaluation, evaluate_standard_resource_cases
from analysis.risk_analysis import build_project_risk_profile
from analysis.scenario_builders import (
    RecalculationScope,
    ScenarioModification,
    ScenarioParameter,
    apply_scenario_parameter,
    get_recalculation_scope,
)
from analysis.sensitivity import (
    find_break_even_parameter,
    run_one_way_sensitivity,
)
from analysis.solar_resource_analysis import assess_long_term_solar_resource
from analysis.two_way_sensitivity import (
    build_competitiveness_map,
    estimate_competitiveness_frontier,
    run_two_way_sensitivity,
)
from analysis.uncertainty import (
    EmpiricalDistribution,
    TriangularDistribution,
    TruncatedNormalDistribution,
    UncertainVariable,
    UniformDistribution,
    run_monte_carlo,
)
from analysis.wave_resource_analysis import assess_long_term_wave_resource
from analysis.wind_resource_analysis import assess_long_term_wind_resource
from core.models import (
    FinancialInputs,
    Location,
    ProjectScenario,
    SolarConfig,
    Technology,
    WaveConfig,
    WindConfig,
)
from data.cache import JsonResourceCache
from data.solar_loader import OpenMeteoSolarProvider, SolarDataRequest
from data.wave_loader import (
    CopernicusMarineWaveProvider,
    OpenMeteoMarineWaveProvider,
    WaveDataRequest,
)
from data.wind_loader import OpenMeteoWindProvider, WindDataRequest
from simulator_api.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    AnnualGenerationSummary,
    BreakEvenRequest,
    BreakEvenResponse,
    ComparisonRequest,
    ComparisonResponse,
    ComparisonRowOutput,
    DistributionKind,
    EvaluationSummary,
    GenerationStatistics,
    MetricDistributionOutput,
    OneWaySensitivityRequest,
    OneWaySensitivityResponse,
    ReproducibilitySummary,
    ResourceProvider,
    ResourceSummary,
    RiskAnalysisRequest,
    RiskAnalysisResponse,
    RiskSampleOutput,
    RankingOutput,
    SensitivityPointOutput,
    TwoWaySensitivityPointOutput,
    TwoWaySensitivityRequest,
    TwoWaySensitivityResponse,
)
from simulator_api.version import METHODOLOGY_VERSION, VERSION


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def cache_root() -> Path:
    configured = os.getenv("PAK_ENERGY_CACHE_DIR", "cache/resources")
    path = Path(configured)
    return path if path.is_absolute() else PROJECT_ROOT / path


def build_cache() -> JsonResourceCache:
    return JsonResourceCache(cache_root())


def _location(request: AnalysisRequest) -> Location:
    return Location(
        name=request.location.name,
        latitude=request.location.latitude,
        longitude=request.location.longitude,
    )


def _finance(request: AnalysisRequest) -> FinancialInputs:
    return FinancialInputs(**request.financial.model_dump())


def _technology_config(request: AnalysisRequest):
    if request.technology is Technology.SOLAR:
        assert request.solar is not None
        return SolarConfig(**request.solar.model_dump())
    if request.technology is Technology.WIND:
        assert request.wind is not None
        return WindConfig(**request.wind.model_dump())
    assert request.wave is not None
    return WaveConfig(**request.wave.model_dump())


def _project(request: AnalysisRequest) -> ProjectScenario:
    return ProjectScenario(
        scenario_id=request.scenario_id,
        technology=request.technology,
        location=_location(request),
        capacity_mw=request.capacity_mw,
        lifetime_years=request.lifetime_years,
        annual_degradation_rate=request.annual_degradation_rate,
        finance=_finance(request),
        technology_config=_technology_config(request),
    )


def _select_provider(
    request: AnalysisRequest,
    cache: JsonResourceCache,
    provider_override: Any | None,
):
    if provider_override is not None:
        return provider_override

    requested_provider = request.resource.provider
    if request.technology is Technology.SOLAR:
        if requested_provider is ResourceProvider.COPERNICUS:
            raise ValueError("Copernicus is not a supported solar provider.")
        return OpenMeteoSolarProvider(cache=cache)

    if request.technology is Technology.WIND:
        if requested_provider is ResourceProvider.COPERNICUS:
            raise ValueError("Copernicus is not a supported wind provider.")
        return OpenMeteoWindProvider(cache=cache)

    if requested_provider is ResourceProvider.COPERNICUS:
        credentials_file = os.getenv("PAK_ENERGY_COPERNICUS_CREDENTIALS_FILE") or None
        return CopernicusMarineWaveProvider(credentials_file=credentials_file)
    return OpenMeteoMarineWaveProvider(cache=cache)


def _fetch_and_assess(
    request: AnalysisRequest,
    project: ProjectScenario,
    provider,
):
    period = request.resource
    if request.technology is Technology.SOLAR:
        assert isinstance(project.technology_config, SolarConfig)
        resource = provider.fetch(
            SolarDataRequest(
                location=project.location,
                solar_config=project.technology_config,
                start_date=period.start_date,
                end_date=period.end_date,
            )
        )
        assessment = assess_long_term_solar_resource(
            project,
            resource,
            minimum_year_completeness=period.minimum_year_completeness,
        )
    elif request.technology is Technology.WIND:
        resource = provider.fetch(
            WindDataRequest(
                location=project.location,
                start_date=period.start_date,
                end_date=period.end_date,
                measurement_height_m=100.0,
            )
        )
        assessment = assess_long_term_wind_resource(
            project,
            resource,
            minimum_year_completeness=period.minimum_year_completeness,
        )
    else:
        resource = provider.fetch(
            WaveDataRequest(
                location=project.location,
                start_date=period.start_date,
                end_date=period.end_date,
                include_bathymetry=True,
            )
        )
        assessment = assess_long_term_wave_resource(
            project,
            resource,
            minimum_year_completeness=period.minimum_year_completeness,
        )
    return resource, assessment


def _evaluation_summary(evaluation: ProjectEvaluation) -> EvaluationSummary:
    return EvaluationSummary(
        generation_basis=evaluation.generation_basis.value,
        first_year_generation_mwh=evaluation.first_year_generation_mwh,
        final_year_generation_mwh=evaluation.final_year_generation_mwh,
        lifetime_generation_mwh=evaluation.lifetime_generation_mwh,
        equivalent_first_year_capacity_factor=(
            evaluation.equivalent_first_year_capacity_factor
        ),
        initial_capex_usd=evaluation.initial_capex_usd,
        npv_usd=evaluation.npv_usd,
        project_irr=evaluation.irr,
        lcoe_usd_per_mwh=evaluation.lcoe_usd_per_mwh,
        simple_payback_years=evaluation.simple_payback_years,
        discounted_payback_years=evaluation.discounted_payback_years,
        lifetime_revenue_usd=evaluation.lifetime_revenue_usd,
        lifetime_opex_usd=evaluation.lifetime_opex_usd,
        additional_capex_usd=evaluation.additional_capex_usd,
    )


def run_analysis(
    request: AnalysisRequest,
    *,
    provider_override: Any | None = None,
) -> AnalysisResponse:
    project = _project(request)
    cache = build_cache()
    provider = _select_provider(request, cache, provider_override)
    resource, assessment = _fetch_and_assess(request, project, provider)
    evaluations = evaluate_standard_resource_cases(project, assessment)

    warnings = list(assessment.warnings)
    for evaluation in evaluations.values():
        warnings.extend(evaluation.warnings)
    if (
        project.technology is Technology.WAVE
        and isinstance(provider, OpenMeteoMarineWaveProvider)
    ):
        warnings.append(
            "Open-Meteo ERA5-Ocean mean wave period is being used as a proxy "
            "for energy period; Copernicus VTM10 is preferred for final studies."
        )

    time_step_hours = resource.time_step_hours
    if time_step_hours is None:
        raise ValueError("Resource time step could not be determined.")

    annual_generation = [
        AnnualGenerationSummary(
            year=item.year,
            generation_mwh=item.generation_mwh,
            capacity_factor=item.capacity_factor,
            completeness_ratio=item.completeness_ratio,
        )
        for item in assessment.years
    ]
    resource_summary = ResourceSummary(
        source_name=resource.metadata.source_name,
        dataset_name=resource.metadata.dataset_name,
        source_reference=resource.metadata.source_reference,
        requested_latitude=resource.location.latitude,
        requested_longitude=resource.location.longitude,
        resolved_latitude=resource.metadata.resolved_latitude,
        resolved_longitude=resource.metadata.resolved_longitude,
        start_time=resource.start_time,
        end_time=resource.end_time,
        sample_count=resource.sample_count,
        time_step_hours=time_step_hours,
        water_depth_m=getattr(resource, "water_depth_m", None),
    )
    statistics = GenerationStatistics(
        p90_mwh=assessment.p90_generation_mwh,
        p50_mwh=assessment.p50_generation_mwh,
        p10_mwh=assessment.p10_generation_mwh,
        mean_mwh=assessment.mean_generation_mwh,
        median_mwh=assessment.median_generation_mwh,
        coefficient_of_variation=assessment.coefficient_of_variation,
        minimum_mwh=assessment.minimum_generation_mwh,
        maximum_mwh=assessment.maximum_generation_mwh,
        worst_year=assessment.worst_year,
        best_year=assessment.best_year,
        accepted_years=[item.year for item in assessment.years],
        excluded_years=list(assessment.excluded_years),
    )
    assumptions = {
        "classification": "user_input",
        "project": {
            "capacity_mw": project.capacity_mw,
            "lifetime_years": project.lifetime_years,
            "annual_degradation_rate": project.annual_degradation_rate,
        },
        "financial": request.financial.model_dump(mode="json"),
        "technology": asdict(project.technology_config),
    }
    return AnalysisResponse(
        scenario_id=project.scenario_id,
        technology=project.technology,
        resource=resource_summary,
        annual_generation=annual_generation,
        generation_statistics=statistics,
        evaluations={
            basis.value: _evaluation_summary(evaluation)
            for basis, evaluation in evaluations.items()
        },
        warnings=list(dict.fromkeys(warnings)),
        assumptions=assumptions,
        reproducibility=ReproducibilitySummary(
            software_version=VERSION,
            methodology_version=METHODOLOGY_VERSION,
            generated_at=datetime.now(timezone.utc),
        ),
    )


def _prepare_context(
    request: AnalysisRequest,
    generation_basis,
    provider_override: Any | None = None,
) -> tuple[EvaluationContext, Any]:
    project = _project(request)
    provider = _select_provider(request, build_cache(), provider_override)
    resource, assessment = _fetch_and_assess(request, project, provider)
    evaluations = evaluate_standard_resource_cases(project, assessment)
    if generation_basis not in evaluations:
        raise ValueError(
            "Sensitivity and risk endpoints currently support P90, P50, P10, "
            "mean, and median generation bases."
        )
    evaluation = evaluations[generation_basis]

    def resource_loader(modified_project: ProjectScenario):
        if modified_project.technology is not Technology.SOLAR:
            raise ValueError("Only solar orientation currently requires resource reloading.")
        assert isinstance(modified_project.technology_config, SolarConfig)
        return provider.fetch(
            SolarDataRequest(
                location=modified_project.location,
                solar_config=modified_project.technology_config,
                start_date=request.resource.start_date,
                end_date=request.resource.end_date,
            )
        )

    return (
        EvaluationContext(
            project=project,
            resource=resource,
            assessment=assessment,
            generation_scenario=evaluation.generation_scenario,
            evaluation=evaluation,
            generation_basis=generation_basis,
            resource_loader=resource_loader,
        ),
        provider,
    )


def _baseline_parameter_value(
    project: ProjectScenario,
    parameter: ScenarioParameter,
) -> float:
    finance_fields = {
        ScenarioParameter.CAPEX_PER_KW: "capex_per_kw",
        ScenarioParameter.FIXED_OPEX_PER_KW_YEAR: "fixed_opex_per_kw_year",
        ScenarioParameter.VARIABLE_OPEX_PER_MWH: "variable_opex_per_mwh",
        ScenarioParameter.ELECTRICITY_PRICE_PER_MWH: "electricity_price_per_mwh",
        ScenarioParameter.DISCOUNT_RATE: "discount_rate",
        ScenarioParameter.ELECTRICITY_PRICE_GROWTH_RATE: "electricity_price_growth_rate",
        ScenarioParameter.OPEX_GROWTH_RATE: "opex_growth_rate",
    }
    if parameter in finance_fields:
        return float(getattr(project.finance, finance_fields[parameter]))
    if parameter is ScenarioParameter.ANNUAL_DEGRADATION_RATE:
        return project.annual_degradation_rate

    config_fields = {
        ScenarioParameter.SOLAR_TILT_DEG: "tilt_deg",
        ScenarioParameter.SOLAR_AZIMUTH_DEG: "azimuth_deg",
        ScenarioParameter.SOLAR_SYSTEM_LOSSES: "system_losses",
        ScenarioParameter.SOLAR_TEMPERATURE_COEFFICIENT: "temperature_coefficient_per_c",
        ScenarioParameter.WIND_HUB_HEIGHT_M: "hub_height_m",
        ScenarioParameter.WIND_SHEAR_EXPONENT: "wind_shear_exponent",
        ScenarioParameter.WIND_AVAILABILITY: "availability",
        ScenarioParameter.WIND_CUT_IN_SPEED_MS: "cut_in_speed_ms",
        ScenarioParameter.WIND_RATED_SPEED_MS: "rated_speed_ms",
        ScenarioParameter.WIND_CUT_OUT_SPEED_MS: "cut_out_speed_ms",
        ScenarioParameter.WAVE_CONVERSION_EFFICIENCY: "conversion_efficiency",
        ScenarioParameter.WAVE_CAPTURE_WIDTH_M: "capture_width_m",
        ScenarioParameter.WAVE_AVAILABILITY: "availability",
        ScenarioParameter.WAVE_DEVICE_RATED_POWER_MW: "device_rated_power_mw",
    }
    return float(getattr(project.technology_config, config_fields[parameter]))


def run_one_way_analysis(
    request: OneWaySensitivityRequest,
    *,
    provider_override: Any | None = None,
) -> OneWaySensitivityResponse:
    context, _ = _prepare_context(
        request.analysis,
        request.generation_basis,
        provider_override,
    )
    evaluator = create_parameter_evaluator(context, request.parameter)
    baseline_value = _baseline_parameter_value(context.project, request.parameter)
    result = run_one_way_sensitivity(
        parameter_name=request.parameter.value,
        parameter_values=request.values,
        evaluator=evaluator,
        metric=request.metric,
        baseline_parameter_value=baseline_value,
        baseline_evaluation=context.evaluation,
    )
    return OneWaySensitivityResponse(
        parameter=request.parameter,
        metric=request.metric,
        generation_basis=request.generation_basis,
        points=[
            SensitivityPointOutput(
                parameter_value=point.parameter_value,
                metric_value=point.metric_value,
            )
            for point in result.points
        ],
        baseline_parameter_value=result.baseline_parameter_value,
        baseline_metric_value=result.baseline_metric_value,
        warnings=list(result.warnings),
    )


def run_break_even_analysis(
    request: BreakEvenRequest,
    *,
    provider_override: Any | None = None,
) -> BreakEvenResponse:
    context, _ = _prepare_context(
        request.analysis,
        request.generation_basis,
        provider_override,
    )
    result = find_break_even_parameter(
        parameter_name=request.parameter.value,
        evaluator=create_parameter_evaluator(context, request.parameter),
        metric=request.metric,
        target_metric_value=request.target_metric_value,
        lower_bound=request.lower_bound,
        upper_bound=request.upper_bound,
    )
    return BreakEvenResponse(
        parameter=request.parameter,
        metric=request.metric,
        target_metric_value=result.target_metric_value,
        break_even_parameter_value=result.break_even_parameter_value,
        achieved_metric_value=result.achieved_metric_value,
        converged=result.converged,
        iterations=result.iterations,
        lower_bound=result.lower_bound,
        upper_bound=result.upper_bound,
        warning=result.warning,
    )


_SCOPE_ORDER = {
    RecalculationScope.FINANCE_ONLY: 0,
    RecalculationScope.LIFECYCLE_AND_FINANCE: 1,
    RecalculationScope.PHYSICS_AND_DOWNSTREAM: 2,
    RecalculationScope.RESOURCE_AND_DOWNSTREAM: 3,
}


def run_two_way_analysis(
    request: TwoWaySensitivityRequest,
    *,
    provider_override: Any | None = None,
) -> TwoWaySensitivityResponse:
    context, _ = _prepare_context(
        request.analysis,
        request.generation_basis,
        provider_override,
    )
    x_scope = get_recalculation_scope(request.x_parameter)
    y_scope = get_recalculation_scope(request.y_parameter)
    combined_scope = max((x_scope, y_scope), key=_SCOPE_ORDER.__getitem__)

    def evaluator(x_value: float, y_value: float) -> ProjectEvaluation:
        x_modification = apply_scenario_parameter(
            context.project,
            request.x_parameter,
            x_value,
        )
        y_modification = apply_scenario_parameter(
            x_modification.project,
            request.y_parameter,
            y_value,
        )
        combined = ScenarioModification(
            project=y_modification.project,
            parameter=request.y_parameter,
            parameter_value=y_value,
            recalculation_scope=combined_scope,
        )
        return evaluate_scenario_modification(combined, context)

    result = run_two_way_sensitivity(
        x_parameter_name=request.x_parameter.value,
        x_values=request.x_values,
        y_parameter_name=request.y_parameter.value,
        y_values=request.y_values,
        evaluator=evaluator,
        metric=request.metric,
    )
    competitiveness = None
    frontier: tuple[tuple[float, float], ...] = ()
    if request.benchmark_value is not None:
        competitiveness = build_competitiveness_map(result, request.benchmark_value)
        frontier = estimate_competitiveness_frontier(competitiveness)

    competitive_by_coordinate = {}
    if competitiveness is not None:
        competitive_by_coordinate = {
            (point.x_parameter_value, point.y_parameter_value): point.is_competitive
            for point in competitiveness.points
        }
    return TwoWaySensitivityResponse(
        x_parameter=request.x_parameter,
        x_values=list(result.x_values),
        y_parameter=request.y_parameter,
        y_values=list(result.y_values),
        metric=request.metric,
        generation_basis=request.generation_basis,
        benchmark_value=request.benchmark_value,
        lower_is_better=(
            None if competitiveness is None else competitiveness.lower_is_better
        ),
        points=[
            TwoWaySensitivityPointOutput(
                x_value=point.x_parameter_value,
                y_value=point.y_parameter_value,
                metric_value=point.metric_value,
                is_competitive=competitive_by_coordinate.get(
                    (point.x_parameter_value, point.y_parameter_value)
                ),
            )
            for point in result.points
        ],
        frontier=list(frontier),
        warnings=list(result.warnings),
    )


def _distribution(variable):
    if variable.distribution is DistributionKind.UNIFORM:
        return UniformDistribution(variable.minimum_value, variable.maximum_value)
    if variable.distribution is DistributionKind.TRIANGULAR:
        return TriangularDistribution(
            variable.minimum_value,
            variable.mode_value,
            variable.maximum_value,
        )
    if variable.distribution is DistributionKind.TRUNCATED_NORMAL:
        return TruncatedNormalDistribution(
            mean=variable.mean,
            standard_deviation=variable.standard_deviation,
            minimum_value=variable.minimum_value,
            maximum_value=variable.maximum_value,
        )
    return EmpiricalDistribution(tuple(variable.values or ()))


def run_risk_analysis(
    request: RiskAnalysisRequest,
    *,
    provider_override: Any | None = None,
) -> RiskAnalysisResponse:
    context, _ = _prepare_context(
        request.analysis,
        request.generation_basis,
        provider_override,
    )
    variables = tuple(
        UncertainVariable(
            name=variable.name.value,
            distribution=_distribution(variable),
            units=variable.units,
        )
        for variable in request.variables
    )
    evaluator = create_monte_carlo_evaluator(
        context,
        resource_resampling_mode=request.resource_resampling_mode,
        resource_random_seed=(
            None if request.random_seed is None else request.random_seed + 1000
        ),
    )
    analysis = run_monte_carlo(
        scenario_id=context.project.scenario_id,
        variables=variables,
        evaluator=evaluator,
        sample_count=request.sample_count,
        random_seed=request.random_seed,
        irr_hurdle_rate=request.irr_hurdle_rate,
    )
    profile = build_project_risk_profile(
        analysis,
        irr_hurdle_rate=request.irr_hurdle_rate,
        lcoe_benchmark_usd_per_mwh=request.lcoe_benchmark_usd_per_mwh,
    )
    warnings = list(dict.fromkeys((*analysis.warnings, *profile.warnings)))
    return RiskAnalysisResponse(
        scenario_id=analysis.scenario_id,
        sample_count=analysis.sample_count,
        random_seed=analysis.random_seed,
        generation_basis=request.generation_basis,
        metric_summaries=[
            MetricDistributionOutput(**asdict(summary))
            for summary in analysis.metric_summaries
        ],
        probability_npv_positive=analysis.probability_npv_positive,
        probability_irr_above_hurdle=analysis.probability_irr_above_hurdle,
        risk_profile=asdict(profile),
        samples=[
            RiskSampleOutput(
                iteration=sample.iteration,
                sampled_inputs=dict(sample.sampled_inputs),
                npv_usd=sample.npv_usd,
                project_irr=sample.irr,
                lcoe_usd_per_mwh=sample.lcoe_usd_per_mwh,
            )
            for sample in analysis.samples
        ],
        warnings=warnings,
    )


def run_comparison(
    request: ComparisonRequest,
    *,
    provider_overrides: list[Any] | None = None,
) -> ComparisonResponse:
    contexts: list[EvaluationContext] = []
    for index, analysis_request in enumerate(request.analyses):
        provider_override = (
            None
            if provider_overrides is None
            else provider_overrides[index]
        )
        context, _ = _prepare_context(
            analysis_request,
            request.generation_basis,
            provider_override,
        )
        contexts.append(context)
    comparison = compare_projects(
        evaluations=[context.evaluation for context in contexts],
        assessments_by_scenario_id={
            context.project.scenario_id: context.assessment for context in contexts
        },
    )
    contexts_by_scenario_id = {
        context.project.scenario_id: context for context in contexts
    }
    return ComparisonResponse(
        generation_basis=request.generation_basis,
        rows=[
            ComparisonRowOutput(
                scenario_id=row.scenario_id,
                technology=row.technology,
                location_name=(
                    contexts_by_scenario_id[row.scenario_id].project.location.name
                ),
                requested_latitude=(
                    contexts_by_scenario_id[row.scenario_id].resource.location.latitude
                ),
                requested_longitude=(
                    contexts_by_scenario_id[row.scenario_id].resource.location.longitude
                ),
                resolved_latitude=(
                    contexts_by_scenario_id[
                        row.scenario_id
                    ].resource.metadata.resolved_latitude
                ),
                resolved_longitude=(
                    contexts_by_scenario_id[
                        row.scenario_id
                    ].resource.metadata.resolved_longitude
                ),
                resource_source_name=(
                    contexts_by_scenario_id[
                        row.scenario_id
                    ].resource.metadata.source_name
                ),
                resource_dataset_name=(
                    contexts_by_scenario_id[
                        row.scenario_id
                    ].resource.metadata.dataset_name
                ),
                generation_basis=row.generation_basis,
                capacity_mw=row.capacity_mw,
                lifetime_years=row.lifetime_years,
                first_year_generation_mwh=row.first_year_generation_mwh,
                equivalent_capacity_factor=row.equivalent_capacity_factor,
                lifetime_generation_mwh=row.lifetime_generation_mwh,
                initial_capex_usd=row.initial_capex_usd,
                npv_usd=row.npv_usd,
                project_irr=row.irr,
                lcoe_usd_per_mwh=row.lcoe_usd_per_mwh,
                simple_payback_years=row.simple_payback_years,
                discounted_payback_years=row.discounted_payback_years,
                lifetime_revenue_usd=row.lifetime_revenue_usd,
                lifetime_opex_usd=row.lifetime_opex_usd,
                resource_coefficient_of_variation=(
                    row.resource_coefficient_of_variation
                ),
                p90_generation_mwh=row.p90_generation_mwh,
                p50_generation_mwh=row.p50_generation_mwh,
                p10_generation_mwh=row.p10_generation_mwh,
                resource_spread_fraction=row.resource_spread_fraction,
            )
            for row in comparison.rows
        ],
        rankings=[
            RankingOutput(
                metric=ranking.metric.value,
                direction=ranking.direction.value,
                ordered_scenario_ids=list(ranking.ordered_scenario_ids),
                winner_scenario_id=ranking.winner_scenario_id,
            )
            for ranking in comparison.rankings
        ],
        warnings=list(comparison.warnings),
    )
