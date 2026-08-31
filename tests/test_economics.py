# tests/test_economics.py

from __future__ import annotations

import math

import pytest

from core.models import (
    FinancialInputs,
    Location,
    ProjectScenario,
    SolarConfig,
    Technology,
)

from finance.economics import (
    analyze_project_financials,
    calculate_initial_capex_usd,
    calculate_irr,
    calculate_npv,
)


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def project() -> ProjectScenario:
    """
    Simple 100 MW project used for transparent
    hand calculations.
    """

    return ProjectScenario(

        scenario_id="FINANCE_TEST_001",

        technology=Technology.SOLAR,

        location=Location(
            name="Test Site",
            latitude=30.0,
            longitude=70.0,
        ),

        capacity_mw=100.0,

        lifetime_years=20,

        annual_degradation_rate=0.0,

        finance=FinancialInputs(

            capex_per_kw=700.0,

            fixed_opex_per_kw_year=12.0,

            variable_opex_per_mwh=0.0,

            electricity_price_per_mwh=60.0,

            discount_rate=0.10,

            electricity_price_growth_rate=0.0,

            opex_growth_rate=0.0,
        ),

        technology_config=SolarConfig(
            tilt_deg=30.0,
            azimuth_deg=180.0,
        ),
    )


@pytest.fixture
def constant_generation() -> tuple[float, ...]:
    """
    100 MW project at 25% capacity factor:

        E =
            100 MW
            * 8760 h
            * 0.25

        = 219,000 MWh/year.
    """

    return tuple(
        219_000.0
        for _ in range(20)
    )


# ============================================================
# CAPEX
# ============================================================

def test_initial_capex(
    project: ProjectScenario,
):
    """
    100 MW = 100,000 kW

    CAPEX:

        100,000 kW
        * $700/kW

        = $70,000,000
    """

    result = (
        calculate_initial_capex_usd(
            project
        )
    )

    assert result == pytest.approx(
        70_000_000.0,
        rel=1e-12,
    )


# ============================================================
# BASIC NPV
# ============================================================

def test_npv_manual_two_period_example():
    """
    Cash flows:

        t0 = -100
        t1 = +60
        t2 = +60

    r = 10%

    NPV =
        -100
        + 60/1.1
        + 60/1.1²

        ≈ 4.13223
    """

    result = calculate_npv(

        cash_flows=(
            -100.0,
            60.0,
            60.0,
        ),

        discount_rate=0.10,
    )

    expected = (
        -100.0
        + 60.0 / 1.10
        + 60.0 / (1.10 ** 2)
    )

    assert result == pytest.approx(
        expected,
        rel=1e-12,
    )


def test_npv_at_zero_discount_rate():
    """
    At r = 0:

        NPV = simple sum of cash flows.
    """

    result = calculate_npv(

        cash_flows=(
            -100.0,
            50.0,
            60.0,
        ),

        discount_rate=0.0,
    )

    assert result == pytest.approx(
        10.0
    )


# ============================================================
# IRR
# ============================================================

def test_irr_simple_one_year_example():
    """
    Investment:

        t0 = -100
        t1 = +110

    Solve:

        -100 + 110/(1+r) = 0

    therefore:

        r = 10%
    """

    result = calculate_irr(
        cash_flows=(
            -100.0,
            110.0,
        )
    )

    assert result is not None

    assert result == pytest.approx(
        0.10,
        rel=1e-8,
    )


def test_irr_requires_positive_and_negative_cash_flow():

    result = calculate_irr(
        cash_flows=(
            10.0,
            20.0,
            30.0,
        )
    )

    assert result is None


def test_irr_multiple_sign_changes_returns_none():
    """
    Our IRR implementation deliberately avoids
    ambiguous multiple-IRR cases.

    Example:

        -100
        +230
        -132

    has more than one sign change.
    """

    result = calculate_irr(
        cash_flows=(
            -100.0,
            230.0,
            -132.0,
        )
    )

    assert result is None


# ============================================================
# COMPLETE 100 MW PROJECT
# ============================================================

