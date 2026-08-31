# analysis/comparison.py

from __future__ import annotations

import math

from collections.abc import (
    Mapping,
    Sequence,
)

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from analysis.generation_scenarios import (
    GenerationBasis,
)

from analysis.project_evaluation import (
    ProjectEvaluation,
)

from core.models import (
    Technology,
)


# ============================================================
# RESOURCE-ASSESSMENT INTERFACE
# ============================================================

class ComparableResourceAssessment(Protocol):
    """
    Minimum resource-risk information required
    for cross-technology comparison.

    SolarResourceAssessment,
    WindResourceAssessment,
    and WaveResourceAssessment

    all satisfy this structure.
    """

    scenario_id: str

    p10_generation_mwh: float
    p50_generation_mwh: float
    p90_generation_mwh: float

    coefficient_of_variation: float


# ============================================================
# COMPARISON METRICS
# ============================================================

class ComparisonMetric(str, Enum):
    """
    Metrics available for ranking technologies.
    """

    FIRST_YEAR_GENERATION = (
        "first_year_generation"
    )

    CAPACITY_FACTOR = (
        "capacity_factor"
    )

    LIFETIME_GENERATION = (
        "lifetime_generation"
    )

    NPV = "npv"

    IRR = "irr"

    LCOE = "lcoe"

    SIMPLE_PAYBACK = (
        "simple_payback"
    )

    DISCOUNTED_PAYBACK = (
        "discounted_payback"
    )

    RESOURCE_VARIABILITY = (
        "resource_variability"
    )

    RESOURCE_SPREAD = (
        "resource_spread"
    )


# ============================================================
# RANKING DIRECTION
# ============================================================

class RankingDirection(str, Enum):
    """
    Defines whether a larger or smaller value
    is preferable for one metric.
    """

    HIGHER_IS_BETTER = (
        "higher_is_better"
    )

    LOWER_IS_BETTER = (
        "lower_is_better"
    )


# ============================================================
# ONE COMPARISON ROW
# ============================================================

@dataclass(frozen=True)
class TechnologyComparisonRow:
    """
    Standardized comparison snapshot for one
    technology/project case.

    Example:

        Solar P50
        Wind P50
        Wave P50
    """

    scenario_id: str

    technology: Technology

    generation_basis: GenerationBasis

    capacity_mw: float

    lifetime_years: int

    # --------------------------------------------------------
    # PHYSICAL PERFORMANCE
    # --------------------------------------------------------

    first_year_generation_mwh: float

    equivalent_capacity_factor: float

    lifetime_generation_mwh: float

    # --------------------------------------------------------
    # FINANCIAL PERFORMANCE
    # --------------------------------------------------------

    initial_capex_usd: float

    npv_usd: float

    irr: float | None

    lcoe_usd_per_mwh: float | None

    simple_payback_years: float | None

    discounted_payback_years: float | None

    lifetime_revenue_usd: float

    lifetime_opex_usd: float

    # --------------------------------------------------------
    # RESOURCE RISK
    # --------------------------------------------------------

    resource_coefficient_of_variation: (
        float | None
    ) = None

    p90_generation_mwh: (
        float | None
    ) = None

    p50_generation_mwh: (
        float | None
    ) = None

    p10_generation_mwh: (
        float | None
    ) = None

    resource_spread_fraction: (
        float | None
    ) = None


    def __post_init__(self):

        if not self.scenario_id.strip():
            raise ValueError(
                "Scenario ID cannot be empty."
            )

        if self.capacity_mw <= 0:
            raise ValueError(
                "Project capacity must be positive."
            )

        if self.lifetime_years <= 0:
            raise ValueError(
                "Project lifetime must be positive."
            )

        if self.first_year_generation_mwh < 0:
            raise ValueError(
                "First-year generation cannot "
                "be negative."
            )

        if not (
            0
            <= self.equivalent_capacity_factor
            <= 1
        ):
            raise ValueError(
                "Capacity factor must be "
                "between 0 and 1."
            )

        if self.lifetime_generation_mwh < 0:
            raise ValueError(
                "Lifetime generation cannot "
                "be negative."
            )

        if self.initial_capex_usd < 0:
            raise ValueError(
                "Initial CAPEX cannot be negative."
            )

        if (
            self.lcoe_usd_per_mwh is not None
            and self.lcoe_usd_per_mwh < 0
        ):
            raise ValueError(
                "LCOE cannot be negative."
            )

        if (
            self.resource_coefficient_of_variation
            is not None
            and self.resource_coefficient_of_variation
            < 0
        ):
            raise ValueError(
                "Resource coefficient of variation "
                "cannot be negative."
            )

        if (
            self.resource_spread_fraction
            is not None
            and self.resource_spread_fraction < 0
        ):
            raise ValueError(
                "Resource spread cannot be negative."
            )


