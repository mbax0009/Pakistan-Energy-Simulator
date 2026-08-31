from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from analysis.comparison import ComparisonMetric, compare_projects
from analysis.evaluators import EvaluationContext, create_parameter_evaluator
from analysis.generation_scenarios import (
    GenerationBasis,
    build_lifetime_generation_scenario,
    build_standard_generation_scenarios,
)
from analysis.joint_uncertainty import (
    JointComparisonMetric,
    JointTechnologyModel,
    compare_joint_technologies,
    run_joint_uncertainty,
)
from analysis.monte_carlo_evaluators import create_monte_carlo_evaluator
from analysis.project_evaluation import (
    evaluate_generation_scenario,
    evaluate_standard_resource_cases,
)
from analysis.risk_analysis import build_project_risk_profile
from analysis.scenario_builders import ScenarioParameter
from analysis.sensitivity import (
    SensitivityMetric,
    find_break_even_parameter,
    run_one_way_sensitivity,
)
from analysis.solar_resource_analysis import (
    AnnualSolarGeneration,
    SolarResourceAssessment,
)
from analysis.two_way_sensitivity import (
    build_competitiveness_map,
    estimate_competitiveness_frontier,
    run_two_way_sensitivity,
)
from analysis.uncertainty import (
    TriangularDistribution,
    UncertainVariable,
    UniformDistribution,
    run_monte_carlo,
)
from analysis.wave_resource_analysis import (
    AnnualWaveGeneration,
    WaveResourceAssessment,
)
from analysis.wind_resource_analysis import (
    AnnualWindGeneration,
    WindResourceAssessment,
)
from core.models import (
    FinancialInputs,
    Location,
    ProjectScenario,
    SolarConfig,
    Technology,
    WaveConfig,
    WindConfig,
)
from core.resources import (
    ResourceMetadata,
    SolarResourcePoint,
    SolarResourceSeries,
    WaveResourcePoint,
    WaveResourceSeries,
    WindResourcePoint,
    WindResourceSeries,
)


LOCATION = Location(
    name="Integration Site",
    latitude=25.025,
    longitude=67.95,
)

METADATA = ResourceMetadata(
    source_name="Integration Test",
    dataset_name="Synthetic annual records",
    retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
)


def _finance(
    *,
    capex_per_kw: float,
    fixed_opex_per_kw_year: float,
) -> FinancialInputs:
    return FinancialInputs(
        capex_per_kw=capex_per_kw,
        fixed_opex_per_kw_year=fixed_opex_per_kw_year,
        variable_opex_per_mwh=2.0,
        electricity_price_per_mwh=110.0,
        discount_rate=0.09,
        electricity_price_growth_rate=0.01,
        opex_growth_rate=0.02,
    )


def _project(technology: Technology) -> ProjectScenario:
    if technology is Technology.SOLAR:
        config = SolarConfig(tilt_deg=25.0, azimuth_deg=180.0)
        finance = _finance(capex_per_kw=700.0, fixed_opex_per_kw_year=18.0)
    elif technology is Technology.WIND:
        config = WindConfig(
            hub_height_m=100.0,
            cut_in_speed_ms=3.0,
            rated_speed_ms=12.0,
            cut_out_speed_ms=25.0,
            turbine_rated_power_mw=5.0,
            availability=0.95,
        )
        finance = _finance(capex_per_kw=1_200.0, fixed_opex_per_kw_year=38.0)
    else:
        config = WaveConfig(
            conversion_efficiency=0.35,
            capture_width_m=25.0,
            device_rated_power_mw=1.0,
            availability=0.90,
        )
        finance = _finance(capex_per_kw=3_500.0, fixed_opex_per_kw_year=95.0)

    return ProjectScenario(
        scenario_id=f"{technology.value.upper()}_INTEGRATION",
        technology=technology,
        location=LOCATION,
        capacity_mw=100.0,
        lifetime_years=8,
        annual_degradation_rate=0.005,
        finance=finance,
        technology_config=config,
    )


