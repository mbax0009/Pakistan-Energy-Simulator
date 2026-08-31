# analysis/evaluators.py

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from analysis.generation_scenarios import (
    GenerationBasis,
    LifetimeGenerationScenario,
)

from analysis.project_evaluation import (
    ProjectEvaluation,
    evaluate_generation_scenario,
    evaluate_resource_case,
)

from analysis.scenario_builders import (
    RecalculationScope,
    ScenarioModification,
    ScenarioParameter,
    apply_scenario_parameter,
)

from core.lifecycle import (
    build_lifetime_generation,
)

from core.models import (
    ProjectScenario,
    Technology,
)

from core.resources import (
    SolarResourceSeries,
    WindResourceSeries,
    WaveResourceSeries,
)

from physics.solar import (
    simulate_solar,
)

from physics.wind import (
    WindDensityMode,
    simulate_wind,
)

from physics.wave import (
    simulate_wave,
)

from analysis.solar_resource_analysis import (
    SolarResourceAssessment,
    assess_long_term_solar_resource,
)

from analysis.wind_resource_analysis import (
    WindResourceAssessment,
    assess_long_term_wind_resource,
)

from analysis.wave_resource_analysis import (
    WaveResourceAssessment,
    assess_long_term_wave_resource,
)


# ============================================================
# RESOURCE TYPES
# ============================================================

ResourceSeries = (
    SolarResourceSeries
    | WindResourceSeries
    | WaveResourceSeries
)


AssessmentType = (
    SolarResourceAssessment
    | WindResourceAssessment
    | WaveResourceAssessment
)


# ============================================================
# RESOURCE LOADER INTERFACE
# ============================================================

class ResourceLoader(Protocol):
    """
    Callable interface for retrieving resource data
    for a modified project.

    Required mainly when a sensitivity parameter changes
    the resource request itself.

    Example:
        solar tilt / azimuth
    """

    def __call__(
        self,
        project: ProjectScenario,
    ) -> ResourceSeries:
        ...


# ============================================================
# BASELINE ANALYSIS CONTEXT
# ============================================================

@dataclass(frozen=True)
class EvaluationContext:
    """
    Stores the baseline information required to perform
    sensitivity recalculations efficiently.

    project:
        Original project assumptions.

    resource:
        Already-loaded historical resource data.

    assessment:
        Already-calculated long-term resource assessment.

    generation_scenario:
        Existing lifetime P90/P50/P10 generation case.

    evaluation:
        Existing financial project evaluation.

    generation_basis:
        Resource basis used for the evaluation.

    resource_loader:
        Optional function capable of retrieving new
        resource data when a parameter change requires
        upstream resource recalculation.
    """

    project: ProjectScenario

    resource: ResourceSeries

    assessment: AssessmentType

    generation_scenario: LifetimeGenerationScenario

    evaluation: ProjectEvaluation

    generation_basis: GenerationBasis

    resource_loader: (
        ResourceLoader | None
    ) = None

    def __post_init__(self):

        scenario_id = (
            self.project.scenario_id
        )

        if (
            self.assessment.scenario_id
            != scenario_id
        ):
            raise ValueError(
                "Assessment does not belong "
                "to the baseline project."
            )

        if (
            self.generation_scenario.scenario_id
            != scenario_id
        ):
            raise ValueError(
                "Generation scenario does not belong "
                "to the baseline project."
            )

        if (
            self.evaluation.scenario_id
            != scenario_id
        ):
            raise ValueError(
                "Evaluation does not belong "
                "to the baseline project."
            )

        if (
            self.generation_scenario.basis
            is not self.generation_basis
        ):
            raise ValueError(
                "Generation basis does not match "
                "the stored generation scenario."
            )


# ============================================================
# PHYSICS DISPATCH
# ============================================================

def simulate_project_resource(
    project: ProjectScenario,
    resource: ResourceSeries,
):
    """
    Dispatch project/resource data to the appropriate
    technology physics engine.

    This function produces a GenerationResult for the
    supplied time series.

    It is useful for single-period simulations, although
    long-term sensitivity normally uses the corresponding
    resource-assessment functions below.
    """

    if project.technology is Technology.SOLAR:

        if not isinstance(
            resource,
            SolarResourceSeries,
        ):
            raise TypeError(
                "Solar project requires "
                "SolarResourceSeries."
            )

        return simulate_solar(
            scenario=project,
            resource=resource,
        )

    if project.technology is Technology.WIND:

        if not isinstance(
            resource,
            WindResourceSeries,
        ):
            raise TypeError(
                "Wind project requires "
                "WindResourceSeries."
            )

        return simulate_wind(
            scenario=project,
            resource=resource,
            density_mode=WindDensityMode.AUTO,
        )

    if project.technology is Technology.WAVE:

        if not isinstance(
            resource,
            WaveResourceSeries,
        ):
            raise TypeError(
                "Wave project requires "
                "WaveResourceSeries."
            )

        return simulate_wave(
            scenario=project,
            resource=resource,
        )

    raise ValueError(
        f"Unsupported technology: "
        f"{project.technology}"
    )


