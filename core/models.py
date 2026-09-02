from __future__ import annotations
import math
from dataclasses import dataclass
from enum import Enum


# ============================================================
# TECHNOLOGY
# ============================================================

class Technology(str, Enum):
    """
    Renewable-energy technologies supported by the simulator.
    """

    SOLAR = "solar"
    WIND = "wind"
    WAVE = "wave"


# ============================================================
# LOCATION
# ============================================================

@dataclass(frozen=True)
class Location:
    """
    Geographic location of an energy project.
    """

    name: str
    latitude: float
    longitude: float

    def __post_init__(self):
        if not self.name.strip():
            raise ValueError("Location name cannot be empty.")

        if not -90 <= self.latitude <= 90:
            raise ValueError("Latitude must be between -90 and 90 degrees.")

        if not -180 <= self.longitude <= 180:
            raise ValueError("Longitude must be between -180 and 180 degrees.")


# ============================================================
# FINANCIAL INPUTS
# ============================================================

@dataclass(frozen=True)
class FinancialInputs:
    """
    Economic assumptions used by the financial model.

    Internal monetary units:
    - CAPEX: USD/kW
    - Fixed OPEX: USD/kW/year
    - Variable OPEX: USD/MWh
    - Electricity price: USD/MWh
    """

    capex_per_kw: float
    fixed_opex_per_kw_year: float
    variable_opex_per_mwh: float
    electricity_price_per_mwh: float

    discount_rate: float

    electricity_price_growth_rate: float = 0.0
    opex_growth_rate: float = 0.0

    def __post_init__(self):
        if self.capex_per_kw <= 0:
            raise ValueError("CAPEX must be greater than zero.")

        if self.fixed_opex_per_kw_year < 0:
            raise ValueError("Fixed OPEX cannot be negative.")

        if self.variable_opex_per_mwh < 0:
            raise ValueError("Variable OPEX cannot be negative.")

        if self.electricity_price_per_mwh < 0:
            raise ValueError("Electricity price cannot be negative.")

        if not 0 <= self.discount_rate < 1:
            raise ValueError(
                "Discount rate must be entered as a decimal between 0 and 1."
            )

        if self.electricity_price_growth_rate <= -1:
            raise ValueError(
                "Electricity price growth rate must be greater than -1."
            )

        if self.opex_growth_rate <= -1:
            raise ValueError(
                "OPEX growth rate must be greater than -1."
            )


# ============================================================
# SOLAR CONFIGURATION
# ============================================================

@dataclass(frozen=True)
class SolarConfig:
    """
    Physical configuration of a solar PV project.

    Azimuth convention used throughout this simulator:

        0°   = North
        90°  = East
        180° = South
        270° = West

    Azimuth increases clockwise from North.

    This is the simulator's internal convention.
    External data providers may use different conventions;
    provider-specific loaders are responsible for converting
    between conventions.
    """

    tilt_deg: float
    azimuth_deg: float

    system_losses: float = 0.14

    reference_irradiance_wm2: float = 1000.0
    reference_cell_temperature_c: float = 25.0

    temperature_coefficient_per_c: float = -0.004

    def __post_init__(self):

        if not 0 <= self.tilt_deg <= 90:
            raise ValueError(
                "Solar tilt must be between 0 and 90 degrees."
            )

        if not 0 <= self.azimuth_deg < 360:
            raise ValueError(
                "Solar azimuth must be between 0 and "
                "less than 360 degrees, using "
                "0°=North, 90°=East, "
                "180°=South, 270°=West."
            )

        if not 0 <= self.system_losses < 1:
            raise ValueError(
                "System losses must be between 0 and 1."
            )

        if self.reference_irradiance_wm2 <= 0:
            raise ValueError(
                "Reference irradiance must be greater than zero."
            )

        if not math.isfinite(
            self.reference_cell_temperature_c
        ):
            raise ValueError(
                "Reference cell temperature must be finite."
            )

        if not math.isfinite(
            self.temperature_coefficient_per_c
        ):
            raise ValueError(
                "Temperature coefficient must be finite."
            )

# ============================================================
# WIND CONFIGURATION
# ============================================================