def test_project_financial_analysis(
    project: ProjectScenario,
    constant_generation: tuple[float, ...],
):
    """
    Baseline:

        Capacity:
            100 MW

        Annual generation:
            219,000 MWh

        CAPEX:
            $70m

        Fixed OPEX:
            100,000 kW
            * $12/kW/year
            = $1.2m/year

        Revenue:
            219,000
            * $60/MWh
            = $13.14m/year

        Operating cash flow:
            13.14 - 1.20
            = $11.94m/year
    """

    analysis = (
        analyze_project_financials(

            project=project,

            generation_by_year_mwh=(
                constant_generation
            ),
        )
    )

    metrics = analysis.metrics

    assert metrics.initial_capex_usd == pytest.approx(
        70_000_000.0
    )

    assert (
        metrics.lifetime_generation_mwh
        == pytest.approx(
            4_380_000.0
        )
    )

    assert (
        metrics.lifetime_revenue_usd
        == pytest.approx(
            262_800_000.0
        )
    )

    assert (
        metrics.lifetime_opex_usd
        == pytest.approx(
            24_000_000.0
        )
    )


# ============================================================
# FIRST CASH-FLOW ROW
# ============================================================

def test_year_zero_contains_initial_capex(
    project: ProjectScenario,
    constant_generation: tuple[float, ...],
):

    analysis = (
        analyze_project_financials(
            project=project,
            generation_by_year_mwh=(
                constant_generation
            ),
        )
    )

    year_zero = (
        analysis.cash_flows[0]
    )

    assert year_zero.year == 0

    assert year_zero.capital_cost_usd == pytest.approx(
        70_000_000.0
    )

    assert year_zero.net_cash_flow_usd == pytest.approx(
        -70_000_000.0
    )


# ============================================================
# YEAR 1 CASH FLOW
# ============================================================

def test_first_operating_year_cash_flow(
    project: ProjectScenario,
    constant_generation: tuple[float, ...],
):
    """
    Revenue:

        219000 * 60
        = $13.14m

    Fixed OPEX:

        100000 * 12
        = $1.2m

    Variable OPEX:

        zero

    Net:

        13.14m - 1.2m
        = $11.94m
    """

    analysis = (
        analyze_project_financials(
            project=project,
            generation_by_year_mwh=(
                constant_generation
            ),
        )
    )

    year_one = (
        analysis.cash_flows[1]
    )

    assert year_one.year == 1

    assert year_one.generation_mwh == pytest.approx(
        219_000.0
    )

    assert (
        year_one.electricity_price_per_mwh
        == pytest.approx(
            60.0
        )
    )

    assert year_one.revenue_usd == pytest.approx(
        13_140_000.0
    )

    assert year_one.fixed_opex_usd == pytest.approx(
        1_200_000.0
    )

    assert year_one.variable_opex_usd == pytest.approx(
        0.0
    )

    assert year_one.net_cash_flow_usd == pytest.approx(
        11_940_000.0
    )


# ============================================================
# NPV OF FULL PROJECT
# ============================================================

def test_project_npv_matches_manual_discounting(
    project: ProjectScenario,
    constant_generation: tuple[float, ...],
):
    """
    Every operating year produces:

        $11.94m

    for 20 years.

    Manually:

        NPV =
            -70m
            + sum(
                11.94m / 1.1^t
            )
    """

    analysis = (
        analyze_project_financials(
            project=project,
            generation_by_year_mwh=(
                constant_generation
            ),
        )
    )

    expected_npv = (
        -70_000_000.0
        + math.fsum(

            11_940_000.0
            / (
                1.10 ** year
            )

            for year in range(
                1,
                21,
            )
        )
    )

    assert analysis.metrics.npv_usd == pytest.approx(
        expected_npv,
        rel=1e-10,
    )


# ============================================================
# IRR OF FULL PROJECT
# ============================================================

def test_project_irr_is_about_16_21_percent(
    project: ProjectScenario,
    constant_generation: tuple[float, ...],
):

    analysis = (
        analyze_project_financials(
            project=project,
            generation_by_year_mwh=(
                constant_generation
            ),
        )
    )

    assert analysis.metrics.irr is not None

    # Solves 70 / 11.94 = (1 - (1 + r) ** -20) / r.
    assert analysis.metrics.irr == pytest.approx(
        0.162120987,
        abs=1e-8,
    )


