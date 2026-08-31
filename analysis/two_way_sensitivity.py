# analysis/two_way_sensitivity.py

from __future__ import annotations

import math

from collections.abc import (
    Callable,
    Sequence,
)

from dataclasses import dataclass

from analysis.project_evaluation import (
    ProjectEvaluation,
)

from analysis.sensitivity import (
    SensitivityMetric,
    get_evaluation_metric,
)


# ============================================================
# ONE POINT IN A TWO-DIMENSIONAL PARAMETER SPACE
# ============================================================

@dataclass(frozen=True)
class TwoWaySensitivityPoint:
    """
    Result for one combination of two parameter values.

    Example:

        CAPEX = 2500 USD/kW
        efficiency = 0.50

        LCOE = 92 USD/MWh
    """

    x_parameter_name: str
    x_parameter_value: float

    y_parameter_name: str
    y_parameter_value: float

    metric: SensitivityMetric

    metric_value: float | None

    scenario_id: str

    def __post_init__(self):

        if not self.x_parameter_name.strip():
            raise ValueError(
                "X parameter name cannot be empty."
            )

        if not self.y_parameter_name.strip():
            raise ValueError(
                "Y parameter name cannot be empty."
            )

        if not math.isfinite(
            self.x_parameter_value
        ):
            raise ValueError(
                "X parameter value must be finite."
            )

        if not math.isfinite(
            self.y_parameter_value
        ):
            raise ValueError(
                "Y parameter value must be finite."
            )

        if (
            self.metric_value is not None
            and not math.isfinite(
                self.metric_value
            )
        ):
            raise ValueError(
                "Metric value must be finite "
                "when defined."
            )

        if not self.scenario_id.strip():
            raise ValueError(
                "Scenario ID cannot be empty."
            )


# ============================================================
# COMPLETE TWO-WAY SENSITIVITY RESULT
# ============================================================

@dataclass(frozen=True)
class TwoWaySensitivityResult:
    """
    Complete rectangular sensitivity grid.

    points contains every evaluated combination:

        x1,y1
        x1,y2
        ...
        xn,ym
    """

    x_parameter_name: str
    x_values: tuple[float, ...]

    y_parameter_name: str
    y_values: tuple[float, ...]

    metric: SensitivityMetric

    points: tuple[
        TwoWaySensitivityPoint,
        ...
    ]

    warnings: tuple[str, ...] = ()

    def __post_init__(self):

        if not self.x_parameter_name.strip():
            raise ValueError(
                "X parameter name cannot be empty."
            )

        if not self.y_parameter_name.strip():
            raise ValueError(
                "Y parameter name cannot be empty."
            )

        if not self.x_values:
            raise ValueError(
                "X values cannot be empty."
            )

        if not self.y_values:
            raise ValueError(
                "Y values cannot be empty."
            )

        expected_points = (
            len(self.x_values)
            * len(self.y_values)
        )

        if len(self.points) != expected_points:
            raise ValueError(
                "Number of two-way sensitivity points "
                "does not match the rectangular grid."
            )

    @property
    def valid_points(
        self,
    ) -> tuple[
        TwoWaySensitivityPoint,
        ...
    ]:
        """
        Return only points where the selected
        metric could be calculated.
        """

        return tuple(
            point
            for point in self.points
            if point.metric_value is not None
        )


# ============================================================
# COMPETITIVENESS POINT
# ============================================================

@dataclass(frozen=True)
class CompetitivenessPoint:
    """
    Classification of one two-way sensitivity point
    relative to a benchmark.

    Example:

        wave LCOE <= solar LCOE

    means wave is competitive at this point.
    """

    x_parameter_value: float

    y_parameter_value: float

    metric_value: float | None

    benchmark_value: float

    is_competitive: bool | None


# ============================================================
# COMPETITIVENESS MAP
# ============================================================

