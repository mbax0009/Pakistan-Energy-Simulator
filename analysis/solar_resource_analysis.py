# analysis/solar_resource_analysis.py

from __future__ import annotations

import calendar
import math
import statistics

from collections import defaultdict
from dataclasses import dataclass

from core.models import (
    ProjectScenario,
    Technology,
)

from core.resources import (
    SolarResourcePoint,
    SolarResourceSeries,
)

from physics.solar import (
    SolarIrradianceMode,
    SolarTemperatureMode,
    simulate_solar,
)


# ============================================================
# ANNUAL RESULT
# ============================================================

@dataclass(frozen=True)
class AnnualSolarGeneration:
    """
    Solar-generation result for one historical year.

    Attributes
    ----------
    year:
        Calendar year represented.

    generation_mwh:
        Simulated electrical generation during that year.

    capacity_factor:
        Capacity factor for that year's available data.

    observed_hours:
        Number of hours represented by the resource data.

    expected_hours:
        Number of hours expected in the complete year.

        Normally:
            8760 hours

        Leap year:
            8784 hours

    completeness_ratio:
        observed_hours / expected_hours
    """

    year: int

    generation_mwh: float
    capacity_factor: float

    observed_hours: float
    expected_hours: float

    completeness_ratio: float

    warnings: tuple[str, ...] = ()

    def __post_init__(self):

        if self.year <= 0:
            raise ValueError(
                "Year must be positive."
            )

        if not math.isfinite(
            self.generation_mwh
        ):
            raise ValueError(
                "Annual generation must be finite."
            )

        if self.generation_mwh < 0:
            raise ValueError(
                "Annual generation cannot be negative."
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

        if self.observed_hours <= 0:
            raise ValueError(
                "Observed hours must be "
                "greater than zero."
            )

        if self.expected_hours <= 0:
            raise ValueError(
                "Expected hours must be "
                "greater than zero."
            )

        if not (
            0
            <= self.completeness_ratio
            <= 1.000001
        ):
            raise ValueError(
                "Completeness ratio must be "
                "between 0 and 1."
            )


# ============================================================
# LONG-TERM ASSESSMENT RESULT
# ============================================================

@dataclass(frozen=True)
class SolarResourceAssessment:
    """
    Long-term solar-generation assessment for one site.

    P-values use exceedance-probability terminology:

        P90 = conservative
        P50 = median
        P10 = relatively optimistic
    """

    scenario_id: str

    years: tuple[
        AnnualSolarGeneration,
        ...
    ]

    excluded_years: tuple[int, ...]

    mean_generation_mwh: float
    median_generation_mwh: float

    p10_generation_mwh: float
    p50_generation_mwh: float
    p90_generation_mwh: float

    standard_deviation_mwh: float

    coefficient_of_variation: float

    minimum_generation_mwh: float
    maximum_generation_mwh: float

    worst_year: int
    best_year: int

    warnings: tuple[str, ...] = ()

    @property
    def year_count(self) -> int:
        """
        Number of historical years included.
        """

        return len(
            self.years
        )


# ============================================================
# YEAR LENGTH
# ============================================================

def _expected_hours_in_year(
    year: int,
) -> float:
    """
    Return calendar hours in a year.

    Normal year:
        365 × 24 = 8760

    Leap year:
        366 × 24 = 8784
    """

    days = (
        366
        if calendar.isleap(year)
        else 365
    )

    return float(
        days * 24
    )


# ============================================================
# EMPIRICAL PERCENTILE
# ============================================================

def _percentile(
    values: tuple[float, ...],
    probability: float,
) -> float:
    """
    Calculate an empirical percentile using
    linear interpolation.

    probability is expressed from 0 to 1.

    Examples
    --------
    0.10 -> 10th percentile
    0.50 -> median
    0.90 -> 90th percentile
    """

    if not values:
        raise ValueError(
            "Cannot calculate percentile "
            "of an empty dataset."
        )

    if not (
        0 <= probability <= 1
    ):
        raise ValueError(
            "Probability must be between "
            "0 and 1."
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

    lower_value = ordered[
        lower_index
    ]

    upper_value = ordered[
        upper_index
    ]

    return (
        lower_value
        + fraction
        * (
            upper_value
            - lower_value
        )
    )


# ============================================================
# EXCEEDANCE PROBABILITY
# ============================================================

def calculate_exceedance_generation_mwh(
    annual_generation_mwh: tuple[float, ...],
    exceedance_probability: float,
) -> float:
    """
    Calculate generation corresponding to an
    exceedance probability.

    Examples
    --------
    P90 means:

        90% probability that annual generation
        will exceed this value.

    Therefore:

        P90 = 10th percentile

    Similarly:

        P50 = 50th percentile
        P10 = 90th percentile
    """

    if not (
        0 <= exceedance_probability <= 1
    ):
        raise ValueError(
            "Exceedance probability must "
            "be between 0 and 1."
        )

    percentile_probability = (
        1.0
        - exceedance_probability
    )

    return _percentile(
        values=annual_generation_mwh,
        probability=percentile_probability,
    )


# ============================================================
# GROUP RESOURCE DATA BY YEAR
# ============================================================

def _group_points_by_year(
    resource: SolarResourceSeries,
) -> dict[
    int,
    tuple[SolarResourcePoint, ...],
]:
    """
    Split a multi-year solar-resource dataset
    into individual calendar years.
    """

    grouped: dict[
        int,
        list[SolarResourcePoint],
    ] = defaultdict(list)

    for point in resource.points:

        year = (
            point.timestamp.year
        )

        grouped[year].append(
            point
        )

    return {
        year: tuple(points)
        for year, points in grouped.items()
    }


# ============================================================
# CREATE ANNUAL RESOURCE SERIES
# ============================================================

def _build_annual_resource_series(
    original_resource: SolarResourceSeries,
    points: tuple[
        SolarResourcePoint,
        ...
    ],
) -> SolarResourceSeries:
    """
    Create a SolarResourceSeries representing
    one calendar year.

    Provider metadata and location are preserved.
    """

    return SolarResourceSeries(
        location=(
            original_resource.location
        ),

        metadata=(
            original_resource.metadata
        ),

        points=points,
    )


# ============================================================
# SIMULATE ONE HISTORICAL YEAR
# ============================================================

def _simulate_year(
    scenario: ProjectScenario,
    original_resource: SolarResourceSeries,
    year: int,
    points: tuple[
        SolarResourcePoint,
        ...
    ],
    irradiance_mode: SolarIrradianceMode,
    temperature_mode: SolarTemperatureMode,
) -> AnnualSolarGeneration:
    """
    Run the solar physics model for one
    historical calendar year.
    """

    annual_resource = (
        _build_annual_resource_series(
            original_resource=(
                original_resource
            ),
            points=points,
        )
    )

    time_step_hours = (
        annual_resource.time_step_hours
    )

    if time_step_hours is None:
        raise ValueError(
            f"Year {year} does not contain enough "
            "resource observations."
        )

    result = simulate_solar(
        scenario=scenario,
        resource=annual_resource,
        irradiance_mode=(
            irradiance_mode
        ),
        temperature_mode=(
            temperature_mode
        ),
    )

    observed_hours = (
        len(points)
        * time_step_hours
    )

    expected_hours = (
        _expected_hours_in_year(
            year
        )
    )

    completeness_ratio = (
        observed_hours
        / expected_hours
    )

    # Protect against tiny floating-point
    # overshoots such as 1.00000000002.
    completeness_ratio = min(
        1.0,
        completeness_ratio,
    )

    return AnnualSolarGeneration(
        year=year,

        generation_mwh=(
            result.total_generation_mwh
        ),

        capacity_factor=(
            result.capacity_factor
        ),

        warnings=result.warnings,

        observed_hours=(
            observed_hours
        ),

        expected_hours=(
            expected_hours
        ),

        completeness_ratio=(
            completeness_ratio
        ),
    )


# ============================================================
# MAIN LONG-TERM ASSESSMENT
# ============================================================

def assess_long_term_solar_resource(
    scenario: ProjectScenario,
    resource: SolarResourceSeries,
    minimum_year_completeness: float = 0.99,
    irradiance_mode: SolarIrradianceMode = (
        SolarIrradianceMode.AUTO
    ),
    temperature_mode: SolarTemperatureMode = (
        SolarTemperatureMode.AUTO
    ),
) -> SolarResourceAssessment:
    """
    Perform a multi-year solar-resource assessment.

    Steps
    -----
    1. Split hourly resource data by year.
    2. Simulate each year independently.
    3. Reject substantially incomplete years.
    4. Calculate interannual statistics.
    5. Calculate empirical P10/P50/P90 values.

    Parameters
    ----------
    minimum_year_completeness:

        Fraction of calendar-year hours required
        before a year is accepted.

        Default:
            0.99 = 99%

    Returns
    -------
    SolarResourceAssessment
    """

    # --------------------------------------------------------
    # Validate technology
    # --------------------------------------------------------

    if (
        scenario.technology
        is not Technology.SOLAR
    ):
        raise ValueError(
            "Long-term solar assessment requires "
            "a solar project scenario."
        )

    if not (
        0
        < minimum_year_completeness
        <= 1
    ):
        raise ValueError(
            "minimum_year_completeness must "
            "be between 0 and 1."
        )

    # --------------------------------------------------------
    # Split resource data
    # --------------------------------------------------------

    grouped_years = (
        _group_points_by_year(
            resource
        )
    )

    if not grouped_years:
        raise ValueError(
            "Solar resource contains no data."
        )

    accepted_years: list[
        AnnualSolarGeneration
    ] = []

    excluded_years: list[int] = []

    warnings: list[str] = []

    # --------------------------------------------------------
    # Simulate each year
    # --------------------------------------------------------

    for year in sorted(
        grouped_years
    ):

        annual_result = (
            _simulate_year(
                scenario=scenario,

                original_resource=(
                    resource
                ),

                year=year,

                points=(
                    grouped_years[
                        year
                    ]
                ),

                irradiance_mode=(
                    irradiance_mode
                ),

                temperature_mode=(
                    temperature_mode
                ),
            )
        )

        if (
            annual_result.completeness_ratio
            < minimum_year_completeness
        ):

            excluded_years.append(
                year
            )

            continue

        accepted_years.append(
            annual_result
        )

        warnings.extend(
            annual_result.warnings
        )

    # --------------------------------------------------------
    # Ensure usable data remain
    # --------------------------------------------------------

    if not accepted_years:

        raise ValueError(
            "No historical years met the "
            "minimum completeness requirement."
        )

    # --------------------------------------------------------
    # Extract annual-generation distribution
    # --------------------------------------------------------

    generation_values = tuple(
        year.generation_mwh
        for year in accepted_years
    )

    # --------------------------------------------------------
    # Central tendency
    # --------------------------------------------------------

    mean_generation = (
        statistics.fmean(
            generation_values
        )
    )

    median_generation = (
        statistics.median(
            generation_values
        )
    )

    # --------------------------------------------------------
    # Exceedance probabilities
    # --------------------------------------------------------

    p90 = (
        calculate_exceedance_generation_mwh(
            annual_generation_mwh=(
                generation_values
            ),
            exceedance_probability=0.90,
        )
    )

    p50 = (
        calculate_exceedance_generation_mwh(
            annual_generation_mwh=(
                generation_values
            ),
            exceedance_probability=0.50,
        )
    )

    p10 = (
        calculate_exceedance_generation_mwh(
            annual_generation_mwh=(
                generation_values
            ),
            exceedance_probability=0.10,
        )
    )

    # --------------------------------------------------------
    # Variability
    # --------------------------------------------------------

    if len(
        generation_values
    ) > 1:

        standard_deviation = (
            statistics.stdev(
                generation_values
            )
        )

    else:

        standard_deviation = 0.0

    if mean_generation > 0:

        coefficient_of_variation = (
            standard_deviation
            / mean_generation
        )

    else:

        coefficient_of_variation = 0.0

    # --------------------------------------------------------
    # Best / worst year
    # --------------------------------------------------------

    worst = min(
        accepted_years,
        key=lambda item: (
            item.generation_mwh
        ),
    )

    best = max(
        accepted_years,
        key=lambda item: (
            item.generation_mwh
        ),
    )

    # --------------------------------------------------------
    # Methodological warnings
    # --------------------------------------------------------

    if excluded_years:

        warnings.append(
            "One or more calendar years were "
            "excluded because their resource "
            "data were incomplete."
        )

    if len(
        accepted_years
    ) < 10:

        warnings.append(
            "Fewer than 10 complete historical "
            "years were available. P10/P50/P90 "
            "estimates may be unstable."
        )

    if len(
        accepted_years
    ) == 1:

        warnings.append(
            "Only one complete historical year "
            "was available. Interannual "
            "variability cannot be estimated "
            "meaningfully."
        )

    # --------------------------------------------------------
    # Return complete assessment
    # --------------------------------------------------------

    return SolarResourceAssessment(
        scenario_id=(
            scenario.scenario_id
        ),

        years=tuple(
            accepted_years
        ),

        excluded_years=tuple(
            excluded_years
        ),

        mean_generation_mwh=(
            mean_generation
        ),

        median_generation_mwh=(
            median_generation
        ),

        p10_generation_mwh=(
            p10
        ),

        p50_generation_mwh=(
            p50
        ),

        p90_generation_mwh=(
            p90
        ),

        standard_deviation_mwh=(
            standard_deviation
        ),

        coefficient_of_variation=(
            coefficient_of_variation
        ),

        minimum_generation_mwh=(
            worst.generation_mwh
        ),

        maximum_generation_mwh=(
            best.generation_mwh
        ),

        worst_year=(
            worst.year
        ),

        best_year=(
            best.year
        ),

        warnings=tuple(
            dict.fromkeys(warnings)
        ),
    )
