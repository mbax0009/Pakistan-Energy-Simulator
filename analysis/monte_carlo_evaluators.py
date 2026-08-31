# analysis/monte_carlo_evaluators.py

from __future__ import annotations

import math
import random

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from analysis.evaluators import (
    AssessmentType,
    EvaluationContext,
    assess_project_resource,
)

from analysis.generation_scenarios import (
    GenerationBasis,
    LifetimeGenerationScenario,
    build_lifetime_generation_scenario,
)

from analysis.project_evaluation import (
    ProjectEvaluation,
    evaluate_generation_scenario,
)

from analysis.scenario_builders import (
    RecalculationScope,
    ScenarioParameter,
    apply_scenario_parameter,
)

from core.models import (
    ProjectScenario,
)


# ============================================================
# RESOURCE RESAMPLING MODE
# ============================================================

class ResourceResamplingMode(str, Enum):
    """
    Defines how renewable-resource uncertainty is
    represented during Monte Carlo simulation.

    NONE
        Do not introduce additional weather-year
        variability.

        Use the deterministic generation basis stored
        in EvaluationContext, such as P50.

    ANNUAL_EMPIRICAL
        For every future project year, randomly draw
        one complete historical annual-generation
        result from the accepted resource assessment.

        This preserves the empirical annual resource
        distribution without assuming normality.
    """

    NONE = "none"

    ANNUAL_EMPIRICAL = (
        "annual_empirical"
    )


# ============================================================
# RESOURCE-YEAR DRAW
# ============================================================

@dataclass(frozen=True)
class ResourceYearDraw:
    """
    One historical resource year selected to represent
    one future operating year.

    Example:

        project_year = 7
        historical_year = 2014
        undegraded_generation = 304000 MWh
        degradation_factor = 0.9704
        final_generation = 295002 MWh
    """

    project_year: int

    historical_year: int

    undegraded_generation_mwh: float

    degradation_factor: float

    final_generation_mwh: float

    def __post_init__(self):

        if self.project_year < 1:

            raise ValueError(
                "Project year must be at least 1."
            )

        if self.historical_year < 1:

            raise ValueError(
                "Historical year must be positive."
            )

        if (
            not math.isfinite(
                self.undegraded_generation_mwh
            )
            or self.undegraded_generation_mwh < 0
        ):

            raise ValueError(
                "Undegraded generation must be "
                "finite and non-negative."
            )

        if not (
            0
            <= self.degradation_factor
            <= 1
        ):

            raise ValueError(
                "Degradation factor must be "
                "between 0 and 1."
            )

        if (
            not math.isfinite(
                self.final_generation_mwh
            )
            or self.final_generation_mwh < 0
        ):

            raise ValueError(
                "Final generation must be "
                "finite and non-negative."
            )


# ============================================================
# EMPIRICAL LIFETIME RESOURCE DRAW
# ============================================================

@dataclass(frozen=True)
class EmpiricalLifetimeResourceDraw:
    """
    Complete sequence of historical weather/resource
    years selected for one simulated project lifetime.
    """

    draws: tuple[
        ResourceYearDraw,
        ...
    ]

    def __post_init__(self):

        if not self.draws:

            raise ValueError(
                "Lifetime resource draw "
                "cannot be empty."
            )

    @property
    def generation_by_year_mwh(
        self,
    ) -> tuple[float, ...]:

        return tuple(
            draw.final_generation_mwh
            for draw in self.draws
        )

    @property
    def historical_years(
        self,
    ) -> tuple[int, ...]:

        return tuple(
            draw.historical_year
            for draw in self.draws
        )

    @property
    def lifetime_generation_mwh(
        self,
    ) -> float:

        return math.fsum(
            self.generation_by_year_mwh
        )


# ============================================================
# RECALCULATION SCOPE ORDER
# ============================================================

_SCOPE_PRIORITY = {

    RecalculationScope.FINANCE_ONLY:
        0,

    RecalculationScope
    .LIFECYCLE_AND_FINANCE:
        1,

    RecalculationScope
    .PHYSICS_AND_DOWNSTREAM:
        2,

    RecalculationScope
    .RESOURCE_AND_DOWNSTREAM:
        3,
}


