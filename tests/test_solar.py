# tests/test_solar.py

from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from core.models import (
    FinancialInputs,
    Location,
    ProjectScenario,
    SolarConfig,
    Technology,
)

from core.resources import (
    ResourceMetadata,
    SolarResourcePoint,
    SolarResourceSeries,
)

from physics.solar import (
    SolarIrradianceMode,
    SolarTemperatureMode,
    calculate_solar_power_mw,
    simulate_solar,
)


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def location() -> Location:

    return Location(
        name="Test Solar Site",
        latitude=30.0,
        longitude=70.0,
    )


@pytest.fixture
def solar_config() -> SolarConfig:
    """
    Simplified PV configuration.

    Important:

        azimuth = 180°

    means SOUTH under our simulator convention.
    """

    return SolarConfig(
        tilt_deg=30.0,
        azimuth_deg=180.0,
        system_losses=0.14,
        reference_irradiance_wm2=1000.0,
        reference_cell_temperature_c=25.0,
        temperature_coefficient_per_c=-0.004,
    )


@pytest.fixture
def finance() -> FinancialInputs:

    return FinancialInputs(
        capex_per_kw=700.0,
        fixed_opex_per_kw_year=12.0,
        variable_opex_per_mwh=0.0,
        electricity_price_per_mwh=60.0,
        discount_rate=0.10,
    )


@pytest.fixture
def solar_project(
    location: Location,
    solar_config: SolarConfig,
    finance: FinancialInputs,
) -> ProjectScenario:

    return ProjectScenario(
        scenario_id="SOLAR_TEST_001",
        technology=Technology.SOLAR,
        location=location,
        capacity_mw=100.0,
        lifetime_years=25,
        annual_degradation_rate=0.005,
        finance=finance,
        technology_config=solar_config,
    )


# ============================================================
# BASIC RATED-POWER MODEL
# ============================================================

def test_reference_irradiance_without_losses():
    """
    If:

        P_rated = 100 MW
        G = G_ref = 1000 W/m²
        temperature factor = 1
        losses = 0

    then:

        P = 100 MW.
    """

    config = SolarConfig(
        tilt_deg=30.0,
        azimuth_deg=180.0,
        system_losses=0.0,
    )

    result = (
        calculate_solar_power_mw(
            installed_capacity_mw=100.0,
            irradiance_wm2=1000.0,
            config=config,
            temperature_factor=1.0,
        )
    )

    assert result == pytest.approx(
        100.0,
        rel=1e-12,
    )


def test_reference_irradiance_with_14_percent_losses(
    solar_config: SolarConfig,
):
    """
    Formula:

        P =
            100 MW
            * (1000 / 1000)
            * 1
            * (1 - 0.14)

        = 86 MW.
    """

    result = (
        calculate_solar_power_mw(
            installed_capacity_mw=100.0,
            irradiance_wm2=1000.0,
            config=solar_config,
            temperature_factor=1.0,
        )
    )

    assert result == pytest.approx(
        86.0,
        rel=1e-12,
    )


# ============================================================
# IRRADIANCE SCALING
# ============================================================

def test_half_reference_irradiance_halves_pre_loss_power(
    solar_config: SolarConfig,
):
    """
    With:

        G = 500 W/m²
        Gref = 1000 W/m²

    irradiance ratio = 0.5.

    Therefore:

        P =
            100 * 0.5 * 0.86
            = 43 MW.
    """

    result = (
        calculate_solar_power_mw(
            installed_capacity_mw=100.0,
            irradiance_wm2=500.0,
            config=solar_config,
            temperature_factor=1.0,
        )
    )

    assert result == pytest.approx(
        43.0,
        rel=1e-12,
    )


def test_zero_irradiance_produces_zero_power(
    solar_config: SolarConfig,
):

    result = (
        calculate_solar_power_mw(
            installed_capacity_mw=100.0,
            irradiance_wm2=0.0,
            config=solar_config,
            temperature_factor=1.0,
        )
    )

    assert result == pytest.approx(
        0.0
    )


# ============================================================
# RATED POWER CAP
# ============================================================

