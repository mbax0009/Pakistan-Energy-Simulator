# analysis/uncertainty.py

from __future__ import annotations

import math
import random
import statistics

from collections.abc import (
    Callable,
    Mapping,
    Sequence,
)

from dataclasses import dataclass
from typing import Protocol

from analysis.project_evaluation import (
    ProjectEvaluation,
)

from analysis.sensitivity import (
    SensitivityMetric,
)


# ============================================================
# PROBABILITY DISTRIBUTION INTERFACE
# ============================================================

class ProbabilityDistribution(Protocol):
    """
    Common interface for uncertainty distributions.

    Every distribution must be able to generate one
    random sample using the supplied random-number
    generator.

    Supplying the RNG externally allows complete
    reproducibility through a fixed random seed.
    """

    def sample(
        self,
        rng: random.Random,
    ) -> float:
        ...


# ============================================================
# UNIFORM DISTRIBUTION
# ============================================================

@dataclass(frozen=True)
class UniformDistribution:
    """
    Continuous uniform distribution.

    Every value between minimum_value and maximum_value
    is equally likely.

    Appropriate only when there is no strong reason to
    favour values near the centre.

    Example:
        discount rate between 8% and 12%
    """

    minimum_value: float
    maximum_value: float

    def __post_init__(self):

        if not math.isfinite(
            self.minimum_value
        ):
            raise ValueError(
                "Uniform minimum must be finite."
            )

        if not math.isfinite(
            self.maximum_value
        ):
            raise ValueError(
                "Uniform maximum must be finite."
            )

        if (
            self.minimum_value
            >= self.maximum_value
        ):
            raise ValueError(
                "Uniform minimum must be less "
                "than maximum."
            )

    def sample(
        self,
        rng: random.Random,
    ) -> float:

        return rng.uniform(
            self.minimum_value,
            self.maximum_value,
        )


# ============================================================
# TRIANGULAR DISTRIBUTION
# ============================================================

@dataclass(frozen=True)
class TriangularDistribution:
    """
    Triangular probability distribution.

    Defined by:

        minimum
        most-likely value (mode)
        maximum

    Very useful for engineering-cost assumptions when
    detailed statistical evidence is unavailable.

    Example:

        wave CAPEX:
            minimum = 2500
            mode    = 3500
            maximum = 5000
    """

    minimum_value: float
    mode_value: float
    maximum_value: float

    def __post_init__(self):

        values = (
            self.minimum_value,
            self.mode_value,
            self.maximum_value,
        )

        if not all(
            math.isfinite(value)
            for value in values
        ):
            raise ValueError(
                "Triangular-distribution values "
                "must be finite."
            )

        if not (
            self.minimum_value
            <= self.mode_value
            <= self.maximum_value
        ):
            raise ValueError(
                "Triangular distribution must satisfy "
                "minimum <= mode <= maximum."
            )

        if (
            self.minimum_value
            == self.maximum_value
        ):
            raise ValueError(
                "Triangular distribution requires "
                "a non-zero range."
            )

    def sample(
        self,
        rng: random.Random,
    ) -> float:

        return rng.triangular(
            self.minimum_value,
            self.maximum_value,
            self.mode_value,
        )


# ============================================================
# TRUNCATED NORMAL DISTRIBUTION
# ============================================================

