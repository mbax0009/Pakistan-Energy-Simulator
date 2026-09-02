from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from analysis.generation_scenarios import GenerationBasis
from analysis.joint_uncertainty import JointComparisonMetric
from analysis.monte_carlo_evaluators import ResourceResamplingMode
from analysis.scenario_builders import ScenarioParameter
from analysis.sensitivity import SensitivityMetric
from core.models import Technology


class ResourceProvider(str, Enum):
    AUTO = "auto"
    OPEN_METEO = "open_meteo"
    COPERNICUS = "copernicus"


class LocationInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class FinancialInput(BaseModel):
    capex_per_kw: float = Field(gt=0)
    fixed_opex_per_kw_year: float = Field(ge=0)
    variable_opex_per_mwh: float = Field(default=0, ge=0)
    electricity_price_per_mwh: float = Field(gt=0)
    discount_rate: float = Field(ge=0, lt=1)
    electricity_price_growth_rate: float = Field(default=0, gt=-1)
    opex_growth_rate: float = Field(default=0, gt=-1)


class SolarConfigInput(BaseModel):
    tilt_deg: float = Field(default=25, ge=0, le=90)
    azimuth_deg: float = Field(default=180, ge=0, lt=360)
    system_losses: float = Field(default=0.141, ge=0, lt=1)
    reference_irradiance_wm2: float = Field(default=1000, gt=0)
    reference_cell_temperature_c: float = 25
    temperature_coefficient_per_c: float = Field(default=-0.004, lt=0)


class WindConfigInput(BaseModel):
    hub_height_m: float = Field(default=100, gt=0)
    cut_in_speed_ms: float = Field(default=3, ge=0)
    rated_speed_ms: float = Field(default=9.8127, gt=0)
    cut_out_speed_ms: float = Field(default=25.01, gt=0)
    turbine_rated_power_mw: float = Field(default=3.37, gt=0)
    availability: float = Field(default=0.95, gt=0, le=1)
    wind_shear_exponent: float = Field(default=1 / 7, ge=0)
    reference_air_density_kg_m3: float = Field(default=1.225, gt=0)
    power_curve_id: Literal["iea_reference_3_4mw_130"] | None = (
        "iea_reference_3_4mw_130"
    )

    @model_validator(mode="after")
    def validate_speed_order(self):
        if not self.cut_in_speed_ms < self.rated_speed_ms < self.cut_out_speed_ms:
            raise ValueError("Wind speeds must satisfy cut-in < rated < cut-out.")
        return self


class WaveConfigInput(BaseModel):
    conversion_efficiency: float = Field(default=0.30, gt=0, le=1)
    capture_width_m: float = Field(default=20, gt=0)
    device_rated_power_mw: float = Field(default=1, gt=0)
    availability: float = Field(default=0.90, gt=0, le=1)


class ResourceInput(BaseModel):
    start_date: date
    end_date: date
    provider: ResourceProvider = ResourceProvider.AUTO
    minimum_year_completeness: float = Field(default=0.99, gt=0, le=1)

    @model_validator(mode="after")
    def validate_date_order(self):
        if self.start_date > self.end_date:
            raise ValueError("start_date cannot be after end_date.")
        return self


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=False)

    scenario_id: str = Field(min_length=1, max_length=120)
    technology: Technology
    location: LocationInput
    capacity_mw: float = Field(gt=0)
    lifetime_years: int = Field(gt=0, le=100)
    annual_degradation_rate: float = Field(default=0, ge=0, lt=1)
    financial: FinancialInput
    resource: ResourceInput
    solar: SolarConfigInput | None = None
    wind: WindConfigInput | None = None
    wave: WaveConfigInput | None = None

    @model_validator(mode="after")
    def validate_matching_technology_config(self):
        selected = {
            Technology.SOLAR: self.solar,
            Technology.WIND: self.wind,
            Technology.WAVE: self.wave,
        }
        if selected[self.technology] is None:
            raise ValueError(f"{self.technology.value} configuration is required.")
        return self


class ResourceSummary(BaseModel):
    source_name: str
    dataset_name: str
    source_reference: str | None
    requested_latitude: float
    requested_longitude: float
    resolved_latitude: float | None
    resolved_longitude: float | None
    start_time: datetime
    end_time: datetime
    sample_count: int
    time_step_hours: float
    water_depth_m: float | None = None


class AnnualGenerationSummary(BaseModel):
    year: int
    generation_mwh: float
    capacity_factor: float
    completeness_ratio: float