def test_solar_power_cannot_exceed_installed_capacity():
    """
    If irradiance is extremely high and losses are zero,
    the simplified model must still cap output at
    installed rated capacity.
    """

    config = SolarConfig(
        tilt_deg=30.0,
        azimuth_deg=180.0,
        system_losses=0.0,
    )

    result = (
        calculate_solar_power_mw(
            installed_capacity_mw=100.0,
            irradiance_wm2=1500.0,
            config=config,
            temperature_factor=1.0,
        )
    )

    assert result == pytest.approx(
        100.0,
        rel=1e-12,
    )


# ============================================================
# TEMPERATURE PHYSICS
# ============================================================

def test_hot_cell_temperature_reduces_power(
    solar_project: ProjectScenario,
    location: Location,
):
    """
    Temperature coefficient:

        gamma = -0.004 / °C

    At:

        Tcell = 45°C

    relative to:

        Tref = 25°C

    temperature difference:

        20°C

    factor:

        1 + (-0.004 * 20)

        = 0.92

    So hot-cell output should be lower.
    """

    normal_resource = (
        _build_solar_resource(
            location=location,
            irradiances_wm2=(
                1000.0,
                1000.0,
            ),
            cell_temperature_c=25.0,
        )
    )

    hot_resource = (
        _build_solar_resource(
            location=location,
            irradiances_wm2=(
                1000.0,
                1000.0,
            ),
            cell_temperature_c=45.0,
        )
    )

    normal = simulate_solar(
        scenario=solar_project,
        resource=normal_resource,
        irradiance_mode=(
            SolarIrradianceMode.POA_ONLY
        ),
        temperature_mode=(
            SolarTemperatureMode.CELL_TEMPERATURE
        ),
    )

    hot = simulate_solar(
        scenario=solar_project,
        resource=hot_resource,
        irradiance_mode=(
            SolarIrradianceMode.POA_ONLY
        ),
        temperature_mode=(
            SolarTemperatureMode.CELL_TEMPERATURE
        ),
    )

    assert (
        hot.total_generation_mwh
        <
        normal.total_generation_mwh
    )


def test_temperature_factor_expected_ratio(
    solar_project: ProjectScenario,
    location: Location,
):
    """
    At 45°C:

        f_T = 0.92

    Both cases are below clipping in this test,
    so generation ratio should also be 0.92.
    """

    cool = (
        _build_solar_resource(
            location=location,
            irradiances_wm2=(
                500.0,
                500.0,
            ),
            cell_temperature_c=25.0,
        )
    )

    hot = (
        _build_solar_resource(
            location=location,
            irradiances_wm2=(
                500.0,
                500.0,
            ),
            cell_temperature_c=45.0,
        )
    )

    cool_result = simulate_solar(
        scenario=solar_project,
        resource=cool,
        irradiance_mode=(
            SolarIrradianceMode.POA_ONLY
        ),
        temperature_mode=(
            SolarTemperatureMode.CELL_TEMPERATURE
        ),
    )

    hot_result = simulate_solar(
        scenario=solar_project,
        resource=hot,
        irradiance_mode=(
            SolarIrradianceMode.POA_ONLY
        ),
        temperature_mode=(
            SolarTemperatureMode.CELL_TEMPERATURE
        ),
    )

    ratio = (
        hot_result.total_generation_mwh
        / cool_result.total_generation_mwh
    )

    assert ratio == pytest.approx(
        0.92,
        rel=1e-12,
    )


# ============================================================
# SYNTHETIC RESOURCE HELPER
# ============================================================

