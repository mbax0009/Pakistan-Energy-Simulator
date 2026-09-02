# analysis/scenario_builders.py

from __future__ import annotations

import math

from dataclasses import (
    dataclass,
    replace,
)
from enum import Enum

from core.models import (
    ProjectScenario,
    SolarConfig,
    Technology,
    WaveConfig,
    WindConfig,
)


# ============================================================
# RECALCULATION SCOPE
# ============================================================

class RecalculationScope(str, Enum):
    """
    Describes how much of the simulation pipeline must
    be rerun when one parameter changes.

    FINANCE_ONLY
        Physical generation is unchanged.

    LIFECYCLE_AND_FINANCE
        First-year resource generation is unchanged,
        but lifetime production changes.

    PHYSICS_AND_DOWNSTREAM
        Existing weather/resource data can be reused,
        but physics and everything downstream must rerun.

    RESOURCE_AND_DOWNSTREAM
        Even the resource-loading stage must be rerun.
    """

    FINANCE_ONLY = "finance_only"

    LIFECYCLE_AND_FINANCE = (
        "lifecycle_and_finance"
    )

    PHYSICS_AND_DOWNSTREAM = (
        "physics_and_downstream"
    )

    RESOURCE_AND_DOWNSTREAM = (
        "resource_and_downstream"
    )


# ============================================================
# SUPPORTED SCENARIO PARAMETERS
# ============================================================

class ScenarioParameter(str, Enum):
    """
    Parameters that can currently be modified safely
    for sensitivity and break-even experiments.
    """

    # --------------------------------------------------------
    # FINANCIAL
    # --------------------------------------------------------

    CAPEX_PER_KW = "capex_per_kw"

    FIXED_OPEX_PER_KW_YEAR = (
        "fixed_opex_per_kw_year"
    )

    VARIABLE_OPEX_PER_MWH = (
        "variable_opex_per_mwh"
    )

    ELECTRICITY_PRICE_PER_MWH = (
        "electricity_price_per_mwh"
    )

    DISCOUNT_RATE = (
        "discount_rate"
    )

    ELECTRICITY_PRICE_GROWTH_RATE = (
        "electricity_price_growth_rate"
    )

    OPEX_GROWTH_RATE = (
        "opex_growth_rate"
    )

    # --------------------------------------------------------
    # LIFECYCLE
    # --------------------------------------------------------

    ANNUAL_DEGRADATION_RATE = (
        "annual_degradation_rate"
    )

    # --------------------------------------------------------
    # SOLAR
    # --------------------------------------------------------

    SOLAR_TILT_DEG = (
        "solar_tilt_deg"
    )

    SOLAR_AZIMUTH_DEG = (
        "solar_azimuth_deg"
    )

    SOLAR_SYSTEM_LOSSES = (
        "solar_system_losses"
    )

    SOLAR_TEMPERATURE_COEFFICIENT = (
        "solar_temperature_coefficient"
    )

    # --------------------------------------------------------
    # WIND
    # --------------------------------------------------------

    WIND_HUB_HEIGHT_M = (
        "wind_hub_height_m"
    )

    WIND_SHEAR_EXPONENT = (
        "wind_shear_exponent"
    )

    WIND_AVAILABILITY = (
        "wind_availability"
    )

    WIND_CUT_IN_SPEED_MS = (
        "wind_cut_in_speed_ms"
    )

    WIND_RATED_SPEED_MS = (
        "wind_rated_speed_ms"
    )

    WIND_CUT_OUT_SPEED_MS = (
        "wind_cut_out_speed_ms"
    )

    # --------------------------------------------------------
    # WAVE
    # --------------------------------------------------------

    WAVE_CONVERSION_EFFICIENCY = (
        "wave_conversion_efficiency"
    )

    WAVE_CAPTURE_WIDTH_M = (
        "wave_capture_width_m"
    )

    WAVE_AVAILABILITY = (
        "wave_availability"
    )

    WAVE_DEVICE_RATED_POWER_MW = (
        "wave_device_rated_power_mw"
    )


# ============================================================
# MODIFICATION RESULT
# ============================================================

@dataclass(frozen=True)
class ScenarioModification:
    """
    One modified project scenario together with metadata
    describing why it was created.

    scenario_id intentionally remains the same as the
    baseline scenario ID.

    The parameter value identifies the sensitivity run.
    """

    project: ProjectScenario

    parameter: ScenarioParameter

    parameter_value: float

    recalculation_scope: RecalculationScope

    def __post_init__(self):

        if not math.isfinite(
            self.parameter_value
        ):
            raise ValueError(
                "Modified parameter value "
                "must be finite."
            )