@dataclass(frozen=True)
class WindConfig:
    """
    Physical configuration of an onshore wind project.

    Wind speeds are expressed in m/s.

    wind_shear_exponent controls the vertical adjustment
    of wind speed from the resource measurement height
    to turbine hub height.

    power_curve_id selects a bundled tabulated turbine curve.
    When it is None, the simplified cubic curve is used as a
    fallback.

    reference_air_density_kg_m3 is the air density at which
    the selected turbine power curve is assumed to apply.
    """

    hub_height_m: float

    cut_in_speed_ms: float
    rated_speed_ms: float
    cut_out_speed_ms: float

    turbine_rated_power_mw: float

    availability: float = 0.95

    wind_shear_exponent: float = 1.0 / 7.0

    reference_air_density_kg_m3: float = 1.225

    power_curve_id: str | None = (
        "iea_reference_3_4mw_130"
    )

    def __post_init__(self):

        if self.hub_height_m <= 0:
            raise ValueError(
                "Hub height must be greater than zero."
            )

        if self.turbine_rated_power_mw <= 0:
            raise ValueError(
                "Turbine rated power must "
                "be greater than zero."
            )

        if not (
            0
            <= self.cut_in_speed_ms
            < self.rated_speed_ms
            < self.cut_out_speed_ms
        ):
            raise ValueError(
                "Wind speeds must satisfy: "
                "cut-in < rated < cut-out."
            )

        if not 0 < self.availability <= 1:
            raise ValueError(
                "Availability must be between 0 and 1."
            )

        if self.wind_shear_exponent < 0:
            raise ValueError(
                "Wind shear exponent cannot be negative."
            )

        if self.reference_air_density_kg_m3 <= 0:
            raise ValueError(
                "Reference air density must "
                "be greater than zero."
            )

        if (
            self.power_curve_id is not None
            and not self.power_curve_id.strip()
        ):
            raise ValueError(
                "Power curve ID cannot be empty."
            )

# ============================================================
# WAVE CONFIGURATION
# ============================================================

@dataclass(frozen=True)
class WaveConfig:
    """
    Physical configuration of a wave-energy project.

    capture_width_m:
        Effective hydrodynamic capture width of ONE
        wave-energy converter.

        This is not necessarily the physical width of
        the machine.

    conversion_efficiency:
        Fraction of captured mechanical wave power
        converted to electrical output.

    device_rated_power_mw:
        Maximum electrical output of one device.

    availability:
        Fraction representing expected operational
        availability of the device.
    """

    conversion_efficiency: float

    capture_width_m: float

    device_rated_power_mw: float

    availability: float = 0.90

    def __post_init__(self):

        if not (
            0
            < self.conversion_efficiency
            <= 1
        ):
            raise ValueError(
                "Conversion efficiency must "
                "be between 0 and 1."
            )

        if self.capture_width_m <= 0:
            raise ValueError(
                "Capture width must be "
                "greater than zero."
            )

        if self.device_rated_power_mw <= 0:
            raise ValueError(
                "Device rated power must "
                "be greater than zero."
            )

        if not (
            0
            < self.availability
            <= 1
        ):
            raise ValueError(
                "Availability must be "
                "between 0 and 1."
            )

# These are the three configuration types that a project can use.
TechnologyConfig = SolarConfig | WindConfig | WaveConfig


# ============================================================
# PROJECT SCENARIO
# ============================================================

@dataclass(frozen=True)
class ProjectScenario:
    """
    Complete description of one simulated renewable-energy project.
    """

    scenario_id: str

    technology: Technology

    location: Location

    capacity_mw: float
    lifetime_years: int

    annual_degradation_rate: float

    finance: FinancialInputs

    technology_config: TechnologyConfig

    def __post_init__(self):
        if not self.scenario_id.strip():
            raise ValueError("Scenario ID cannot be empty.")

        if self.capacity_mw <= 0:
            raise ValueError(
                "Project capacity must be greater than zero."
            )

        if self.lifetime_years <= 0:
            raise ValueError(
                "Project lifetime must be greater than zero."
            )

        if not 0 <= self.annual_degradation_rate < 1:
            raise ValueError(
                "Annual degradation rate must be between 0 and 1."
            )

        self._validate_technology_config()

    def _validate_technology_config(self):
        """
        Ensures that the technology and its configuration agree.

        Example:
        A solar project cannot accidentally receive WindConfig.
        """

        expected_types = {
            Technology.SOLAR: SolarConfig,
            Technology.WIND: WindConfig,
            Technology.WAVE: WaveConfig,
        }

        expected_type = expected_types[self.technology]

        if not isinstance(self.technology_config, expected_type):
            raise TypeError(
                f"{self.technology.value} projects require "
                f"{expected_type.__name__}."
            )