def _build_solar_resource(
    location: Location,
    irradiances_wm2: tuple[
        float,
        ...
    ],
    *,
    time_step_hours: int = 1,
    cell_temperature_c: float | None = None,
    ambient_temperature_c: float | None = None,
    use_poa: bool = True,
) -> SolarResourceSeries:
    """
    Build a simple synthetic solar time series.

    If use_poa=True:
        supplied irradiance is written to both GHI and POA.

    If use_poa=False:
        supplied irradiance is available only as GHI.
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

        SolarResourcePoint(

            timestamp=(
                start
                + timedelta(
                    hours=(
                        index
                        * time_step_hours
                    )
                )
            ),

            ghi_wm2=irradiance,

            poa_irradiance_wm2=(
                irradiance
                if use_poa
                else None
            ),

            ambient_temperature_c=(
                ambient_temperature_c
            ),

            cell_temperature_c=(
                cell_temperature_c
            ),
        )

        for index, irradiance
        in enumerate(
            irradiances_wm2
        )
    )

    metadata = ResourceMetadata(
        source_name="Unit Test",
        dataset_name="Synthetic Solar Data",
        retrieved_at=datetime.now(
            timezone.utc
        ),
    )

    return SolarResourceSeries(
        location=location,
        metadata=metadata,
        points=points,
    )


# ============================================================
# FULL ENERGY INTEGRATION
# ============================================================

def test_simulate_solar_energy_integration(
    solar_project: ProjectScenario,
    location: Location,
):
    """
    Four one-hour observations at:

        POA = 500 W/m²

    Power:

        P =
            100
            * 500/1000
            * (1 - 0.14)

        = 43 MW

    Energy:

        E =
            43 MW
            * 4 h

        = 172 MWh.
    """

    resource = (
        _build_solar_resource(
            location=location,
            irradiances_wm2=(
                500.0,
                500.0,
                500.0,
                500.0,
            ),
        )
    )

    result = simulate_solar(
        scenario=solar_project,
        resource=resource,
        irradiance_mode=(
            SolarIrradianceMode.POA_ONLY
        ),
        temperature_mode=(
            SolarTemperatureMode.IGNORE
        ),
    )

    assert (
        result.total_generation_mwh
        == pytest.approx(
            172.0,
            rel=1e-12,
        )
    )

    assert (
        result.power_by_interval_mw
        == pytest.approx(
            (
                43.0,
                43.0,
                43.0,
                43.0,
            )
        )
    )

# ============================================================
# CAPACITY FACTOR
# ============================================================

def test_solar_capacity_factor(
    solar_project: ProjectScenario,
    location: Location,
):
    """
    Four hours at 500 W/m² give:

        E = 172 MWh

    Maximum possible:

        100 MW * 4 h
        = 400 MWh

    Therefore:

        CF = 172 / 400
           = 0.43
    """

    resource = (
        _build_solar_resource(
            location=location,
            irradiances_wm2=(
                500.0,
                500.0,
                500.0,
                500.0,
            ),
        )
    )

    result = simulate_solar(
        scenario=solar_project,
        resource=resource,
        irradiance_mode=(
            SolarIrradianceMode.POA_ONLY
        ),
        temperature_mode=(
            SolarTemperatureMode.IGNORE
        ),
    )

    assert result.capacity_factor == pytest.approx(
        0.43,
        rel=1e-12,
    )


# ============================================================
# TIME-STEP HANDLING
# ============================================================

def test_three_hour_solar_intervals(
    solar_project: ProjectScenario,
    location: Location,
):
    """
    Two observations separated by 3 hours.

    Power at each point:

        43 MW

    Represented duration:

        2 * 3
        = 6 hours

    Energy:

        43 * 6
        = 258 MWh.
    """

    resource = (
        _build_solar_resource(
            location=location,
            irradiances_wm2=(
                500.0,
                500.0,
            ),
            time_step_hours=3,
        )
    )

    result = simulate_solar(
        scenario=solar_project,
        resource=resource,
        irradiance_mode=(
            SolarIrradianceMode.POA_ONLY
        ),
        temperature_mode=(
            SolarTemperatureMode.IGNORE
        ),
    )

    assert result.time_step_hours == pytest.approx(
        3.0
    )

    assert (
        result.total_generation_mwh
        == pytest.approx(
            258.0,
            rel=1e-12,
        )
    )


# ============================================================
# POA VS GHI
# ============================================================

def test_auto_mode_prefers_complete_poa(
    solar_project: ProjectScenario,
    location: Location,
):
    """
    AUTO should use POA when POA exists for the
    complete resource series.
    """

    start = datetime(
        2025,
        1,
        1,
        tzinfo=timezone.utc,
    )

    points = (

        SolarResourcePoint(
            timestamp=start,
            ghi_wm2=500.0,
            poa_irradiance_wm2=800.0,
        ),

        SolarResourcePoint(
            timestamp=(
                start
                + timedelta(hours=1)
            ),
            ghi_wm2=500.0,
            poa_irradiance_wm2=800.0,
        ),
    )

    resource = SolarResourceSeries(

        location=location,

        metadata=ResourceMetadata(
            source_name="Unit Test",
            dataset_name="POA Preference Test",
            retrieved_at=datetime.now(
                timezone.utc
            ),
        ),

        points=points,
    )

    result = simulate_solar(
        scenario=solar_project,
        resource=resource,
        irradiance_mode=(
            SolarIrradianceMode.AUTO
        ),
        temperature_mode=(
            SolarTemperatureMode.IGNORE
        ),
    )

    # 100 MW * 0.8 * 0.86
    expected_power = 68.8

    assert (
        result.power_by_interval_mw
        == pytest.approx(
            (
                expected_power,
                expected_power,
            )
        )
    )


def test_ghi_fallback_when_poa_missing(
    solar_project: ProjectScenario,
    location: Location,
):
    """
    If POA is unavailable, AUTO should fall back to
    the simplified GHI approximation.
    """

    resource = (
        _build_solar_resource(
            location=location,
            irradiances_wm2=(
                500.0,
                500.0,
            ),
            use_poa=False,
        )
    )

    result = simulate_solar(
        scenario=solar_project,
        resource=resource,
        irradiance_mode=(
            SolarIrradianceMode.AUTO
        ),
        temperature_mode=(
            SolarTemperatureMode.IGNORE
        ),
    )

    assert (
        result.total_generation_mwh
        > 0
    )

    assert any(
        "GHI" in warning
        or "ghi" in warning
        for warning in result.warnings
    )


# ============================================================
# AMBIENT TEMPERATURE MUST NOT BECOME CELL TEMPERATURE
# ============================================================

def test_ambient_temperature_is_not_used_as_cell_temperature(
    solar_project: ProjectScenario,
    location: Location,
):
    """
    A central modelling rule:

        ambient temperature != PV cell temperature.

    If only ambient temperature exists, AUTO should not
    silently treat it as cell temperature.
    """

    resource = (
        _build_solar_resource(
            location=location,
            irradiances_wm2=(
                500.0,
                500.0,
            ),
            ambient_temperature_c=50.0,
            cell_temperature_c=None,
        )
    )

    result = simulate_solar(
        scenario=solar_project,
        resource=resource,
        irradiance_mode=(
            SolarIrradianceMode.POA_ONLY
        ),
        temperature_mode=(
            SolarTemperatureMode.AUTO
        ),
    )

    expected_power = (
        100.0
        * 0.5
        * 0.86
    )

    assert (
        result.power_by_interval_mw
        == pytest.approx(
            (
                expected_power,
                expected_power,
            )
        )
    )

    assert any(
        "temperature" in warning.lower()
        and "not applied" in warning.lower()
        for warning in result.warnings
    )


# ============================================================
# NIGHT / ZERO RESOURCE
# ============================================================

def test_zero_solar_resource_has_zero_generation(
    solar_project: ProjectScenario,
    location: Location,
):

    resource = (
        _build_solar_resource(
            location=location,
            irradiances_wm2=(
                0.0,
                0.0,
                0.0,
                0.0,
            ),
        )
    )

    result = simulate_solar(
        scenario=solar_project,
        resource=resource,
        irradiance_mode=(
            SolarIrradianceMode.POA_ONLY
        ),
        temperature_mode=(
            SolarTemperatureMode.IGNORE
        ),
    )

    assert result.total_generation_mwh == pytest.approx(
        0.0
    )

    assert result.capacity_factor == pytest.approx(
        0.0
    )


# ============================================================
# LOCATION VALIDATION
# ============================================================

def test_solar_resource_location_must_match_project(
    solar_project: ProjectScenario,
):

    wrong_location = Location(
        name="Wrong Solar Site",
        latitude=35.0,
        longitude=75.0,
    )

    resource = (
        _build_solar_resource(
            location=wrong_location,
            irradiances_wm2=(
                500.0,
                500.0,
            ),
        )
    )

    with pytest.raises(
        ValueError
    ):

        simulate_solar(
            scenario=solar_project,
            resource=resource,
        )


# ============================================================
# AZIMUTH CONVENTION
# ============================================================

def test_solar_azimuth_convention_accepts_south():

    config = SolarConfig(
        tilt_deg=30.0,
        azimuth_deg=180.0,
    )

    assert config.azimuth_deg == pytest.approx(
        180.0
    )


def test_invalid_azimuth_rejected():

    with pytest.raises(
        ValueError
    ):

        SolarConfig(
            tilt_deg=30.0,
            azimuth_deg=360.0,
        )


def test_invalid_tilt_rejected():

    with pytest.raises(
        ValueError
    ):

        SolarConfig(
            tilt_deg=95.0,
            azimuth_deg=180.0,
        )
