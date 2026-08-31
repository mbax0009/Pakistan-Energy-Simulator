# tests/test_wave.py

from __future__ import annotations

import math

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from core.constants import (
    GRAVITY_MS2,
    SEAWATER_DENSITY_KG_M3,
)

from core.models import (
    FinancialInputs,
    Location,
    ProjectScenario,
    Technology,
    WaveConfig,
)

from core.resources import (
    ResourceMetadata,
    WaveResourcePoint,
    WaveResourceSeries,
)

from physics.wave import (
    calculate_captured_wave_power_kw,
    calculate_project_wave_power_mw,
    calculate_wave_device_count,
    calculate_wave_device_power_mw,
    calculate_wave_power_flux_kw_per_m,
    simulate_wave,
)


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def location() -> Location:

    return Location(
        name="Test Offshore Site",
        latitude=24.5,
        longitude=66.7,
    )


@pytest.fixture
def wave_config() -> WaveConfig:
    """
    Simplified wave-energy converter:

        capture width      = 20 m
        efficiency         = 80%
        rated power        = 1 MW
        availability       = 90%
    """

    return WaveConfig(
        conversion_efficiency=0.80,
        capture_width_m=20.0,
        device_rated_power_mw=1.0,
        availability=0.90,
    )


@pytest.fixture
def finance() -> FinancialInputs:

    return FinancialInputs(
        capex_per_kw=4000.0,
        fixed_opex_per_kw_year=100.0,
        variable_opex_per_mwh=0.0,
        electricity_price_per_mwh=100.0,
        discount_rate=0.10,
    )


@pytest.fixture
def wave_project(
    location: Location,
    wave_config: WaveConfig,
    finance: FinancialInputs,
) -> ProjectScenario:

    return ProjectScenario(
        scenario_id="WAVE_TEST_001",
        technology=Technology.WAVE,
        location=location,
        capacity_mw=10.0,
        lifetime_years=25,
        annual_degradation_rate=0.005,
        finance=finance,
        technology_config=wave_config,
    )


# ============================================================
# WAVE POWER FLUX
# ============================================================

def test_wave_power_flux_matches_manual_equation():
    """
    Verify:

              rho * g²
        J = -----------
               64*pi

            * Hs²
            * Te

    Example:

        Hs = 2 m
        Te = 8 s
    """

    hs = 2.0
    te = 8.0

    expected_w_per_m = (
        (
            SEAWATER_DENSITY_KG_M3
            * GRAVITY_MS2 ** 2
        )
        / (
            64.0 * math.pi
        )
        * hs ** 2
        * te
    )

    expected_kw_per_m = (
        expected_w_per_m
        / 1000.0
    )

    result = (
        calculate_wave_power_flux_kw_per_m(
            significant_wave_height_m=hs,
            energy_period_s=te,
        )
    )

    assert result == pytest.approx(
        expected_kw_per_m,
        rel=1e-12,
    )


def test_wave_flux_is_about_15_7_kw_per_m():
    """
    For approximately:

        Hs = 2 m
        Te = 8 s

    wave power should be about 15.7 kW/m.
    """

    result = (
        calculate_wave_power_flux_kw_per_m(
            significant_wave_height_m=2.0,
            energy_period_s=8.0,
        )
    )

    assert result == pytest.approx(
        15.7,
        rel=0.02,
    )


def test_zero_wave_height_has_zero_power_flux():

    result = (
        calculate_wave_power_flux_kw_per_m(
            significant_wave_height_m=0.0,
            energy_period_s=8.0,
        )
    )

    assert result == pytest.approx(
        0.0
    )


# ============================================================
# NONLINEAR WAVE-HEIGHT EFFECT
# ============================================================

def test_doubling_wave_height_quadruples_power():
    """
    Since:

        J ∝ Hs²

    doubling Hs should multiply wave power by 4
    when Te remains fixed.
    """

    small = (
        calculate_wave_power_flux_kw_per_m(
            significant_wave_height_m=1.0,
            energy_period_s=8.0,
        )
    )

    large = (
        calculate_wave_power_flux_kw_per_m(
            significant_wave_height_m=2.0,
            energy_period_s=8.0,
        )
    )

    assert large == pytest.approx(
        small * 4.0,
        rel=1e-12,
    )