# ============================================================
# SIMPLE PAYBACK
# ============================================================

def test_simple_payback(
    project: ProjectScenario,
    constant_generation: tuple[float, ...],
):
    """
    Initial investment:

        $70m

    yearly operating cash flow:

        $11.94m

    Simple payback:

        70 / 11.94

        ≈ 5.86265 years
    """

    analysis = (
        analyze_project_financials(
            project=project,
            generation_by_year_mwh=(
                constant_generation
            ),
        )
    )

    expected = (
        70_000_000.0
        / 11_940_000.0
    )

    assert (
        analysis.metrics.simple_payback_years
        == pytest.approx(
            expected,
            rel=1e-8,
        )
    )


# ============================================================
# DISCOUNTED PAYBACK
# ============================================================

def test_discounted_payback_is_longer_than_simple_payback(
    project: ProjectScenario,
    constant_generation: tuple[float, ...],
):

    analysis = (
        analyze_project_financials(
            project=project,
            generation_by_year_mwh=(
                constant_generation
            ),
        )
    )

    simple = (
        analysis.metrics
        .simple_payback_years
    )

    discounted = (
        analysis.metrics
        .discounted_payback_years
    )

    assert simple is not None
    assert discounted is not None

    assert discounted > simple


# ============================================================
# LCOE
# ============================================================

def test_lcoe_matches_discounted_cost_equation(
    project: ProjectScenario,
    constant_generation: tuple[float, ...],
):
    """
    LCOE:

        PV(costs)
        ---------
        PV(energy)

    Costs include:

        initial CAPEX
        +
        discounted OPEX.
    """

    analysis = (
        analyze_project_financials(
            project=project,
            generation_by_year_mwh=(
                constant_generation
            ),
        )
    )

    pv_opex = math.fsum(

        1_200_000.0
        / (
            1.10 ** year
        )

        for year in range(
            1,
            21,
        )
    )

    pv_generation = math.fsum(

        219_000.0
        / (
            1.10 ** year
        )

        for year in range(
            1,
            21,
        )
    )

    expected_lcoe = (
        (
            70_000_000.0
            + pv_opex
        )
        / pv_generation
    )

    assert (
        analysis.metrics.lcoe_usd_per_mwh
        == pytest.approx(
            expected_lcoe,
            rel=1e-10,
        )
    )


# ============================================================
# LCOE MUST NOT USE REVENUE
# ============================================================

def test_lcoe_independent_of_electricity_sale_price(
    project: ProjectScenario,
    constant_generation: tuple[float, ...],
):
    """
    LCOE is a cost-of-generation metric.

    Electricity selling price affects:

        revenue
        NPV
        IRR
        payback

    but NOT:

        LCOE
    """

    from dataclasses import replace

    high_price_finance = replace(
        project.finance,
        electricity_price_per_mwh=200.0,
    )

    high_price_project = replace(
        project,
        finance=high_price_finance,
    )

    baseline = (
        analyze_project_financials(
            project=project,
            generation_by_year_mwh=(
                constant_generation
            ),
        )
    )

    high_price = (
        analyze_project_financials(
            project=high_price_project,
            generation_by_year_mwh=(
                constant_generation
            ),
        )
    )

    assert (
        baseline.metrics.lcoe_usd_per_mwh
        == pytest.approx(
            high_price
            .metrics
            .lcoe_usd_per_mwh,
            rel=1e-12,
        )
    )

    assert (
        high_price.metrics.npv_usd
        >
        baseline.metrics.npv_usd
    )


# ============================================================
# VARIABLE OPEX
# ============================================================

def test_variable_opex_scales_with_generation(
    project: ProjectScenario,
    constant_generation: tuple[float, ...],
):
    """
    Set variable OPEX to:

        $5/MWh

    At:

        219,000 MWh

    expected variable OPEX:

        219000 * 5
        = $1,095,000
    """

    from dataclasses import replace

    new_finance = replace(
        project.finance,
        variable_opex_per_mwh=5.0,
    )

    modified_project = replace(
        project,
        finance=new_finance,
    )

    analysis = (
        analyze_project_financials(
            project=modified_project,
            generation_by_year_mwh=(
                constant_generation
            ),
        )
    )

    year_one = (
        analysis.cash_flows[1]
    )

    assert (
        year_one.variable_opex_usd
        == pytest.approx(
            1_095_000.0
        )
    )


