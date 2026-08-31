# physics/wind.py

from __future__ import annotations

import math

from enum import Enum

from core.models import (
    GenerationResult,
    ProjectScenario,
    Technology,
    WindConfig,
)

from core.resources import (
    WindResourcePoint,
    WindResourceSeries,
)


# ============================================================
# AIR-DENSITY MODE
# ============================================================

class WindDensityMode(str, Enum):
    """
    Controls whether air-density correction is applied.

    AUTO:
        Apply density correction when every observation
        contains air-density data. Otherwise ignore it.

    APPLY:
        Require air-density data for every observation.

    IGNORE:
        Do not apply air-density correction.
    """

    AUTO = "auto"
    APPLY = "apply"
    IGNORE = "ignore"


# ============================================================
# SCENARIO VALIDATION
# ============================================================

def _validate_wind_scenario(
    scenario: ProjectScenario,
) -> WindConfig:
    """
    Ensure that the scenario represents a wind project.
    """

    if scenario.technology is not Technology.WIND:

        raise ValueError(
            "wind.py can only simulate "
            "wind project scenarios."
        )

    if not isinstance(
        scenario.technology_config,
        WindConfig,
    ):

        raise TypeError(
            "Wind project requires WindConfig."
        )

    return scenario.technology_config


# ============================================================
# LOCATION VALIDATION
# ============================================================

def _validate_resource_location(
    scenario: ProjectScenario,
    resource: WindResourceSeries,
) -> None:
    """
    Ensure that wind-resource data correspond to
    the simulated project coordinates.
    """

    latitude_matches = math.isclose(
        scenario.location.latitude,
        resource.location.latitude,
        rel_tol=0.0,
        abs_tol=1e-6,
    )

    longitude_matches = math.isclose(
        scenario.location.longitude,
        resource.location.longitude,
        rel_tol=0.0,
        abs_tol=1e-6,
    )

    if not (
        latitude_matches
        and longitude_matches
    ):

        raise ValueError(
            "Wind resource coordinates do not "
            "match project coordinates."
        )


# ============================================================
# WIND POWER DENSITY
# ============================================================

def calculate_wind_power_density_wm2(
    wind_speed_ms: float,
    air_density_kg_m3: float = 1.225,
) -> float:
    """
    Calculate kinetic power carried by wind per
    square metre of area.

    Formula:

        P/A = 0.5 * rho * v^3

    Units:

        W/m²
    """

    wind_speed_ms = float(
        wind_speed_ms
    )

    air_density_kg_m3 = float(
        air_density_kg_m3
    )

    if not math.isfinite(
        wind_speed_ms
    ):

        raise ValueError(
            "Wind speed must be finite."
        )

    if wind_speed_ms < 0:

        raise ValueError(
            "Wind speed cannot be negative."
        )

    if (
        not math.isfinite(
            air_density_kg_m3
        )
        or air_density_kg_m3 <= 0
    ):

        raise ValueError(
            "Air density must be finite "
            "and greater than zero."
        )

    return (
        0.5
        * air_density_kg_m3
        * wind_speed_ms ** 3
    )


# ============================================================
# HUB-HEIGHT WIND SPEED
# ============================================================

def calculate_hub_height_wind_speed_ms(
    measured_wind_speed_ms: float,
    measurement_height_m: float,
    hub_height_m: float,
    shear_exponent: float,
) -> float:
    """
    Adjust wind speed from measurement height
    to turbine hub height.

    Power-law wind profile:

        v_hub =
            v_ref
            * (h_hub / h_ref) ** alpha

    where:

        alpha = wind shear exponent
    """

    measured_wind_speed_ms = float(
        measured_wind_speed_ms
    )

    measurement_height_m = float(
        measurement_height_m
    )

    hub_height_m = float(
        hub_height_m
    )

    shear_exponent = float(
        shear_exponent
    )

    if not math.isfinite(
        measured_wind_speed_ms
    ):

        raise ValueError(
            "Measured wind speed must be finite."
        )

    if measured_wind_speed_ms < 0:

        raise ValueError(
            "Measured wind speed cannot be negative."
        )

    if (
        not math.isfinite(
            measurement_height_m
        )
        or measurement_height_m <= 0
    ):

        raise ValueError(
            "Measurement height must be positive."
        )

    if (
        not math.isfinite(
            hub_height_m
        )
        or hub_height_m <= 0
    ):

        raise ValueError(
            "Hub height must be positive."
        )

    if (
        not math.isfinite(
            shear_exponent
        )
        or shear_exponent < 0
    ):

        raise ValueError(
            "Wind shear exponent must be "
            "finite and non-negative."
        )

    height_ratio = (
        hub_height_m
        / measurement_height_m
    )

    return (
        measured_wind_speed_ms
        * height_ratio ** shear_exponent
    )


