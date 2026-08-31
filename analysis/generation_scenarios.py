# analysis/generation_scenarios.py

from __future__ import annotations

import math

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from core.lifecycle import (
    build_lifetime_generation,
)

from core.models import (
    ProjectScenario,
    Technology,
)


# ============================================================
# STRUCTURAL TYPES
# ============================================================

class AnnualGenerationRecord(Protocol):
    """
    Minimum information required from an annual
    technology-generation result.

    Solar, wind, and wave annual results all satisfy
    this interface because they contain:

        year
        generation_mwh
    """

    year: int
    generation_mwh: float


class ResourceAssessment(Protocol):
    """
    Common structure required from a long-term
    resource assessment.

    SolarResourceAssessment,
    WindResourceAssessment,
    and WaveResourceAssessment

    can all be used without generation_scenarios.py
    needing technology-specific logic.
    """

    scenario_id: str

    years: tuple[
        AnnualGenerationRecord,
        ...
    ]

    mean_generation_mwh: float
    median_generation_mwh: float

    p10_generation_mwh: float
    p50_generation_mwh: float
    p90_generation_mwh: float


# ============================================================
# GENERATION BASIS
# ============================================================

class GenerationBasis(str, Enum):
    """
    Defines which long-term generation estimate is used
    as the first-year production basis.

    P90:
        Conservative annual resource case.

    P50:
        Central annual resource case.

    P10:
        Relatively optimistic annual resource case.

    MEAN:
        Historical arithmetic mean.

    MEDIAN:
        Historical median.

    HISTORICAL_YEAR:
        Generation from one specific accepted
        historical year.
    """

    P90 = "p90"
    P50 = "p50"
    P10 = "p10"

    MEAN = "mean"
    MEDIAN = "median"

    HISTORICAL_YEAR = "historical_year"
    MONTE_CARLO = "monte_carlo"

# ============================================================
# LIFETIME GENERATION CASE
# ============================================================

@dataclass(frozen=True)
class LifetimeGenerationScenario:
    """
    One complete lifetime electricity-production case.

    This object is technology-independent.

    Examples:

        Solar P50
        Wind P90
        Wave P10
        Solar historical year 2018
    """

    scenario_id: str

    technology: Technology

    basis: GenerationBasis

    first_year_generation_mwh: float

    generation_by_year_mwh: tuple[
        float,
        ...
    ]

    annual_degradation_rate: float

    source_year: int | None = None

    warnings: tuple[str, ...] = ()

    def __post_init__(self):

        if not self.scenario_id.strip():
            raise ValueError(
                "Scenario ID cannot be empty."
            )

        if not math.isfinite(
            self.first_year_generation_mwh
        ):
            raise ValueError(
                "First-year generation must be finite."
            )

        if self.first_year_generation_mwh < 0:
            raise ValueError(
                "First-year generation cannot "
                "be negative."
            )

        if not self.generation_by_year_mwh:
            raise ValueError(
                "Lifetime generation schedule "
                "cannot be empty."
            )

        for generation in (
            self.generation_by_year_mwh
        ):

            if not math.isfinite(
                generation
            ):
                raise ValueError(
                    "Lifetime generation values "
                    "must be finite."
                )

            if generation < 0:
                raise ValueError(
                    "Lifetime generation cannot "
                    "be negative."
                )

        if not (
            0
            <= self.annual_degradation_rate
            < 1
        ):
            raise ValueError(
                "Annual degradation rate must "
                "be between 0 and 1."
            )

        if (
            self.basis
            is GenerationBasis.HISTORICAL_YEAR
            and self.source_year is None
        ):
            raise ValueError(
                "Historical-year generation basis "
                "requires source_year."
            )

        if (
            self.basis
            is not GenerationBasis.HISTORICAL_YEAR
            and self.source_year is not None
        ):
            raise ValueError(
                "source_year should only be provided "
                "for HISTORICAL_YEAR basis."
            )

    @property
    def lifetime_generation_mwh(
        self,
    ) -> float:
        """
        Total electricity generated throughout
        the project lifetime.
        """

        return math.fsum(
            self.generation_by_year_mwh
        )

    @property
    def final_year_generation_mwh(
        self,
    ) -> float:
        """
        Generation during the final project year.
        """

        return (
            self.generation_by_year_mwh[-1]
        )

    @property
    def lifetime_years(
        self,
    ) -> int:
        """
        Number of operating years represented.
        """

        return len(
            self.generation_by_year_mwh
        )