def test_doubling_energy_period_doubles_wave_power():
    """
    Since:

        J ∝ Te

    doubling energy period doubles wave power
    if Hs remains fixed.
    """

    short = (
        calculate_wave_power_flux_kw_per_m(
            significant_wave_height_m=2.0,
            energy_period_s=5.0,
        )
    )

    long = (
        calculate_wave_power_flux_kw_per_m(
            significant_wave_height_m=2.0,
            energy_period_s=10.0,
        )
    )

    assert long == pytest.approx(
        short * 2.0,
        rel=1e-12,
    )


# ============================================================
# CAPTURE WIDTH
# ============================================================

def test_captured_power_is_flux_times_width():
    """
    15 kW/m across an effective 20 m capture width:

        P = 15 * 20
          = 300 kW
    """

    result = (
        calculate_captured_wave_power_kw(
            wave_power_flux_kw_per_m=15.0,
            capture_width_m=20.0,
        )
    )

    assert result == pytest.approx(
        300.0
    )


# ============================================================
# DEVICE POWER
# ============================================================

def test_wave_device_power_before_rated_limit(
    wave_config: WaveConfig,
):
    """
    Suppose wave flux is:

        15 kW/m

    Capture width:

        20 m

    Mechanical captured power:

        15 * 20
        = 300 kW

    Electrical conversion:

        300 * 0.80
        = 240 kW

    Availability:

        240 * 0.90
        = 216 kW

        = 0.216 MW
    """

    result = (
        calculate_wave_device_power_mw(
            wave_power_flux_kw_per_m=15.0,
            config=wave_config,
        )
    )

    assert result == pytest.approx(
        0.216,
        rel=1e-12,
    )


def test_wave_device_power_is_capped_at_rated_power(
    wave_config: WaveConfig,
):
    """
    Very large wave flux could mathematically imply
    electrical output above rated power.

    Device should be capped first at:

        1 MW

    then availability gives:

        1 * 0.90
        = 0.90 MW.
    """

    result = (
        calculate_wave_device_power_mw(
            wave_power_flux_kw_per_m=1000.0,
            config=wave_config,
        )
    )

    assert result == pytest.approx(
        0.90,
        rel=1e-12,
    )


# ============================================================
# DEVICE COUNT
# ============================================================

def test_wave_device_count():
    """
    10 MW project using 1 MW devices:

        N = 10 / 1 = 10
    """

    result = (
        calculate_wave_device_count(
            project_capacity_mw=10.0,
            device_rated_power_mw=1.0,
        )
    )

    assert result == pytest.approx(
        10.0
    )


def test_fractional_equivalent_wave_device_count():

    result = (
        calculate_wave_device_count(
            project_capacity_mw=12.5,
            device_rated_power_mw=1.0,
        )
    )

    assert result == pytest.approx(
        12.5
    )


# ============================================================
# PROJECT POWER
# ============================================================

def test_project_power_at_device_rated_conditions(
    wave_config: WaveConfig,
):
    """
    If every 1 MW device reaches rated power,
    availability reduces expected output to 90%.

    Therefore a 10 MW farm becomes:

        9 MW expected output.
    """

    result = (
        calculate_project_wave_power_mw(
            significant_wave_height_m=10.0,
            energy_period_s=12.0,
            project_capacity_mw=10.0,
            config=wave_config,
        )
    )

    assert result == pytest.approx(
        9.0,
        rel=1e-12,
    )


def test_wave_project_never_exceeds_capacity(
    wave_config: WaveConfig,
):

    result = (
        calculate_project_wave_power_mw(
            significant_wave_height_m=20.0,
            energy_period_s=20.0,
            project_capacity_mw=10.0,
            config=wave_config,
        )
    )

    assert result <= 10.0


# ============================================================
# SYNTHETIC RESOURCE HELPER
# ============================================================