@dataclass(frozen=True)
class TruncatedNormalDistribution:
    """
    Normal distribution restricted to physically or
    economically meaningful bounds.

    Samples outside the bounds are rejected and redrawn.

    Example:

        electricity-price growth:
            mean = 0.03
            standard deviation = 0.01
            minimum = 0
            maximum = 0.08
    """

    mean: float
    standard_deviation: float

    minimum_value: float | None = None
    maximum_value: float | None = None

    max_sampling_attempts: int = 10_000

    def __post_init__(self):

        if not math.isfinite(
            self.mean
        ):
            raise ValueError(
                "Normal mean must be finite."
            )

        if (
            not math.isfinite(
                self.standard_deviation
            )
            or self.standard_deviation <= 0
        ):
            raise ValueError(
                "Normal standard deviation must "
                "be finite and positive."
            )

        if (
            self.minimum_value is not None
            and not math.isfinite(
                self.minimum_value
            )
        ):
            raise ValueError(
                "Minimum bound must be finite."
            )

        if (
            self.maximum_value is not None
            and not math.isfinite(
                self.maximum_value
            )
        ):
            raise ValueError(
                "Maximum bound must be finite."
            )

        if (
            self.minimum_value is not None
            and self.maximum_value is not None
            and self.minimum_value
            >= self.maximum_value
        ):
            raise ValueError(
                "Minimum bound must be less "
                "than maximum bound."
            )

        if self.max_sampling_attempts <= 0:
            raise ValueError(
                "max_sampling_attempts must "
                "be positive."
            )

    def sample(
        self,
        rng: random.Random,
    ) -> float:

        for _ in range(
            self.max_sampling_attempts
        ):

            value = rng.gauss(
                self.mean,
                self.standard_deviation,
            )

            if (
                self.minimum_value is not None
                and value < self.minimum_value
            ):
                continue

            if (
                self.maximum_value is not None
                and value > self.maximum_value
            ):
                continue

            return value

        raise RuntimeError(
            "Unable to draw a truncated-normal "
            "sample within the specified bounds."
        )


# ============================================================
# EMPIRICAL DISTRIBUTION
# ============================================================

@dataclass(frozen=True)
class EmpiricalDistribution:
    """
    Draw directly from observed historical values.

    This is particularly valuable for renewable-resource
    uncertainty because it avoids assuming that resource
    performance follows a normal distribution.

    Example:
        annual wind-generation multipliers derived from
        20 historical years.
    """

    values: tuple[float, ...]

    def __post_init__(self):

        if not self.values:
            raise ValueError(
                "Empirical distribution cannot "
                "be empty."
            )

        if not all(
            math.isfinite(value)
            for value in self.values
        ):
            raise ValueError(
                "Empirical values must be finite."
            )

    def sample(
        self,
        rng: random.Random,
    ) -> float:

        return rng.choice(
            self.values
        )


# ============================================================
# UNCERTAIN VARIABLE
# ============================================================

@dataclass(frozen=True)
class UncertainVariable:
    """
    One uncertain model input.

    name:
        Identifier understood by the Monte Carlo evaluator.

    distribution:
        Probability model from which values are sampled.

    units:
        Optional descriptive units.

    Examples:
        capex_per_kw
        electricity_price_per_mwh
        discount_rate
        generation_multiplier
    """

    name: str

    distribution: ProbabilityDistribution

    units: str | None = None

    def __post_init__(self):

        if not self.name.strip():
            raise ValueError(
                "Uncertain-variable name "
                "cannot be empty."
            )


# ============================================================
# ONE MONTE CARLO SAMPLE
# ============================================================

@dataclass(frozen=True)
class MonteCarloSample:
    """
    Inputs and resulting outputs from one Monte Carlo run.

    sampled_inputs is stored as immutable name/value pairs
    rather than a mutable dictionary.
    """

    iteration: int

    sampled_inputs: tuple[
        tuple[str, float],
        ...
    ]

    npv_usd: float

    irr: float | None

    lcoe_usd_per_mwh: float | None

    simple_payback_years: float | None

    discounted_payback_years: float | None

    first_year_generation_mwh: float

    lifetime_generation_mwh: float

    def __post_init__(self):

        if self.iteration < 1:
            raise ValueError(
                "Monte Carlo iteration must "
                "be at least 1."
            )

        if not math.isfinite(
            self.npv_usd
        ):
            raise ValueError(
                "NPV must be finite."
            )

        if (
            self.irr is not None
            and not math.isfinite(
                self.irr
            )
        ):
            raise ValueError(
                "IRR must be finite when defined."
            )

        if (
            self.lcoe_usd_per_mwh is not None
            and not math.isfinite(
                self.lcoe_usd_per_mwh
            )
        ):
            raise ValueError(
                "LCOE must be finite when defined."
            )

    def input_value(
        self,
        name: str,
    ) -> float:
        """
        Retrieve one sampled input by name.
        """

        for (
            variable_name,
            value,
        ) in self.sampled_inputs:

            if variable_name == name:
                return value

        raise KeyError(
            f"No sampled input named {name!r}."
        )