# ============================================================
# ELECTRICITY PRICE GROWTH
# ============================================================

def test_electricity_price_growth(
    project: ProjectScenario,
    constant_generation: tuple[float, ...],
):
    """
    Initial price:

        $60/MWh

    Growth:

        5%

    Therefore:

        Year 1 = 60
        Year 2 = 63
        Year 3 = 66.15
    """

    from dataclasses import replace

    new_finance = replace(

        project.finance,

        electricity_price_growth_rate=0.05,
    )

    modified_project = replace(
        project,
        finance=new_finance,
    )

    analysis = (
        analyze_project_financials(
            project=modified_project,
            generation_by_year_mwh=(
                constant_generation
            ),
        )
    )

    assert (
        analysis.cash_flows[1]
        .electricity_price_per_mwh
        == pytest.approx(
            60.0
        )
    )

    assert (
        analysis.cash_flows[2]
        .electricity_price_per_mwh
        == pytest.approx(
            63.0
        )
    )

    assert (
        analysis.cash_flows[3]
        .electricity_price_per_mwh
        == pytest.approx(
            66.15
        )
    )


# ============================================================
# REPLACEMENT / ADDITIONAL CAPEX
# ============================================================

def test_additional_capex_reduces_npv(
    project: ProjectScenario,
    constant_generation: tuple[float, ...],
):
    """
    Add a $10m replacement expenditure in year 10.

    NPV must decrease relative to the baseline.
    """

    baseline = (
        analyze_project_financials(
            project=project,
            generation_by_year_mwh=(
                constant_generation
            ),
        )
    )

    replacement = (
        analyze_project_financials(

            project=project,

            generation_by_year_mwh=(
                constant_generation
            ),

            additional_capex_by_year={
                10: 10_000_000.0
            },
        )
    )

    assert (
        replacement.metrics.npv_usd
        <
        baseline.metrics.npv_usd
    )

    assert (
        replacement.metrics.additional_capex_usd
        == pytest.approx(
            10_000_000.0
        )
    )


def test_additional_capex_increases_lcoe(
    project: ProjectScenario,
    constant_generation: tuple[float, ...],
):

    baseline = (
        analyze_project_financials(
            project=project,
            generation_by_year_mwh=(
                constant_generation
            ),
        )
    )

    replacement = (
        analyze_project_financials(

            project=project,

            generation_by_year_mwh=(
                constant_generation
            ),

            additional_capex_by_year={
                10: 10_000_000.0
            },
        )
    )

    assert (
        replacement.metrics.lcoe_usd_per_mwh
        >
        baseline.metrics.lcoe_usd_per_mwh
    )


# ============================================================
# ZERO GENERATION
# ============================================================

def test_zero_generation_has_undefined_lcoe(
    project: ProjectScenario,
):

    generation = tuple(
        0.0
        for _ in range(
            project.lifetime_years
        )
    )

    analysis = (
        analyze_project_financials(
            project=project,
            generation_by_year_mwh=(
                generation
            ),
        )
    )

    assert (
        analysis.metrics
        .lcoe_usd_per_mwh
        is None
    )


# ============================================================
# GENERATION SCHEDULE VALIDATION
# ============================================================

def test_generation_schedule_must_match_lifetime(
    project: ProjectScenario,
):

    wrong_generation = (
        100_000.0,
        100_000.0,
    )

    with pytest.raises(
        ValueError
    ):

        analyze_project_financials(
            project=project,
            generation_by_year_mwh=(
                wrong_generation
            ),
        )


def test_negative_generation_rejected(
    project: ProjectScenario,
):

    generation = tuple(
        -1.0
        for _ in range(
            project.lifetime_years
        )
    )

    with pytest.raises(
        ValueError
    ):

        analyze_project_financials(
            project=project,
            generation_by_year_mwh=(
                generation
            ),
        )
