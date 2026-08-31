# physics/solar.py

from __future__ import annotations

import math

from enum import Enum

from core.models import (
    GenerationResult,
    ProjectScenario,
    SolarConfig,
    Technology,
)

from core.resources import (
    SolarResourcePoint,
    SolarResourceSeries,
)


# ============================================================
# SOLAR MODEL MODES
# ============================================================

class SolarIrradianceMode(str, Enum):
    """
    Selects which irradiance quantity is used by the PV model.

    AUTO:
        Prefer plane-of-array (POA) irradiance when it is
        available for every observation. Otherwise use GHI
        as an approximation.

    POA_ONLY:
        Require POA irradiance for every observation.

    GHI_APPROXIMATION:
        Explicitly use GHI as a simplified approximation.
    """

    AUTO = "auto"
    POA_ONLY = "poa_only"
    GHI_APPROXIMATION = "ghi_approximation"


class SolarTemperatureMode(str, Enum):
    """
    Controls whether PV cell-temperature correction is applied.

    AUTO:
        Use cell temperature when available for every
        observation. Otherwise do not apply temperature
        correction.

    CELL_TEMPERATURE:
        Require cell temperature for every observation.

    IGNORE:
        Do not apply a temperature correction.
    """

    AUTO = "auto"
    CELL_TEMPERATURE = "cell_temperature"
    IGNORE = "ignore"


# ============================================================
# SCENARIO VALIDATION
# ============================================================

def _validate_solar_scenario(
    scenario: ProjectScenario,
) -> SolarConfig:
    """
    Validate that the supplied scenario represents a
    solar-PV project.

    Returns
    -------
    SolarConfig
        The solar-specific configuration belonging to
        the scenario.
    """

    if scenario.technology is not Technology.SOLAR:
        raise ValueError(
            "solar.py can only simulate solar project scenarios."
        )

    if not isinstance(
        scenario.technology_config,
        SolarConfig,
    ):
        raise TypeError(
            "Solar project requires SolarConfig."
        )

    return scenario.technology_config