def _maximum_recalculation_scope(
    scopes: tuple[
        RecalculationScope,
        ...
    ],
) -> RecalculationScope:
    """
    Return the furthest-upstream recalculation required
    by a collection of sampled parameters.

    Example:

        CAPEX
            finance only

        wave efficiency
            physics + downstream

    Together:
        physics + downstream
    """

    if not scopes:

        return (
            RecalculationScope.FINANCE_ONLY
        )

    return max(
        scopes,
        key=lambda scope: (
            _SCOPE_PRIORITY[
                scope
            ]
        ),
    )


# ============================================================
# APPLY MONTE CARLO INPUTS
# ============================================================

def apply_sampled_parameters(
    baseline_project: ProjectScenario,
    sampled_inputs: Mapping[
        str,
        float,
    ],
) -> tuple[
    ProjectScenario,
    RecalculationScope,
]:
    """
    Apply sampled Monte Carlo values to an immutable
    baseline project.

    Variable names are expected to correspond to
    ScenarioParameter values.

    Examples:

        "capex_per_kw"
        "discount_rate"
        "wave_conversion_efficiency"
        "annual_degradation_rate"

    Returns:

        modified project
        maximum required recalculation scope
    """

    project = baseline_project

    scopes: list[
        RecalculationScope
    ] = []

    for (
        parameter_name,
        parameter_value,
    ) in sampled_inputs.items():

        try:

            parameter = (
                ScenarioParameter(
                    parameter_name
                )
            )

        except ValueError as exc:

            raise ValueError(
                "Monte Carlo input name "
                f"{parameter_name!r} is not a "
                "supported ScenarioParameter."
            ) from exc

        modification = (
            apply_scenario_parameter(

                project=project,

                parameter=parameter,

                value=parameter_value,
            )
        )

        project = (
            modification.project
        )

        scopes.append(
            modification.recalculation_scope
        )

    return (
        project,
        _maximum_recalculation_scope(
            tuple(scopes)
        ),
    )


# ============================================================
# GET HISTORICAL ANNUAL GENERATION
# ============================================================

def _historical_generation_population(
    assessment: AssessmentType,
) -> tuple[
    tuple[int, float],
    ...
]:
    """
    Extract accepted historical annual-generation
    observations.

    These have already passed completeness checks
    in the relevant solar/wind/wave resource analysis.
    """

    population: list[
        tuple[int, float]
    ] = []

    for annual_result in (
        assessment.years
    ):

        year = int(
            annual_result.year
        )

        generation = float(
            annual_result.generation_mwh
        )

        if (
            not math.isfinite(
                generation
            )
            or generation < 0
        ):

            raise ValueError(
                f"Historical generation for {year} "
                "is invalid."
            )

        population.append(
            (
                year,
                generation,
            )
        )

    if not population:

        raise ValueError(
            "Resource assessment contains no "
            "accepted historical years."
        )

    return tuple(
        population
    )


# ============================================================
# BUILD EMPIRICAL FUTURE RESOURCE SEQUENCE
# ============================================================

def build_empirical_lifetime_resource_draw(
    project: ProjectScenario,
    assessment: AssessmentType,
    rng: random.Random,
) -> EmpiricalLifetimeResourceDraw:
    """
    Construct one possible future lifetime by sampling
    historical annual resource years WITH replacement.

    Mathematical model
    ------------------

    Let:

        G_y

    represent annual generation from accepted historical
    resource year y.

    For future project year t, randomly select:

        Y_t

    from the historical-year population.

    Then:

        E_t =
            G_(Y_t)
            * (1 - d) ** (t - 1)

    where:

        d = annual degradation rate.

    Sampling with replacement means the same historical
    analogue can appear more than once.
    """

    historical_population = (
        _historical_generation_population(
            assessment
        )
    )

    degradation_rate = (
        project.annual_degradation_rate
    )

    draws: list[
        ResourceYearDraw
    ] = []

    for project_year in range(
        1,
        project.lifetime_years + 1,
    ):

        (
            historical_year,
            undegraded_generation_mwh,
        ) = rng.choice(
            historical_population
        )

        degradation_factor = (
            (
                1.0
                - degradation_rate
            )
            ** (
                project_year
                - 1
            )
        )

        final_generation_mwh = (
            undegraded_generation_mwh
            * degradation_factor
        )

        draws.append(
            ResourceYearDraw(

                project_year=(
                    project_year
                ),

                historical_year=(
                    historical_year
                ),

                undegraded_generation_mwh=(
                    undegraded_generation_mwh
                ),

                degradation_factor=(
                    degradation_factor
                ),

                final_generation_mwh=(
                    final_generation_mwh
                ),
            )
        )

    return (
        EmpiricalLifetimeResourceDraw(
            draws=tuple(
                draws
            )
        )
    )