def _annual_values(scale: float) -> tuple[float, float, float]:
    return (90_000.0 * scale, 100_000.0 * scale, 110_000.0 * scale)


def _solar_assessment(project: ProjectScenario) -> SolarResourceAssessment:
    values = _annual_values(1.0)
    years = tuple(
        AnnualSolarGeneration(
            year=year,
            generation_mwh=value,
            capacity_factor=value / (100.0 * 8760.0),
            observed_hours=8760.0,
            expected_hours=8760.0,
            completeness_ratio=1.0,
        )
        for year, value in zip((2019, 2020, 2021), values)
    )
    return SolarResourceAssessment(
        scenario_id=project.scenario_id,
        years=years,
        excluded_years=(),
        mean_generation_mwh=100_000.0,
        median_generation_mwh=100_000.0,
        p10_generation_mwh=108_000.0,
        p50_generation_mwh=100_000.0,
        p90_generation_mwh=92_000.0,
        standard_deviation_mwh=10_000.0,
        coefficient_of_variation=0.10,
        minimum_generation_mwh=90_000.0,
        maximum_generation_mwh=110_000.0,
        worst_year=2019,
        best_year=2021,
    )


def _wind_assessment(project: ProjectScenario) -> WindResourceAssessment:
    values = _annual_values(2.6)
    years = tuple(
        AnnualWindGeneration(
            year=year,
            generation_mwh=value,
            capacity_factor=value / (100.0 * 8760.0),
            observed_hours=8760.0,
            expected_hours=8760.0,
            completeness_ratio=1.0,
        )
        for year, value in zip((2019, 2020, 2021), values)
    )
    return WindResourceAssessment(
        scenario_id=project.scenario_id,
        years=years,
        excluded_years=(),
        mean_generation_mwh=260_000.0,
        median_generation_mwh=260_000.0,
        p10_generation_mwh=280_800.0,
        p50_generation_mwh=260_000.0,
        p90_generation_mwh=239_200.0,
        standard_deviation_mwh=26_000.0,
        coefficient_of_variation=0.10,
        minimum_generation_mwh=234_000.0,
        maximum_generation_mwh=286_000.0,
        worst_year=2019,
        best_year=2021,
        mean_capacity_factor=260_000.0 / (100.0 * 8760.0),
    )


def _wave_assessment(project: ProjectScenario) -> WaveResourceAssessment:
    values = _annual_values(1.8)
    years = tuple(
        AnnualWaveGeneration(
            year=year,
            generation_mwh=value,
            capacity_factor=value / (100.0 * 8760.0),
            observed_hours=8760.0,
            expected_hours=8760.0,
            completeness_ratio=1.0,
        )
        for year, value in zip((2019, 2020, 2021), values)
    )
    return WaveResourceAssessment(
        scenario_id=project.scenario_id,
        years=years,
        excluded_years=(),
        mean_generation_mwh=180_000.0,
        median_generation_mwh=180_000.0,
        p10_generation_mwh=194_400.0,
        p50_generation_mwh=180_000.0,
        p90_generation_mwh=165_600.0,
        standard_deviation_mwh=18_000.0,
        coefficient_of_variation=0.10,
        minimum_generation_mwh=162_000.0,
        maximum_generation_mwh=198_000.0,
        worst_year=2019,
        best_year=2021,
        mean_capacity_factor=180_000.0 / (100.0 * 8760.0),
        water_depth_m=100.0,
    )