# ============================================================
# SCENARIO / ASSESSMENT MATCHING
# ============================================================

def _validate_assessment_match(
    scenario: ProjectScenario,
    assessment: ResourceAssessment,
) -> None:
    """
    Ensure that the resource assessment belongs
    to the same project scenario.

    This prevents accidentally using:

        solar assessment A

    with:

        project scenario B.
    """

    if (
        assessment.scenario_id
        != scenario.scenario_id
    ):

        raise ValueError(
            "Resource assessment scenario ID does "
            "not match the project scenario ID."
        )


# ============================================================
# NUMERIC VALIDATION
# ============================================================

def _validate_generation_value(
    generation_mwh: float,
    name: str,
) -> float:
    """
    Validate a selected annual-generation estimate.
    """

    generation_mwh = float(
        generation_mwh
    )

    if not math.isfinite(
        generation_mwh
    ):

        raise ValueError(
            f"{name} generation must be finite."
        )

    if generation_mwh < 0:

        raise ValueError(
            f"{name} generation cannot be negative."
        )

    return generation_mwh


# ============================================================
# HISTORICAL-YEAR SELECTION
# ============================================================

def _find_historical_year_generation(
    assessment: ResourceAssessment,
    year: int,
) -> float:
    """
    Retrieve generation for one accepted historical year.

    Note:
        Years excluded from the long-term assessment
        because of incomplete data are not available here.
    """

    if not isinstance(
        year,
        int,
    ):

        raise TypeError(
            "Historical year must be an integer."
        )

    for annual_result in assessment.years:

        if annual_result.year == year:

            return _validate_generation_value(
                annual_result.generation_mwh,
                f"Historical year {year}",
            )

    available_years = tuple(
        result.year
        for result in assessment.years
    )

    raise ValueError(
        f"Historical year {year} is not available "
        f"in the accepted resource assessment. "
        f"Available years: {available_years}"
    )


# ============================================================
# SELECT FIRST-YEAR GENERATION
# ============================================================

def select_first_year_generation_mwh(
    assessment: ResourceAssessment,
    basis: GenerationBasis,
    historical_year: int | None = None,
) -> float:
    """
    Select the annual-generation value that will
    become Year 1 of the lifetime projection.
    """

    # --------------------------------------------------------
    # P90
    # --------------------------------------------------------

    if basis is GenerationBasis.P90:

        if historical_year is not None:

            raise ValueError(
                "historical_year must not be supplied "
                "when using P90."
            )

        return _validate_generation_value(
            assessment.p90_generation_mwh,
            "P90",
        )

    # --------------------------------------------------------
    # P50
    # --------------------------------------------------------

    if basis is GenerationBasis.P50:

        if historical_year is not None:

            raise ValueError(
                "historical_year must not be supplied "
                "when using P50."
            )

        return _validate_generation_value(
            assessment.p50_generation_mwh,
            "P50",
        )

    # --------------------------------------------------------
    # P10
    # --------------------------------------------------------

    if basis is GenerationBasis.P10:

        if historical_year is not None:

            raise ValueError(
                "historical_year must not be supplied "
                "when using P10."
            )

        return _validate_generation_value(
            assessment.p10_generation_mwh,
            "P10",
        )

    # --------------------------------------------------------
    # Historical mean
    # --------------------------------------------------------

    if basis is GenerationBasis.MEAN:

        if historical_year is not None:

            raise ValueError(
                "historical_year must not be supplied "
                "when using historical mean."
            )

        return _validate_generation_value(
            assessment.mean_generation_mwh,
            "Mean",
        )

    # --------------------------------------------------------
    # Historical median
    # --------------------------------------------------------

    if basis is GenerationBasis.MEDIAN:

        if historical_year is not None:

            raise ValueError(
                "historical_year must not be supplied "
                "when using historical median."
            )

        return _validate_generation_value(
            assessment.median_generation_mwh,
            "Median",
        )

    # --------------------------------------------------------
    # Specific historical year
    # --------------------------------------------------------

    if (
        basis
        is GenerationBasis.HISTORICAL_YEAR
    ):

        if historical_year is None:

            raise ValueError(
                "historical_year must be supplied "
                "when using HISTORICAL_YEAR basis."
            )

        return _find_historical_year_generation(
            assessment=assessment,
            year=historical_year,
        )

    raise ValueError(
        f"Unsupported generation basis: {basis}"
    )