# ============================================================
# ONE METRIC RANKING
# ============================================================

@dataclass(frozen=True)
class MetricRanking:
    """
    Ranking of projects under one metric.

    ordered_scenario_ids[0]
        is the strongest result for that metric.
    """

    metric: ComparisonMetric

    direction: RankingDirection

    ordered_scenario_ids: tuple[
        str,
        ...
    ]

    @property
    def winner_scenario_id(
        self,
    ) -> str | None:

        if not self.ordered_scenario_ids:
            return None

        return self.ordered_scenario_ids[0]


# ============================================================
# COMPLETE COMPARISON
# ============================================================

@dataclass(frozen=True)
class ProjectComparison:
    """
    Complete cross-technology comparison.
    """

    rows: tuple[
        TechnologyComparisonRow,
        ...
    ]

    rankings: tuple[
        MetricRanking,
        ...
    ]

    warnings: tuple[str, ...] = ()

    def __post_init__(self):

        if len(self.rows) < 2:

            raise ValueError(
                "At least two project evaluations "
                "are required for comparison."
            )

    @property
    def technologies(
        self,
    ) -> tuple[Technology, ...]:

        return tuple(
            row.technology
            for row in self.rows
        )

    def ranking_for(
        self,
        metric: ComparisonMetric,
    ) -> MetricRanking:
        """
        Retrieve ranking for one comparison metric.
        """

        for ranking in self.rankings:

            if ranking.metric is metric:
                return ranking

        raise KeyError(
            f"No ranking exists for {metric.value}."
        )


# ============================================================
# ASSESSMENT MATCHING
# ============================================================

def _validate_assessment_match(
    evaluation: ProjectEvaluation,
    assessment: ComparableResourceAssessment,
) -> None:
    """
    Ensure the resource-risk assessment belongs
    to the same project.
    """

    if (
        evaluation.scenario_id
        != assessment.scenario_id
    ):

        raise ValueError(
            "Resource assessment scenario ID "
            "does not match project evaluation."
        )


# ============================================================
# RESOURCE SPREAD
# ============================================================

def calculate_resource_spread_fraction(
    p90_generation_mwh: float,
    p50_generation_mwh: float,
    p10_generation_mwh: float,
) -> float | None:
    """
    Calculate relative P10-P90 generation spread.

    Formula:

        spread =
            (P10 - P90)
            -----------
                P50

    A smaller value indicates a tighter annual
    generation distribution.
    """

    values = (
        p90_generation_mwh,
        p50_generation_mwh,
        p10_generation_mwh,
    )

    if not all(
        math.isfinite(value)
        for value in values
    ):
        raise ValueError(
            "P-values must be finite."
        )

    if any(
        value < 0
        for value in values
    ):
        raise ValueError(
            "Generation P-values cannot be negative."
        )

    if p50_generation_mwh <= 0:
        return None

    # Our exceedance convention should satisfy:
    #
    # P90 <= P50 <= P10

    if not (
        p90_generation_mwh
        <= p50_generation_mwh
        <= p10_generation_mwh
    ):

        raise ValueError(
            "Generation values must satisfy "
            "P90 <= P50 <= P10."
        )

    return (
        (
            p10_generation_mwh
            - p90_generation_mwh
        )
        / p50_generation_mwh
    )


# ============================================================
# BUILD ONE COMPARISON ROW
# ============================================================

