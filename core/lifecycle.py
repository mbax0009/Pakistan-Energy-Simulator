from __future__ import annotations

import math

from collections.abc import Mapping, Sequence

from core.models import ProjectScenario


def _validate_generation_mwh(
    generation_mwh: float,
) -> float:
    """
    Validate an electricity-generation value.

    Generation must be:
    - numeric
    - finite
    - zero or positive
    """

    generation_mwh = float(generation_mwh)

    if not math.isfinite(generation_mwh):
        raise ValueError(
            "Generation must be a finite number."
        )

    if generation_mwh < 0:
        raise ValueError(
            "Generation cannot be negative."
        )

    return generation_mwh


def build_degradation_schedule(
    lifetime_years: int,
    annual_degradation_rate: float,
) -> tuple[float, ...]:
    """
    Build the dimensionless yearly degradation factors.

    factor_t = (1 - d) ** (t - 1)

    Year 1 is always 1.0 and is therefore not degraded.
    """

    if lifetime_years <= 0:
        raise ValueError(
            "Lifetime must be greater than zero."
        )

    if not (
        0 <= annual_degradation_rate < 1
    ):
        raise ValueError(
            "Annual degradation rate must be "
            "between 0 and 1."
        )


    return tuple(
        (1 - annual_degradation_rate) ** year_index
        for year_index in range(lifetime_years)
    )


def apply_yearly_performance_multipliers(
    generation_by_year_mwh: Sequence[float],
    performance_multipliers_by_year: Mapping[int, float] | None,
) -> tuple[float, ...]:
    """
    Apply explicit year-specific performance adjustments.

    Example:
        {10: 0.95}

    means Year 10 generation is multiplied by 0.95.
    """

    generation = tuple(
        _validate_generation_mwh(value)
        for value in generation_by_year_mwh
    )


    if performance_multipliers_by_year is None:
        return generation


    adjusted = list(generation)


    for year, multiplier in (
        performance_multipliers_by_year.items()
    ):

        if not isinstance(year, int):
            raise TypeError(
                "Performance-adjustment year "
                "must be an integer."
            )

        if not 1 <= year <= len(adjusted):
            raise ValueError(
                f"Performance-adjustment year must "
                f"be between 1 and {len(adjusted)}."
            )


        multiplier = float(multiplier)


        if not math.isfinite(multiplier):
            raise ValueError(
                "Performance multiplier must be finite."
            )


        if multiplier < 0:
            raise ValueError(
                "Performance multiplier cannot "
                "be negative."
            )


        adjusted[year - 1] *= multiplier


    return tuple(adjusted)


def build_lifetime_generation(
    scenario: ProjectScenario,
    first_year_generation_mwh: float,
    performance_multipliers_by_year: (
        Mapping[int, float] | None
    ) = None,
) -> tuple[float, ...]:
    """
    Build the complete lifetime generation schedule.

    First:
        apply annual degradation.

    Then:
        apply optional year-specific adjustments.
    """

    degradation_factors = (
        build_degradation_schedule(
            lifetime_years=(
                scenario.lifetime_years
            ),
            annual_degradation_rate=(
                scenario.annual_degradation_rate
            ),
        )
    )

    degradation_schedule = tuple(
        first_year_generation_mwh * factor
        for factor in degradation_factors
    )


    return apply_yearly_performance_multipliers(
        generation_by_year_mwh=(
            degradation_schedule
        ),
        performance_multipliers_by_year=(
            performance_multipliers_by_year
        ),
    )


def calculate_lifetime_generation_loss_mwh(
    scenario: ProjectScenario,
    first_year_generation_mwh: float,
) -> float:
    """
    Calculate total generation lost compared with
    a hypothetical zero-degradation project.
    """

    first_year_generation_mwh = (
        _validate_generation_mwh(
            first_year_generation_mwh
        )
    )


    generation = build_lifetime_generation(
        scenario=scenario,
        first_year_generation_mwh=(
            first_year_generation_mwh
        ),
    )


    no_degradation_generation = (
        first_year_generation_mwh
        * len(generation)
    )


    actual_lifetime_generation = math.fsum(
        generation
    )


    return (
        no_degradation_generation
        - actual_lifetime_generation
    )