# ============================================================
# LONG-TERM RESOURCE ASSESSMENT DISPATCH
# ============================================================

def assess_project_resource(
    project: ProjectScenario,
    resource: ResourceSeries,
) -> AssessmentType:
    """
    Run the correct long-term resource assessment
    for solar, wind or wave.

    This is the main physics/downstream dispatcher.
    """

    if project.technology is Technology.SOLAR:

        if not isinstance(
            resource,
            SolarResourceSeries,
        ):
            raise TypeError(
                "Solar project requires "
                "SolarResourceSeries."
            )

        return assess_long_term_solar_resource(
            scenario=project,
            resource=resource,
        )

    if project.technology is Technology.WIND:

        if not isinstance(
            resource,
            WindResourceSeries,
        ):
            raise TypeError(
                "Wind project requires "
                "WindResourceSeries."
            )

        return assess_long_term_wind_resource(
            scenario=project,
            resource=resource,
            density_mode=WindDensityMode.AUTO,
        )

    if project.technology is Technology.WAVE:

        if not isinstance(
            resource,
            WaveResourceSeries,
        ):
            raise TypeError(
                "Wave project requires "
                "WaveResourceSeries."
            )

        return assess_long_term_wave_resource(
            scenario=project,
            resource=resource,
        )

    raise ValueError(
        f"Unsupported technology: "
        f"{project.technology}"
    )


# ============================================================
# FINANCE-ONLY RECALCULATION
# ============================================================

def _evaluate_finance_only(
    modification: ScenarioModification,
    context: EvaluationContext,
) -> ProjectEvaluation:
    """
    Recalculate financial results while preserving
    the existing lifetime generation schedule.

    Used for parameters such as:

        CAPEX
        OPEX
        electricity price
        discount rate
    """

    modified_project = (
        modification.project
    )

    baseline_generation = (
        context.generation_scenario
    )

    # --------------------------------------------------------
    # Create an equivalent lifetime generation object
    # associated with the modified project assumptions.
    #
    # Generation itself is unchanged.
    # --------------------------------------------------------

    modified_generation = (
        LifetimeGenerationScenario(

            scenario_id=(
                modified_project.scenario_id
            ),

            technology=(
                modified_project.technology
            ),

            basis=(
                baseline_generation.basis
            ),

            first_year_generation_mwh=(
                baseline_generation
                .first_year_generation_mwh
            ),

            generation_by_year_mwh=(
                baseline_generation
                .generation_by_year_mwh
            ),

            annual_degradation_rate=(
                baseline_generation
                .annual_degradation_rate
            ),

            source_year=(
                baseline_generation.source_year
            ),

            warnings=(
                baseline_generation.warnings
            ),
        )
    )

    return evaluate_generation_scenario(
        project=modified_project,
        generation_scenario=(
            modified_generation
        ),
    )


# ============================================================
# LIFECYCLE + FINANCE RECALCULATION
# ============================================================

def _evaluate_lifecycle_and_finance(
    modification: ScenarioModification,
    context: EvaluationContext,
) -> ProjectEvaluation:
    """
    Reuse the selected first-year resource generation,
    but rebuild the lifetime degradation schedule.

    Used primarily for:

        annual_degradation_rate
    """

    modified_project = (
        modification.project
    )

    baseline_generation = (
        context.generation_scenario
    )

    # --------------------------------------------------------
    # Preserve first-year P90/P50/P10 generation.
    #
    # Only degradation changes.
    # --------------------------------------------------------

    generation_by_year_mwh = (
        build_lifetime_generation(

            scenario=modified_project,

            first_year_generation_mwh=(
                baseline_generation
                .first_year_generation_mwh
            ),
        )
    )

    modified_generation = (
        LifetimeGenerationScenario(

            scenario_id=(
                modified_project.scenario_id
            ),

            technology=(
                modified_project.technology
            ),

            basis=(
                baseline_generation.basis
            ),

            first_year_generation_mwh=(
                baseline_generation
                .first_year_generation_mwh
            ),

            generation_by_year_mwh=(
                generation_by_year_mwh
            ),

            annual_degradation_rate=(
                modified_project
                .annual_degradation_rate
            ),

            source_year=(
                baseline_generation.source_year
            ),

            warnings=(
                baseline_generation.warnings
            ),
        )
    )

    return evaluate_generation_scenario(
        project=modified_project,
        generation_scenario=(
            modified_generation
        ),
    )


# ============================================================
# PHYSICS + DOWNSTREAM RECALCULATION
# ============================================================