# ============================================================
# PARAMETER SCOPE
# ============================================================

def get_recalculation_scope(
    parameter: ScenarioParameter,
) -> RecalculationScope:
    """
    Return the minimum section of the model that must
    be recalculated after changing a parameter.
    """

    # --------------------------------------------------------
    # Purely financial assumptions
    # --------------------------------------------------------

    finance_only = {
        ScenarioParameter.CAPEX_PER_KW,
        ScenarioParameter.FIXED_OPEX_PER_KW_YEAR,
        ScenarioParameter.VARIABLE_OPEX_PER_MWH,
        ScenarioParameter.ELECTRICITY_PRICE_PER_MWH,
        ScenarioParameter.DISCOUNT_RATE,
        ScenarioParameter.ELECTRICITY_PRICE_GROWTH_RATE,
        ScenarioParameter.OPEX_GROWTH_RATE,
    }

    if parameter in finance_only:

        return (
            RecalculationScope.FINANCE_ONLY
        )

    # --------------------------------------------------------
    # Lifecycle assumption
    # --------------------------------------------------------

    if (
        parameter
        is ScenarioParameter.ANNUAL_DEGRADATION_RATE
    ):

        return (
            RecalculationScope.LIFECYCLE_AND_FINANCE
        )

    # --------------------------------------------------------
    # Solar orientation
    #
    # Our solar loader can retrieve POA/GTI based on
    # tilt and azimuth.
    #
    # Therefore changing orientation requires the resource
    # request itself to be repeated.
    # --------------------------------------------------------

    if parameter in {
        ScenarioParameter.SOLAR_TILT_DEG,
        ScenarioParameter.SOLAR_AZIMUTH_DEG,
    }:

        return (
            RecalculationScope.RESOURCE_AND_DOWNSTREAM
        )

    # --------------------------------------------------------
    # Technology physics
    # --------------------------------------------------------

    physics_parameters = {

        ScenarioParameter.SOLAR_SYSTEM_LOSSES,

        ScenarioParameter
        .SOLAR_TEMPERATURE_COEFFICIENT,

        ScenarioParameter.WIND_HUB_HEIGHT_M,
        ScenarioParameter.WIND_SHEAR_EXPONENT,
        ScenarioParameter.WIND_AVAILABILITY,
        ScenarioParameter.WIND_CUT_IN_SPEED_MS,
        ScenarioParameter.WIND_RATED_SPEED_MS,
        ScenarioParameter.WIND_CUT_OUT_SPEED_MS,

        ScenarioParameter
        .WAVE_CONVERSION_EFFICIENCY,

        ScenarioParameter
        .WAVE_CAPTURE_WIDTH_M,

        ScenarioParameter
        .WAVE_AVAILABILITY,

        ScenarioParameter
        .WAVE_DEVICE_RATED_POWER_MW,
    }

    if parameter in physics_parameters:

        return (
            RecalculationScope.PHYSICS_AND_DOWNSTREAM
        )

    raise ValueError(
        f"No recalculation scope defined "
        f"for parameter {parameter.value}."
    )


# ============================================================
# VALUE VALIDATION
# ============================================================

def _validate_parameter_value(
    value: float,
) -> float:
    """
    Convert a parameter value to float and ensure
    it is finite.

    More specific physical/economic validation is
    performed by the project's dataclasses.
    """

    value = float(
        value
    )

    if not math.isfinite(
        value
    ):

        raise ValueError(
            "Scenario parameter value "
            "must be finite."
        )

    return value


# ============================================================
# TECHNOLOGY CONFIG HELPERS
# ============================================================

def _require_solar_config(
    project: ProjectScenario,
) -> SolarConfig:
    """
    Return SolarConfig only if this really is
    a solar project.
    """

    if (
        project.technology
        is not Technology.SOLAR
    ):

        raise ValueError(
            "Solar parameter cannot be applied "
            "to a non-solar project."
        )

    if not isinstance(
        project.technology_config,
        SolarConfig,
    ):

        raise TypeError(
            "Solar project does not contain "
            "SolarConfig."
        )

    return project.technology_config


def _require_wind_config(
    project: ProjectScenario,
) -> WindConfig:
    """
    Return WindConfig only for a wind project.
    """

    if (
        project.technology
        is not Technology.WIND
    ):

        raise ValueError(
            "Wind parameter cannot be applied "
            "to a non-wind project."
        )

    if not isinstance(
        project.technology_config,
        WindConfig,
    ):

        raise TypeError(
            "Wind project does not contain "
            "WindConfig."
        )

    return project.technology_config


