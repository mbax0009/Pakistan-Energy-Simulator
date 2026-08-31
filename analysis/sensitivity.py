# analysis/sensitivity.py

from __future__ import annotations

import math

from collections.abc import (
    Callable,
    Sequence,
)

from dataclasses import dataclass
from enum import Enum

from analysis.project_evaluation import (
    ProjectEvaluation,
)


# ============================================================
# SENSITIVITY METRIC
# ============================================================

class SensitivityMetric(str, Enum):
    """
    Output metric examined during sensitivity analysis.
    """

    NPV = "npv"
    IRR = "irr"
    LCOE = "lcoe"

    SIMPLE_PAYBACK = (
        "simple_payback"
    )

    DISCOUNTED_PAYBACK = (
        "discounted_payback"
    )

    FIRST_YEAR_GENERATION = (
        "first_year_generation"
    )

    LIFETIME_GENERATION = (
        "lifetime_generation"
    )

    CAPACITY_FACTOR = (
        "capacity_factor"
    )


# ============================================================
# ONE SENSITIVITY POINT
# ============================================================

@dataclass(frozen=True)
class SensitivityPoint:
    """
    One evaluated parameter value.

    Example:

        parameter_name:
            "wave_capex_per_kw"

        parameter_value:
            3500

        metric:
            LCOE

        metric_value:
            160
    """

    parameter_name: str

    parameter_value: float

    metric: SensitivityMetric

    metric_value: float | None

    scenario_id: str

    def __post_init__(self):

        if not self.parameter_name.strip():

            raise ValueError(
                "Parameter name cannot be empty."
            )

        if not math.isfinite(
            self.parameter_value
        ):

            raise ValueError(
                "Parameter value must be finite."
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
# COMPLETE ONE-WAY SENSITIVITY RESULT
# ============================================================

@dataclass(frozen=True)
class SensitivityResult:
    """
    Results from varying one parameter while
    evaluating one selected metric.
    """

    parameter_name: str

    metric: SensitivityMetric

    points: tuple[
        SensitivityPoint,
        ...
    ]

    baseline_parameter_value: float | None = None

    baseline_metric_value: float | None = None

    warnings: tuple[str, ...] = ()

    def __post_init__(self):

        if not self.parameter_name.strip():

            raise ValueError(
                "Parameter name cannot be empty."
            )

        if not self.points:

            raise ValueError(
                "Sensitivity result must contain "
                "at least one point."
            )

    @property
    def valid_points(
        self,
    ) -> tuple[SensitivityPoint, ...]:
        """
        Points for which the selected metric
        could actually be calculated.
        """

        return tuple(
            point
            for point in self.points
            if point.metric_value is not None
        )


# ============================================================
# BREAK-EVEN RESULT
# ============================================================

@dataclass(frozen=True)
class BreakEvenResult:
    """
    Result from solving:

        selected metric = target value

    Example:

        wave LCOE = solar LCOE
    """

    parameter_name: str

    metric: SensitivityMetric

    target_metric_value: float

    break_even_parameter_value: float | None

    achieved_metric_value: float | None

    converged: bool

    iterations: int

    lower_bound: float

    upper_bound: float

    warning: str | None = None


# ============================================================
# EXTRACT METRIC
# ============================================================

def get_evaluation_metric(
    evaluation: ProjectEvaluation,
    metric: SensitivityMetric,
) -> float | None:
    """
    Extract one metric from a ProjectEvaluation.
    """

    if metric is SensitivityMetric.NPV:

        return (
            evaluation.npv_usd
        )

    if metric is SensitivityMetric.IRR:

        return (
            evaluation.irr
        )

    if metric is SensitivityMetric.LCOE:

        return (
            evaluation.lcoe_usd_per_mwh
        )

    if (
        metric
        is SensitivityMetric.SIMPLE_PAYBACK
    ):

        return (
            evaluation.simple_payback_years
        )

    if (
        metric
        is SensitivityMetric.DISCOUNTED_PAYBACK
    ):

        return (
            evaluation.discounted_payback_years
        )

    if (
        metric
        is SensitivityMetric.FIRST_YEAR_GENERATION
    ):

        return (
            evaluation.first_year_generation_mwh
        )

    if (
        metric
        is SensitivityMetric.LIFETIME_GENERATION
    ):

        return (
            evaluation.lifetime_generation_mwh
        )

    if (
        metric
        is SensitivityMetric.CAPACITY_FACTOR
    ):

        return (
            evaluation
            .equivalent_first_year_capacity_factor
        )

    raise ValueError(
        f"Unsupported sensitivity metric: {metric}"
    )


# ============================================================
# VALIDATE PARAMETER VALUES
# ============================================================

def _validate_parameter_values(
    values: Sequence[float],
) -> tuple[float, ...]:
    """
    Validate the values used in a sensitivity sweep.
    """

    if not values:

        raise ValueError(
            "Sensitivity analysis requires "
            "at least one parameter value."
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
                "Sensitivity parameter values "
                "must be finite."
            )

        validated.append(
            value
        )

    return tuple(
        validated
    )


# ============================================================
# RUN ONE-WAY SENSITIVITY
# ============================================================

def run_one_way_sensitivity(
    parameter_name: str,
    parameter_values: Sequence[float],
    evaluator: Callable[
        [float],
        ProjectEvaluation,
    ],
    metric: SensitivityMetric,
    baseline_parameter_value: float | None = None,
    baseline_evaluation: ProjectEvaluation | None = None,
) -> SensitivityResult:
    """
    Run a one-way sensitivity analysis.

    The evaluator function contains the project-specific
    recalculation logic.

    This allows the same sensitivity engine to examine:

        financial assumptions
        physical assumptions
        technology assumptions

    without sensitivity.py itself needing to know how
    solar, wind or wave physics work.

    Example
    -------

        evaluator(3000)

    might mean:

        rebuild wave project with
        CAPEX = $3000/kW

        then return its complete
        ProjectEvaluation.
    """

    if not parameter_name.strip():

        raise ValueError(
            "Parameter name cannot be empty."
        )

    values = (
        _validate_parameter_values(
            parameter_values
        )
    )

    points: list[
        SensitivityPoint
    ] = []

    warnings: list[str] = []

    for parameter_value in values:

        evaluation = evaluator(
            parameter_value
        )

        metric_value = (
            get_evaluation_metric(
                evaluation=evaluation,
                metric=metric,
            )
        )

        points.append(
            SensitivityPoint(

                parameter_name=(
                    parameter_name
                ),

                parameter_value=(
                    parameter_value
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

    # --------------------------------------------------------
    # Optional baseline result
    # --------------------------------------------------------

    baseline_metric_value: (
        float | None
    ) = None

    if baseline_evaluation is not None:

        baseline_metric_value = (
            get_evaluation_metric(
                evaluation=(
                    baseline_evaluation
                ),
                metric=metric,
            )
        )

    undefined_count = sum(
        point.metric_value is None
        for point in points
    )

    if undefined_count:

        warnings.append(
            f"{undefined_count} sensitivity point(s) "
            "produced an undefined metric."
        )

    return SensitivityResult(

        parameter_name=(
            parameter_name
        ),

        metric=metric,

        points=tuple(
            points
        ),

        baseline_parameter_value=(
            baseline_parameter_value
        ),

        baseline_metric_value=(
            baseline_metric_value
        ),

        warnings=tuple(
            warnings
        ),
    )


# ============================================================
# GENERATE EVENLY SPACED VALUES
# ============================================================

def generate_linear_parameter_values(
    minimum_value: float,
    maximum_value: float,
    number_of_points: int,
) -> tuple[float, ...]:
    """
    Generate evenly spaced sensitivity values.

    Example:

        min = 1000
        max = 5000
        n   = 5

    gives:

        1000
        2000
        3000
        4000
        5000
    """

    minimum_value = float(
        minimum_value
    )

    maximum_value = float(
        maximum_value
    )

    if not math.isfinite(
        minimum_value
    ):

        raise ValueError(
            "Minimum value must be finite."
        )

    if not math.isfinite(
        maximum_value
    ):

        raise ValueError(
            "Maximum value must be finite."
        )

    if maximum_value < minimum_value:

        raise ValueError(
            "Maximum value cannot be less "
            "than minimum value."
        )

    if number_of_points < 2:

        raise ValueError(
            "At least two sensitivity points "
            "are required."
        )

    step = (
        maximum_value
        - minimum_value
    ) / (
        number_of_points
        - 1
    )

    return tuple(

        minimum_value
        + step * index

        for index in range(
            number_of_points
        )
    )


# ============================================================
# BREAK-EVEN OBJECTIVE
# ============================================================

def _objective_value(
    parameter_value: float,
    evaluator: Callable[
        [float],
        ProjectEvaluation,
    ],
    metric: SensitivityMetric,
    target_metric_value: float,
) -> tuple[
    float,
    float,
]:
    """
    Evaluate:

        objective(x) =
            project_metric(x)
            - target_metric

    Break-even occurs when:

        objective(x) = 0
    """

    evaluation = evaluator(
        parameter_value
    )

    metric_value = (
        get_evaluation_metric(
            evaluation=evaluation,
            metric=metric,
        )
    )

    if metric_value is None:

        raise ValueError(
            "Selected metric is undefined at "
            f"parameter value {parameter_value}."
        )

    objective = (
        metric_value
        - target_metric_value
    )

    return (
        objective,
        metric_value,
    )


# ============================================================
# BREAK-EVEN SEARCH
# ============================================================

def find_break_even_parameter(
    parameter_name: str,
    evaluator: Callable[
        [float],
        ProjectEvaluation,
    ],
    metric: SensitivityMetric,
    target_metric_value: float,
    lower_bound: float,
    upper_bound: float,
    parameter_tolerance: float = 1e-6,
    metric_tolerance: float = 1e-6,
    max_iterations: int = 200,
) -> BreakEvenResult:
    """
    Find parameter value where:

        selected project metric
        =
        target metric

    using the bisection method.

    Example
    -------

        Find wave CAPEX where:

            LCOE_wave
            =
            LCOE_solar

    Important
    ---------
    Bisection requires the target to be bracketed.

    The metric should also behave monotonically or
    near-monotonically over the selected interval for
    the result to have a clear interpretation.
    """

    if not parameter_name.strip():

        raise ValueError(
            "Parameter name cannot be empty."
        )

    target_metric_value = float(
        target_metric_value
    )

    lower_bound = float(
        lower_bound
    )

    upper_bound = float(
        upper_bound
    )

    if not math.isfinite(
        target_metric_value
    ):

        raise ValueError(
            "Target metric value must be finite."
        )

    if not math.isfinite(
        lower_bound
    ):

        raise ValueError(
            "Lower bound must be finite."
        )

    if not math.isfinite(
        upper_bound
    ):

        raise ValueError(
            "Upper bound must be finite."
        )

    if lower_bound >= upper_bound:

        raise ValueError(
            "Lower bound must be less "
            "than upper bound."
        )

    if parameter_tolerance <= 0:

        raise ValueError(
            "Parameter tolerance must be positive."
        )

    if metric_tolerance <= 0:

        raise ValueError(
            "Metric tolerance must be positive."
        )

    if max_iterations <= 0:

        raise ValueError(
            "max_iterations must be positive."
        )

    # --------------------------------------------------------
    # Evaluate bounds
    # --------------------------------------------------------

    (
        lower_objective,
        lower_metric,
    ) = _objective_value(

        parameter_value=(
            lower_bound
        ),

        evaluator=evaluator,

        metric=metric,

        target_metric_value=(
            target_metric_value
        ),
    )

    (
        upper_objective,
        upper_metric,
    ) = _objective_value(

        parameter_value=(
            upper_bound
        ),

        evaluator=evaluator,

        metric=metric,

        target_metric_value=(
            target_metric_value
        ),
    )

    # --------------------------------------------------------
    # Exact lower-bound solution
    # --------------------------------------------------------

    if abs(
        lower_objective
    ) <= metric_tolerance:

        return BreakEvenResult(

            parameter_name=(
                parameter_name
            ),

            metric=metric,

            target_metric_value=(
                target_metric_value
            ),

            break_even_parameter_value=(
                lower_bound
            ),

            achieved_metric_value=(
                lower_metric
            ),

            converged=True,

            iterations=0,

            lower_bound=(
                lower_bound
            ),

            upper_bound=(
                upper_bound
            ),
        )

    # --------------------------------------------------------
    # Exact upper-bound solution
    # --------------------------------------------------------

    if abs(
        upper_objective
    ) <= metric_tolerance:

        return BreakEvenResult(

            parameter_name=(
                parameter_name
            ),

            metric=metric,

            target_metric_value=(
                target_metric_value
            ),

            break_even_parameter_value=(
                upper_bound
            ),

            achieved_metric_value=(
                upper_metric
            ),

            converged=True,

            iterations=0,

            lower_bound=(
                lower_bound
            ),

            upper_bound=(
                upper_bound
            ),
        )

    # --------------------------------------------------------
    # Target must be bracketed
    # --------------------------------------------------------

    if (
        lower_objective
        * upper_objective
        > 0
    ):

        return BreakEvenResult(

            parameter_name=(
                parameter_name
            ),

            metric=metric,

            target_metric_value=(
                target_metric_value
            ),

            break_even_parameter_value=None,

            achieved_metric_value=None,

            converged=False,

            iterations=0,

            lower_bound=(
                lower_bound
            ),

            upper_bound=(
                upper_bound
            ),

            warning=(
                "Target metric is not bracketed "
                "within the supplied parameter range."
            ),
        )

    # --------------------------------------------------------
    # Bisection
    # --------------------------------------------------------

    current_lower = (
        lower_bound
    )

    current_upper = (
        upper_bound
    )

    current_lower_objective = (
        lower_objective
    )

    last_midpoint: float | None = None

    last_metric: float | None = None

    for iteration in range(
        1,
        max_iterations + 1,
    ):

        midpoint = (
            current_lower
            + current_upper
        ) / 2.0

        (
            midpoint_objective,
            midpoint_metric,
        ) = _objective_value(

            parameter_value=(
                midpoint
            ),

            evaluator=evaluator,

            metric=metric,

            target_metric_value=(
                target_metric_value
            ),
        )

        last_midpoint = midpoint
        last_metric = midpoint_metric

        # ----------------------------------------------------
        # Metric convergence
        # ----------------------------------------------------

        if abs(
            midpoint_objective
        ) <= metric_tolerance:

            return BreakEvenResult(

                parameter_name=(
                    parameter_name
                ),

                metric=metric,

                target_metric_value=(
                    target_metric_value
                ),

                break_even_parameter_value=(
                    midpoint
                ),

                achieved_metric_value=(
                    midpoint_metric
                ),

                converged=True,

                iterations=(
                    iteration
                ),

                lower_bound=(
                    lower_bound
                ),

                upper_bound=(
                    upper_bound
                ),
            )

        # ----------------------------------------------------
        # Parameter convergence
        # ----------------------------------------------------

        if (
            current_upper
            - current_lower
        ) <= parameter_tolerance:

            return BreakEvenResult(

                parameter_name=(
                    parameter_name
                ),

                metric=metric,

                target_metric_value=(
                    target_metric_value
                ),

                break_even_parameter_value=(
                    midpoint
                ),

                achieved_metric_value=(
                    midpoint_metric
                ),

                converged=True,

                iterations=(
                    iteration
                ),

                lower_bound=(
                    lower_bound
                ),

                upper_bound=(
                    upper_bound
                ),
            )

        # ----------------------------------------------------
        # Keep the half containing the root
        # ----------------------------------------------------

        if (
            current_lower_objective
            * midpoint_objective
            <= 0
        ):

            current_upper = (
                midpoint
            )

        else:

            current_lower = (
                midpoint
            )

            current_lower_objective = (
                midpoint_objective
            )

    # --------------------------------------------------------
    # Iteration limit reached
    # --------------------------------------------------------

    return BreakEvenResult(

        parameter_name=(
            parameter_name
        ),

        metric=metric,

        target_metric_value=(
            target_metric_value
        ),

        break_even_parameter_value=(
            last_midpoint
        ),

        achieved_metric_value=(
            last_metric
        ),

        converged=False,

        iterations=(
            max_iterations
        ),

        lower_bound=(
            lower_bound
        ),

        upper_bound=(
            upper_bound
        ),

        warning=(
            "Maximum iterations reached before "
            "the requested tolerance was achieved."
        ),
    )