# ============================================================
# AIR-DENSITY MODE SELECTION
# ============================================================

def _resolve_density_mode(
    resource: WindResourceSeries,
    requested_mode: WindDensityMode,
) -> tuple[
    WindDensityMode,
    tuple[str, ...],
]:
    """
    Determine whether air-density correction
    will actually be applied.
    """

    all_have_density = all(
        point.air_density_kg_m3 is not None
        for point in resource.points
    )

    # --------------------------------------------------------
    # Explicit density correction
    # --------------------------------------------------------

    if requested_mode is WindDensityMode.APPLY:

        if not all_have_density:

            raise ValueError(
                "Air-density correction was required "
                "but air density is missing from one "
                "or more observations."
            )

        return (
            WindDensityMode.APPLY,
            (),
        )

    # --------------------------------------------------------
    # Explicitly ignore density
    # --------------------------------------------------------

    if requested_mode is WindDensityMode.IGNORE:

        return (
            WindDensityMode.IGNORE,
            (),
        )

    # --------------------------------------------------------
    # Automatic selection
    # --------------------------------------------------------

    if requested_mode is WindDensityMode.AUTO:

        if all_have_density:

            return (
                WindDensityMode.APPLY,
                (),
            )

        return (
            WindDensityMode.IGNORE,
            (
                "Air-density data were unavailable "
                "for the complete resource series, "
                "so density correction was not applied.",
            ),
        )

    raise ValueError(
        f"Unsupported density mode: {requested_mode}"
    )


# ============================================================
# DENSITY FACTOR
# ============================================================

def _calculate_density_factor(
    point: WindResourcePoint,
    config: WindConfig,
    mode: WindDensityMode,
) -> float:
    """
    Calculate approximate wind-power correction
    caused by air density.

    factor =
        rho_actual / rho_reference
    """

    if mode is WindDensityMode.IGNORE:

        return 1.0

    if mode is not WindDensityMode.APPLY:

        raise ValueError(
            "Density mode must be resolved before "
            "calculating power."
        )

    if point.air_density_kg_m3 is None:

        raise ValueError(
            "Air density is required for "
            "density correction."
        )

    factor = (
        point.air_density_kg_m3
        / config.reference_air_density_kg_m3
    )

    if not math.isfinite(
        factor
    ):

        raise ValueError(
            "Density correction factor "
            "must be finite."
        )

    if factor <= 0:

        raise ValueError(
            "Density correction factor "
            "must be positive."
        )

    return factor


# ============================================================
# SIMPLIFIED TURBINE POWER CURVE
# ============================================================