def _require_wave_config(
    project: ProjectScenario,
) -> WaveConfig:
    """
    Return WaveConfig only for a wave project.
    """

    if (
        project.technology
        is not Technology.WAVE
    ):

        raise ValueError(
            "Wave parameter cannot be applied "
            "to a non-wave project."
        )

    if not isinstance(
        project.technology_config,
        WaveConfig,
    ):

        raise TypeError(
            "Wave project does not contain "
            "WaveConfig."
        )

    return project.technology_config


# ============================================================
# FINANCIAL PARAMETER REPLACEMENT
# ============================================================

def _replace_financial_parameter(
    project: ProjectScenario,
    field_name: str,
    value: float,
) -> ProjectScenario:
    """
    Create a new FinancialInputs object and then
    a new ProjectScenario.

    The baseline project remains untouched.
    """

    new_finance = replace(
        project.finance,
        **{
            field_name: value
        },
    )

    return replace(
        project,
        finance=new_finance,
    )


# ============================================================
# SOLAR CONFIG REPLACEMENT
# ============================================================

def _replace_solar_parameter(
    project: ProjectScenario,
    field_name: str,
    value: float,
) -> ProjectScenario:

    config = (
        _require_solar_config(
            project
        )
    )

    new_config = replace(
        config,
        **{
            field_name: value
        },
    )

    return replace(
        project,
        technology_config=new_config,
    )


# ============================================================
# WIND CONFIG REPLACEMENT
# ============================================================

def _replace_wind_parameter(
    project: ProjectScenario,
    field_name: str,
    value: float,
) -> ProjectScenario:

    config = (
        _require_wind_config(
            project
        )
    )

    changes: dict[str, float | None] = {
        field_name: value
    }

    # Cut-in, rated, and cut-out speeds describe the
    # parametric cubic curve. Varying one of them therefore
    # selects that fallback instead of silently pretending the
    # fixed tabulated reference curve changed shape.
    if field_name in {
        "cut_in_speed_ms",
        "rated_speed_ms",
        "cut_out_speed_ms",
    }:
        changes["power_curve_id"] = None

    new_config = replace(
        config,
        **changes,
    )

    return replace(
        project,
        technology_config=new_config,
    )


# ============================================================
# WAVE CONFIG REPLACEMENT
# ============================================================

def _replace_wave_parameter(
    project: ProjectScenario,
    field_name: str,
    value: float,
) -> ProjectScenario:

    config = (
        _require_wave_config(
            project
        )
    )

    new_config = replace(
        config,
        **{
            field_name: value
        },
    )

    return replace(
        project,
        technology_config=new_config,
    )


# ============================================================
# MAIN PARAMETER MODIFICATION FUNCTION
# ============================================================