def _build_wave_resource(
    location: Location,
    sea_states: tuple[
        tuple[float, float],
        ...
    ],
    time_step_hours: int = 3,
) -> WaveResourceSeries:
    """
    sea_states:

        (
            (Hs, Te),
            (Hs, Te),
            ...
        )
    """

    start = datetime(
        2025,
        1,
        1,
        0,
        0,
        tzinfo=timezone.utc,
    )

    points = tuple(

        WaveResourcePoint(

            timestamp=(
                start
                + timedelta(
                    hours=(
                        index
                        * time_step_hours
                    )
                )
            ),

            significant_wave_height_m=hs,

            energy_period_s=te,

            wave_direction_deg=180.0,
        )

        for index, (
            hs,
            te,
        ) in enumerate(
            sea_states
        )
    )

    metadata = ResourceMetadata(
        source_name="Unit Test",
        dataset_name="Synthetic Wave Data",
        retrieved_at=datetime.now(
            timezone.utc
        ),
    )

    return WaveResourceSeries(
        location=location,
        metadata=metadata,
        points=points,
        water_depth_m=100.0,
    )


# ============================================================
# FULL WAVE SIMULATION
# ============================================================

def test_simulate_wave_energy_integration(
    wave_project: ProjectScenario,
    wave_config: WaveConfig,
    location: Location,
):
    """
    Use four identical 3-hour sea states.

    We calculate the expected project power separately,
    then:

        E = P * total time

          = P * 12 hours
    """

    resource = (
        _build_wave_resource(
            location=location,
            sea_states=(
                (2.0, 8.0),
                (2.0, 8.0),
                (2.0, 8.0),
                (2.0, 8.0),
            ),
        )
    )

    expected_power_mw = (
        calculate_project_wave_power_mw(
            significant_wave_height_m=2.0,
            energy_period_s=8.0,
            project_capacity_mw=10.0,
            config=wave_config,
        )
    )

    expected_energy_mwh = (
        expected_power_mw
        * 12.0
    )

    result = simulate_wave(
        scenario=wave_project,
        resource=resource,
    )

    assert (
        result.total_generation_mwh
        == pytest.approx(
            expected_energy_mwh,
            rel=1e-12,
        )
    )


def test_wave_capacity_factor(
    wave_project: ProjectScenario,
    location: Location,
):
    """
    At extremely energetic conditions, each interval
    should reach 90% expected project output because
    availability is 0.90.

    Therefore capacity factor should approach 0.90.
    """

    resource = (
        _build_wave_resource(
            location=location,
            sea_states=(
                (10.0, 12.0),
                (10.0, 12.0),
                (10.0, 12.0),
                (10.0, 12.0),
            ),
        )
    )

    result = simulate_wave(
        scenario=wave_project,
        resource=resource,
    )

    assert result.capacity_factor == pytest.approx(
        0.90,
        rel=1e-12,
    )


# ============================================================
# LOCATION VALIDATION
# ============================================================

def test_wave_resource_location_must_match_project(
    wave_project: ProjectScenario,
):

    wrong_location = Location(
        name="Wrong Offshore Site",
        latitude=20.0,
        longitude=60.0,
    )

    resource = (
        _build_wave_resource(
            location=wrong_location,
            sea_states=(
                (2.0, 8.0),
                (2.0, 8.0),
            ),
        )
    )

    with pytest.raises(
        ValueError
    ):

        simulate_wave(
            scenario=wave_project,
            resource=resource,
        )


# ============================================================
# INVALID PHYSICAL INPUTS
# ============================================================

def test_negative_wave_height_rejected():

    with pytest.raises(
        ValueError
    ):

        calculate_wave_power_flux_kw_per_m(
            significant_wave_height_m=-1.0,
            energy_period_s=8.0,
        )


def test_zero_wave_period_rejected():

    with pytest.raises(
        ValueError
    ):

        calculate_wave_power_flux_kw_per_m(
            significant_wave_height_m=2.0,
            energy_period_s=0.0,
        )