class GenerationStatistics(BaseModel):
    p90_mwh: float
    p50_mwh: float
    p10_mwh: float
    mean_mwh: float
    median_mwh: float
    coefficient_of_variation: float
    minimum_mwh: float
    maximum_mwh: float
    worst_year: int
    best_year: int
    accepted_years: list[int]
    excluded_years: list[int]


class EvaluationSummary(BaseModel):
    generation_basis: str
    first_year_generation_mwh: float
    final_year_generation_mwh: float
    lifetime_generation_mwh: float
    equivalent_first_year_capacity_factor: float
    initial_capex_usd: float
    npv_usd: float
    project_irr: float | None
    lcoe_usd_per_mwh: float | None
    simple_payback_years: float | None
    discounted_payback_years: float | None
    lifetime_revenue_usd: float
    lifetime_opex_usd: float
    additional_capex_usd: float


class ReproducibilitySummary(BaseModel):
    software_version: str
    methodology_version: str
    generated_at: datetime
    random_seed: int | None = None


class AnalysisResponse(BaseModel):
    scenario_id: str
    technology: Technology
    resource: ResourceSummary
    annual_generation: list[AnnualGenerationSummary]
    generation_statistics: GenerationStatistics
    evaluations: dict[str, EvaluationSummary]
    warnings: list[str]
    assumptions: dict
    reproducibility: ReproducibilitySummary


class HealthResponse(BaseModel):
    status: str
    software_version: str
    methodology_version: str


class CostBenchmarkOutput(BaseModel):
    technology: Technology
    capex_per_kw: float | None
    unit: str | None
    basis_year: int | None
    source_name: str | None
    source_url: str | None
    evidence_level: str
    note: str


class FxRateOutput(BaseModel):
    base_currency: str
    quote_currency: str
    rate: float
    as_of: datetime
    source_name: str
    source_url: str
    official_reference_url: str
    is_live: bool
    is_stale: bool
    warning: str


class MarketContextResponse(BaseModel):
    generated_at: datetime
    default_currency: str
    resource_period: str
    cost_basis_label: str
    cost_benchmarks: list[CostBenchmarkOutput]
    fx: FxRateOutput
    electricity_price_policy: str


class CacheClearResponse(BaseModel):
    deleted_entries: int
    namespace: str | None


class SensitivityPointOutput(BaseModel):
    parameter_value: float
    metric_value: float | None


class OneWaySensitivityRequest(BaseModel):
    analysis: AnalysisRequest
    parameter: ScenarioParameter
    metric: SensitivityMetric
    values: list[float] = Field(min_length=2, max_length=101)
    generation_basis: GenerationBasis = GenerationBasis.P50


class OneWaySensitivityResponse(BaseModel):
    parameter: ScenarioParameter
    metric: SensitivityMetric
    generation_basis: GenerationBasis
    points: list[SensitivityPointOutput]
    baseline_parameter_value: float | None
    baseline_metric_value: float | None
    warnings: list[str]


class BreakEvenRequest(BaseModel):
    analysis: AnalysisRequest
    parameter: ScenarioParameter
    metric: SensitivityMetric
    target_metric_value: float
    lower_bound: float
    upper_bound: float
    generation_basis: GenerationBasis = GenerationBasis.P50

    @model_validator(mode="after")
    def validate_bounds(self):
        if self.lower_bound >= self.upper_bound:
            raise ValueError("lower_bound must be less than upper_bound.")
        return self


class BreakEvenResponse(BaseModel):
    parameter: ScenarioParameter
    metric: SensitivityMetric
    target_metric_value: float
    break_even_parameter_value: float | None
    achieved_metric_value: float | None
    converged: bool
    iterations: int
    lower_bound: float
    upper_bound: float
    warning: str | None


class TwoWaySensitivityRequest(BaseModel):
    analysis: AnalysisRequest
    x_parameter: ScenarioParameter
    x_values: list[float] = Field(min_length=2, max_length=51)
    y_parameter: ScenarioParameter
    y_values: list[float] = Field(min_length=2, max_length=51)
    metric: SensitivityMetric
    generation_basis: GenerationBasis = GenerationBasis.P50
    benchmark_value: float | None = None

    @model_validator(mode="after")
    def validate_distinct_parameters(self):
        if self.x_parameter is self.y_parameter:
            raise ValueError("x_parameter and y_parameter must differ.")
        if len(self.x_values) * len(self.y_values) > 1000:
            raise ValueError("Two-way sensitivity is limited to 1,000 grid cells.")
        return self


