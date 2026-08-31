# tests/test_lifecycle.py

from __future__ import annotations

import pytest

from core.lifecycle import (
    apply_yearly_performance_multipliers,
    build_degradation_schedule,
    build_lifetime_generation,
    calculate_lifetime_generation_loss_mwh,
)

from core.models import (
    FinancialInputs,
    Location,
    ProjectScenario,
    SolarConfig,
    Technology,
)


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def project() -> ProjectScenario:

    return ProjectScenario(

        scenario_id="LIFECYCLE_TEST_001",

        technology=Technology.SOLAR,

        location=Location(
            name="Test Site",
            latitude=30.0,
            longitude=70.0,
        ),

        capacity_mw=100.0,

        lifetime_years=5,

        annual_degradation_rate=0.01,

        finance=FinancialInputs(
            capex_per_kw=700.0,
            fixed_opex_per_kw_year=12.0,
            variable_opex_per_mwh=0.0,
            electricity_price_per_mwh=60.0,
            discount_rate=0.10,
        ),

        technology_config=SolarConfig(
            tilt_deg=30.0,
            azimuth_deg=180.0,
        ),
    )


# ============================================================
# DEGRADATION SCHEDULE
# ============================================================

def test_degradation_schedule_starts_at_one():

    result = build_degradation_schedule(
        lifetime_years=5,
        annual_degradation_rate=0.01,
    )

    assert result[0] == pytest.approx(
        1.0
    )


def test_degradation_schedule_matches_equation():
    """
    d = 1%

    Factors should be:

        Year 1 = 1
        Year 2 = 0.99
        Year 3 = 0.99²
        Year 4 = 0.99³
        Year 5 = 0.99⁴
    """

    result = build_degradation_schedule(
        lifetime_years=5,
        annual_degradation_rate=0.01,
    )

    expected = tuple(
        0.99 ** year_index
        for year_index in range(5)
    )

    assert result == pytest.approx(
        expected,
        rel=1e-12,
    )


def test_zero_degradation_keeps_constant_factor():

    result = build_degradation_schedule(
        lifetime_years=4,
        annual_degradation_rate=0.0,
    )

    assert result == pytest.approx(
        (
            1.0,
            1.0,
            1.0,
            1.0,
        )
    )


# ============================================================
# LIFETIME GENERATION
# ============================================================

def test_lifetime_generation_matches_formula(
    project: ProjectScenario,
):
    """
    First-year generation:

        E1 = 100,000 MWh

    degradation:

        d = 1%

    Therefore:

        Year 1 = 100000
        Year 2 = 99000
        Year 3 = 98010
        Year 4 = 97029.9
        Year 5 = 96059.601
    """

    result = build_lifetime_generation(

        scenario=project,

        first_year_generation_mwh=100_000.0,
    )

    expected = (
        100_000.0,
        99_000.0,
        98_010.0,
        97_029.9,
        96_059.601,
    )

    assert result == pytest.approx(
        expected,
        rel=1e-12,
    )


def test_first_year_is_not_degraded(
    project: ProjectScenario,
):
    """
    Critical convention:

        E1 = first-year generation

    not:

        E1 * (1-d)

    because:

        E_t = E1(1-d)^(t-1)
    """

    result = build_lifetime_generation(
        scenario=project,
        first_year_generation_mwh=100_000.0,
    )

    assert result[0] == pytest.approx(
        100_000.0
    )


def test_lifetime_schedule_length_matches_project(
    project: ProjectScenario,
):

    result = build_lifetime_generation(
        scenario=project,
        first_year_generation_mwh=100_000.0,
    )

    assert len(result) == 5


