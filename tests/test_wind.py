from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.models import (
    FinancialInputs,
    Location,
    ProjectScenario,
    Technology,
    WindConfig,
)
from core.resources import (
    ResourceMetadata,
    WindResourcePoint,
    WindResourceSeries,
)
from physics.wind import (
    IEA_REFERENCE_3_4MW_POWER_CURVE_ID,
    WindDensityMode,
    calculate_project_wind_power_mw,
    calculate_turbine_power_mw,
    calculate_turbine_count,
    load_tabulated_turbine_power_curve,
    simulate_wind,
)


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def location() -> Location:
    return Location(
        name="Test Wind Site",
        latitude=24.9,
        longitude=67.1,
    )


@pytest.fixture
def wind_config() -> WindConfig:
    return WindConfig(
        hub_height_m=100.0,
        cut_in_speed_ms=3.0,
        rated_speed_ms=12.0,
        cut_out_speed_ms=25.0,
        turbine_rated_power_mw=5.0,
        availability=0.95,
        wind_shear_exponent=1.0 / 7.0,
        reference_air_density_kg_m3=1.225,
        power_curve_id=None,
    )


@pytest.fixture
def reference_curve_config() -> WindConfig:
    return WindConfig(
        hub_height_m=100.0,
        cut_in_speed_ms=3.0,
        rated_speed_ms=9.8127,
        cut_out_speed_ms=25.01,
        turbine_rated_power_mw=3.37,
        availability=1.0,
        wind_shear_exponent=1.0 / 7.0,
        reference_air_density_kg_m3=1.225,
        power_curve_id=IEA_REFERENCE_3_4MW_POWER_CURVE_ID,
    )


@pytest.fixture
def wind_project(
    location: Location,
    wind_config: WindConfig,
) -> ProjectScenario:
    return ProjectScenario(
        scenario_id="WIND_TEST_001",
        technology=Technology.WIND,
        location=location,
        capacity_mw=100.0,
        lifetime_years=25,
        annual_degradation_rate=0.005,
        finance=FinancialInputs(
            capex_per_kw=1_400.0,
            fixed_opex_per_kw_year=40.0,
            variable_opex_per_mwh=0.0,
            electricity_price_per_mwh=70.0,
            discount_rate=0.10,
        ),
        technology_config=wind_config,
    )


# ============================================================
# TURBINE COUNT
# ============================================================

def test_reference_curve_is_loaded_and_used_at_exact_point(
    reference_curve_config: WindConfig,
):
    curve = load_tabulated_turbine_power_curve(
        IEA_REFERENCE_3_4MW_POWER_CURVE_ID
    )

    assert curve.reference_rated_power_mw == pytest.approx(3.37)
    assert calculate_turbine_power_mw(
        5.3862,
        reference_curve_config,
    ) == pytest.approx(0.5608983052)


def test_reference_curve_uses_linear_interpolation(
    reference_curve_config: WindConfig,
):
    midpoint_speed = (5.3862 + 5.7654) / 2
    midpoint_power = (0.5608983052 + 0.688906312) / 2

    assert calculate_turbine_power_mw(
        midpoint_speed,
        reference_curve_config,
    ) == pytest.approx(midpoint_power)


def test_reference_curve_respects_cut_out_boundary(
    reference_curve_config: WindConfig,
):
    assert calculate_turbine_power_mw(25.0, reference_curve_config) == pytest.approx(3.37)
    assert calculate_turbine_power_mw(25.01, reference_curve_config) == 0.0


def test_cubic_curve_remains_available_only_as_fallback(
    wind_config: WindConfig,
):
    expected = 5.0 * (7.0**3 - 3.0**3) / (12.0**3 - 3.0**3) * 0.95

    assert wind_config.power_curve_id is None
    assert calculate_turbine_power_mw(7.0, wind_config) == pytest.approx(expected)


def test_unknown_reference_curve_is_rejected():
    with pytest.raises(ValueError, match="Unsupported wind power curve"):
        load_tabulated_turbine_power_curve("unknown")