# ============================================================
# METRIC DISTRIBUTION SUMMARY
# ============================================================

@dataclass(frozen=True)
class MetricDistributionSummary:
    """
    Statistical summary of one Monte Carlo output.

    Percentiles are ordinary statistical percentiles.

    Therefore:

        percentile_10
            lower 10th percentile

        percentile_90
            upper 90th percentile

    This naming deliberately avoids confusing them with
    renewable-energy P90 exceedance terminology.
    """

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


# ============================================================
# COMPLETE MONTE CARLO ANALYSIS
# ============================================================

@dataclass(frozen=True)
class MonteCarloAnalysis:
    """
    Complete probabilistic project-risk analysis.
    """

    scenario_id: str

    sample_count: int

    random_seed: int | None

    variables: tuple[
        UncertainVariable,
        ...
    ]

    samples: tuple[
        MonteCarloSample,
        ...
    ]

    metric_summaries: tuple[
        MetricDistributionSummary,
        ...
    ]

    probability_npv_positive: float

    irr_hurdle_rate: float | None

    probability_irr_above_hurdle: float | None

    warnings: tuple[str, ...] = ()

    def summary_for(
        self,
        metric: SensitivityMetric,
    ) -> MetricDistributionSummary:
        """
        Retrieve distribution summary for one metric.
        """

        for summary in self.metric_summaries:

            if summary.metric is metric:
                return summary

        raise KeyError(
            f"No Monte Carlo summary exists "
            f"for {metric.value}."
        )


# ============================================================
# EMPIRICAL PERCENTILE
# ============================================================

def _percentile(
    values: Sequence[float],
    probability: float,
) -> float:
    """
    Empirical percentile using linear interpolation.
    """

    if not values:
        raise ValueError(
            "Cannot calculate percentile "
            "from an empty dataset."
        )

    if not (
        0
        <= probability
        <= 1
    ):
        raise ValueError(
            "Probability must be between 0 and 1."
        )

    ordered = sorted(
        float(value)
        for value in values
    )

    if len(ordered) == 1:
        return ordered[0]

    position = (
        probability
        * (len(ordered) - 1)
    )

    lower_index = math.floor(
        position
    )

    upper_index = math.ceil(
        position
    )

    if lower_index == upper_index:
        return ordered[
            lower_index
        ]

    fraction = (
        position
        - lower_index
    )

    return (
        ordered[lower_index]
        + fraction
        * (
            ordered[upper_index]
            - ordered[lower_index]
        )
    )


# ============================================================
# BUILD ONE METRIC SUMMARY
# ============================================================

def _summarize_metric(
    metric: SensitivityMetric,
    values: Sequence[
        float | None
    ],
) -> MetricDistributionSummary:
    """
    Build descriptive statistics for one
    Monte Carlo output metric.
    """

    valid_values = tuple(
        float(value)
        for value in values
        if value is not None
        and math.isfinite(value)
    )

    undefined_count = (
        len(values)
        - len(valid_values)
    )

    if not valid_values:
        return MetricDistributionSummary(
            metric=metric,
            valid_count=0,
            undefined_count=len(values),
            mean=None,
            median=None,
            standard_deviation=None,
            percentile_05=None,
            percentile_10=None,
            percentile_50=None,
            percentile_90=None,
            percentile_95=None,
            minimum=None,
            maximum=None,
        )

    mean = statistics.fmean(
        valid_values
    )

    median = statistics.median(
        valid_values
    )

    if len(valid_values) > 1:

        standard_deviation = (
            statistics.stdev(
                valid_values
            )
        )

    else:

        standard_deviation = 0.0

    return MetricDistributionSummary(

        metric=metric,

        valid_count=len(
            valid_values
        ),

        undefined_count=(
            undefined_count
        ),

        mean=mean,

        median=median,

        standard_deviation=(
            standard_deviation
        ),

        percentile_05=_percentile(
            valid_values,
            0.05,
        ),

        percentile_10=_percentile(
            valid_values,
            0.10,
        ),

        percentile_50=_percentile(
            valid_values,
            0.50,
        ),

        percentile_90=_percentile(
            valid_values,
            0.90,
        ),

        percentile_95=_percentile(
            valid_values,
            0.95,
        ),

        minimum=min(
            valid_values
        ),

        maximum=max(
            valid_values
        ),
    )