def build_comparison_row(
    evaluation: ProjectEvaluation,
    assessment: (
        ComparableResourceAssessment | None
    ) = None,
) -> TechnologyComparisonRow:
    """
    Convert one complete project evaluation into
    a standardized comparison row.

    Resource-risk metrics are included when the
    original long-term resource assessment is supplied.
    """

    resource_cv: float | None = None

    p90: float | None = None
    p50: float | None = None
    p10: float | None = None

    spread: float | None = None

    # --------------------------------------------------------
    # Optional resource-risk information
    # --------------------------------------------------------

    if assessment is not None:

        _validate_assessment_match(
            evaluation=evaluation,
            assessment=assessment,
        )

        resource_cv = float(
            assessment
            .coefficient_of_variation
        )

        p90 = float(
            assessment
            .p90_generation_mwh
        )

        p50 = float(
            assessment
            .p50_generation_mwh
        )

        p10 = float(
            assessment
            .p10_generation_mwh
        )

        spread = (
            calculate_resource_spread_fraction(
                p90_generation_mwh=p90,
                p50_generation_mwh=p50,
                p10_generation_mwh=p10,
            )
        )

    # --------------------------------------------------------
    # Build standardized snapshot
    # --------------------------------------------------------

    return TechnologyComparisonRow(

        scenario_id=(
            evaluation.scenario_id
        ),

        technology=(
            evaluation.technology
        ),

        generation_basis=(
            evaluation.generation_basis
        ),

        capacity_mw=(
            evaluation.project.capacity_mw
        ),

        lifetime_years=(
            evaluation.project.lifetime_years
        ),

        first_year_generation_mwh=(
            evaluation
            .first_year_generation_mwh
        ),

        equivalent_capacity_factor=(
            evaluation
            .equivalent_first_year_capacity_factor
        ),

        lifetime_generation_mwh=(
            evaluation
            .lifetime_generation_mwh
        ),

        initial_capex_usd=(
            evaluation.initial_capex_usd
        ),

        npv_usd=(
            evaluation.npv_usd
        ),

        irr=(
            evaluation.irr
        ),

        lcoe_usd_per_mwh=(
            evaluation
            .lcoe_usd_per_mwh
        ),

        simple_payback_years=(
            evaluation
            .simple_payback_years
        ),

        discounted_payback_years=(
            evaluation
            .discounted_payback_years
        ),

        lifetime_revenue_usd=(
            evaluation
            .lifetime_revenue_usd
        ),

        lifetime_opex_usd=(
            evaluation
            .lifetime_opex_usd
        ),

        resource_coefficient_of_variation=(
            resource_cv
        ),

        p90_generation_mwh=(
            p90
        ),

        p50_generation_mwh=(
            p50
        ),

        p10_generation_mwh=(
            p10
        ),

        resource_spread_fraction=(
            spread
        ),
    )


# ============================================================
# RANKABLE VALUE
# ============================================================

def _metric_value(
    row: TechnologyComparisonRow,
    metric: ComparisonMetric,
) -> float | None:
    """
    Extract one numeric comparison metric.
    """

    if (
        metric
        is ComparisonMetric.FIRST_YEAR_GENERATION
    ):

        return (
            row.first_year_generation_mwh
        )

    if (
        metric
        is ComparisonMetric.CAPACITY_FACTOR
    ):

        return (
            row.equivalent_capacity_factor
        )

    if (
        metric
        is ComparisonMetric.LIFETIME_GENERATION
    ):

        return (
            row.lifetime_generation_mwh
        )

    if metric is ComparisonMetric.NPV:

        return row.npv_usd

    if metric is ComparisonMetric.IRR:

        return row.irr

    if metric is ComparisonMetric.LCOE:

        return row.lcoe_usd_per_mwh

    if (
        metric
        is ComparisonMetric.SIMPLE_PAYBACK
    ):

        return (
            row.simple_payback_years
        )

    if (
        metric
        is ComparisonMetric.DISCOUNTED_PAYBACK
    ):

        return (
            row.discounted_payback_years
        )

    if (
        metric
        is ComparisonMetric.RESOURCE_VARIABILITY
    ):

        return (
            row
            .resource_coefficient_of_variation
        )

    if (
        metric
        is ComparisonMetric.RESOURCE_SPREAD
    ):

        return (
            row.resource_spread_fraction
        )

    raise ValueError(
        f"Unsupported comparison metric: {metric}"
    )


# ============================================================
# RANKING DIRECTION
# ============================================================

def _ranking_direction(
    metric: ComparisonMetric,
) -> RankingDirection:
    """
    Define what 'better' means for each metric.
    """

    higher_is_better = {
        ComparisonMetric.FIRST_YEAR_GENERATION,
        ComparisonMetric.CAPACITY_FACTOR,
        ComparisonMetric.LIFETIME_GENERATION,
        ComparisonMetric.NPV,
        ComparisonMetric.IRR,
    }

    lower_is_better = {
        ComparisonMetric.LCOE,
        ComparisonMetric.SIMPLE_PAYBACK,
        ComparisonMetric.DISCOUNTED_PAYBACK,
        ComparisonMetric.RESOURCE_VARIABILITY,
        ComparisonMetric.RESOURCE_SPREAD,
    }

    if metric in higher_is_better:

        return (
            RankingDirection.HIGHER_IS_BETTER
        )

    if metric in lower_is_better:

        return (
            RankingDirection.LOWER_IS_BETTER
        )

    raise ValueError(
        f"No ranking direction defined "
        f"for {metric.value}."
    )


