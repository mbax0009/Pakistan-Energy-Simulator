# physics/wave.py

from __future__ import annotations

import math

from core.constants import (
    GRAVITY_MS2,
    SEAWATER_DENSITY_KG_M3,
)

from core.models import (
    GenerationResult,
    ProjectScenario,
    Technology,
    WaveConfig,
)

from core.resources import (
    WaveResourcePoint,
    WaveResourceSeries,
)


# ============================================================
# SCENARIO VALIDATION
# ============================================================

def _validate_wave_scenario(
    scenario: ProjectScenario,
) -> WaveConfig:
    """
    Ensure that the supplied project scenario
    represents a wave-energy project.

    Returns
    -------
    WaveConfig
        Wave-specific project configuration.
    """

    if scenario.technology is not Technology.WAVE:

        raise ValueError(
            "wave.py can only simulate "
            "wave-energy project scenarios."
        )

    if not isinstance(
        scenario.technology_config,
        WaveConfig,
    ):

        raise TypeError(
            "Wave project requires WaveConfig."
        )

    return scenario.technology_config


# ============================================================
# LOCATION VALIDATION
# ============================================================

def _validate_resource_location(
    scenario: ProjectScenario,
    resource: WaveResourceSeries,
) -> None:
    """
    Ensure that the wave-resource data correspond
    to the simulated project coordinates.
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
            "Wave-resource coordinates do not "
            "match project coordinates."
        )


# ============================================================
# DEEP-WATER WAVE POWER FLUX
# ============================================================

def calculate_wave_power_flux_kw_per_m(
    significant_wave_height_m: float,
    energy_period_s: float,
    seawater_density_kg_m3: float = (
        SEAWATER_DENSITY_KG_M3
    ),
    gravity_ms2: float = GRAVITY_MS2,
) -> float:
    """
    Calculate deep-water wave-energy flux per metre
    of wave crest.

    Formula
    -------

        J =
            rho * g²
            --------
             64*pi

            * Hs²
            * Te

    where:

        J   = wave power flux
        rho = seawater density
        g   = gravitational acceleration
        Hs  = significant wave height
        Te  = wave energy period

    Formula initially produces W/m.

    The returned value is converted to kW/m.

    Important
    ---------
    This equation assumes deep-water wave conditions.
    """

    significant_wave_height_m = float(
        significant_wave_height_m
    )

    energy_period_s = float(
        energy_period_s
    )

    seawater_density_kg_m3 = float(
        seawater_density_kg_m3
    )

    gravity_ms2 = float(
        gravity_ms2
    )

    # --------------------------------------------------------
    # Validate wave height
    # --------------------------------------------------------

    if not math.isfinite(
        significant_wave_height_m
    ):

        raise ValueError(
            "Significant wave height must be finite."
        )

    if significant_wave_height_m < 0:

        raise ValueError(
            "Significant wave height cannot "
            "be negative."
        )

    # --------------------------------------------------------
    # Validate wave period
    # --------------------------------------------------------

    if not math.isfinite(
        energy_period_s
    ):

        raise ValueError(
            "Wave energy period must be finite."
        )

    if energy_period_s <= 0:

        raise ValueError(
            "Wave energy period must be "
            "greater than zero."
        )

    # --------------------------------------------------------
    # Validate seawater density
    # --------------------------------------------------------

    if (
        not math.isfinite(
            seawater_density_kg_m3
        )
        or seawater_density_kg_m3 <= 0
    ):

        raise ValueError(
            "Seawater density must be "
            "finite and positive."
        )

    # --------------------------------------------------------
    # Validate gravity
    # --------------------------------------------------------

    if (
        not math.isfinite(
            gravity_ms2
        )
        or gravity_ms2 <= 0
    ):

        raise ValueError(
            "Gravity must be finite "
            "and positive."
        )

    # --------------------------------------------------------
    # Deep-water wave-power flux
    #
    # Units:
    #
    # kg/m³ × (m/s²)² × m² × s
    #
    # gives:
    #
    # W/m
    # --------------------------------------------------------

    power_flux_w_per_m = (
        (
            seawater_density_kg_m3
            * gravity_ms2 ** 2
        )
        / (
            64.0
            * math.pi
        )
        * significant_wave_height_m ** 2
        * energy_period_s
    )

    # --------------------------------------------------------
    # Convert W/m → kW/m
    # --------------------------------------------------------

    return (
        power_flux_w_per_m
        / 1000.0
    )


# ============================================================
# DEVICE CAPTURED WAVE POWER
# ============================================================

def calculate_captured_wave_power_kw(
    wave_power_flux_kw_per_m: float,
    capture_width_m: float,
) -> float:
    """
    Calculate mechanical wave power captured
    by one device.

    Formula:

        P_capture =
            wave power flux
            * capture width

    Units:

        kW/m × m = kW
    """

    wave_power_flux_kw_per_m = float(
        wave_power_flux_kw_per_m
    )

    capture_width_m = float(
        capture_width_m
    )

    if (
        not math.isfinite(
            wave_power_flux_kw_per_m
        )
        or wave_power_flux_kw_per_m < 0
    ):

        raise ValueError(
            "Wave-power flux must be finite "
            "and non-negative."
        )

    if (
        not math.isfinite(
            capture_width_m
        )
        or capture_width_m <= 0
    ):

        raise ValueError(
            "Capture width must be finite "
            "and greater than zero."
        )

    return (
        wave_power_flux_kw_per_m
        * capture_width_m
    )


# ============================================================
# ELECTRICAL POWER FROM ONE WAVE DEVICE
# ============================================================

def calculate_wave_device_power_mw(
    wave_power_flux_kw_per_m: float,
    config: WaveConfig,
) -> float:
    """
    Calculate expected electrical output of one
    wave-energy converter.

    Processing
    ----------
    wave power flux
        ↓
    effective capture width
        ↓
    captured mechanical power
        ↓
    electrical conversion efficiency
        ↓
    rated-power cap
        ↓
    availability
    """

    # --------------------------------------------------------
    # Mechanical power captured from the wave field
    # --------------------------------------------------------

    captured_power_kw = (
        calculate_captured_wave_power_kw(
            wave_power_flux_kw_per_m=(
                wave_power_flux_kw_per_m
            ),
            capture_width_m=(
                config.capture_width_m
            ),
        )
    )

    # --------------------------------------------------------
    # Mechanical → electrical conversion
    # --------------------------------------------------------

    electrical_power_kw = (
        captured_power_kw
        * config.conversion_efficiency
    )

    # --------------------------------------------------------
    # kW → MW
    # --------------------------------------------------------

    electrical_power_mw = (
        electrical_power_kw
        / 1000.0
    )

    # --------------------------------------------------------
    # Device cannot exceed rated electrical output
    # --------------------------------------------------------

    capped_power_mw = min(
        electrical_power_mw,
        config.device_rated_power_mw,
    )

    # --------------------------------------------------------
    # Expected operational availability
    # --------------------------------------------------------

    expected_power_mw = (
        capped_power_mw
        * config.availability
    )

    return max(
        0.0,
        expected_power_mw,
    )


# ============================================================
# NUMBER OF WAVE DEVICES
# ============================================================

def calculate_wave_device_count(
    project_capacity_mw: float,
    device_rated_power_mw: float,
) -> float:
    """
    Calculate equivalent number of wave-energy
    converters represented by project capacity.

    For the mathematical comparison model, fractional
    device counts are allowed.

    Final engineering/site-layout analysis can later
    require whole devices.
    """

    project_capacity_mw = float(
        project_capacity_mw
    )

    device_rated_power_mw = float(
        device_rated_power_mw
    )

    if (
        not math.isfinite(
            project_capacity_mw
        )
        or project_capacity_mw <= 0
    ):

        raise ValueError(
            "Project capacity must be "
            "finite and positive."
        )

    if (
        not math.isfinite(
            device_rated_power_mw
        )
        or device_rated_power_mw <= 0
    ):

        raise ValueError(
            "Device rated power must be "
            "finite and positive."
        )

    return (
        project_capacity_mw
        / device_rated_power_mw
    )


# ============================================================
# COMPLETE PROJECT POWER AT ONE SEA STATE
# ============================================================

def calculate_project_wave_power_mw(
    significant_wave_height_m: float,
    energy_period_s: float,
    project_capacity_mw: float,
    config: WaveConfig,
) -> float:
    """
    Calculate expected total wave-farm output
    for one sea-state observation.

    The sea state is represented by:

        significant wave height, Hs
        energy period, Te
    """

    # --------------------------------------------------------
    # Ocean resource
    # --------------------------------------------------------

    wave_power_flux_kw_per_m = (
        calculate_wave_power_flux_kw_per_m(
            significant_wave_height_m=(
                significant_wave_height_m
            ),
            energy_period_s=(
                energy_period_s
            ),
        )
    )

    # --------------------------------------------------------
    # One converter
    # --------------------------------------------------------

    device_power_mw = (
        calculate_wave_device_power_mw(
            wave_power_flux_kw_per_m=(
                wave_power_flux_kw_per_m
            ),
            config=config,
        )
    )

    # --------------------------------------------------------
    # Equivalent number of converters
    # --------------------------------------------------------

    device_count = (
        calculate_wave_device_count(
            project_capacity_mw=(
                project_capacity_mw
            ),
            device_rated_power_mw=(
                config.device_rated_power_mw
            ),
        )
    )

    # --------------------------------------------------------
    # Whole project
    # --------------------------------------------------------

    project_power_mw = (
        device_power_mw
        * device_count
    )

    # --------------------------------------------------------
    # Project electrical power cannot exceed
    # nominal project capacity.
    # --------------------------------------------------------

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
    point: WaveResourcePoint,
    scenario: ProjectScenario,
    config: WaveConfig,
) -> float:
    """
    Convert one observed sea state into expected
    project electrical output.
    """

    return calculate_project_wave_power_mw(

        significant_wave_height_m=(
            point.significant_wave_height_m
        ),

        energy_period_s=(
            point.energy_period_s
        ),

        project_capacity_mw=(
            scenario.capacity_mw
        ),

        config=config,
    )


# ============================================================
# COMPLETE WAVE SIMULATION
# ============================================================

def simulate_wave(
    scenario: ProjectScenario,
    resource: WaveResourceSeries,
) -> GenerationResult:
    """
    Simulate wave-energy generation over an entire
    marine-resource time series.

    Processing chain
    ----------------

    Hs and Te
        ↓
    deep-water wave power flux
        ↓
    effective capture width
        ↓
    mechanical captured power
        ↓
    electrical conversion
        ↓
    device rated-power cap
        ↓
    availability
        ↓
    project output
        ↓
    energy integration
        ↓
    capacity factor
    """

    # --------------------------------------------------------
    # Validate project
    # --------------------------------------------------------

    config = (
        _validate_wave_scenario(
            scenario
        )
    )

    # --------------------------------------------------------
    # Validate project/resource location
    # --------------------------------------------------------

    _validate_resource_location(
        scenario=scenario,
        resource=resource,
    )

    # --------------------------------------------------------
    # Determine resource time resolution
    # --------------------------------------------------------

    time_step_hours = (
        resource.time_step_hours
    )

    if time_step_hours is None:

        raise ValueError(
            "At least two wave-resource observations "
            "are required to determine the time step."
        )

    if (
        not math.isfinite(
            time_step_hours
        )
        or time_step_hours <= 0
    ):

        raise ValueError(
            "Wave-resource time step must be "
            "finite and positive."
        )

    # --------------------------------------------------------
    # Calculate project power for every sea state
    # --------------------------------------------------------

    power_by_interval_mw = tuple(

        _calculate_point_power_mw(
            point=point,
            scenario=scenario,
            config=config,
        )

        for point
        in resource.points
    )

    # --------------------------------------------------------
    # Energy integration
    #
    # E = Σ P_t Δt
    # --------------------------------------------------------

    total_generation_mwh = math.fsum(

        power_mw
        * time_step_hours

        for power_mw
        in power_by_interval_mw
    )

    # --------------------------------------------------------
    # Duration represented by resource data
    # --------------------------------------------------------

    total_duration_hours = (
        len(
            power_by_interval_mw
        )
        * time_step_hours
    )

    # --------------------------------------------------------
    # Maximum possible electrical generation
    # --------------------------------------------------------

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
    # Warnings describing model limitations
    # --------------------------------------------------------

    warnings = (
        (
            "Wave-power flux is calculated using "
            "the deep-water wave-energy equation. "
            "Finite-depth effects are not currently "
            "modelled."
        ),

        (
            "Wave-device performance currently uses "
            "effective capture width and conversion "
            "efficiency rather than a manufacturer- "
            "or device-specific power matrix."
        ),

        (
            "Wave direction is preserved in resource "
            "data but is not currently used to modify "
            "device output."
        ),
    )

    # --------------------------------------------------------
    # Standard physics result
    # --------------------------------------------------------

    return GenerationResult(

        scenario_id=(
            scenario.scenario_id
        ),

        technology=(
            Technology.WAVE
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
            "deep_water_capture_width_wave_v1"
        ),

        warnings=(
            warnings
        ),
    )