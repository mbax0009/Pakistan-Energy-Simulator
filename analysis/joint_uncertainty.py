# analysis/joint_uncertainty.py

from __future__ import annotations

import math
import random

from collections.abc import (
    Mapping,
    Sequence,
)

from dataclasses import dataclass
from enum import Enum

from analysis.monte_carlo_evaluators import (
    MonteCarloProjectEvaluator,
)

from analysis.project_evaluation import (
    ProjectEvaluation,
)

from analysis.uncertainty import (
    UncertainVariable,
)


# ============================================================
# COMPARISON METRIC
# ============================================================

class JointComparisonMetric(str, Enum):
    """
    Metrics for direct paired technology comparison.
    """

    NPV = "npv"
    IRR = "irr"
    LCOE = "lcoe"

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
# ONE TECHNOLOGY IN THE JOINT MODEL
# ============================================================

@dataclass(frozen=True)
class JointTechnologyModel:
    """
    One technology participating in a joint
    uncertainty experiment.

    name:
        Human-readable identifier such as:
            "solar"
            "wind"
            "wave"

    evaluator:
        Project-specific Monte Carlo evaluator.

    specific_variables:
        Uncertain inputs unique to this technology.

    Examples
    --------

    Solar-specific:
        solar CAPEX
        solar system losses

    Wind-specific:
        wind CAPEX
        hub height

    Wave-specific:
        wave CAPEX
        conversion efficiency
    """

    name: str

    evaluator: MonteCarloProjectEvaluator

    specific_variables: tuple[
        UncertainVariable,
        ...
    ] = ()

    def __post_init__(self):

        if not self.name.strip():

            raise ValueError(
                "Technology name cannot be empty."
            )

        variable_names = tuple(
            variable.name
            for variable in self.specific_variables
        )

        if (
            len(set(variable_names))
            != len(variable_names)
        ):

            raise ValueError(
                f"Technology {self.name!r} contains "
                "duplicate specific-variable names."
            )


# ============================================================
# ONE TECHNOLOGY RESULT WITHIN ONE JOINT ITERATION
# ============================================================