def calculate_turbine_power_mw(
    wind_speed_ms: float,
    config: WindConfig,
    density_factor: float = 1.0,
) -> float:
    """
    Calculate expected electrical output of one turbine.

    Operating regions
    -----------------

    1. Below cut-in:
        P = 0

    2. Cut-in to rated:
        cubic interpolation

    3. Rated to cut-out:
        P = rated power

    4. At/above cut-out:
        P = 0

    Availability is applied to expected output.
    """

    wind_speed_ms = float(
        wind_speed_ms
    )

    density_factor = float(
        density_factor
    )

    if not math.isfinite(
        wind_speed_ms
    ):

        raise ValueError(
            "Wind speed must be finite."
        )

    if wind_speed_ms < 0:

        raise ValueError(
            "Wind speed cannot be negative."
        )

    if (
        not math.isfinite(
            density_factor
        )
        or density_factor <= 0
    ):

        raise ValueError(
            "Density factor must be positive "
            "and finite."
        )

    cut_in = (
        config.cut_in_speed_ms
    )

    rated = (
        config.rated_speed_ms
    )

    cut_out = (
        config.cut_out_speed_ms
    )

    rated_power = (
        config.turbine_rated_power_mw
    )

    # --------------------------------------------------------
    # Region 1: below cut-in
    # --------------------------------------------------------

    if wind_speed_ms < cut_in:

        return 0.0

    # --------------------------------------------------------
    # Region 4: cut-out and above
    # --------------------------------------------------------

    if wind_speed_ms >= cut_out:

        return 0.0

    # --------------------------------------------------------
    # Region 2: partial-load region
    # --------------------------------------------------------

    if wind_speed_ms < rated:

        numerator = (
            wind_speed_ms ** 3
            - cut_in ** 3
        )

        denominator = (
            rated ** 3
            - cut_in ** 3
        )

        power_fraction = (
            numerator
            / denominator
        )

        power_mw = (
            rated_power
            * power_fraction
            * density_factor
        )

        # Turbine cannot exceed rated output.
        power_mw = min(
            rated_power,
            power_mw,
        )

    # --------------------------------------------------------
    # Region 3: rated-power region
    # --------------------------------------------------------

    else:

        power_mw = rated_power

    # --------------------------------------------------------
    # Expected availability
    # --------------------------------------------------------

    expected_power_mw = (
        power_mw
        * config.availability
    )

    return max(
        0.0,
        expected_power_mw,
    )


# ============================================================
# NUMBER OF TURBINES
# ============================================================

def calculate_turbine_count(
    project_capacity_mw: float,
    turbine_rated_power_mw: float,
) -> float:
    """
    Determine the equivalent number of turbines represented
    by the project capacity.

    A float is intentionally returned so that the mathematical
    model can represent arbitrary project capacities.

    Final engineering/site design may later enforce whole
    turbine counts.
    """

    if project_capacity_mw <= 0:

        raise ValueError(
            "Project capacity must be positive."
        )

    if turbine_rated_power_mw <= 0:

        raise ValueError(
            "Turbine rated power must be positive."
        )

    return (
        project_capacity_mw
        / turbine_rated_power_mw
    )


# ============================================================
# PROJECT POWER AT ONE WIND SPEED
# ============================================================

def calculate_project_wind_power_mw(
    wind_speed_ms: float,
    project_capacity_mw: float,
    config: WindConfig,
    density_factor: float = 1.0,
) -> float:
    """
    Calculate expected total output of the wind project
    for one hub-height wind-speed observation.
    """

    turbine_power_mw = (
        calculate_turbine_power_mw(
            wind_speed_ms=wind_speed_ms,
            config=config,
            density_factor=density_factor,
        )
    )

    turbine_count = (
        calculate_turbine_count(
            project_capacity_mw=(
                project_capacity_mw
            ),
            turbine_rated_power_mw=(
                config.turbine_rated_power_mw
            ),
        )
    )

    project_power_mw = (
        turbine_power_mw
        * turbine_count
    )

    return min(
        project_capacity_mw,
        max(
            0.0,
            project_power_mw,
        ),
    )


# ============================================================
# ONE RESOURCE OBSERVATION
# ============================================================

def _calculate_point_power_mw(
    point: WindResourcePoint,
    resource: WindResourceSeries,
    scenario: ProjectScenario,
    config: WindConfig,
    density_mode: WindDensityMode,
) -> float:
    """
    Convert one measured wind-resource observation
    into expected project electrical output.
    """

    # --------------------------------------------------------
    # Convert resource wind speed to hub height
    # --------------------------------------------------------

    hub_wind_speed_ms = (
        calculate_hub_height_wind_speed_ms(
            measured_wind_speed_ms=(
                point.wind_speed_ms
            ),

            measurement_height_m=(
                resource.measurement_height_m
            ),

            hub_height_m=(
                config.hub_height_m
            ),

            shear_exponent=(
                config.wind_shear_exponent
            ),
        )
    )

    # --------------------------------------------------------
    # Optional air-density correction
    # --------------------------------------------------------

    density_factor = (
        _calculate_density_factor(
            point=point,
            config=config,
            mode=density_mode,
        )
    )

    # --------------------------------------------------------
    # Project power
    # --------------------------------------------------------

    return calculate_project_wind_power_mw(
        wind_speed_ms=(
            hub_wind_speed_ms
        ),

        project_capacity_mw=(
            scenario.capacity_mw
        ),

        config=config,

        density_factor=(
            density_factor
        ),
    )