def test_turbine_count():
    """
    100 MW project / 5 MW turbine = 20 turbines.
    """

    result = (
        calculate_turbine_count(
            project_capacity_mw=100.0,
            turbine_rated_power_mw=5.0,
        )
    )

    assert result == pytest.approx(
        20.0
    )


def test_fractional_equivalent_turbine_count():
    """
    Continuous capacity is intentional in the
    screening model.

        102.5 MW / 5 MW = 20.5

    A later engineering-layout mode can enforce
    whole turbine counts.
    """

    result = (
        calculate_turbine_count(
            project_capacity_mw=102.5,
            turbine_rated_power_mw=5.0,
        )
    )

    assert result == pytest.approx(
        20.5
    )


# ============================================================
# PROJECT POWER
# ============================================================

def test_100mw_project_at_rated_wind(
    wind_config: WindConfig,
):
    """
    100 MW project at rated wind:

        physical project output = 100 MW

    after 95% availability:

        expected output = 95 MW
    """

    result = (
        calculate_project_wind_power_mw(
            wind_speed_ms=12.0,
            project_capacity_mw=100.0,
            config=wind_config,
        )
    )

    assert result == pytest.approx(
        95.0,
        rel=1e-12,
    )


def test_project_power_never_exceeds_capacity(
    wind_config: WindConfig,
):
    """
    Project output must never exceed
    installed capacity.
    """

    result = (
        calculate_project_wind_power_mw(
            wind_speed_ms=12.0,
            project_capacity_mw=100.0,
            config=wind_config,
        )
    )

    assert result <= 100.0


# ============================================================
# RESOURCE-SERIES HELPER
# ============================================================