# ============================================================
# RANK PROJECTS
# ============================================================

def rank_projects(
    rows: Sequence[
        TechnologyComparisonRow
    ],
    metric: ComparisonMetric,
) -> MetricRanking:
    """
    Rank projects according to one metric.

    Missing metrics such as undefined IRR or
    no payback are placed after valid results.
    """

    direction = (
        _ranking_direction(
            metric
        )
    )

    valid_rows = []

    missing_rows = []

    for row in rows:

        value = _metric_value(
            row,
            metric,
        )

        if (
            value is None
            or not math.isfinite(value)
        ):

            missing_rows.append(
                row
            )

        else:

            valid_rows.append(
                row
            )

    reverse = (
        direction
        is RankingDirection.HIGHER_IS_BETTER
    )

    valid_rows.sort(
        key=lambda row: (
            _metric_value(
                row,
                metric,
            )
        ),
        reverse=reverse,
    )

    # Missing/undefined results always come last.
    ordered_rows = (
        valid_rows
        + missing_rows
    )

    return MetricRanking(

        metric=metric,

        direction=direction,

        ordered_scenario_ids=tuple(
            row.scenario_id
            for row in ordered_rows
        ),
    )


# ============================================================
# LIKE-FOR-LIKE VALIDATION
# ============================================================

def _all_numeric_values_close(
    values: Sequence[float],
    tolerance: float = 1e-12,
) -> bool:
    """
    Test whether a collection of numerical assumptions
    is effectively identical.
    """

    if len(values) < 2:
        return True

    first = values[0]

    return all(
        math.isclose(
            value,
            first,
            rel_tol=tolerance,
            abs_tol=tolerance,
        )
        for value in values[1:]
    )


def _build_comparison_warnings(
    evaluations: Sequence[
        ProjectEvaluation
    ],
) -> tuple[str, ...]:
    """
    Detect important differences that may make
    interpretation less like-for-like.
    """

    warnings: list[str] = []

    # --------------------------------------------------------
    # Installed capacity
    # --------------------------------------------------------

    capacities = [
        evaluation.project.capacity_mw
        for evaluation in evaluations
    ]

    if not _all_numeric_values_close(
        capacities
    ):

        warnings.append(
            "Projects have different installed "
            "capacities. Total generation and NPV "
            "should not be interpreted as purely "
            "technology-driven differences."
        )

    # --------------------------------------------------------
    # Project lifetime
    # --------------------------------------------------------

    lifetimes = {
        evaluation.project.lifetime_years
        for evaluation in evaluations
    }

    if len(lifetimes) > 1:

        warnings.append(
            "Projects use different operating "
            "lifetimes. Lifetime generation, NPV "
            "and LCOE are therefore not based on "
            "identical time horizons."
        )

    # --------------------------------------------------------
    # Discount rate
    # --------------------------------------------------------

    discount_rates = [
        evaluation
        .project
        .finance
        .discount_rate

        for evaluation
        in evaluations
    ]

    if not _all_numeric_values_close(
        discount_rates
    ):

        warnings.append(
            "Projects use different discount rates. "
            "NPV and LCOE comparisons are not "
            "strictly like-for-like."
        )

    # --------------------------------------------------------
    # Electricity price
    # --------------------------------------------------------

    electricity_prices = [
        evaluation
        .project
        .finance
        .electricity_price_per_mwh

        for evaluation
        in evaluations
    ]

    if not _all_numeric_values_close(
        electricity_prices
    ):

        warnings.append(
            "Projects use different electricity "
            "prices. NPV and IRR differences therefore "
            "include commercial assumptions as well "
            "as technology performance."
        )

    # --------------------------------------------------------
    # Electricity price growth
    # --------------------------------------------------------

    price_growth_rates = [
        evaluation
        .project
        .finance
        .electricity_price_growth_rate

        for evaluation
        in evaluations
    ]

    if not _all_numeric_values_close(
        price_growth_rates
    ):

        warnings.append(
            "Projects use different electricity-price "
            "growth assumptions."
        )

    return tuple(
        warnings
    )