# ============================================================
# CREATE MONTE CARLO GENERATION SCENARIO
# ============================================================

def build_monte_carlo_generation_scenario(
    project: ProjectScenario,
    assessment: AssessmentType,
    rng: random.Random,
) -> tuple[
    LifetimeGenerationScenario,
    EmpiricalLifetimeResourceDraw,
]:
    """
    Build a complete stochastic lifetime generation
    schedule using annual empirical resource resampling.
    """

    resource_draw = (
        build_empirical_lifetime_resource_draw(

            project=project,

            assessment=assessment,

            rng=rng,
        )
    )

    generation_by_year_mwh = (
        resource_draw
        .generation_by_year_mwh
    )

    generation_scenario = (
        LifetimeGenerationScenario(

            scenario_id=(
                project.scenario_id
            ),

            technology=(
                project.technology
            ),

            basis=(
                GenerationBasis.MONTE_CARLO
            ),

            first_year_generation_mwh=(
                generation_by_year_mwh[
                    0
                ]
            ),

            generation_by_year_mwh=(
                generation_by_year_mwh
            ),

            annual_degradation_rate=(
                project
                .annual_degradation_rate
            ),

            source_year=None,

            warnings=(
                (
                    "Lifetime generation uses "
                    "independent empirical resampling "
                    "of accepted historical annual "
                    "resource years."
                ),
            ),
        )
    )

    return (
        generation_scenario,
        resource_draw,
    )


# ============================================================
# MONTE CARLO PROJECT EVALUATOR
# ============================================================