def _evaluate_physics_and_downstream(
    modification: ScenarioModification,
    context: EvaluationContext,
) -> ProjectEvaluation:
    """
    Reuse existing raw resource data, but rerun:

        physics
            ↓
        annual generation
            ↓
        P-values
            ↓
        lifecycle
            ↓
        finance

    Used for parameters such as:

        wind hub height
        wind availability
        solar losses
        wave efficiency
        wave capture width
    """

    modified_project = (
        modification.project
    )

    # --------------------------------------------------------
    # Historical resource itself stays unchanged.
    # --------------------------------------------------------

    resource = (
        context.resource
    )

    # --------------------------------------------------------
    # Re-run technology physics through the
    # long-term assessment.
    # --------------------------------------------------------

    modified_assessment = (
        assess_project_resource(
            project=modified_project,
            resource=resource,
        )
    )

    # --------------------------------------------------------
    # Select the same resource-risk basis as baseline.
    # --------------------------------------------------------

    return evaluate_resource_case(

        project=modified_project,

        assessment=modified_assessment,

        basis=context.generation_basis,

        historical_year=(
            context.generation_scenario.source_year
        ),
    )


# ============================================================
# RESOURCE + DOWNSTREAM RECALCULATION
# ============================================================

def _evaluate_resource_and_downstream(
    modification: ScenarioModification,
    context: EvaluationContext,
) -> ProjectEvaluation:
    """
    Reload resource data and then rerun the entire
    downstream simulation.

    Used when the modified parameter changes the
    resource request itself.

    Main current example:

        solar tilt
        solar azimuth

    because our POA/GTI request depends on orientation.
    """

    if context.resource_loader is None:

        raise ValueError(
            "This parameter requires resource "
            "recalculation, but no resource_loader "
            "was supplied in EvaluationContext."
        )

    modified_project = (
        modification.project
    )

    # --------------------------------------------------------
    # Get NEW resource data
    # --------------------------------------------------------

    modified_resource = (
        context.resource_loader(
            modified_project
        )
    )

    # --------------------------------------------------------
    # Re-run long-term physical assessment
    # --------------------------------------------------------

    modified_assessment = (
        assess_project_resource(
            project=modified_project,
            resource=modified_resource,
        )
    )

    # --------------------------------------------------------
    # Recreate same resource-risk case and finance
    # --------------------------------------------------------

    return evaluate_resource_case(

        project=modified_project,

        assessment=modified_assessment,

        basis=context.generation_basis,

        historical_year=(
            context.generation_scenario.source_year
        ),
    )


# ============================================================
# EXECUTE ONE MODIFICATION
# ============================================================

def evaluate_scenario_modification(
    modification: ScenarioModification,
    context: EvaluationContext,
) -> ProjectEvaluation:
    """
    Execute the minimum scientifically valid
    recalculation required by a scenario modification.

    This is the central sensitivity dispatcher.
    """

    scope = (
        modification.recalculation_scope
    )

    if (
        scope
        is RecalculationScope.FINANCE_ONLY
    ):

        return _evaluate_finance_only(
            modification=modification,
            context=context,
        )

    if (
        scope
        is RecalculationScope
        .LIFECYCLE_AND_FINANCE
    ):

        return (
            _evaluate_lifecycle_and_finance(
                modification=modification,
                context=context,
            )
        )

    if (
        scope
        is RecalculationScope
        .PHYSICS_AND_DOWNSTREAM
    ):

        return (
            _evaluate_physics_and_downstream(
                modification=modification,
                context=context,
            )
        )

    if (
        scope
        is RecalculationScope
        .RESOURCE_AND_DOWNSTREAM
    ):

        return (
            _evaluate_resource_and_downstream(
                modification=modification,
                context=context,
            )
        )

    raise ValueError(
        f"Unsupported recalculation scope: {scope}"
    )


# ============================================================
# CREATE PARAMETER EVALUATOR
# ============================================================

def create_parameter_evaluator(
    context: EvaluationContext,
    parameter: ScenarioParameter,
) -> Callable[
    [float],
    ProjectEvaluation,
]:
    """
    Build the evaluator function expected by
    analysis/sensitivity.py.

    Example
    -------

        wave_capex_evaluator =
            create_parameter_evaluator(
                context=wave_context,
                parameter=ScenarioParameter.CAPEX_PER_KW,
            )

        result =
            wave_capex_evaluator(2500)

    will:

        change CAPEX to $2500/kW
        determine recalculation scope
        reuse generation
        rerun finance
        return ProjectEvaluation
    """

    def evaluator(
        value: float,
    ) -> ProjectEvaluation:

        modification = (
            apply_scenario_parameter(

                project=context.project,

                parameter=parameter,

                value=value,
            )
        )

        return (
            evaluate_scenario_modification(

                modification=modification,

                context=context,
            )
        )

    return evaluator