# ============================================================
# COMPLETE CROSS-TECHNOLOGY COMPARISON
# ============================================================

def compare_projects(
    evaluations: Sequence[
        ProjectEvaluation
    ],
    assessments_by_scenario_id: (
        Mapping[
            str,
            ComparableResourceAssessment,
        ]
        | None
    ) = None,
    require_same_generation_basis: bool = True,
) -> ProjectComparison:
    """
    Compare two or more evaluated renewable-energy projects.

    Typical use:

        Solar P50
        Wind P50
        Wave P50

    The function does not create a universal weighted score.

    Instead it ranks the projects independently on
    physically and financially meaningful metrics.
    """

    evaluations = tuple(
        evaluations
    )

    if len(evaluations) < 2:

        raise ValueError(
            "At least two project evaluations "
            "are required."
        )

    # --------------------------------------------------------
    # Unique scenario IDs
    # --------------------------------------------------------

    scenario_ids = tuple(
        evaluation.scenario_id
        for evaluation in evaluations
    )

    if (
        len(set(scenario_ids))
        != len(scenario_ids)
    ):

        raise ValueError(
            "Each compared project must have "
            "a unique scenario ID."
        )

    # --------------------------------------------------------
    # Compare equivalent resource-risk cases
    # --------------------------------------------------------

    bases = {
        evaluation.generation_basis
        for evaluation in evaluations
    }

    if (
        require_same_generation_basis
        and len(bases) > 1
    ):

        raise ValueError(
            "Compared projects must use the same "
            "generation basis, for example all P50 "
            "or all P90."
        )

    # --------------------------------------------------------
    # Historical-year comparison requires same year
    # --------------------------------------------------------

    if (
        len(bases) == 1
        and GenerationBasis.HISTORICAL_YEAR
        in bases
    ):

        source_years = {
            evaluation.source_year
            for evaluation in evaluations
        }

        if len(source_years) > 1:

            raise ValueError(
                "Historical-year comparison requires "
                "the same source year for every "
                "technology."
            )

    # --------------------------------------------------------
    # Construct comparison rows
    # --------------------------------------------------------

    rows: list[
        TechnologyComparisonRow
    ] = []

    for evaluation in evaluations:

        assessment = None

        if assessments_by_scenario_id is not None:

            assessment = (
                assessments_by_scenario_id.get(
                    evaluation.scenario_id
                )
            )

        rows.append(
            build_comparison_row(
                evaluation=evaluation,
                assessment=assessment,
            )
        )

    # --------------------------------------------------------
    # Rank metrics
    # --------------------------------------------------------

    metrics = (
        ComparisonMetric.FIRST_YEAR_GENERATION,
        ComparisonMetric.CAPACITY_FACTOR,
        ComparisonMetric.LIFETIME_GENERATION,
        ComparisonMetric.NPV,
        ComparisonMetric.IRR,
        ComparisonMetric.LCOE,
        ComparisonMetric.SIMPLE_PAYBACK,
        ComparisonMetric.DISCOUNTED_PAYBACK,
    )

    # Resource-risk metrics only make sense if
    # every row has the required assessment information.

    all_have_resource_cv = all(
        row.resource_coefficient_of_variation
        is not None
        for row in rows
    )

    all_have_resource_spread = all(
        row.resource_spread_fraction
        is not None
        for row in rows
    )

    metric_list = list(
        metrics
    )

    if all_have_resource_cv:

        metric_list.append(
            ComparisonMetric.RESOURCE_VARIABILITY
        )

    if all_have_resource_spread:

        metric_list.append(
            ComparisonMetric.RESOURCE_SPREAD
        )

    rankings = tuple(

        rank_projects(
            rows=rows,
            metric=metric,
        )

        for metric
        in metric_list
    )

    # --------------------------------------------------------
    # Fair-comparison warnings
    # --------------------------------------------------------

    warnings = list(
        _build_comparison_warnings(
            evaluations
        )
    )

    if len(bases) > 1:

        warnings.append(
            "Generation-risk bases differ across "
            "projects. Interpret the comparison "
            "with caution."
        )

    if assessments_by_scenario_id is None:

        warnings.append(
            "Resource assessments were not supplied, "
            "so resource variability and P10-P90 "
            "spread are not included."
        )

    # --------------------------------------------------------
    # Final comparison object
    # --------------------------------------------------------

    return ProjectComparison(

        rows=tuple(
            rows
        ),

        rankings=rankings,

        warnings=tuple(
            warnings
        ),
    )