class MonteCarloProjectEvaluator:
    """
    Callable evaluator used by uncertainty.run_monte_carlo.

    Each call:

        sampled inputs
            ↓
        modified immutable project
            ↓
        determine recalculation scope
            ↓
        update resource assessment if necessary
            ↓
        construct lifetime resource realization
            ↓
        run finance
            ↓
        ProjectEvaluation

    Resource-year sampling uses a separate RNG from the
    parameter-distribution RNG in uncertainty.py.
    """

    def __init__(
        self,
        context: EvaluationContext,

        resource_resampling_mode: (
            ResourceResamplingMode
        ) = (
            ResourceResamplingMode
            .ANNUAL_EMPIRICAL
        ),

        resource_random_seed: (
            int | None
        ) = 1042,
    ):

        self.context = context

        self.resource_resampling_mode = (
            resource_resampling_mode
        )

        self.resource_random_seed = (
            resource_random_seed
        )

        self._resource_rng = (
            random.Random(
                resource_random_seed
            )
        )

        self._last_resource_draw: (
            EmpiricalLifetimeResourceDraw
            | None
        ) = None


    # ========================================================
    # LAST DRAW
    # ========================================================

    @property
    def last_resource_draw(
        self,
    ) -> (
        EmpiricalLifetimeResourceDraw
        | None
    ):
        """
        Resource-year sequence from the most recent
        Monte Carlo evaluation.

        Useful for debugging and model validation.
        """

        return (
            self._last_resource_draw
        )


    # ========================================================
    # RESET
    # ========================================================

    def reset_resource_rng(
        self,
    ) -> None:
        """
        Reset empirical resource sampling so an
        experiment can be reproduced exactly.
        """

        self._resource_rng = (
            random.Random(
                self.resource_random_seed
            )
        )

        self._last_resource_draw = None


    # ========================================================
    # ENSURE CORRECT RESOURCE ASSESSMENT
    # ========================================================

    def _resolve_assessment(
        self,
        project: ProjectScenario,
        scope: RecalculationScope,
    ) -> AssessmentType:
        """
        Determine which resource assessment should be
        used for the current Monte Carlo sample.
        """

        # ----------------------------------------------------
        # Finance/lifecycle changes do not change the
        # historical physical generation distribution.
        # ----------------------------------------------------

        if scope in {

            RecalculationScope.FINANCE_ONLY,

            RecalculationScope
            .LIFECYCLE_AND_FINANCE,
        }:

            return (
                self.context.assessment
            )

        # ----------------------------------------------------
        # Physical parameter changed.
        #
        # Reuse the same raw historical resource data but
        # simulate generation again.
        # ----------------------------------------------------

        if (
            scope
            is RecalculationScope
            .PHYSICS_AND_DOWNSTREAM
        ):

            return assess_project_resource(

                project=project,

                resource=(
                    self.context.resource
                ),
            )

        # ----------------------------------------------------
        # Resource-dependent parameter changed.
        #
        # Example:
        # solar tilt or azimuth.
        # ----------------------------------------------------

        if (
            scope
            is RecalculationScope
            .RESOURCE_AND_DOWNSTREAM
        ):

            if (
                self.context.resource_loader
                is None
            ):

                raise ValueError(
                    "Monte Carlo sample requires "
                    "resource reloading but the "
                    "EvaluationContext has no "
                    "resource_loader."
                )

            resource = (
                self.context.resource_loader(
                    project
                )
            )

            return assess_project_resource(

                project=project,

                resource=resource,
            )

        raise ValueError(
            "Unsupported Monte Carlo "
            f"recalculation scope: {scope}"
        )


    # ========================================================
    # BUILD GENERATION
    # ========================================================

    def _build_generation_scenario(
        self,
        project: ProjectScenario,
        assessment: AssessmentType,
    ) -> LifetimeGenerationScenario:
        """
        Build either:

            deterministic P50/P90/P10 lifetime generation

        or:

            stochastic empirical year-by-year generation.
        """

        if (
            self.resource_resampling_mode
            is ResourceResamplingMode.NONE
        ):

            self._last_resource_draw = None

            return (
                build_lifetime_generation_scenario(

                    scenario=project,

                    assessment=assessment,

                    basis=(
                        self.context
                        .generation_basis
                    ),

                    historical_year=(
                        self.context
                        .generation_scenario
                        .source_year
                    ),
                )
            )

        if (
            self.resource_resampling_mode
            is ResourceResamplingMode
            .ANNUAL_EMPIRICAL
        ):

            (
                generation_scenario,
                resource_draw,
            ) = (
                build_monte_carlo_generation_scenario(

                    project=project,

                    assessment=assessment,

                    rng=(
                        self._resource_rng
                    ),
                )
            )

            self._last_resource_draw = (
                resource_draw
            )

            return (
                generation_scenario
            )

        raise ValueError(
            "Unsupported resource-resampling mode: "
            f"{self.resource_resampling_mode}"
        )


    # ========================================================
    # CALLABLE INTERFACE
    # ========================================================

    def __call__(
        self,
        sampled_inputs: Mapping[
            str,
            float,
        ],
    ) -> ProjectEvaluation:
        """
        Evaluate one complete Monte Carlo realization.
        """

        # ----------------------------------------------------
        # Apply all sampled project assumptions
        # ----------------------------------------------------

        (
            modified_project,
            recalculation_scope,
        ) = (
            apply_sampled_parameters(

                baseline_project=(
                    self.context.project
                ),

                sampled_inputs=(
                    sampled_inputs
                ),
            )
        )

        # ----------------------------------------------------
        # Obtain correct historical physical assessment
        # ----------------------------------------------------

        assessment = (
            self._resolve_assessment(

                project=(
                    modified_project
                ),

                scope=(
                    recalculation_scope
                ),
            )
        )

        # ----------------------------------------------------
        # Build this iteration's lifetime generation
        # ----------------------------------------------------

        generation_scenario = (
            self._build_generation_scenario(

                project=(
                    modified_project
                ),

                assessment=assessment,
            )
        )

        # ----------------------------------------------------
        # Finance
        # ----------------------------------------------------

        return (
            evaluate_generation_scenario(

                project=(
                    modified_project
                ),

                generation_scenario=(
                    generation_scenario
                ),
            )
        )


# ============================================================
# CONVENIENCE FACTORY
# ============================================================

def create_monte_carlo_evaluator(
    context: EvaluationContext,

    resource_resampling_mode: (
        ResourceResamplingMode
    ) = (
        ResourceResamplingMode
        .ANNUAL_EMPIRICAL
    ),

    resource_random_seed: (
        int | None
    ) = 1042,
) -> MonteCarloProjectEvaluator:
    """
    Convenience constructor for the project-specific
    Monte Carlo evaluator.
    """

    return MonteCarloProjectEvaluator(

        context=context,

        resource_resampling_mode=(
            resource_resampling_mode
        ),

        resource_random_seed=(
            resource_random_seed
        ),
    )