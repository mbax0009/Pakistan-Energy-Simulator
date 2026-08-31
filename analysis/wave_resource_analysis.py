# analysis/wave_resource_analysis.py

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
    WaveResourcePoint,
    WaveResourceSeries,
)

from physics.wave import (
    simulate_wave,
)


# ============================================================
# ANNUAL WAVE RESULT
# ============================================================

@dataclass(frozen=True)
class AnnualWaveGeneration:
    """
    Wave-generation result for one historical year.

    year:
        Calendar year.

    generation_mwh:
        Total simulated electrical generation.

    capacity_factor:
        Actual electrical generation divided by the
        maximum possible generation for the represented
        time period.

    observed_hours:
        Number of hours represented by the marine data.

    expected_hours:
        8760 hours for a normal year.
        8784 hours for a leap year.

    completeness_ratio:
        Fraction of the expected calendar year represented
        by the resource dataset.
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

        if not math.isfinite(
            self.observed_hours
        ):
            raise ValueError(
                "Observed hours must be finite."
            )

        if self.observed_hours <= 0:
            raise ValueError(
                "Observed hours must be positive."
            )

        if not math.isfinite(
            self.expected_hours
        ):
            raise ValueError(
                "Expected hours must be finite."
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
                "Completeness ratio must be "
                "between 0 and 1."
            )


# ============================================================
# LONG-TERM WAVE ASSESSMENT
# ============================================================

@dataclass(frozen=True)
class WaveResourceAssessment:
    """
    Long-term wave-energy assessment for one site.

    Exceedance interpretation:

        P90 = conservative generation
        P50 = central generation
        P10 = relatively optimistic generation
    """

    scenario_id: str

    years: tuple[
        AnnualWaveGeneration,
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

    water_depth_m: float | None

    warnings: tuple[str, ...] = ()

    @property
    def year_count(self) -> int:
        """
        Number of complete historical years included
        in the long-term analysis.
        """

        return len(
            self.years
        )


# ============================================================
# EXPECTED HOURS
# ============================================================

def _expected_hours_in_year(
    year: int,
) -> float:
    """
    Calculate expected calendar hours.

    Normal year:
        365 * 24 = 8760

    Leap year:
        366 * 24 = 8784
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

    probability examples:

        0.10 -> 10th percentile
        0.50 -> median
        0.90 -> 90th percentile
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
            "Probability must be between 0 and 1."
        )

    ordered = sorted(
        float(value)
        for value in values
    )

    for value in ordered:

        if not math.isfinite(
            value
        ):
            raise ValueError(
                "Percentile values must be finite."
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

    lower_value = (
        ordered[
            lower_index
        ]
    )

    upper_value = (
        ordered[
            upper_index
        ]
    )

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
    Calculate annual generation corresponding to an
    exceedance probability.

    Examples
    --------

    P90:
        90% probability that annual generation
        exceeds this value.

        Therefore P90 corresponds to approximately
        the 10th percentile.

    P50:
        50th percentile.

    P10:
        90th percentile.
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
# GROUP RESOURCE POINTS BY YEAR
# ============================================================

def _group_points_by_year(
    resource: WaveResourceSeries,
) -> dict[
    int,
    tuple[WaveResourcePoint, ...],
]:
    """
    Split a multi-year marine dataset into
    individual calendar years.
    """

    grouped: dict[
        int,
        list[WaveResourcePoint],
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
    original_resource: WaveResourceSeries,
    points: tuple[
        WaveResourcePoint,
        ...
    ],
) -> WaveResourceSeries:
    """
    Construct a WaveResourceSeries representing one
    historical calendar year.

    The original:
        location
        metadata
        water depth

    are preserved.
    """

    return WaveResourceSeries(

        location=(
            original_resource.location
        ),

        metadata=(
            original_resource.metadata
        ),

        points=points,

        water_depth_m=(
            original_resource.water_depth_m
        ),
    )


# ============================================================
# SIMULATE ONE YEAR
# ============================================================

def _simulate_year(
    scenario: ProjectScenario,
    original_resource: WaveResourceSeries,
    year: int,
    points: tuple[
        WaveResourcePoint,
        ...
    ],
) -> AnnualWaveGeneration:
    """
    Run the wave-energy physics model for one
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
            "enough wave observations."
        )

    if (
        not math.isfinite(
            time_step_hours
        )
        or time_step_hours <= 0
    ):

        raise ValueError(
            f"Year {year} has an invalid "
            "wave-resource time step."
        )

    # --------------------------------------------------------
    # Run physical WEC model
    # --------------------------------------------------------

    result = simulate_wave(
        scenario=scenario,
        resource=annual_resource,
    )

    # --------------------------------------------------------
    # Determine represented time
    #
    # For WAVERYS:
    #
    # approximately:
    #
    # number of observations * 3 hours
    # --------------------------------------------------------

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

    # Protect against tiny floating-point overshoot.
    completeness_ratio = min(
        1.0,
        completeness_ratio,
    )

    return AnnualWaveGeneration(

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

def assess_long_term_wave_resource(
    scenario: ProjectScenario,
    resource: WaveResourceSeries,
    minimum_year_completeness: float = 0.99,
) -> WaveResourceAssessment:
    """
    Perform a multi-year wave-resource assessment.

    Processing
    ----------
    1. Divide marine data into calendar years.
    2. Simulate WEC generation for each year.
    3. Exclude substantially incomplete years.
    4. Construct annual-generation distribution.
    5. Calculate P10/P50/P90.
    6. Calculate interannual variability.
    7. Identify best and worst years.
    """

    # --------------------------------------------------------
    # Validate project technology
    # --------------------------------------------------------

    if (
        scenario.technology
        is not Technology.WAVE
    ):

        raise ValueError(
            "Long-term wave assessment requires "
            "a wave-energy project scenario."
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
    # Divide resource data by calendar year
    # --------------------------------------------------------

    grouped_years = (
        _group_points_by_year(
            resource
        )
    )

    if not grouped_years:

        raise ValueError(
            "Wave resource contains no data."
        )

    accepted_years: list[
        AnnualWaveGeneration
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
            )
        )

        # ----------------------------------------------------
        # Reject substantially incomplete years
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
    # Ensure usable data remain
    # --------------------------------------------------------

    if not accepted_years:

        raise ValueError(
            "No historical wave years met "
            "the minimum completeness requirement."
        )

    # --------------------------------------------------------
    # Annual generation distribution
    # --------------------------------------------------------

    generation_values = tuple(

        annual.generation_mwh

        for annual
        in accepted_years
    )

    capacity_factors = tuple(

        annual.capacity_factor

        for annual
        in accepted_years
    )

    # --------------------------------------------------------
    # Historical mean
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
    # Conservative generation case
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
    # Central generation case
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
    # Relatively optimistic generation case
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
    # Interannual standard deviation
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
    # CV = s / mean
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
    # Best and worst historical years
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
    # Assessment warnings
    # --------------------------------------------------------

    if excluded_years:

        warnings.append(
            "One or more calendar years were "
            "excluded because their wave-resource "
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
            "was available. Interannual wave "
            "variability cannot be estimated "
            "meaningfully."
        )

    if (
        resource.water_depth_m
        is None
    ):

        warnings.append(
            "Water depth is unavailable. The "
            "deep-water assumption used by the "
            "wave-physics model cannot yet be "
            "checked at this site."
        )

    # --------------------------------------------------------
    # Return complete assessment
    # --------------------------------------------------------

    return WaveResourceAssessment(

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

        water_depth_m=(
            resource.water_depth_m
        ),

        warnings=tuple(
            dict.fromkeys(warnings)
        ),
    )