# ============================================================
# BUILD ONE LIFETIME GENERATION CASE
# ============================================================

def build_lifetime_generation_scenario(
    scenario: ProjectScenario,
    assessment: ResourceAssessment,
    basis: GenerationBasis,
    historical_year: int | None = None,
) -> LifetimeGenerationScenario:
    """
    Convert a long-term resource assessment into a
    complete lifetime generation projection.

    Mathematical model
    ------------------

        E_t =
            E_1 * (1 - d) ** (t - 1)

    where:

        E_1
            selected annual generation:
            P90, P50, P10, mean, median,
            or one historical year

        d
            project annual degradation rate

        t
            project operating year
    """

    # --------------------------------------------------------
    # Confirm assessment belongs to this project
    # --------------------------------------------------------

    _validate_assessment_match(
        scenario=scenario,
        assessment=assessment,
    )

    # --------------------------------------------------------
    # Select Year-1 generation basis
    # --------------------------------------------------------

    first_year_generation_mwh = (
        select_first_year_generation_mwh(
            assessment=assessment,
            basis=basis,
            historical_year=historical_year,
        )
    )

    # --------------------------------------------------------
    # Apply lifecycle degradation
    # --------------------------------------------------------

    generation_by_year_mwh = (
        build_lifetime_generation(
            scenario=scenario,

            first_year_generation_mwh=(
                first_year_generation_mwh
            ),
        )
    )

    # --------------------------------------------------------
    # Methodological warnings
    # --------------------------------------------------------

    warnings: list[str] = []

    if basis is GenerationBasis.P90:

        warnings.append(
            "P90 is being used as a deterministic "
            "annual resource case. This is not the "
            "same as a probabilistic P90 for total "
            "lifetime project generation or NPV."
        )

    if basis is GenerationBasis.P10:

        warnings.append(
            "P10 represents a relatively optimistic "
            "annual resource case and should not be "
            "treated as expected central performance."
        )

    if (
        basis
        is GenerationBasis.HISTORICAL_YEAR
    ):

        warnings.append(
            "Lifetime generation is based on one "
            "specific historical resource year. "
            "This does not represent long-term "
            "average conditions."
        )

    # --------------------------------------------------------
    # Return technology-independent lifetime case
    # --------------------------------------------------------

    return LifetimeGenerationScenario(

        scenario_id=(
            scenario.scenario_id
        ),

        technology=(
            scenario.technology
        ),

        basis=basis,

        first_year_generation_mwh=(
            first_year_generation_mwh
        ),

        generation_by_year_mwh=(
            generation_by_year_mwh
        ),

        annual_degradation_rate=(
            scenario.annual_degradation_rate
        ),

        source_year=(
            historical_year
            if basis
            is GenerationBasis.HISTORICAL_YEAR
            else None
        ),

        warnings=tuple(
            warnings
        ),
    )


# ============================================================
# BUILD STANDARD RISK CASES
# ============================================================

def build_standard_generation_scenarios(
    scenario: ProjectScenario,
    assessment: ResourceAssessment,
) -> dict[
    GenerationBasis,
    LifetimeGenerationScenario,
]:
    """
    Build the standard three generation-risk cases:

        P90
        P50
        P10

    These can then be sent independently into the
    financial engine.
    """

    bases = (
        GenerationBasis.P90,
        GenerationBasis.P50,
        GenerationBasis.P10,
    )

    return {
        basis: (
            build_lifetime_generation_scenario(
                scenario=scenario,
                assessment=assessment,
                basis=basis,
            )
        )
        for basis in bases
    }