def _build_resource(
    location: Location,
    wind_speeds_ms: tuple[float, ...],
    measurement_height_m: float = 100.0,
    air_density_kg_m3: float | None = None,
) -> WindResourceSeries:
    """
    Construct an hourly wind series for simulation tests.
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

        WindResourcePoint(

            timestamp=(
                start
                + timedelta(
                    hours=index
                )
            ),

            wind_speed_ms=(
                wind_speed
            ),

            air_density_kg_m3=(
                air_density_kg_m3
            ),
        )

        for index, wind_speed
        in enumerate(
            wind_speeds_ms
        )
    )

    metadata = ResourceMetadata(

        source_name="Unit Test",

        dataset_name="Synthetic Wind Data",

        retrieved_at=datetime.now(
            timezone.utc
        ),
    )

    return WindResourceSeries(

        location=location,

        metadata=metadata,

        measurement_height_m=(
            measurement_height_m
        ),

        points=points,
    )


# ============================================================
# FULL SIMULATION TEST
# ============================================================

def test_simulate_constant_rated_wind(
    wind_project: ProjectScenario,
    location: Location,
):
    """
    Four hourly intervals, each at 12 m/s.

    At rated speed:

        project output = 95 MW

    Therefore:

        E = P * t

          = 95 MW * 4 h

          = 380 MWh

    Capacity factor:

        CF =
            380
            --------
            100 * 4

        = 0.95
    """

    resource = (
        _build_resource(

            location=location,

            wind_speeds_ms=(
                12.0,
                12.0,
                12.0,
                12.0,
            ),
        )
    )

    result = simulate_wind(

        scenario=wind_project,

        resource=resource,

        density_mode=(
            WindDensityMode.IGNORE
        ),
    )

    assert (
        result.total_generation_mwh
        == pytest.approx(
            380.0,
            rel=1e-12,
        )
    )

    assert (
        result.capacity_factor
        == pytest.approx(
            0.95,
            rel=1e-12,
        )
    )

    assert (
        result.power_by_interval_mw
        == pytest.approx(
            (
                95.0,
                95.0,
                95.0,
                95.0,
            )
        )
    )


# ============================================================
# ZERO-GENERATION SIMULATION
# ============================================================

def test_all_wind_below_cut_in_produces_zero_generation(
    wind_project: ProjectScenario,
    location: Location,
):
    resource = (
        _build_resource(

            location=location,

            wind_speeds_ms=(
                1.0,
                2.0,
                2.5,
                0.0,
            ),
        )
    )

    result = simulate_wind(

        scenario=wind_project,

        resource=resource,

        density_mode=(
            WindDensityMode.IGNORE
        ),
    )

    assert (
        result.total_generation_mwh
        == pytest.approx(
            0.0
        )
    )

    assert (
        result.capacity_factor
        == pytest.approx(
            0.0
        )
    )


# ============================================================
# CUT-OUT TEST
# ============================================================

def test_extreme_wind_causes_shutdown(
    wind_project: ProjectScenario,
    location: Location,
):
    """
    Stronger wind does not always mean more electricity.

    At or above cut-out:

        turbine output = 0.
    """

    resource = (
        _build_resource(

            location=location,

            wind_speeds_ms=(
                30.0,
                30.0,
                30.0,
                30.0,
            ),
        )
    )

    result = simulate_wind(

        scenario=wind_project,

        resource=resource,

        density_mode=(
            WindDensityMode.IGNORE
        ),
    )

    assert (
        result.total_generation_mwh
        == pytest.approx(
            0.0
        )
    )


# ============================================================
# HUB HEIGHT IN FULL SIMULATION
# ============================================================

def test_higher_hub_height_can_increase_generation(
    wind_project: ProjectScenario,
    location: Location,
):
    """
    Start with wind measured at 50 m.

    Positive shear means extrapolation to the project's
    100 m hub height should increase wind speed and,
    while still in partial-load operation, increase
    electrical generation.
    """

    resource_50m = (
        _build_resource(

            location=location,

            wind_speeds_ms=(
                7.0,
                7.0,
                7.0,
                7.0,
            ),

            measurement_height_m=50.0,
        )
    )

    # Compare with data already measured at hub height.
    resource_100m = (
        _build_resource(

            location=location,

            wind_speeds_ms=(
                7.0,
                7.0,
                7.0,
                7.0,
            ),

            measurement_height_m=100.0,
        )
    )

    extrapolated = simulate_wind(

        scenario=wind_project,

        resource=resource_50m,

        density_mode=(
            WindDensityMode.IGNORE
        ),
    )

    unchanged = simulate_wind(

        scenario=wind_project,

        resource=resource_100m,

        density_mode=(
            WindDensityMode.IGNORE
        ),
    )

    assert (
        extrapolated.total_generation_mwh
        >
        unchanged.total_generation_mwh
    )


# ============================================================
# DENSITY AUTO MODE
# ============================================================

def test_density_auto_uses_complete_density_series(
    wind_project: ProjectScenario,
    location: Location,
):
    """
    If every resource point contains air density,
    AUTO should apply density correction.

    Low density should therefore reduce partial-load
    generation.
    """

    normal_density_resource = (
        _build_resource(

            location=location,

            wind_speeds_ms=(
                8.0,
                8.0,
                8.0,
                8.0,
            ),

            air_density_kg_m3=1.225,
        )
    )

    low_density_resource = (
        _build_resource(

            location=location,

            wind_speeds_ms=(
                8.0,
                8.0,
                8.0,
                8.0,
            ),

            air_density_kg_m3=1.0,
        )
    )

    normal = simulate_wind(

        scenario=wind_project,

        resource=(
            normal_density_resource
        ),

        density_mode=(
            WindDensityMode.AUTO
        ),
    )

    low = simulate_wind(

        scenario=wind_project,

        resource=(
            low_density_resource
        ),

        density_mode=(
            WindDensityMode.AUTO
        ),
    )

    assert (
        low.total_generation_mwh
        <
        normal.total_generation_mwh
    )


# ============================================================
# LOCATION VALIDATION
# ============================================================

def test_resource_location_must_match_project(
    wind_project: ProjectScenario,
):
    wrong_location = Location(
        name="Wrong Site",
        latitude=30.0,
        longitude=70.0,
    )

    resource = (
        _build_resource(

            location=wrong_location,

            wind_speeds_ms=(
                8.0,
                8.0,
            ),
        )
    )

    with pytest.raises(
        ValueError
    ):

        simulate_wind(
            scenario=wind_project,
            resource=resource,
        )
