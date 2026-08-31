# analysis/wind_resource_analysis.py

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
    WindResourcePoint,
    WindResourceSeries,
)

from physics.wind import (
    WindDensityMode,
    simulate_wind,
)


# ============================================================
# ANNUAL WIND RESULT
# ============================================================

@dataclass(frozen=True)
class AnnualWindGeneration:
    """
    Wind-generation result for one historical year.

    generation_mwh:
        Total simulated electrical generation.

    capacity_factor:
        Actual generation divided by maximum possible
        generation during the represented period.

    observed_hours:
        Number of hours represented in the dataset.

    expected_hours:
        8760 for a normal year,
        8784 for a leap year.

    completeness_ratio:
        Fraction of the calendar year represented.
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
                "Observed hours must be positive."
            )

        if self.expected_hours <= 0:
            raise ValueError(
                "Expected hours must be positive."
            )

        if not (
            0
            <= self.completeness_ratio
            <= 1.000001
        ):
            raise ValueError(
                "Completeness ratio must "
                "be between 0 and 1."
            )


# ============================================================
# LONG-TERM WIND ASSESSMENT
# ============================================================

@dataclass(frozen=True)
class WindResourceAssessment:
    """
    Long-term wind-energy assessment for one site.

    Exceedance terminology:

        P90 = conservative generation
        P50 = central generation
        P10 = relatively optimistic generation
    """

    scenario_id: str

    years: tuple[
        AnnualWindGeneration,
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

    mean_capacity_factor: float

    warnings: tuple[str, ...] = ()

    @property
    def year_count(self) -> int:
        """
        Number of complete historical years
        included in the assessment.
        """

        return len(
            self.years
        )


# ============================================================
# EXPECTED CALENDAR HOURS
# ============================================================

def _expected_hours_in_year(
    year: int,
) -> float:
    """
    Return the number of calendar hours.

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

    probability:
        0.10 = 10th percentile
        0.50 = 50th percentile
        0.90 = 90th percentile
    """

    if not values:
        raise ValueError(
            "Cannot calculate a percentile "
            "from an empty dataset."
        )

    if not (
        0
        <= probability
        <= 1
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
# EXCEEDANCE GENERATION
# ============================================================

def calculate_exceedance_generation_mwh(
    annual_generation_mwh: tuple[float, ...],
    exceedance_probability: float,
) -> float:
    """
    Calculate generation for an exceedance probability.

    Important:

        P90 means there is approximately a 90%
        probability generation will exceed this value.

    Therefore:

        P90 = 10th percentile
        P50 = 50th percentile
        P10 = 90th percentile
    """

    if not (
        0
        <= exceedance_probability
        <= 1
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
        probability=(
            percentile_probability
        ),
    )


# ============================================================
# GROUP WIND DATA BY YEAR
# ============================================================

def _group_points_by_year(
    resource: WindResourceSeries,
) -> dict[
    int,
    tuple[WindResourcePoint, ...],
]:
    """
    Split a multi-year wind-resource dataset
    into individual calendar years.
    """

    grouped: dict[
        int,
        list[WindResourcePoint],
    ] = defaultdict(list)

    for point in resource.points:

        year = (
            point.timestamp.year
        )

        grouped[
            year
        ].append(
            point
        )

    return {
        year: tuple(points)
        for year, points
        in grouped.items()
    }


# ============================================================
# CREATE ONE-YEAR RESOURCE SERIES
# ============================================================

def _build_annual_resource_series(
    original_resource: WindResourceSeries,
    points: tuple[
        WindResourcePoint,
        ...
    ],
) -> WindResourceSeries:
    """
    Build a WindResourceSeries representing
    one calendar year.

    Location, metadata, and measurement height
    are preserved.
    """

    return WindResourceSeries(

        location=(
            original_resource.location
        ),

        metadata=(
            original_resource.metadata
        ),

        measurement_height_m=(
            original_resource.measurement_height_m
        ),

        points=points,
    )


# ============================================================
# SIMULATE ONE HISTORICAL YEAR
# ============================================================

def _simulate_year(
    scenario: ProjectScenario,
    original_resource: WindResourceSeries,
    year: int,
    points: tuple[
        WindResourcePoint,
        ...
    ],
    density_mode: WindDensityMode,
) -> AnnualWindGeneration:
    """
    Run the wind-physics model for one
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
            f"Year {year} does not contain "
            "enough wind observations."
        )

    result = simulate_wind(
        scenario=scenario,
        resource=annual_resource,
        density_mode=density_mode,
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

    completeness_ratio = min(
        1.0,
        completeness_ratio,
    )

    return AnnualWindGeneration(

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
# LONG-TERM WIND ASSESSMENT
# ============================================================

def assess_long_term_wind_resource(
    scenario: ProjectScenario,
    resource: WindResourceSeries,

    minimum_year_completeness: float = 0.99,

    density_mode: WindDensityMode = (
        WindDensityMode.AUTO
    ),
) -> WindResourceAssessment:
    """
    Perform a multi-year wind-resource assessment.

    Processing
    ----------
    1. Separate hourly data by calendar year.
    2. Simulate turbine/farm generation for each year.
    3. Exclude substantially incomplete years.
    4. Build the annual-generation distribution.
    5. Calculate P10, P50, and P90.
    6. Measure interannual variability.
    7. Identify best and worst historical years.
    """

    # --------------------------------------------------------
    # Validate technology
    # --------------------------------------------------------

    if (
        scenario.technology
        is not Technology.WIND
    ):

        raise ValueError(
            "Long-term wind assessment requires "
            "a wind project scenario."
        )

    # --------------------------------------------------------
    # Validate completeness threshold
    # --------------------------------------------------------

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
    # Divide historical data into calendar years
    # --------------------------------------------------------

    grouped_years = (
        _group_points_by_year(
            resource
        )
    )

    if not grouped_years:

        raise ValueError(
            "Wind resource contains no data."
        )

    accepted_years: list[
        AnnualWindGeneration
    ] = []

    excluded_years: list[int] = []

    warnings: list[str] = []

    # --------------------------------------------------------
    # Simulate every historical year
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

                density_mode=(
                    density_mode
                ),
            )
        )

        # ----------------------------------------------------
        # Reject incomplete years
        # ----------------------------------------------------

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
    # Ensure some usable years remain
    # --------------------------------------------------------

    if not accepted_years:

        raise ValueError(
            "No historical wind years met the "
            "minimum completeness requirement."
        )

    # --------------------------------------------------------
    # Annual generation distribution
    # --------------------------------------------------------

    generation_values = tuple(
        annual.generation_mwh
        for annual in accepted_years
    )

    capacity_factors = tuple(
        annual.capacity_factor
        for annual in accepted_years
    )

    # --------------------------------------------------------
    # Mean
    # --------------------------------------------------------

    mean_generation = (
        statistics.fmean(
            generation_values
        )
    )

    # --------------------------------------------------------
    # Median
    # --------------------------------------------------------

    median_generation = (
        statistics.median(
            generation_values
        )
    )

    # --------------------------------------------------------
    # P90
    #
    # Conservative case
    # --------------------------------------------------------

    p90 = (
        calculate_exceedance_generation_mwh(
            annual_generation_mwh=(
                generation_values
            ),
            exceedance_probability=0.90,
        )
    )

    # --------------------------------------------------------
    # P50
    #
    # Central case
    # --------------------------------------------------------

    p50 = (
        calculate_exceedance_generation_mwh(
            annual_generation_mwh=(
                generation_values
            ),
            exceedance_probability=0.50,
        )
    )

    # --------------------------------------------------------
    # P10
    #
    # Relatively optimistic case
    # --------------------------------------------------------

    p10 = (
        calculate_exceedance_generation_mwh(
            annual_generation_mwh=(
                generation_values
            ),
            exceedance_probability=0.10,
        )
    )

    # --------------------------------------------------------
    # Standard deviation
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

    # --------------------------------------------------------
    # Coefficient of variation
    #
    # CV = standard deviation / mean
    # --------------------------------------------------------

    if mean_generation > 0:

        coefficient_of_variation = (
            standard_deviation
            / mean_generation
        )

    else:

        coefficient_of_variation = 0.0

    # --------------------------------------------------------
    # Mean capacity factor
    # --------------------------------------------------------

    mean_capacity_factor = (
        statistics.fmean(
            capacity_factors
        )
    )

    # --------------------------------------------------------
    # Best and worst years
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
    # Warnings
    # --------------------------------------------------------

    if excluded_years:

        warnings.append(
            "One or more calendar years were "
            "excluded because their wind-resource "
            "data were incomplete."
        )

    if len(
        accepted_years
    ) < 10:

        warnings.append(
            "Fewer than 10 complete historical "
            "years were available. Long-term "
            "P10/P50/P90 estimates may be unstable."
        )

    if len(
        accepted_years
    ) == 1:

        warnings.append(
            "Only one complete historical year "
            "was available. Interannual wind "
            "variability cannot be estimated "
            "meaningfully."
        )

    # --------------------------------------------------------
    # Final assessment
    # --------------------------------------------------------

    return WindResourceAssessment(

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

        mean_capacity_factor=(
            mean_capacity_factor
        ),

        warnings=tuple(
            dict.fromkeys(warnings)
        ),
    )