class TwoWaySensitivityPointOutput(BaseModel):
    x_value: float
    y_value: float
    metric_value: float | None
    is_competitive: bool | None = None


class TwoWaySensitivityResponse(BaseModel):
    x_parameter: ScenarioParameter
    x_values: list[float]
    y_parameter: ScenarioParameter
    y_values: list[float]
    metric: SensitivityMetric
    generation_basis: GenerationBasis
    benchmark_value: float | None
    lower_is_better: bool | None
    points: list[TwoWaySensitivityPointOutput]
    frontier: list[tuple[float, float]]
    warnings: list[str]


class DistributionKind(str, Enum):
    UNIFORM = "uniform"
    TRIANGULAR = "triangular"
    TRUNCATED_NORMAL = "truncated_normal"
    EMPIRICAL = "empirical"


class UncertainVariableInput(BaseModel):
    name: ScenarioParameter
    distribution: DistributionKind
    units: str | None = None
    minimum_value: float | None = None
    maximum_value: float | None = None
    mode_value: float | None = None
    mean: float | None = None
    standard_deviation: float | None = None
    values: list[float] | None = None

    @model_validator(mode="after")
    def validate_distribution_parameters(self):
        if self.distribution is DistributionKind.UNIFORM:
            if self.minimum_value is None or self.maximum_value is None:
                raise ValueError("Uniform distribution requires minimum and maximum.")
        elif self.distribution is DistributionKind.TRIANGULAR:
            if any(
                value is None
                for value in (self.minimum_value, self.mode_value, self.maximum_value)
            ):
                raise ValueError("Triangular distribution requires minimum, mode, and maximum.")
        elif self.distribution is DistributionKind.TRUNCATED_NORMAL:
            if self.mean is None or self.standard_deviation is None:
                raise ValueError("Truncated normal requires mean and standard deviation.")
        elif not self.values:
            raise ValueError("Empirical distribution requires values.")
        return self


class RiskAnalysisRequest(BaseModel):
    analysis: AnalysisRequest
    variables: list[UncertainVariableInput] = Field(min_length=1, max_length=12)
    generation_basis: GenerationBasis = GenerationBasis.P50
    sample_count: int = Field(default=1000, ge=1, le=20_000)
    random_seed: int | None = 42
    resource_resampling_mode: ResourceResamplingMode = (
        ResourceResamplingMode.ANNUAL_EMPIRICAL
    )
    irr_hurdle_rate: float | None = Field(default=None, gt=-1)
    lcoe_benchmark_usd_per_mwh: float | None = Field(default=None, gt=0)


class MetricDistributionOutput(BaseModel):
    metric: SensitivityMetric
    valid_count: int
    undefined_count: int
    mean: float | None
    median: float | None
    standard_deviation: float | None
    percentile_05: float | None
    percentile_10: float | None
    percentile_50: float | None
    percentile_90: float | None
    percentile_95: float | None
    minimum: float | None
    maximum: float | None


class RiskSampleOutput(BaseModel):
    iteration: int
    sampled_inputs: dict[str, float]
    npv_usd: float
    project_irr: float | None
    lcoe_usd_per_mwh: float | None


class RiskAnalysisResponse(BaseModel):
    scenario_id: str
    sample_count: int
    random_seed: int | None
    generation_basis: GenerationBasis
    metric_summaries: list[MetricDistributionOutput]
    probability_npv_positive: float
    probability_irr_above_hurdle: float | None
    risk_profile: dict
    samples: list[RiskSampleOutput]
    warnings: list[str]


class JointTechnologyRiskInput(BaseModel):
    analysis: AnalysisRequest
    variables: list[UncertainVariableInput] = Field(default_factory=list, max_length=12)