@dataclass(frozen=True)
class JointTechnologyResult:
    """
    Result for one technology in one shared
    Monte Carlo world.
    """

    technology_name: str

    scenario_id: str

    sampled_specific_inputs: tuple[
        tuple[str, float],
        ...
    ]

    npv_usd: float

    irr: float | None

    lcoe_usd_per_mwh: float | None

    first_year_generation_mwh: float

    lifetime_generation_mwh: float

    capacity_factor: float

    def __post_init__(self):

        if not self.technology_name.strip():

            raise ValueError(
                "Technology name cannot be empty."
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

        if not (
            0
            <= self.capacity_factor
            <= 1
        ):

            raise ValueError(
                "Capacity factor must be "
                "between 0 and 1."
            )


# ============================================================
# ONE SHARED ECONOMIC WORLD
# ============================================================

@dataclass(frozen=True)
class JointMonteCarloIteration:
    """
    One complete joint Monte Carlo realization.

    Shared inputs are identical for all technologies
    during this iteration.

    Technology-specific inputs may differ.
    """

    iteration: int

    shared_inputs: tuple[
        tuple[str, float],
        ...
    ]

    technology_results: tuple[
        JointTechnologyResult,
        ...
    ]

    def __post_init__(self):

        if self.iteration < 1:

            raise ValueError(
                "Iteration must be at least 1."
            )

        if len(
            self.technology_results
        ) < 2:

            raise ValueError(
                "Joint uncertainty requires at least "
                "two technologies."
            )

    def result_for(
        self,
        technology_name: str,
    ) -> JointTechnologyResult:
        """
        Retrieve one technology result from
        this shared iteration.
        """

        for result in (
            self.technology_results
        ):

            if (
                result.technology_name
                == technology_name
            ):

                return result

        raise KeyError(
            f"No technology named "
            f"{technology_name!r}."
        )


# ============================================================
# PAIRED COMPARISON RESULT
# ============================================================

@dataclass(frozen=True)
class PairedTechnologyComparison:
    """
    Direct probabilistic comparison between two
    technologies.

    probability_a_better:
        Fraction of valid paired iterations where
        technology A beats technology B.

    probability_b_better:
        Opposite probability.

    probability_tie:
        Fraction effectively equal within tolerance.
    """

    technology_a: str

    technology_b: str

    metric: JointComparisonMetric

    valid_pair_count: int

    probability_a_better: float

    probability_b_better: float

    probability_tie: float

    mean_difference_a_minus_b: float

    median_difference_a_minus_b: float


# ============================================================
# COMPLETE JOINT ANALYSIS
# ============================================================

@dataclass(frozen=True)
class JointUncertaintyAnalysis:
    """
    Complete joint uncertainty experiment.
    """

    sample_count: int

    random_seed: int | None

    shared_variables: tuple[
        UncertainVariable,
        ...
    ]

    technology_names: tuple[
        str,
        ...
    ]

    iterations: tuple[
        JointMonteCarloIteration,
        ...
    ]

    warnings: tuple[str, ...] = ()

    def __post_init__(self):

        if self.sample_count < 1:

            raise ValueError(
                "Sample count must be positive."
            )

        if len(
            self.technology_names
        ) < 2:

            raise ValueError(
                "At least two technologies "
                "are required."
            )


# ============================================================
# SAMPLE A SET OF VARIABLES
# ============================================================

def _sample_variables(
    variables: Sequence[
        UncertainVariable
    ],
    rng: random.Random,
) -> dict[str, float]:
    """
    Sample one realization of a collection of
    uncertain inputs.
    """

    result: dict[
        str,
        float
    ] = {}

    for variable in variables:

        if variable.name in result:

            raise ValueError(
                f"Duplicate uncertain variable "
                f"{variable.name!r}."
            )

        value = (
            variable.distribution.sample(
                rng
            )
        )

        value = float(
            value
        )

        if not math.isfinite(
            value
        ):

            raise ValueError(
                f"Variable {variable.name!r} "
                "produced a non-finite sample."
            )

        result[
            variable.name
        ] = value

    return result


# ============================================================
# MERGE SHARED AND TECHNOLOGY-SPECIFIC INPUTS
# ============================================================

def _merge_inputs(
    shared_inputs: Mapping[
        str,
        float,
    ],
    specific_inputs: Mapping[
        str,
        float,
    ],
) -> dict[str, float]:
    """
    Combine common and technology-specific assumptions.

    Duplicate names are prohibited because it would be
    unclear which value should take precedence.
    """

    overlap = (
        set(shared_inputs)
        & set(specific_inputs)
    )

    if overlap:

        raise ValueError(
            "Shared and technology-specific "
            "uncertain inputs overlap: "
            + ", ".join(
                sorted(overlap)
            )
        )

    return {
        **shared_inputs,
        **specific_inputs,
    }


# ============================================================
# CONVERT PROJECT EVALUATION TO JOINT RESULT
# ============================================================

def _build_joint_technology_result(
    technology_name: str,

    evaluation: ProjectEvaluation,

    specific_inputs: Mapping[
        str,
        float,
    ],
) -> JointTechnologyResult:
    """
    Store only the quantities required for joint
    technology comparison.
    """

    return JointTechnologyResult(

        technology_name=(
            technology_name
        ),

        scenario_id=(
            evaluation.scenario_id
        ),

        sampled_specific_inputs=tuple(
            specific_inputs.items()
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

        first_year_generation_mwh=(
            evaluation
            .first_year_generation_mwh
        ),

        lifetime_generation_mwh=(
            evaluation
            .lifetime_generation_mwh
        ),

        capacity_factor=(
            evaluation
            .equivalent_first_year_capacity_factor
        ),
    )


# ============================================================
# RUN JOINT MONTE CARLO
# ============================================================

def run_joint_uncertainty(
    technologies: Sequence[
        JointTechnologyModel
    ],

    shared_variables: Sequence[
        UncertainVariable
    ] = (),

    sample_count: int = 5000,

    random_seed: int | None = 42,
) -> JointUncertaintyAnalysis:
    """
    Run multiple technologies inside the same simulated
    economic worlds.

    For iteration i:

        1. Draw shared economic assumptions ONCE.

        2. Draw technology-specific assumptions
           independently for each technology.

        3. Combine them.

        4. Evaluate solar / wind / wave.

        5. Store all results under the same
           iteration number.

    This makes paired technology probabilities
    meaningful.
    """

    technologies = tuple(
        technologies
    )

    shared_variables = tuple(
        shared_variables
    )

    if len(technologies) < 2:

        raise ValueError(
            "Joint uncertainty requires at "
            "least two technologies."
        )

    if sample_count < 1:

        raise ValueError(
            "sample_count must be positive."
        )

    technology_names = tuple(
        technology.name
        for technology in technologies
    )

    if (
        len(set(technology_names))
        != len(technology_names)
    ):

        raise ValueError(
            "Technology names must be unique."
        )

    # --------------------------------------------------------
    # Shared-variable uniqueness
    # --------------------------------------------------------

    shared_variable_names = tuple(
        variable.name
        for variable in shared_variables
    )

    if (
        len(set(shared_variable_names))
        != len(shared_variable_names)
    ):

        raise ValueError(
            "Shared uncertain-variable names "
            "must be unique."
        )

    # --------------------------------------------------------
    # Prevent shared/specific variable duplication
    # --------------------------------------------------------

    shared_name_set = set(
        shared_variable_names
    )

    for technology in technologies:

        specific_names = {
            variable.name
            for variable
            in technology.specific_variables
        }

        overlap = (
            shared_name_set
            & specific_names
        )

        if overlap:

            raise ValueError(
                f"Technology {technology.name!r} "
                "contains variables already defined "
                "as shared: "
                + ", ".join(
                    sorted(overlap)
                )
            )

    # --------------------------------------------------------
    # Master RNG
    # --------------------------------------------------------

    master_rng = random.Random(
        random_seed
    )

    iterations: list[
        JointMonteCarloIteration
    ] = []

    # ========================================================
    # MONTE CARLO LOOP
    # ========================================================

    for iteration_number in range(
        1,
        sample_count + 1,
    ):

        # ----------------------------------------------------
        # Shared economic world
        # ----------------------------------------------------

        shared_inputs = (
            _sample_variables(
                variables=(
                    shared_variables
                ),
                rng=master_rng,
            )
        )

        technology_results: list[
            JointTechnologyResult
        ] = []

        # ----------------------------------------------------
        # Evaluate every technology in SAME shared world
        # ----------------------------------------------------

        for technology in technologies:

            specific_inputs = (
                _sample_variables(
                    variables=(
                        technology
                        .specific_variables
                    ),
                    rng=master_rng,
                )
            )

            combined_inputs = (
                _merge_inputs(
                    shared_inputs=(
                        shared_inputs
                    ),
                    specific_inputs=(
                        specific_inputs
                    ),
                )
            )

            evaluation = (
                technology.evaluator(
                    combined_inputs
                )
            )

            technology_results.append(
                _build_joint_technology_result(

                    technology_name=(
                        technology.name
                    ),

                    evaluation=(
                        evaluation
                    ),

                    specific_inputs=(
                        specific_inputs
                    ),
                )
            )

        iterations.append(
            JointMonteCarloIteration(

                iteration=(
                    iteration_number
                ),

                shared_inputs=tuple(
                    shared_inputs.items()
                ),

                technology_results=tuple(
                    technology_results
                ),
            )
        )

    warnings = (
        (
            "Shared uncertain variables are sampled "
            "once per iteration and applied to every "
            "technology."
        ),

        (
            "Technology-specific variables are "
            "currently sampled independently unless "
            "their relationship is explicitly built "
            "into the model."
        ),

        (
            "Renewable-resource resampling is handled "
            "inside each technology's Monte Carlo "
            "evaluator and is therefore technology "
            "and site specific."
        ),
    )

    return JointUncertaintyAnalysis(

        sample_count=(
            sample_count
        ),

        random_seed=(
            random_seed
        ),

        shared_variables=(
            shared_variables
        ),

        technology_names=(
            technology_names
        ),

        iterations=tuple(
            iterations
        ),

        warnings=warnings,
    )


# ============================================================
# GET METRIC FROM JOINT RESULT
# ============================================================

def _joint_metric_value(
    result: JointTechnologyResult,
    metric: JointComparisonMetric,
) -> float | None:
    """
    Extract one metric for paired comparison.
    """

    if metric is JointComparisonMetric.NPV:

        return (
            result.npv_usd
        )

    if metric is JointComparisonMetric.IRR:

        return (
            result.irr
        )

    if metric is JointComparisonMetric.LCOE:

        return (
            result.lcoe_usd_per_mwh
        )

    if (
        metric
        is JointComparisonMetric
        .FIRST_YEAR_GENERATION
    ):

        return (
            result
            .first_year_generation_mwh
        )

    if (
        metric
        is JointComparisonMetric
        .LIFETIME_GENERATION
    ):

        return (
            result
            .lifetime_generation_mwh
        )

    if (
        metric
        is JointComparisonMetric
        .CAPACITY_FACTOR
    ):

        return (
            result.capacity_factor
        )

    raise ValueError(
        f"Unsupported metric: "
        f"{metric.value}"
    )


# ============================================================
# METRIC DIRECTION
# ============================================================

def _higher_is_better(
    metric: JointComparisonMetric,
) -> bool:
    """
    Define which technology wins a paired comparison.
    """

    if metric in {

        JointComparisonMetric.NPV,

        JointComparisonMetric.IRR,

        JointComparisonMetric
        .FIRST_YEAR_GENERATION,

        JointComparisonMetric
        .LIFETIME_GENERATION,

        JointComparisonMetric
        .CAPACITY_FACTOR,
    }:

        return True

    if (
        metric
        is JointComparisonMetric.LCOE
    ):

        return False

    raise ValueError(
        f"No comparison direction defined "
        f"for {metric.value}."
    )


# ============================================================
# MEDIAN
# ============================================================

def _median(
    values: Sequence[float],
) -> float:
    """
    Calculate median without importing another
    analysis module.
    """

    if not values:

        raise ValueError(
            "Cannot calculate median from "
            "empty values."
        )

    ordered = sorted(
        values
    )

    count = len(
        ordered
    )

    midpoint = (
        count
        // 2
    )

    if count % 2 == 1:

        return (
            ordered[
                midpoint
            ]
        )

    return (
        (
            ordered[
                midpoint - 1
            ]
            + ordered[
                midpoint
            ]
        )
        / 2.0
    )


# ============================================================
# PAIRED TECHNOLOGY COMPARISON
# ============================================================

def compare_joint_technologies(
    analysis: JointUncertaintyAnalysis,

    technology_a: str,

    technology_b: str,

    metric: JointComparisonMetric,

    equality_tolerance: float = 1e-9,
) -> PairedTechnologyComparison:
    """
    Compare two technologies iteration by iteration.

    Example:

        solar vs wind on NPV

    estimates:

        P(
            NPV_solar
            >
            NPV_wind
        )

    because both NPVs come from the same simulated
    economic world.
    """

    if (
        technology_a
        == technology_b
    ):

        raise ValueError(
            "Technology A and B must differ."
        )

    if (
        technology_a
        not in analysis.technology_names
    ):

        raise ValueError(
            f"Unknown technology: "
            f"{technology_a}"
        )

    if (
        technology_b
        not in analysis.technology_names
    ):

        raise ValueError(
            f"Unknown technology: "
            f"{technology_b}"
        )

    if equality_tolerance < 0:

        raise ValueError(
            "Equality tolerance cannot "
            "be negative."
        )

    higher_better = (
        _higher_is_better(
            metric
        )
    )

    a_wins = 0
    b_wins = 0
    ties = 0

    differences: list[
        float
    ] = []

    # --------------------------------------------------------
    # Paired iteration analysis
    # --------------------------------------------------------

    for iteration in (
        analysis.iterations
    ):

        result_a = (
            iteration.result_for(
                technology_a
            )
        )

        result_b = (
            iteration.result_for(
                technology_b
            )
        )

        value_a = (
            _joint_metric_value(
                result_a,
                metric,
            )
        )

        value_b = (
            _joint_metric_value(
                result_b,
                metric,
            )
        )

        # ----------------------------------------------------
        # Skip undefined paired outcomes
        # ----------------------------------------------------

        if (
            value_a is None
            or value_b is None
        ):

            continue

        if (
            not math.isfinite(
                value_a
            )
            or not math.isfinite(
                value_b
            )
        ):

            continue

        difference = (
            value_a
            - value_b
        )

        differences.append(
            difference
        )

        # ----------------------------------------------------
        # Tie
        # ----------------------------------------------------

        if math.isclose(
            value_a,
            value_b,
            rel_tol=0.0,
            abs_tol=equality_tolerance,
        ):

            ties += 1
            continue

        # ----------------------------------------------------
        # Higher metric wins
        # ----------------------------------------------------

        if higher_better:

            if value_a > value_b:
                a_wins += 1
            else:
                b_wins += 1

        # ----------------------------------------------------
        # Lower metric wins
        # ----------------------------------------------------

        else:

            if value_a < value_b:
                a_wins += 1
            else:
                b_wins += 1

    valid_pair_count = len(
        differences
    )

    if valid_pair_count == 0:

        raise ValueError(
            "No valid paired observations exist "
            "for this comparison metric."
        )

    return PairedTechnologyComparison(

        technology_a=(
            technology_a
        ),

        technology_b=(
            technology_b
        ),

        metric=metric,

        valid_pair_count=(
            valid_pair_count
        ),

        probability_a_better=(
            a_wins
            / valid_pair_count
        ),

        probability_b_better=(
            b_wins
            / valid_pair_count
        ),

        probability_tie=(
            ties
            / valid_pair_count
        ),

        mean_difference_a_minus_b=(
            math.fsum(
                differences
            )
            / valid_pair_count
        ),

        median_difference_a_minus_b=(
            _median(
                differences
            )
        ),
    )