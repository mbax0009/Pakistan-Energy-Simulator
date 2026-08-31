# analysis/project_evaluation.py

from __future__ import annotations

import math

from collections.abc import Mapping
from dataclasses import dataclass

from analysis.generation_scenarios import (
    GenerationBasis,
    LifetimeGenerationScenario,
    ResourceAssessment,
    build_lifetime_generation_scenario,
    build_standard_generation_scenarios,
)

from core.constants import (
    HOURS_PER_YEAR,
)

from core.models import (
    FinancialAnalysis,
    ProjectScenario,
    Technology,
)

from finance.economics import (
    analyze_project_financials,
)


# ============================================================
# PROJECT EVALUATION RESULT
# ============================================================

@dataclass(frozen=True)
class ProjectEvaluation:
    """
    Complete techno-economic evaluation of one
    project under one generation-risk case.

    Examples
    --------

        Solar P50
        Solar P90

        Wind P50
        Wind P90

        Wave P50
        Wave historical year 2018

    The object retains:

        project assumptions
        lifetime generation scenario
        financial analysis

    rather than copying financial values into multiple
    locations.
    """

    project: ProjectScenario

    generation_scenario: (
        LifetimeGenerationScenario
    )

    financial_analysis: FinancialAnalysis

    warnings: tuple[str, ...] = ()

    def __post_init__(self):

        # ----------------------------------------------------
        # Scenario IDs must agree
        # ----------------------------------------------------

        if (
            self.project.scenario_id
            != self.generation_scenario.scenario_id
        ):
            raise ValueError(
                "Project and lifetime-generation "
                "scenario IDs do not match."
            )

        # ----------------------------------------------------
        # Technologies must agree
        # ----------------------------------------------------

        if (
            self.project.technology
            is not self.generation_scenario.technology
        ):
            raise ValueError(
                "Project technology does not match "
                "generation-scenario technology."
            )

        # ----------------------------------------------------
        # Lifetime must agree
        # ----------------------------------------------------

        if (
            len(
                self.generation_scenario
                .generation_by_year_mwh
            )
            != self.project.lifetime_years
        ):
            raise ValueError(
                "Generation schedule length does "
                "not match project lifetime."
            )

        # ----------------------------------------------------
        # Finance schedule should contain:
        #
        # Year 0
        # +
        # operating years
        # ----------------------------------------------------

        expected_cash_flow_rows = (
            self.project.lifetime_years
            + 1
        )

        if (
            len(
                self.financial_analysis.cash_flows
            )
            != expected_cash_flow_rows
        ):
            raise ValueError(
                "Financial cash-flow schedule length "
                "does not match project lifetime."
            )


    # ========================================================
    # IDENTIFICATION
    # ========================================================

    @property
    def scenario_id(
        self,
    ) -> str:

        return (
            self.project.scenario_id
        )


    @property
    def technology(
        self,
    ) -> Technology:

        return (
            self.project.technology
        )


    @property
    def generation_basis(
        self,
    ) -> GenerationBasis:

        return (
            self.generation_scenario.basis
        )


    @property
    def source_year(
        self,
    ) -> int | None:

        return (
            self.generation_scenario.source_year
        )


    # ========================================================
    # GENERATION METRICS
    # ========================================================

    @property
    def first_year_generation_mwh(
        self,
    ) -> float:

        return (
            self.generation_scenario
            .first_year_generation_mwh
        )


    @property
    def lifetime_generation_mwh(
        self,
    ) -> float:

        return (
            self.generation_scenario
            .lifetime_generation_mwh
        )


    @property
    def final_year_generation_mwh(
        self,
    ) -> float:

        return (
            self.generation_scenario
            .final_year_generation_mwh
        )


    @property
    def equivalent_first_year_capacity_factor(
        self,
    ) -> float:
        """
        Convert first-year annual generation into an
        equivalent 8760-hour capacity factor.

        Formula:

            CF =
                E_1
                --------------------
                P_rated * 8760

        This is an annualized comparison metric.

        It should not be confused with the exact
        capacity factor calculated from one specific
        historical year's native time series.
        """

        maximum_standard_year_generation = (
            self.project.capacity_mw
            * HOURS_PER_YEAR
        )

        if maximum_standard_year_generation <= 0:

            raise ValueError(
                "Maximum annual generation must "
                "be greater than zero."
            )

        return (
            self.first_year_generation_mwh
            / maximum_standard_year_generation
        )


    # ========================================================
    # FINANCIAL METRICS
    # ========================================================

    @property
    def initial_capex_usd(
        self,
    ) -> float:

        return (
            self.financial_analysis
            .metrics
            .initial_capex_usd
        )


    @property
    def npv_usd(
        self,
    ) -> float:

        return (
            self.financial_analysis
            .metrics
            .npv_usd
        )


    @property
    def irr(
        self,
    ) -> float | None:

        return (
            self.financial_analysis
            .metrics
            .irr
        )


    @property
    def lcoe_usd_per_mwh(
        self,
    ) -> float | None:

        return (
            self.financial_analysis
            .metrics
            .lcoe_usd_per_mwh
        )


    @property
    def simple_payback_years(
        self,
    ) -> float | None:

        return (
            self.financial_analysis
            .metrics
            .simple_payback_years
        )


    @property
    def discounted_payback_years(
        self,
    ) -> float | None:

        return (
            self.financial_analysis
            .metrics
            .discounted_payback_years
        )


    @property
    def lifetime_revenue_usd(
        self,
    ) -> float:

        return (
            self.financial_analysis
            .metrics
            .lifetime_revenue_usd
        )


    @property
    def lifetime_opex_usd(
        self,
    ) -> float:

        return (
            self.financial_analysis
            .metrics
            .lifetime_opex_usd
        )


    @property
    def additional_capex_usd(
        self,
    ) -> float:

        return (
            self.financial_analysis
            .metrics
            .additional_capex_usd
        )