# ============================================================
# COMPLETE WIND SIMULATION
# ============================================================

def simulate_wind(
    scenario: ProjectScenario,
    resource: WindResourceSeries,
    density_mode: WindDensityMode = (
        WindDensityMode.AUTO
    ),
) -> GenerationResult:
    """
    Simulate wind-project electricity generation over
    an entire resource time series.

    Processing chain
    ----------------

    measured wind speed
        ?
    hub-height correction
        ?
    optional density correction
        ?
    turbine power curve
        ?
    project power
        ?
    energy integration
        ?
    capacity factor
    """

    # --------------------------------------------------------
    # Validate project
    # --------------------------------------------------------

    config = _validate_wind_scenario(
        scenario
    )

    # --------------------------------------------------------
    # Validate location
    # --------------------------------------------------------

    _validate_resource_location(
        scenario=scenario,
        resource=resource,
    )

    # --------------------------------------------------------
    # Time resolution
    # --------------------------------------------------------

    time_step_hours = (
        resource.time_step_hours
    )

    if time_step_hours is None:

        raise ValueError(
            "At least two wind-resource observations "
            "are required to determine the time step."
        )

    if (
        not math.isfinite(
            time_step_hours
        )
        or time_step_hours <= 0
    ):

        raise ValueError(
            "Wind-resource time step must be "
            "finite and positive."
        )

    # --------------------------------------------------------
    # Density mode
    # --------------------------------------------------------

    (
        resolved_density_mode,
        density_warnings,
    ) = _resolve_density_mode(
        resource=resource,
        requested_mode=density_mode,
    )

    # --------------------------------------------------------
    # Simulate each interval
    # --------------------------------------------------------

    power_by_interval_mw = tuple(
        _calculate_point_power_mw(
            point=point,
            resource=resource,
            scenario=scenario,
            config=config,
            density_mode=(
                resolved_density_mode
            ),
        )
        for point in resource.points
    )

    # --------------------------------------------------------
    # Energy integration
    #
    # E = S P_t ?t
    # --------------------------------------------------------

    total_generation_mwh = math.fsum(
        power_mw
        * time_step_hours
        for power_mw
        in power_by_interval_mw
    )

    # --------------------------------------------------------
    # Maximum possible energy
    # --------------------------------------------------------

    total_duration_hours = (
        len(
            power_by_interval_mw
        )
        * time_step_hours
    )

    maximum_possible_generation_mwh = (
        scenario.capacity_mw
        * total_duration_hours
    )

    # --------------------------------------------------------
    # Capacity factor
    # --------------------------------------------------------

    if (
        maximum_possible_generation_mwh
        > 0
    ):

        capacity_factor = (
            total_generation_mwh
            / maximum_possible_generation_mwh
        )

    else:

        capacity_factor = 0.0

    capacity_factor = min(
        1.0,
        max(
            0.0,
            capacity_factor,
        ),
    )

    # --------------------------------------------------------
    # Warnings
    # --------------------------------------------------------

    warnings = list(
        density_warnings
    )

    if not math.isclose(
        resource.measurement_height_m,
        config.hub_height_m,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):

        warnings.append(
            "Wind speed was extrapolated from "
            "the resource measurement height to "
            "the turbine hub height using the "
            "power-law wind profile."
        )

    warnings.append(
        "Wind generation currently uses a "
        "simplified cubic turbine power curve. "
        "Final engineering analysis should use "
        "a manufacturer-specific power curve."
    )

    # --------------------------------------------------------
    # Standard physics output
    # --------------------------------------------------------

    return GenerationResult(
        scenario_id=(
            scenario.scenario_id
        ),

        technology=(
            Technology.WIND
        ),

        installed_capacity_mw=(
            scenario.capacity_mw
        ),

        power_by_interval_mw=(
            power_by_interval_mw
        ),

        time_step_hours=(
            time_step_hours
        ),

        total_generation_mwh=(
            total_generation_mwh
        ),

        capacity_factor=(
            capacity_factor
        ),

        model_name=(
            "simplified_cubic_wind_power_curve_v1"
        ),

        warnings=tuple(
            warnings
        ),
    )