def test_zero_degradation_gives_constant_generation():

    zero_degradation_project = ProjectScenario(

        scenario_id="ZERO_DEGRADATION",

        technology=Technology.SOLAR,

        location=Location(
            name="Test",
            latitude=30.0,
            longitude=70.0,
        ),

        capacity_mw=100.0,

        lifetime_years=4,

        annual_degradation_rate=0.0,

        finance=FinancialInputs(
            capex_per_kw=700,
            fixed_opex_per_kw_year=12,
            variable_opex_per_mwh=0,
            electricity_price_per_mwh=60,
            discount_rate=0.10,
        ),

        technology_config=SolarConfig(
            tilt_deg=30,
            azimuth_deg=180,
        ),
    )

    result = build_lifetime_generation(

        scenario=zero_degradation_project,

        first_year_generation_mwh=50_000.0,
    )

    assert result == pytest.approx(
        (
            50_000.0,
            50_000.0,
            50_000.0,
            50_000.0,
        )
    )


# ============================================================
# PERFORMANCE MULTIPLIERS
# ============================================================

def test_single_year_performance_multiplier():
    """
    Important semantic rule:

        {3: 0.90}

    affects ONLY year 3.

    It does not permanently reduce years 4 and 5.
    """

    generation = (
        100.0,
        99.0,
        98.0,
        97.0,
        96.0,
    )

    result = (
        apply_yearly_performance_multipliers(

            generation_by_year_mwh=(
                generation
            ),

            performance_multipliers_by_year={
                3: 0.90
            },
        )
    )

    expected = (
        100.0,
        99.0,
        88.2,
        97.0,
        96.0,
    )

    assert result == pytest.approx(
        expected,
        rel=1e-12,
    )


def test_multiple_independent_year_multipliers():

    generation = (
        100.0,
        100.0,
        100.0,
        100.0,
    )

    result = (
        apply_yearly_performance_multipliers(

            generation_by_year_mwh=(
                generation
            ),

            performance_multipliers_by_year={
                2: 0.90,
                4: 0.80,
            },
        )
    )

    assert result == pytest.approx(
        (
            100.0,
            90.0,
            100.0,
            80.0,
        )
    )


# ============================================================
# LIFETIME GENERATION LOSS
# ============================================================

def test_lifetime_generation_loss_due_to_degradation(
    project: ProjectScenario,
):
    """
    No-degradation lifetime generation:

        100000 * 5
        = 500000 MWh

    degraded generation:

        100000
        + 99000
        + 98010
        + 97029.9
        + 96059.601

        = 490099.501 MWh

    loss:

        500000 - 490099.501

        = 9900.499 MWh
    """

    result = (
        calculate_lifetime_generation_loss_mwh(

            scenario=project,

            first_year_generation_mwh=(
                100_000.0
            ),
        )
    )

    assert result == pytest.approx(
        9_900.499,
        rel=1e-9,
    )


def test_zero_degradation_has_zero_lifetime_loss():

    zero_project = ProjectScenario(

        scenario_id="NO_LOSS",

        technology=Technology.SOLAR,

        location=Location(
            name="Test",
            latitude=30,
            longitude=70,
        ),

        capacity_mw=100,

        lifetime_years=10,

        annual_degradation_rate=0.0,

        finance=FinancialInputs(
            capex_per_kw=700,
            fixed_opex_per_kw_year=12,
            variable_opex_per_mwh=0,
            electricity_price_per_mwh=60,
            discount_rate=0.10,
        ),

        technology_config=SolarConfig(
            tilt_deg=30,
            azimuth_deg=180,
        ),
    )

    loss = (
        calculate_lifetime_generation_loss_mwh(

            scenario=zero_project,

            first_year_generation_mwh=(
                100_000
            ),
        )
    )

    assert loss == pytest.approx(
        0.0
    )


# ============================================================
# INVALID INPUTS
# ============================================================

def test_negative_first_year_generation_rejected(
    project: ProjectScenario,
):

    with pytest.raises(
        ValueError
    ):

        build_lifetime_generation(

            scenario=project,

            first_year_generation_mwh=-1.0,
        )


def test_invalid_degradation_rate_rejected():

    with pytest.raises(
        ValueError
    ):

        build_degradation_schedule(

            lifetime_years=25,

            annual_degradation_rate=1.0,
        )


def test_negative_degradation_rate_rejected():

    with pytest.raises(
        ValueError
    ):

        build_degradation_schedule(

            lifetime_years=25,

            annual_degradation_rate=-0.01,
        )