class JointUncertaintyRequest(BaseModel):
    technologies: list[JointTechnologyRiskInput] = Field(min_length=3, max_length=3)
    shared_variables: list[UncertainVariableInput] = Field(min_length=1, max_length=8)
    metrics: list[JointComparisonMetric] = Field(
        default_factory=lambda: [JointComparisonMetric.NPV, JointComparisonMetric.LCOE],
        min_length=1,
        max_length=6,
    )
    generation_basis: GenerationBasis = GenerationBasis.P50
    sample_count: int = Field(default=1000, ge=1, le=20_000)
    random_seed: int | None = 42
    resource_resampling_mode: ResourceResamplingMode = (
        ResourceResamplingMode.ANNUAL_EMPIRICAL
    )

    @model_validator(mode="after")
    def validate_joint_design(self):
        analyses = [item.analysis for item in self.technologies]
        technologies = [analysis.technology for analysis in analyses]
        required = {Technology.SOLAR, Technology.WIND, Technology.WAVE}
        if set(technologies) != required:
            raise ValueError(
                "Joint uncertainty requires exactly one Solar, one Wind, and one Wave model."
            )
        scenario_ids = [analysis.scenario_id for analysis in analyses]
        if len(set(scenario_ids)) != len(scenario_ids):
            raise ValueError("Joint uncertainty scenario IDs must be unique.")
        shared_names = [variable.name for variable in self.shared_variables]
        if len(set(shared_names)) != len(shared_names):
            raise ValueError("Shared uncertain-variable names must be unique.")
        shared_name_set = set(shared_names)
        for item in self.technologies:
            specific_names = [variable.name for variable in item.variables]
            if len(set(specific_names)) != len(specific_names):
                raise ValueError(
                    f"{item.analysis.technology.value} specific-variable names must be unique."
                )
            overlap = shared_name_set & set(specific_names)
            if overlap:
                raise ValueError(
                    "Shared and technology-specific variables cannot overlap: "
                    + ", ".join(sorted(variable.value for variable in overlap))
                )
        if len(set(self.metrics)) != len(self.metrics):
            raise ValueError("Joint comparison metrics must be unique.")
        return self


class JointTechnologySampleOutput(BaseModel):
    scenario_id: str
    technology: Technology
    sampled_specific_inputs: dict[str, float]
    npv_usd: float
    project_irr: float | None
    lcoe_usd_per_mwh: float | None
    first_year_generation_mwh: float
    lifetime_generation_mwh: float
    capacity_factor: float


class JointIterationOutput(BaseModel):
    iteration: int
    sampled_shared_inputs: dict[str, float]
    technology_results: list[JointTechnologySampleOutput]


class PairedTechnologyComparisonOutput(BaseModel):
    technology_a: Technology
    technology_b: Technology
    metric: JointComparisonMetric
    valid_pair_count: int
    probability_a_better: float
    probability_b_better: float
    probability_tie: float
    mean_difference_a_minus_b: float
    median_difference_a_minus_b: float


class JointUncertaintyResponse(BaseModel):
    sample_count: int
    random_seed: int | None
    generation_basis: GenerationBasis
    technologies: list[Technology]
    comparisons: list[PairedTechnologyComparisonOutput]
    iterations: list[JointIterationOutput]
    warnings: list[str]


class ComparisonRequest(BaseModel):
    analyses: list[AnalysisRequest] = Field(min_length=2, max_length=3)
    generation_basis: GenerationBasis = GenerationBasis.P50

    @model_validator(mode="after")
    def validate_unique_scenario_ids(self):
        scenario_ids = [analysis.scenario_id for analysis in self.analyses]
        if len(set(scenario_ids)) != len(scenario_ids):
            raise ValueError("Comparison scenario IDs must be unique.")
        return self


class ComparisonRowOutput(BaseModel):
    scenario_id: str
    technology: Technology
    location_name: str
    requested_latitude: float
    requested_longitude: float
    resolved_latitude: float | None
    resolved_longitude: float | None
    resource_source_name: str
    resource_dataset_name: str
    generation_basis: GenerationBasis
    capacity_mw: float
    lifetime_years: int
    first_year_generation_mwh: float
    equivalent_capacity_factor: float
    lifetime_generation_mwh: float
    initial_capex_usd: float
    npv_usd: float
    project_irr: float | None
    lcoe_usd_per_mwh: float | None
    simple_payback_years: float | None
    discounted_payback_years: float | None
    lifetime_revenue_usd: float
    lifetime_opex_usd: float
    resource_coefficient_of_variation: float | None
    p90_generation_mwh: float | None
    p50_generation_mwh: float | None
    p10_generation_mwh: float | None
    resource_spread_fraction: float | None


class RankingOutput(BaseModel):
    metric: str
    direction: str
    ordered_scenario_ids: list[str]
    winner_scenario_id: str | None


class ComparisonResponse(BaseModel):
    generation_basis: GenerationBasis
    rows: list[ComparisonRowOutput]
    rankings: list[RankingOutput]
    warnings: list[str]