@dataclass(frozen=True)
class GenerationResult:
    """
    Standard output from a technology physics model.

    The same structure is used by solar, wind, and wave.
    """

    scenario_id: str
    technology: Technology

    installed_capacity_mw: float

    power_by_interval_mw: tuple[float, ...]

    time_step_hours: float

    total_generation_mwh: float

    capacity_factor: float

    model_name: str

    warnings: tuple[str, ...] = ()

    def __post_init__(self):

        if not self.scenario_id.strip():
            raise ValueError(
                "Scenario ID cannot be empty."
            )

        if self.installed_capacity_mw <= 0:
            raise ValueError(
                "Installed capacity must "
                "be greater than zero."
            )

        if self.time_step_hours <= 0:
            raise ValueError(
                "Time step must be greater "
                "than zero."
            )

        if self.total_generation_mwh < 0:
            raise ValueError(
                "Generation cannot be negative."
            )

        if not 0 <= self.capacity_factor <= 1:
            raise ValueError(
                "Capacity factor must be "
                "between 0 and 1."
            )

        for power_mw in self.power_by_interval_mw:

            if not math.isfinite(power_mw):
                raise ValueError(
                    "Power values must be finite."
                )

            if power_mw < 0:
                raise ValueError(
                    "Power cannot be negative."
                )

# ============================================================
# SIMULATION RESULT
# ============================================================

@dataclass(frozen=True)
class SimulationResult:
    """
    Standard output returned by every technology simulation.
    """

    scenario_id: str
    technology: Technology

    annual_generation_mwh: float
    capacity_factor: float

    total_capex_usd: float
    annual_opex_usd: float
    annual_revenue_usd: float

    npv_usd: float
    irr: float | None
    lcoe_usd_per_mwh: float | None

    payback_years: float | None

    def __post_init__(self):
        if self.annual_generation_mwh < 0:
            raise ValueError(
                "Annual generation cannot be negative."
            )

        if not 0 <= self.capacity_factor <= 1:
            raise ValueError(
                "Capacity factor must be between 0 and 1."
            )

        if self.total_capex_usd < 0:
            raise ValueError(
                "Total CAPEX cannot be negative."
            )

        if self.annual_opex_usd < 0:
            raise ValueError(
                "Annual OPEX cannot be negative."
            )

        if (
            self.lcoe_usd_per_mwh is not None
            and self.lcoe_usd_per_mwh < 0
        ):
            raise ValueError(
                "LCOE cannot be negative."
            )
            
@dataclass(frozen=True)
class CashFlowRow:
    """
    Financial and energy values for one project year.

    Year 0 represents project construction / initial investment.
    Years 1...n represent operating years.
    """

    year: int

    generation_mwh: float
    electricity_price_per_mwh: float

    revenue_usd: float

    fixed_opex_usd: float
    variable_opex_usd: float

    capital_cost_usd: float

    net_cash_flow_usd: float

    @property
    def total_opex_usd(self) -> float:
        return self.fixed_opex_usd + self.variable_opex_usd

    def __post_init__(self):
        if self.year < 0:
            raise ValueError("Year cannot be negative.")

        if self.generation_mwh < 0:
            raise ValueError("Generation cannot be negative.")

        if self.fixed_opex_usd < 0:
            raise ValueError("Fixed OPEX cannot be negative.")

        if self.variable_opex_usd < 0:
            raise ValueError("Variable OPEX cannot be negative.")

        if self.capital_cost_usd < 0:
            raise ValueError("Capital cost cannot be negative.")


@dataclass(frozen=True)
class FinancialMetrics:
    """
    Summary financial results for a complete project simulation.
    """

    initial_capex_usd: float

    npv_usd: float
    irr: float | None
    lcoe_usd_per_mwh: float | None

    simple_payback_years: float | None
    discounted_payback_years: float | None

    lifetime_generation_mwh: float
    lifetime_revenue_usd: float
    lifetime_opex_usd: float

    additional_capex_usd: float


@dataclass(frozen=True)
class FinancialAnalysis:
    """
    Complete financial-analysis output.

    Contains both detailed annual cash flows and summary metrics.
    """

    cash_flows: tuple[CashFlowRow, ...]
    metrics: FinancialMetrics