def _validate_resource_location(
    scenario: ProjectScenario,
    resource: SolarResourceSeries,
) -> None:
    """
    Ensure that the resource data correspond to the same
    coordinates as the simulated project.

    This prevents accidentally simulating, for example,
    a Karachi project using Quetta weather data.
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
            "Solar resource coordinates do not match "
            "project coordinates."
        )


# ============================================================
# IRRADIANCE MODE SELECTION
# ============================================================

def _resolve_irradiance_mode(
    resource: SolarResourceSeries,
    requested_mode: SolarIrradianceMode,
) -> tuple[
    SolarIrradianceMode,
    tuple[str, ...],
]:
    """
    Determine which irradiance measure will actually be used.

    A simulation uses one consistent irradiance definition
    across the complete resource series.
    """

    all_have_poa = all(
        point.poa_irradiance_wm2 is not None
        for point in resource.points
    )

    # --------------------------------------------------------
    # POA explicitly required
    # --------------------------------------------------------

    if requested_mode is SolarIrradianceMode.POA_ONLY:

        if not all_have_poa:
            raise ValueError(
                "POA irradiance was required but is missing "
                "from one or more resource observations."
            )

        return (
            SolarIrradianceMode.POA_ONLY,
            (),
        )

    # --------------------------------------------------------
    # GHI explicitly requested
    # --------------------------------------------------------

    if (
        requested_mode
        is SolarIrradianceMode.GHI_APPROXIMATION
    ):

        return (
            SolarIrradianceMode.GHI_APPROXIMATION,
            (
                "GHI is being used as an approximation "
                "for array-plane irradiance. Tilt and "
                "azimuth are not physically represented "
                "in this mode.",
            ),
        )

    # --------------------------------------------------------
    # AUTO
    # --------------------------------------------------------

    if requested_mode is SolarIrradianceMode.AUTO:

        if all_have_poa:
            return (
                SolarIrradianceMode.POA_ONLY,
                (),
            )

        return (
            SolarIrradianceMode.GHI_APPROXIMATION,
            (
                "POA irradiance was unavailable for the "
                "complete dataset, so GHI was used as an "
                "approximation. Tilt and azimuth are not "
                "physically represented.",
            ),
        )

    raise ValueError(
        f"Unsupported irradiance mode: {requested_mode}"
    )


# ============================================================
# TEMPERATURE MODE SELECTION
# ============================================================

def _resolve_temperature_mode(
    resource: SolarResourceSeries,
    requested_mode: SolarTemperatureMode,
) -> tuple[
    SolarTemperatureMode,
    tuple[str, ...],
]:
    """
    Determine whether cell-temperature correction will
    actually be used.
    """

    all_have_cell_temperature = all(
        point.cell_temperature_c is not None
        for point in resource.points
    )

    # --------------------------------------------------------
    # Cell temperature explicitly required
    # --------------------------------------------------------

    if (
        requested_mode
        is SolarTemperatureMode.CELL_TEMPERATURE
    ):

        if not all_have_cell_temperature:
            raise ValueError(
                "Cell-temperature correction was required "
                "but cell temperature is missing from one "
                "or more resource observations."
            )

        return (
            SolarTemperatureMode.CELL_TEMPERATURE,
            (),
        )

    # --------------------------------------------------------
    # Temperature correction explicitly disabled
    # --------------------------------------------------------

    if requested_mode is SolarTemperatureMode.IGNORE:

        return (
            SolarTemperatureMode.IGNORE,
            (),
        )

    # --------------------------------------------------------
    # AUTO
    # --------------------------------------------------------

    if requested_mode is SolarTemperatureMode.AUTO:

        if all_have_cell_temperature:
            return (
                SolarTemperatureMode.CELL_TEMPERATURE,
                (),
            )

        return (
            SolarTemperatureMode.IGNORE,
            (
                "Cell-temperature data were unavailable "
                "for the complete dataset, so temperature "
                "correction was not applied.",
            ),
        )

    raise ValueError(
        f"Unsupported temperature mode: {requested_mode}"
    )


# ============================================================
# IRRADIANCE EXTRACTION
# ============================================================

def _get_irradiance_wm2(
    point: SolarResourcePoint,
    mode: SolarIrradianceMode,
) -> float:
    """
    Obtain the irradiance value used for one resource point.
    """

    if mode is SolarIrradianceMode.POA_ONLY:

        if point.poa_irradiance_wm2 is None:
            raise ValueError(
                "POA irradiance is missing."
            )

        return point.poa_irradiance_wm2

    if (
        mode
        is SolarIrradianceMode.GHI_APPROXIMATION
    ):
        return point.ghi_wm2

    raise ValueError(
        "Irradiance mode must be resolved before "
        "calculating power."
    )


# ============================================================
# TEMPERATURE CORRECTION
# ============================================================

def _calculate_temperature_factor(
    point: SolarResourcePoint,
    config: SolarConfig,
    mode: SolarTemperatureMode,
) -> float:
    """
    Calculate the PV output multiplier caused by cell
    temperature.

    Formula
    -------
    factor = 1 + gamma * (T_cell - T_ref)

    where:

        gamma  = temperature coefficient per °C
        T_cell = PV cell temperature
        T_ref  = reference cell temperature

    Example
    -------
    gamma = -0.004 / °C
    T_cell = 45 °C
    T_ref = 25 °C

    factor = 1 + (-0.004)(20)
           = 0.92
    """

    if mode is SolarTemperatureMode.IGNORE:
        return 1.0

    if (
        mode
        is not SolarTemperatureMode.CELL_TEMPERATURE
    ):
        raise ValueError(
            "Temperature mode must be resolved before "
            "calculating temperature correction."
        )

    if point.cell_temperature_c is None:
        raise ValueError(
            "Cell temperature is required for "
            "temperature correction."
        )

    temperature_difference_c = (
        point.cell_temperature_c
        - config.reference_cell_temperature_c
    )

    factor = (
        1.0
        + config.temperature_coefficient_per_c
        * temperature_difference_c
    )

    if not math.isfinite(factor):
        raise ValueError(
            "Calculated temperature correction "
            "factor is not finite."
        )

    # Electrical output cannot become negative.
    return max(
        0.0,
        factor,
    )


# ============================================================
# INSTANTANEOUS PV POWER
# ============================================================

def calculate_solar_power_mw(
    installed_capacity_mw: float,
    irradiance_wm2: float,
    config: SolarConfig,
    temperature_factor: float = 1.0,
) -> float:
    """
    Calculate PV electrical power for one resource interval.

    Simplified rated-power model
    ----------------------------

    P = P_rated
        * (G / G_ref)
        * f_temperature
        * (1 - system_losses)

    where:

        P_rated
            installed rated electrical capacity in MW

        G
            incident irradiance in W/m²

        G_ref
            reference irradiance in W/m²

        f_temperature
            temperature correction multiplier

        system_losses
            fractional system losses

    Notes
    -----
    The model begins from the installed rated electrical
    capacity. Therefore panel efficiency must NOT be
    multiplied into this equation again.

    Output is currently capped at installed rated capacity.
    """

    installed_capacity_mw = float(
        installed_capacity_mw
    )

    irradiance_wm2 = float(
        irradiance_wm2
    )

    temperature_factor = float(
        temperature_factor
    )

    if not math.isfinite(
        installed_capacity_mw
    ):
        raise ValueError(
            "Installed capacity must be finite."
        )

    if installed_capacity_mw <= 0:
        raise ValueError(
            "Installed capacity must be greater than zero."
        )

    if not math.isfinite(
        irradiance_wm2
    ):
        raise ValueError(
            "Irradiance must be finite."
        )

    if irradiance_wm2 < 0:
        raise ValueError(
            "Irradiance cannot be negative."
        )

    if not math.isfinite(
        temperature_factor
    ):
        raise ValueError(
            "Temperature factor must be finite."
        )

    if temperature_factor < 0:
        raise ValueError(
            "Temperature factor cannot be negative."
        )

    # --------------------------------------------------------
    # Irradiance scaling
    # --------------------------------------------------------

    irradiance_ratio = (
        irradiance_wm2
        / config.reference_irradiance_wm2
    )

    ideal_power_mw = (
        installed_capacity_mw
        * irradiance_ratio
    )

    # --------------------------------------------------------
    # Temperature correction
    # --------------------------------------------------------

    temperature_adjusted_power_mw = (
        ideal_power_mw
        * temperature_factor
    )

    # --------------------------------------------------------
    # System losses
    # --------------------------------------------------------

    net_power_mw = (
        temperature_adjusted_power_mw
        * (1.0 - config.system_losses)
    )

    # --------------------------------------------------------
    # Physical bounds
    # --------------------------------------------------------

    return min(
        installed_capacity_mw,
        max(
            0.0,
            net_power_mw,
        ),
    )


# ============================================================
# SINGLE RESOURCE POINT
# ============================================================

def _calculate_point_power_mw(
    point: SolarResourcePoint,
    scenario: ProjectScenario,
    config: SolarConfig,
    irradiance_mode: SolarIrradianceMode,
    temperature_mode: SolarTemperatureMode,
) -> float:
    """
    Calculate PV electrical power for one resource point.
    """

    irradiance_wm2 = _get_irradiance_wm2(
        point=point,
        mode=irradiance_mode,
    )

    temperature_factor = (
        _calculate_temperature_factor(
            point=point,
            config=config,
            mode=temperature_mode,
        )
    )

    return calculate_solar_power_mw(
        installed_capacity_mw=(
            scenario.capacity_mw
        ),
        irradiance_wm2=irradiance_wm2,
        config=config,
        temperature_factor=(
            temperature_factor
        ),
    )


# ============================================================
# COMPLETE SOLAR SIMULATION
# ============================================================

def simulate_solar(
    scenario: ProjectScenario,
    resource: SolarResourceSeries,
    irradiance_mode: SolarIrradianceMode = (
        SolarIrradianceMode.AUTO
    ),
    temperature_mode: SolarTemperatureMode = (
        SolarTemperatureMode.AUTO
    ),
) -> GenerationResult:
    """
    Simulate solar-PV electricity generation across an
    entire resource time series.

    Processing chain
    ----------------

    Resource observations
        ↓
    irradiance selection
        ↓
    temperature correction
        ↓
    electrical power for each interval
        ↓
    energy integration
        ↓
    total generation
        ↓
    capacity factor

    Returns
    -------
    GenerationResult
        Standard technology-independent physics result.
    """

    # --------------------------------------------------------
    # Validate project
    # --------------------------------------------------------

    config = _validate_solar_scenario(
        scenario
    )

    # --------------------------------------------------------
    # Validate resource/project location
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
            "At least two resource observations are "
            "required to determine the simulation "
            "time step."
        )

    if not math.isfinite(
        time_step_hours
    ):
        raise ValueError(
            "Resource time step must be finite."
        )

    if time_step_hours <= 0:
        raise ValueError(
            "Resource time step must be greater than zero."
        )

    # --------------------------------------------------------
    # Resolve modelling fidelity
    # --------------------------------------------------------

    (
        resolved_irradiance_mode,
        irradiance_warnings,
    ) = _resolve_irradiance_mode(
        resource=resource,
        requested_mode=irradiance_mode,
    )

    (
        resolved_temperature_mode,
        temperature_warnings,
    ) = _resolve_temperature_mode(
        resource=resource,
        requested_mode=temperature_mode,
    )

    # --------------------------------------------------------
    # Simulate power for every resource interval
    # --------------------------------------------------------

    power_by_interval_mw = tuple(
        _calculate_point_power_mw(
            point=point,
            scenario=scenario,
            config=config,
            irradiance_mode=(
                resolved_irradiance_mode
            ),
            temperature_mode=(
                resolved_temperature_mode
            ),
        )
        for point in resource.points
    )

    # --------------------------------------------------------
    # Integrate power through time
    #
    # Energy = Power × Time
    #
    # MW × hours = MWh
    # --------------------------------------------------------

    total_generation_mwh = math.fsum(
        power_mw * time_step_hours
        for power_mw in power_by_interval_mw
    )

    # --------------------------------------------------------
    # Determine total represented duration
    # --------------------------------------------------------

    total_duration_hours = (
        len(power_by_interval_mw)
        * time_step_hours
    )

    maximum_possible_generation_mwh = (
        scenario.capacity_mw
        * total_duration_hours
    )

    # --------------------------------------------------------
    # Capacity factor
    #
    # CF =
    # actual generation
    # -----------------
    # maximum possible generation
    # --------------------------------------------------------

    if maximum_possible_generation_mwh > 0:

        capacity_factor = (
            total_generation_mwh
            / maximum_possible_generation_mwh
        )

    else:

        capacity_factor = 0.0

    # Numerical protection
    capacity_factor = min(
        1.0,
        max(
            0.0,
            capacity_factor,
        ),
    )

    # --------------------------------------------------------
    # Combine model warnings
    # --------------------------------------------------------

    warnings = (
        irradiance_warnings
        + temperature_warnings
    )

    # --------------------------------------------------------
    # Return standardized physics result
    # --------------------------------------------------------

    return GenerationResult(
        scenario_id=(
            scenario.scenario_id
        ),

        technology=(
            Technology.SOLAR
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
            "simplified_rated_power_solar_v1"
        ),

        warnings=(
            warnings
        ),
    )