# ============================================================
# PROJECT / GENERATION VALIDATION
# ============================================================

def _validate_generation_scenario_match(
    project: ProjectScenario,
    generation_scenario: LifetimeGenerationScenario,
) -> None:
    """
    Ensure that a lifetime generation schedule belongs
    to the project being evaluated.
    """

    if (
        project.scenario_id
        != generation_scenario.scenario_id
    ):

        raise ValueError(
            "Lifetime generation scenario does "
            "not belong to this project."
        )

    if (
        project.technology
        is not generation_scenario.technology
    ):

        raise ValueError(
            "Lifetime generation technology does "
            "not match project technology."
        )

    if (
        len(
            generation_scenario
            .generation_by_year_mwh
        )
        != project.lifetime_years
    ):

        raise ValueError(
            "Lifetime generation schedule length "
            "does not match project lifetime."
        )

    if not math.isclose(
        project.annual_degradation_rate,
        generation_scenario
        .annual_degradation_rate,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):

        raise ValueError(
            "Generation scenario degradation rate "
            "does not match project degradation rate."
        )


# ============================================================
# EVALUATE ONE LIFETIME GENERATION CASE
# ============================================================

def evaluate_generation_scenario(
    project: ProjectScenario,
    generation_scenario: LifetimeGenerationScenario,
    additional_capex_by_year: (
        Mapping[int, float] | None
    ) = None,
) -> ProjectEvaluation:
    """
    Evaluate one complete lifetime generation case
    financially.

    Example:

        Wind P50
            ↓
        lifetime generation
            ↓
        annual revenues and costs
            ↓
        NPV / IRR / LCOE / payback
    """

    # --------------------------------------------------------
    # Validate physical/financial project matching
    # --------------------------------------------------------

    _validate_generation_scenario_match(
        project=project,
        generation_scenario=(
            generation_scenario
        ),
    )

    # --------------------------------------------------------
    # Run financial engine
    # --------------------------------------------------------

    financial_analysis = (
        analyze_project_financials(

            project=project,

            generation_by_year_mwh=(
                generation_scenario
                .generation_by_year_mwh
            ),

            additional_capex_by_year=(
                additional_capex_by_year
            ),
        )
    )

    # --------------------------------------------------------
    # Collect methodological warnings
    # --------------------------------------------------------

    warnings: list[str] = list(
        generation_scenario.warnings
    )

    if (
        financial_analysis.metrics.irr
        is None
    ):

        warnings.append(
            "A unique project IRR could not be "
            "calculated for this cash-flow pattern."
        )

    if (
        financial_analysis
        .metrics
        .simple_payback_years
        is None
    ):

        warnings.append(
            "The project does not achieve simple "
            "payback within the modelled lifetime."
        )

    if (
        financial_analysis
        .metrics
        .discounted_payback_years
        is None
    ):

        warnings.append(
            "The project does not achieve discounted "
            "payback within the modelled lifetime."
        )

    # --------------------------------------------------------
    # Complete evaluation
    # --------------------------------------------------------

    return ProjectEvaluation(

        project=project,

        generation_scenario=(
            generation_scenario
        ),

        financial_analysis=(
            financial_analysis
        ),

        warnings=tuple(
            warnings
        ),
    )


# ============================================================
# BUILD AND EVALUATE ONE RESOURCE BASIS
# ============================================================

def evaluate_resource_case(
    project: ProjectScenario,
    assessment: ResourceAssessment,
    basis: GenerationBasis,
    historical_year: int | None = None,
    additional_capex_by_year: (
        Mapping[int, float] | None
    ) = None,
) -> ProjectEvaluation:
    """
    Convenience function.

    Converts:

        long-term resource assessment

    directly into:

        financial project evaluation

    for one selected generation basis.
    """

    generation_scenario = (
        build_lifetime_generation_scenario(

            scenario=project,

            assessment=assessment,

            basis=basis,

            historical_year=(
                historical_year
            ),
        )
    )

    return evaluate_generation_scenario(

        project=project,

        generation_scenario=(
            generation_scenario
        ),

        additional_capex_by_year=(
            additional_capex_by_year
        ),
    )


# ============================================================
# EVALUATE P90 / P50 / P10
# ============================================================

def evaluate_standard_resource_cases(
    project: ProjectScenario,
    assessment: ResourceAssessment,
    additional_capex_by_year: (
        Mapping[int, float] | None
    ) = None,
) -> dict[
    GenerationBasis,
    ProjectEvaluation,
]:
    """
    Build and evaluate the standard resource-risk cases:

        P90
        P50
        P10

    Each case uses the same:

        technology
        project size
        CAPEX
        OPEX
        electricity price
        discount rate
        project lifetime

    Only the selected resource-generation basis changes.
    """

    generation_scenarios = (
        build_standard_generation_scenarios(

            scenario=project,

            assessment=assessment,
        )
    )

    evaluations: dict[
        GenerationBasis,
        ProjectEvaluation,
    ] = {}

    for (
        basis,
        generation_scenario,
    ) in generation_scenarios.items():

        evaluations[
            basis
        ] = (
            evaluate_generation_scenario(

                project=project,

                generation_scenario=(
                    generation_scenario
                ),

                additional_capex_by_year=(
                    additional_capex_by_year
                ),
            )
        )

    return evaluations