def _dummy_resource(project: ProjectScenario):
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    if project.technology is Technology.SOLAR:
        return SolarResourceSeries(
            location=LOCATION,
            metadata=METADATA,
            points=tuple(
                SolarResourcePoint(
                    timestamp=start + timedelta(hours=index),
                    ghi_wm2=500.0,
                    poa_irradiance_wm2=550.0,
                )
                for index in range(2)
            ),
        )
    if project.technology is Technology.WIND:
        return WindResourceSeries(
            location=LOCATION,
            metadata=METADATA,
            measurement_height_m=100.0,
            points=tuple(
                WindResourcePoint(
                    timestamp=start + timedelta(hours=index),
                    wind_speed_ms=8.0,
                )
                for index in range(2)
            ),
        )
    return WaveResourceSeries(
        location=LOCATION,
        metadata=METADATA,
        water_depth_m=100.0,
        points=tuple(
            WaveResourcePoint(
                timestamp=start + timedelta(hours=index * 3),
                significant_wave_height_m=2.0,
                energy_period_s=8.0,
                wave_direction_deg=210.0,
            )
            for index in range(2)
        ),
    )


def _context(project: ProjectScenario, assessment) -> EvaluationContext:
    generation = build_lifetime_generation_scenario(
        scenario=project,
        assessment=assessment,
        basis=GenerationBasis.P50,
    )
    evaluation = evaluate_generation_scenario(
        project=project,
        generation_scenario=generation,
    )
    return EvaluationContext(
        project=project,
        resource=_dummy_resource(project),
        assessment=assessment,
        generation_scenario=generation,
        evaluation=evaluation,
        generation_basis=GenerationBasis.P50,
    )


def test_standard_resource_cases_and_comparison_are_connected():
    solar = _project(Technology.SOLAR)
    wind = _project(Technology.WIND)
    wave = _project(Technology.WAVE)
    assessments = (
        _solar_assessment(solar),
        _wind_assessment(wind),
        _wave_assessment(wave),
    )

    for project, assessment in zip((solar, wind, wave), assessments):
        scenarios = build_standard_generation_scenarios(project, assessment)
        assert set(scenarios) == {
            GenerationBasis.P90,
            GenerationBasis.P50,
            GenerationBasis.P10,
        }
        assert (
            scenarios[GenerationBasis.P90].first_year_generation_mwh
            < scenarios[GenerationBasis.P50].first_year_generation_mwh
            < scenarios[GenerationBasis.P10].first_year_generation_mwh
        )

    evaluations = tuple(
        evaluate_standard_resource_cases(project, assessment)[GenerationBasis.P50]
        for project, assessment in zip((solar, wind, wave), assessments)
    )
    comparison = compare_projects(
        evaluations=evaluations,
        assessments_by_scenario_id={
            assessment.scenario_id: assessment for assessment in assessments
        },
    )
    assert len(comparison.rows) == 3
    assert (
        comparison.ranking_for(ComparisonMetric.FIRST_YEAR_GENERATION)
        .winner_scenario_id
        == wind.scenario_id
    )


def test_sensitivity_break_even_and_two_way_competitiveness():
    project = _project(Technology.SOLAR)
    context = _context(project, _solar_assessment(project))

    capex_evaluator = create_parameter_evaluator(
        context=context,
        parameter=ScenarioParameter.CAPEX_PER_KW,
    )
    result = run_one_way_sensitivity(
        parameter_name=ScenarioParameter.CAPEX_PER_KW.value,
        parameter_values=(500.0, 700.0, 900.0),
        evaluator=capex_evaluator,
        metric=SensitivityMetric.LCOE,
    )
    lcoes = tuple(point.metric_value for point in result.points)
    assert all(value is not None for value in lcoes)
    assert lcoes == tuple(sorted(lcoes))

    price_evaluator = create_parameter_evaluator(
        context=context,
        parameter=ScenarioParameter.ELECTRICITY_PRICE_PER_MWH,
    )
    break_even = find_break_even_parameter(
        parameter_name=ScenarioParameter.ELECTRICITY_PRICE_PER_MWH.value,
        evaluator=price_evaluator,
        metric=SensitivityMetric.NPV,
        target_metric_value=0.0,
        lower_bound=0.0,
        upper_bound=1_000.0,
        metric_tolerance=1.0,
    )
    assert break_even.converged
    assert break_even.break_even_parameter_value is not None

    def two_way_evaluator(capex: float, price: float):
        finance = replace(
            project.finance,
            capex_per_kw=capex,
            electricity_price_per_mwh=price,
        )
        return evaluate_generation_scenario(
            project=replace(project, finance=finance),
            generation_scenario=context.generation_scenario,
        )

    surface = run_two_way_sensitivity(
        x_parameter_name="capex_per_kw",
        x_values=(400.0, 700.0, 1_000.0),
        y_parameter_name="electricity_price_per_mwh",
        y_values=(70.0, 110.0),
        evaluator=two_way_evaluator,
        metric=SensitivityMetric.LCOE,
    )
    competitiveness = build_competitiveness_map(
        sensitivity=surface,
        benchmark_value=context.evaluation.lcoe_usd_per_mwh,
    )
    assert len(competitiveness.points) == 6
    assert estimate_competitiveness_frontier(competitiveness)