@dataclass(frozen=True)
class CompetitivenessMap:
    """
    Classifies every sensitivity point against
    a benchmark technology or threshold.
    """

    x_parameter_name: str
    y_parameter_name: str

    metric: SensitivityMetric

    benchmark_value: float

    lower_is_better: bool

    points: tuple[
        CompetitivenessPoint,
        ...
    ]

    @property
    def competitive_points(
        self,
    ) -> tuple[
        CompetitivenessPoint,
        ...
    ]:
        """
        Return points where the candidate technology
        meets or beats the benchmark.
        """

        return tuple(
            point
            for point in self.points
            if point.is_competitive is True
        )


# ============================================================
# VALIDATE PARAMETER VALUES
# ============================================================

def _validate_values(
    values: Sequence[float],
    name: str,
) -> tuple[float, ...]:
    """
    Validate one parameter axis.
    """

    if not values:

        raise ValueError(
            f"{name} values cannot be empty."
        )

    validated: list[float] = []

    for value in values:

        value = float(
            value
        )

        if not math.isfinite(
            value
        ):

            raise ValueError(
                f"{name} values must be finite."
            )

        validated.append(
            value
        )

    return tuple(
        validated
    )


# ============================================================
# RUN TWO-WAY SENSITIVITY
# ============================================================

def run_two_way_sensitivity(
    x_parameter_name: str,
    x_values: Sequence[float],

    y_parameter_name: str,
    y_values: Sequence[float],

    evaluator: Callable[
        [float, float],
        ProjectEvaluation,
    ],

    metric: SensitivityMetric,
) -> TwoWaySensitivityResult:
    """
    Evaluate one project over a rectangular grid
    of two parameter values.

    evaluator(x, y) must return a complete
    ProjectEvaluation.

    Example:

        evaluator(
            capex_per_kw,
            conversion_efficiency,
        )
    """

    if not x_parameter_name.strip():
        raise ValueError(
            "X parameter name cannot be empty."
        )

    if not y_parameter_name.strip():
        raise ValueError(
            "Y parameter name cannot be empty."
        )

    validated_x = (
        _validate_values(
            values=x_values,
            name="X parameter",
        )
    )

    validated_y = (
        _validate_values(
            values=y_values,
            name="Y parameter",
        )
    )

    points: list[
        TwoWaySensitivityPoint
    ] = []

    undefined_count = 0

    # --------------------------------------------------------
    # Evaluate all combinations
    # --------------------------------------------------------

    for x_value in validated_x:

        for y_value in validated_y:

            evaluation = evaluator(
                x_value,
                y_value,
            )

            metric_value = (
                get_evaluation_metric(
                    evaluation=evaluation,
                    metric=metric,
                )
            )

            if metric_value is None:
                undefined_count += 1

            points.append(
                TwoWaySensitivityPoint(

                    x_parameter_name=(
                        x_parameter_name
                    ),

                    x_parameter_value=(
                        x_value
                    ),

                    y_parameter_name=(
                        y_parameter_name
                    ),

                    y_parameter_value=(
                        y_value
                    ),

                    metric=metric,

                    metric_value=(
                        metric_value
                    ),

                    scenario_id=(
                        evaluation.scenario_id
                    ),
                )
            )

    warnings: list[str] = []

    if undefined_count:

        warnings.append(
            f"{undefined_count} parameter "
            "combination(s) produced an "
            "undefined metric."
        )

    return TwoWaySensitivityResult(

        x_parameter_name=(
            x_parameter_name
        ),

        x_values=validated_x,

        y_parameter_name=(
            y_parameter_name
        ),

        y_values=validated_y,

        metric=metric,

        points=tuple(
            points
        ),

        warnings=tuple(
            warnings
        ),
    )


# ============================================================
# DETERMINE WHETHER LOWER OR HIGHER IS BETTER
# ============================================================