# ============================================================
# SAMPLE UNCERTAIN INPUTS
# ============================================================

def _sample_inputs(
    variables: Sequence[
        UncertainVariable
    ],
    rng: random.Random,
) -> dict[str, float]:
    """
    Draw one realization of all uncertain variables.

    Current version samples variables independently.

    Correlated uncertainty should be added explicitly
    later rather than being silently assumed.
    """

    sampled: dict[
        str,
        float
    ] = {}

    for variable in variables:

        if variable.name in sampled:

            raise ValueError(
                f"Duplicate uncertain variable: "
                f"{variable.name}"
            )

        value = (
            variable.distribution.sample(
                rng
            )
        )

        if not math.isfinite(
            value
        ):
            raise ValueError(
                f"Distribution for {variable.name} "
                "returned a non-finite sample."
            )

        sampled[
            variable.name
        ] = value

    return sampled


# ============================================================
# MONTE CARLO EVALUATOR TYPE
# ============================================================

MonteCarloEvaluator = Callable[
    [Mapping[str, float]],
    ProjectEvaluation,
]


# ============================================================
# RUN MONTE CARLO ANALYSIS
# ============================================================

def run_monte_carlo(
    scenario_id: str,

    variables: Sequence[
        UncertainVariable
    ],

    evaluator: MonteCarloEvaluator,

    sample_count: int = 5000,

    random_seed: int | None = 42,

    irr_hurdle_rate: float | None = None,
) -> MonteCarloAnalysis:
    """
    Run a probabilistic project-risk simulation.

    For every iteration:

        1. sample uncertain inputs
        2. evaluate complete project
        3. store NPV, IRR, LCOE and generation
        4. repeat

    The result describes distributions rather than
    one deterministic project outcome.
    """

    if not scenario_id.strip():

        raise ValueError(
            "Scenario ID cannot be empty."
        )

    variables = tuple(
        variables
    )

    if not variables:

        raise ValueError(
            "Monte Carlo analysis requires at least "
            "one uncertain variable."
        )

    variable_names = tuple(
        variable.name
        for variable in variables
    )

    if (
        len(set(variable_names))
        != len(variable_names)
    ):

        raise ValueError(
            "Uncertain-variable names "
            "must be unique."
        )

    if sample_count < 1:

        raise ValueError(
            "sample_count must be at least 1."
        )

    if irr_hurdle_rate is not None:

        if (
            not math.isfinite(
                irr_hurdle_rate
            )
            or irr_hurdle_rate <= -1
        ):

            raise ValueError(
                "IRR hurdle rate must be finite "
                "and greater than -1."
            )

    # --------------------------------------------------------
    # Reproducible pseudo-random number generator
    # --------------------------------------------------------

    rng = random.Random(
        random_seed
    )

    samples: list[
        MonteCarloSample
    ] = []

    # --------------------------------------------------------
    # Simulation
    # --------------------------------------------------------

    for iteration in range(
        1,
        sample_count + 1,
    ):

        sampled_inputs = (
            _sample_inputs(
                variables=variables,
                rng=rng,
            )
        )

        evaluation = evaluator(
            sampled_inputs
        )

        if (
            evaluation.scenario_id
            != scenario_id
        ):

            raise ValueError(
                "Monte Carlo evaluator returned "
                "an unexpected scenario ID."
            )

        samples.append(
            MonteCarloSample(

                iteration=iteration,

                sampled_inputs=tuple(
                    sampled_inputs.items()
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

                first_year_generation_mwh=(
                    evaluation
                    .first_year_generation_mwh
                ),

                lifetime_generation_mwh=(
                    evaluation
                    .lifetime_generation_mwh
                ),
            )
        )

    # --------------------------------------------------------
    # Build metric distributions
    # --------------------------------------------------------

    summaries = (

        _summarize_metric(
            SensitivityMetric.NPV,
            tuple(
                sample.npv_usd
                for sample in samples
            ),
        ),

        _summarize_metric(
            SensitivityMetric.IRR,
            tuple(
                sample.irr
                for sample in samples
            ),
        ),

        _summarize_metric(
            SensitivityMetric.LCOE,
            tuple(
                sample.lcoe_usd_per_mwh
                for sample in samples
            ),
        ),

        _summarize_metric(
            SensitivityMetric.SIMPLE_PAYBACK,
            tuple(
                sample.simple_payback_years
                for sample in samples
            ),
        ),

        _summarize_metric(
            SensitivityMetric.DISCOUNTED_PAYBACK,
            tuple(
                sample.discounted_payback_years
                for sample in samples
            ),
        ),

        _summarize_metric(
            SensitivityMetric.FIRST_YEAR_GENERATION,
            tuple(
                sample.first_year_generation_mwh
                for sample in samples
            ),
        ),

        _summarize_metric(
            SensitivityMetric.LIFETIME_GENERATION,
            tuple(
                sample.lifetime_generation_mwh
                for sample in samples
            ),
        ),
    )

    # --------------------------------------------------------
    # Probability project NPV is positive
    # --------------------------------------------------------

    positive_npv_count = sum(
        sample.npv_usd > 0
        for sample in samples
    )

    probability_npv_positive = (
        positive_npv_count
        / sample_count
    )

    # --------------------------------------------------------
    # Probability IRR beats hurdle rate
    # --------------------------------------------------------

    probability_irr_above_hurdle: (
        float | None
    ) = None

    warnings: list[str] = []

    if irr_hurdle_rate is not None:

        defined_irrs = tuple(
            sample.irr
            for sample in samples
            if sample.irr is not None
        )

        if defined_irrs:

            probability_irr_above_hurdle = (
                sum(
                    irr
                    > irr_hurdle_rate

                    for irr in defined_irrs
                )
                / len(defined_irrs)
            )

        else:

            warnings.append(
                "IRR was undefined for all Monte Carlo "
                "samples, so hurdle-rate probability "
                "could not be calculated."
            )

    # --------------------------------------------------------
    # Warn about undefined financial metrics
    # --------------------------------------------------------

    undefined_irr_count = sum(
        sample.irr is None
        for sample in samples
    )

    if undefined_irr_count:

        warnings.append(
            f"IRR was undefined for "
            f"{undefined_irr_count} of "
            f"{sample_count} simulations."
        )

    undefined_lcoe_count = sum(
        sample.lcoe_usd_per_mwh
        is None
        for sample in samples
    )

    if undefined_lcoe_count:

        warnings.append(
            f"LCOE was undefined for "
            f"{undefined_lcoe_count} of "
            f"{sample_count} simulations."
        )

    warnings.append(
        "Uncertain variables are currently sampled "
        "independently. Correlation between variables "
        "is not modelled unless the evaluator explicitly "
        "introduces that relationship."
    )

    return MonteCarloAnalysis(

        scenario_id=scenario_id,

        sample_count=sample_count,

        random_seed=random_seed,

        variables=variables,

        samples=tuple(
            samples
        ),

        metric_summaries=(
            summaries
        ),

        probability_npv_positive=(
            probability_npv_positive
        ),

        irr_hurdle_rate=(
            irr_hurdle_rate
        ),

        probability_irr_above_hurdle=(
            probability_irr_above_hurdle
        ),

        warnings=tuple(
            warnings
        ),
    )