def apply_scenario_parameter(
    project: ProjectScenario,
    parameter: ScenarioParameter,
    value: float,
) -> ScenarioModification:
    """
    Create a modified immutable ProjectScenario.

    This is the main public entry point for
    sensitivity analysis.

    Examples
    --------

        change wave CAPEX

        change wind hub height

        change solar losses

        change discount rate
    """

    value = (
        _validate_parameter_value(
            value
        )
    )

    # ========================================================
    # FINANCIAL PARAMETERS
    # ========================================================

    if (
        parameter
        is ScenarioParameter.CAPEX_PER_KW
    ):

        modified = (
            _replace_financial_parameter(
                project,
                "capex_per_kw",
                value,
            )
        )


    elif (
        parameter
        is ScenarioParameter
        .FIXED_OPEX_PER_KW_YEAR
    ):

        modified = (
            _replace_financial_parameter(
                project,
                "fixed_opex_per_kw_year",
                value,
            )
        )


    elif (
        parameter
        is ScenarioParameter
        .VARIABLE_OPEX_PER_MWH
    ):

        modified = (
            _replace_financial_parameter(
                project,
                "variable_opex_per_mwh",
                value,
            )
        )


    elif (
        parameter
        is ScenarioParameter
        .ELECTRICITY_PRICE_PER_MWH
    ):

        modified = (
            _replace_financial_parameter(
                project,
                "electricity_price_per_mwh",
                value,
            )
        )


    elif (
        parameter
        is ScenarioParameter.DISCOUNT_RATE
    ):

        modified = (
            _replace_financial_parameter(
                project,
                "discount_rate",
                value,
            )
        )


    elif (
        parameter
        is ScenarioParameter
        .ELECTRICITY_PRICE_GROWTH_RATE
    ):

        modified = (
            _replace_financial_parameter(
                project,
                "electricity_price_growth_rate",
                value,
            )
        )


    elif (
        parameter
        is ScenarioParameter.OPEX_GROWTH_RATE
    ):

        modified = (
            _replace_financial_parameter(
                project,
                "opex_growth_rate",
                value,
            )
        )


    # ========================================================
    # LIFECYCLE
    # ========================================================

    elif (
        parameter
        is ScenarioParameter
        .ANNUAL_DEGRADATION_RATE
    ):

        modified = replace(
            project,

            annual_degradation_rate=(
                value
            ),
        )


    # ========================================================
    # SOLAR PARAMETERS
    # ========================================================

    elif (
        parameter
        is ScenarioParameter.SOLAR_TILT_DEG
    ):

        modified = (
            _replace_solar_parameter(
                project,
                "tilt_deg",
                value,
            )
        )


    elif (
        parameter
        is ScenarioParameter.SOLAR_AZIMUTH_DEG
    ):

        modified = (
            _replace_solar_parameter(
                project,
                "azimuth_deg",
                value,
            )
        )


    elif (
        parameter
        is ScenarioParameter
        .SOLAR_SYSTEM_LOSSES
    ):

        modified = (
            _replace_solar_parameter(
                project,
                "system_losses",
                value,
            )
        )


    elif (
        parameter
        is ScenarioParameter
        .SOLAR_TEMPERATURE_COEFFICIENT
    ):

        modified = (
            _replace_solar_parameter(
                project,
                "temperature_coefficient_per_c",
                value,
            )
        )


    # ========================================================
    # WIND PARAMETERS
    # ========================================================

    elif (
        parameter
        is ScenarioParameter.WIND_HUB_HEIGHT_M
    ):

        modified = (
            _replace_wind_parameter(
                project,
                "hub_height_m",
                value,
            )
        )


    elif (
        parameter
        is ScenarioParameter.WIND_SHEAR_EXPONENT
    ):

        modified = (
            _replace_wind_parameter(
                project,
                "wind_shear_exponent",
                value,
            )
        )


    elif (
        parameter
        is ScenarioParameter.WIND_AVAILABILITY
    ):

        modified = (
            _replace_wind_parameter(
                project,
                "availability",
                value,
            )
        )


    elif (
        parameter
        is ScenarioParameter.WIND_CUT_IN_SPEED_MS
    ):

        modified = (
            _replace_wind_parameter(
                project,
                "cut_in_speed_ms",
                value,
            )
        )


    elif (
        parameter
        is ScenarioParameter.WIND_RATED_SPEED_MS
    ):

        modified = (
            _replace_wind_parameter(
                project,
                "rated_speed_ms",
                value,
            )
        )


    elif (
        parameter
        is ScenarioParameter.WIND_CUT_OUT_SPEED_MS
    ):

        modified = (
            _replace_wind_parameter(
                project,
                "cut_out_speed_ms",
                value,
            )
        )


    # ========================================================
    # WAVE PARAMETERS
    # ========================================================

    elif (
        parameter
        is ScenarioParameter
        .WAVE_CONVERSION_EFFICIENCY
    ):

        modified = (
            _replace_wave_parameter(
                project,
                "conversion_efficiency",
                value,
            )
        )


    elif (
        parameter
        is ScenarioParameter.WAVE_CAPTURE_WIDTH_M
    ):

        modified = (
            _replace_wave_parameter(
                project,
                "capture_width_m",
                value,
            )
        )


    elif (
        parameter
        is ScenarioParameter.WAVE_AVAILABILITY
    ):

        modified = (
            _replace_wave_parameter(
                project,
                "availability",
                value,
            )
        )


    elif (
        parameter
        is ScenarioParameter
        .WAVE_DEVICE_RATED_POWER_MW
    ):

        modified = (
            _replace_wave_parameter(
                project,
                "device_rated_power_mw",
                value,
            )
        )


    else:

        raise ValueError(
            f"Unsupported scenario parameter: "
            f"{parameter.value}"
        )

    # ========================================================
    # RETURN MODIFICATION
    # ========================================================

    return ScenarioModification(

        project=modified,

        parameter=parameter,

        parameter_value=value,

        recalculation_scope=(
            get_recalculation_scope(
                parameter
            )
        ),
    )


# ============================================================
# BUILD PARAMETER SWEEP
# ============================================================

def build_parameter_sweep(
    project: ProjectScenario,
    parameter: ScenarioParameter,
    values: tuple[float, ...],
) -> tuple[
    ScenarioModification,
    ...
]:
    """
    Create a collection of modified project scenarios
    for one-way sensitivity analysis.

    Example:

        CAPEX =

        1000
        1500
        2000
        2500
        3000
    """

    if not values:

        raise ValueError(
            "Parameter sweep requires at least "
            "one parameter value."
        )

    return tuple(

        apply_scenario_parameter(
            project=project,
            parameter=parameter,
            value=value,
        )

        for value in values
    )