def test_monte_carlo_risk_and_joint_comparison_are_reproducible():
    solar = _project(Technology.SOLAR)
    wind = _project(Technology.WIND)
    solar_context = _context(solar, _solar_assessment(solar))
    wind_context = _context(wind, _wind_assessment(wind))

    variables = (
        UncertainVariable(
            name=ScenarioParameter.CAPEX_PER_KW.value,
            distribution=TriangularDistribution(550.0, 700.0, 900.0),
            units="USD/kW",
        ),
        UncertainVariable(
            name=ScenarioParameter.ELECTRICITY_PRICE_PER_MWH.value,
            distribution=UniformDistribution(80.0, 140.0),
            units="USD/MWh",
        ),
    )
    evaluator = create_monte_carlo_evaluator(
        solar_context,
        resource_random_seed=99,
    )
    analysis = run_monte_carlo(
        scenario_id=solar.scenario_id,
        variables=variables,
        evaluator=evaluator,
        sample_count=30,
        random_seed=42,
        irr_hurdle_rate=0.10,
    )
    assert analysis.sample_count == 30
    assert 0.0 <= analysis.probability_npv_positive <= 1.0
    profile = build_project_risk_profile(
        analysis,
        lcoe_benchmark_usd_per_mwh=120.0,
    )
    assert profile.sample_count == 30

    shared_price = UncertainVariable(
        name=ScenarioParameter.ELECTRICITY_PRICE_PER_MWH.value,
        distribution=UniformDistribution(80.0, 140.0),
        units="USD/MWh",
    )
    joint = run_joint_uncertainty(
        technologies=(
            JointTechnologyModel(
                name="Solar",
                evaluator=create_monte_carlo_evaluator(
                    solar_context,
                    resource_random_seed=100,
                ),
                specific_variables=(
                    UncertainVariable(
                        name=ScenarioParameter.CAPEX_PER_KW.value,
                        distribution=UniformDistribution(600.0, 800.0),
                    ),
                ),
            ),
            JointTechnologyModel(
                name="Wind",
                evaluator=create_monte_carlo_evaluator(
                    wind_context,
                    resource_random_seed=101,
                ),
                specific_variables=(
                    UncertainVariable(
                        name=ScenarioParameter.CAPEX_PER_KW.value,
                        distribution=UniformDistribution(1_000.0, 1_400.0),
                    ),
                ),
            ),
        ),
        shared_variables=(shared_price,),
        sample_count=20,
        random_seed=7,
    )
    paired = compare_joint_technologies(
        analysis=joint,
        technology_a="Solar",
        technology_b="Wind",
        metric=JointComparisonMetric.NPV,
    )
    assert paired.valid_pair_count == 20
    assert (
        paired.probability_a_better
        + paired.probability_b_better
        + paired.probability_tie
    ) == pytest.approx(1.0)