def _metric_lower_is_better(
    metric: SensitivityMetric,
) -> bool:
    """
    Define the direction of competitiveness.

    Lower is better for:

        LCOE
        payback

    Higher is better for:

        NPV
        IRR
        generation
        capacity factor
    """

    if metric in {
        SensitivityMetric.LCOE,
        SensitivityMetric.SIMPLE_PAYBACK,
        SensitivityMetric.DISCOUNTED_PAYBACK,
    }:

        return True

    if metric in {
        SensitivityMetric.NPV,
        SensitivityMetric.IRR,
        SensitivityMetric.FIRST_YEAR_GENERATION,
        SensitivityMetric.LIFETIME_GENERATION,
        SensitivityMetric.CAPACITY_FACTOR,
    }:

        return False

    raise ValueError(
        f"Competitiveness direction is not "
        f"defined for {metric.value}."
    )


# ============================================================
# BUILD COMPETITIVENESS MAP
# ============================================================

def build_competitiveness_map(
    sensitivity: TwoWaySensitivityResult,
    benchmark_value: float,
) -> CompetitivenessMap:
    """
    Compare every two-way sensitivity point with
    a benchmark value.

    Example
    -------

        candidate:
            wave

        metric:
            LCOE

        benchmark:
            solar P50 LCOE

        competitive when:

            LCOE_wave
            <=
            LCOE_solar
    """

    benchmark_value = float(
        benchmark_value
    )

    if not math.isfinite(
        benchmark_value
    ):

        raise ValueError(
            "Benchmark value must be finite."
        )

    lower_is_better = (
        _metric_lower_is_better(
            sensitivity.metric
        )
    )

    points: list[
        CompetitivenessPoint
    ] = []

    for point in sensitivity.points:

        value = (
            point.metric_value
        )

        if value is None:

            is_competitive = None

        elif lower_is_better:

            is_competitive = (
                value
                <= benchmark_value
            )

        else:

            is_competitive = (
                value
                >= benchmark_value
            )

        points.append(
            CompetitivenessPoint(

                x_parameter_value=(
                    point.x_parameter_value
                ),

                y_parameter_value=(
                    point.y_parameter_value
                ),

                metric_value=value,

                benchmark_value=(
                    benchmark_value
                ),

                is_competitive=(
                    is_competitive
                ),
            )
        )

    return CompetitivenessMap(

        x_parameter_name=(
            sensitivity.x_parameter_name
        ),

        y_parameter_name=(
            sensitivity.y_parameter_name
        ),

        metric=(
            sensitivity.metric
        ),

        benchmark_value=(
            benchmark_value
        ),

        lower_is_better=(
            lower_is_better
        ),

        points=tuple(
            points
        ),
    )


# ============================================================
# FIND APPROXIMATE FRONTIER
# ============================================================

def estimate_competitiveness_frontier(
    competitiveness_map: CompetitivenessMap,
) -> tuple[
    tuple[float, float],
    ...
]:
    """
    Estimate the boundary separating competitive and
    non-competitive regions.

    For every unique X value, find the smallest Y value
    that makes the candidate competitive.

    This is most meaningful when increasing Y improves
    performance.

    Example:

        X = wave CAPEX
        Y = conversion efficiency

    result might contain:

        (1500, 0.35)
        (2000, 0.45)
        (2500, 0.58)

    meaning progressively higher efficiency is required
    as CAPEX increases.

    This is a discrete-grid frontier, not an exact
    continuous mathematical solution.
    """

    grouped: dict[
        float,
        list[CompetitivenessPoint],
    ] = {}

    for point in (
        competitiveness_map.points
    ):

        grouped.setdefault(
            point.x_parameter_value,
            [],
        ).append(
            point
        )

    frontier: list[
        tuple[float, float]
    ] = []

    for x_value in sorted(grouped):

        candidates = sorted(
            grouped[x_value],
            key=lambda point: (
                point.y_parameter_value
            ),
        )

        competitive_candidates = [
            point
            for point in candidates
            if point.is_competitive is True
        ]

        if not competitive_candidates:
            continue

        first_competitive = (
            competitive_candidates[0]
        )

        frontier.append(
            (
                x_value,
                first_competitive
                .y_parameter_value,
            )
        )

    return tuple(
        frontier
    )