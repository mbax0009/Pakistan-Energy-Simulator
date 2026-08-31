from __future__ import annotations

import math

from collections.abc import Mapping, Sequence

from core.constants import KW_PER_MW
from core.models import (
    CashFlowRow,
    FinancialAnalysis,
    FinancialMetrics,
    ProjectScenario,
)


def calculate_initial_capex_usd(
    scenario: ProjectScenario,
) -> float:
    """
    Calculate initial project capital expenditure.

    capacity_mw is converted to kW because CAPEX is expressed
    in USD/kW.
    """

    capacity_kw = scenario.capacity_mw * KW_PER_MW

    return capacity_kw * scenario.finance.capex_per_kw

def _validate_generation_schedule(
    scenario: ProjectScenario,
    generation_by_year_mwh: Sequence[float],
) -> tuple[float, ...]:
    """
    Validate and normalize yearly electricity generation.

    The financial engine requires exactly one generation value
    for every operating year.
    """

    if len(generation_by_year_mwh) != scenario.lifetime_years:
        raise ValueError(
            "Generation schedule length must equal "
            "the project lifetime."
        )

    validated_generation = []

    for generation in generation_by_year_mwh:
        generation = float(generation)

        if not math.isfinite(generation):
            raise ValueError(
                "Generation values must be finite numbers."
            )

        if generation < 0:
            raise ValueError(
                "Generation cannot be negative."
            )

        validated_generation.append(generation)

    return tuple(validated_generation)
    
def _validate_additional_capex(
    scenario: ProjectScenario,
    additional_capex_by_year: Mapping[int, float] | None,
) -> dict[int, float]:
    """
    Validate optional additional capital expenditures.

    Example:
        {12: 5_000_000}

    means an additional $5 million capital expenditure
    in project year 12.
    """

    if additional_capex_by_year is None:
        return {}

    validated = {}

    for year, cost in additional_capex_by_year.items():

        if not isinstance(year, int):
            raise TypeError(
                "Additional CAPEX year must be an integer."
            )

        if not 1 <= year <= scenario.lifetime_years:
            raise ValueError(
                f"Additional CAPEX year must be between 1 "
                f"and {scenario.lifetime_years}."
            )

        cost = float(cost)

        if not math.isfinite(cost):
            raise ValueError(
                "Additional CAPEX must be finite."
            )

        if cost < 0:
            raise ValueError(
                "Additional CAPEX cannot be negative."
            )

        validated[year] = cost

    return validated


def build_cash_flow_schedule(
    scenario: ProjectScenario,
    generation_by_year_mwh: Sequence[float],
    additional_capex_by_year: Mapping[int, float] | None = None,
) -> tuple[CashFlowRow, ...]:
    """
    Build the complete project cash-flow schedule.

    Year 0:
        Initial CAPEX.

    Years 1...n:
        Generation
        Revenue
        OPEX
        Optional additional CAPEX
        Net cash flow
    """

    generation_schedule = _validate_generation_schedule(
        scenario,
        generation_by_year_mwh,
    )

    additional_capex = _validate_additional_capex(
        scenario,
        additional_capex_by_year,
    )

    finance = scenario.finance

    capacity_kw = scenario.capacity_mw * KW_PER_MW

    initial_capex_usd = calculate_initial_capex_usd(
        scenario
    )

    rows: list[CashFlowRow] = []


    # --------------------------------------------------------
    # YEAR 0
    # --------------------------------------------------------

    rows.append(
        CashFlowRow(
            year=0,
            generation_mwh=0.0,
            electricity_price_per_mwh=0.0,
            revenue_usd=0.0,
            fixed_opex_usd=0.0,
            variable_opex_usd=0.0,
            capital_cost_usd=initial_capex_usd,
            net_cash_flow_usd=-initial_capex_usd,
        )
    )


    # --------------------------------------------------------
    # OPERATING YEARS
    # --------------------------------------------------------

    for year, generation_mwh in enumerate(
        generation_schedule,
        start=1,
    ):

        growth_exponent = year - 1


        # Electricity price in this year
        electricity_price = (
            finance.electricity_price_per_mwh
            * (
                1
                + finance.electricity_price_growth_rate
            )
            ** growth_exponent
        )


        # OPEX escalation factor
        opex_multiplier = (
            1 + finance.opex_growth_rate
        ) ** growth_exponent


        # Revenue
        revenue_usd = (
            generation_mwh
            * electricity_price
        )


        # Fixed operating cost
        fixed_opex_usd = (
            capacity_kw
            * finance.fixed_opex_per_kw_year
            * opex_multiplier
        )


        # Variable operating cost
        variable_opex_usd = (
            generation_mwh
            * finance.variable_opex_per_mwh
            * opex_multiplier
        )


        # Replacement / additional CAPEX
        capital_cost_usd = additional_capex.get(
            year,
            0.0,
        )


        # Net project cash flow
        net_cash_flow_usd = (
            revenue_usd
            - fixed_opex_usd
            - variable_opex_usd
            - capital_cost_usd
        )


        rows.append(
            CashFlowRow(
                year=year,
                generation_mwh=generation_mwh,
                electricity_price_per_mwh=electricity_price,
                revenue_usd=revenue_usd,
                fixed_opex_usd=fixed_opex_usd,
                variable_opex_usd=variable_opex_usd,
                capital_cost_usd=capital_cost_usd,
                net_cash_flow_usd=net_cash_flow_usd,
            )
        )

    return tuple(rows)

def calculate_npv(
    cash_flows: Sequence[float],
    discount_rate: float,
) -> float:
    """
    Calculate Net Present Value.

    cash_flows[0] represents Year 0.
    """

    if discount_rate <= -1:
        raise ValueError(
            "Discount rate must be greater than -1."
        )

    discounted_cash_flows = []

    for year, cash_flow in enumerate(cash_flows):

        present_value = (
            cash_flow
            / (1 + discount_rate) ** year
        )

        discounted_cash_flows.append(
            present_value
        )

    return math.fsum(discounted_cash_flows)

def _count_cash_flow_sign_changes(
    cash_flows: Sequence[float],
) -> int:
    """
    Count sign changes in non-zero cash flows.

    Multiple sign changes can produce multiple IRRs.
    """

    non_zero = [
        value
        for value in cash_flows
        if abs(value) > 1e-12
    ]

    if len(non_zero) < 2:
        return 0

    sign_changes = 0

    for previous, current in zip(
        non_zero,
        non_zero[1:],
    ):
        if (
            previous < 0 < current
            or previous > 0 > current
        ):
            sign_changes += 1

    return sign_changes
    
def calculate_irr(
    cash_flows: Sequence[float],
    tolerance: float = 1e-8,
    max_iterations: int = 200,
) -> float | None:
    """
    Calculate IRR using a bracketed bisection method.

    Returns None when:
    - cash flows do not contain both positive and negative values,
    - more than one sign change exists,
    - a valid root cannot be bracketed.
    """

    values = tuple(float(value) for value in cash_flows)

    if not any(value < 0 for value in values):
        return None

    if not any(value > 0 for value in values):
        return None


    # Multiple sign changes can imply multiple IRRs.
    # We deliberately refuse to report a misleading single value.
    if _count_cash_flow_sign_changes(values) != 1:
        return None


    lower_rate = -0.999999
    upper_rate = 1.0


    lower_npv = calculate_npv(
        values,
        lower_rate,
    )

    upper_npv = calculate_npv(
        values,
        upper_rate,
    )


    # Increase the upper bound until the NPV
    # changes sign or until the search becomes unreasonable.
    while (
        lower_npv * upper_npv > 0
        and upper_rate < 1_000_000
    ):
        upper_rate = upper_rate * 2 + 1

        upper_npv = calculate_npv(
            values,
            upper_rate,
        )


    if lower_npv * upper_npv > 0:
        return None


    # Bisection search
    for _ in range(max_iterations):

        midpoint = (
            lower_rate + upper_rate
        ) / 2

        midpoint_npv = calculate_npv(
            values,
            midpoint,
        )


        if abs(midpoint_npv) < tolerance:
            return midpoint


        if lower_npv * midpoint_npv <= 0:
            upper_rate = midpoint
            upper_npv = midpoint_npv

        else:
            lower_rate = midpoint
            lower_npv = midpoint_npv


    return (
        lower_rate + upper_rate
    ) / 2
    
def calculate_lcoe_usd_per_mwh(
    cash_flow_rows: Sequence[CashFlowRow],
    discount_rate: float,
) -> float | None:
    """
    Calculate Levelized Cost of Electricity.

    LCOE =
        discounted lifetime costs
        /
        discounted lifetime electricity generation
    """

    discounted_costs = []
    discounted_generation = []


    for row in cash_flow_rows:

        discount_factor = (
            1 + discount_rate
        ) ** row.year


        total_cost_this_year = (
            row.capital_cost_usd
            + row.fixed_opex_usd
            + row.variable_opex_usd
        )


        discounted_costs.append(
            total_cost_this_year
            / discount_factor
        )


        discounted_generation.append(
            row.generation_mwh
            / discount_factor
        )


    present_value_costs = math.fsum(
        discounted_costs
    )

    present_value_generation = math.fsum(
        discounted_generation
    )


    if present_value_generation <= 0:
        return None


    return (
        present_value_costs
        / present_value_generation
    )
    
def calculate_simple_payback_years(
    cash_flow_rows: Sequence[CashFlowRow],
) -> float | None:
    """
    Calculate simple payback period.

    Returns a fractional year using linear interpolation.
    """

    cumulative_cash_flow = 0.0


    for row in cash_flow_rows:

        previous_cumulative = cumulative_cash_flow

        cumulative_cash_flow += (
            row.net_cash_flow_usd
        )


        if (
            row.year > 0
            and previous_cumulative < 0
            and cumulative_cash_flow >= 0
            and row.net_cash_flow_usd > 0
        ):

            amount_remaining = (
                -previous_cumulative
            )

            fraction_of_year = (
                amount_remaining
                / row.net_cash_flow_usd
            )

            return (
                row.year
                - 1
                + fraction_of_year
            )


    return None
    
def calculate_discounted_payback_years(
    cash_flow_rows: Sequence[CashFlowRow],
    discount_rate: float,
) -> float | None:
    """
    Calculate payback using discounted cash flows.
    """

    cumulative_discounted_cash_flow = 0.0


    for row in cash_flow_rows:

        discounted_cash_flow = (
            row.net_cash_flow_usd
            / (1 + discount_rate) ** row.year
        )


        previous_cumulative = (
            cumulative_discounted_cash_flow
        )

        cumulative_discounted_cash_flow += (
            discounted_cash_flow
        )


        if (
            row.year > 0
            and previous_cumulative < 0
            and cumulative_discounted_cash_flow >= 0
            and discounted_cash_flow > 0
        ):

            amount_remaining = (
                -previous_cumulative
            )

            fraction_of_year = (
                amount_remaining
                / discounted_cash_flow
            )

            return (
                row.year
                - 1
                + fraction_of_year
            )


    return None
    
def analyze_project_financials(
    project: ProjectScenario,
    generation_by_year_mwh: Sequence[float],
    additional_capex_by_year: Mapping[int, float] | None = None,
) -> FinancialAnalysis:
    """
    Run the complete financial analysis for one project scenario.

    This is the main public function of economics.py.
    """

    cash_flows = build_cash_flow_schedule(
        scenario=project,
        generation_by_year_mwh=generation_by_year_mwh,
        additional_capex_by_year=additional_capex_by_year,
    )


    cash_flow_values = tuple(
        row.net_cash_flow_usd
        for row in cash_flows
    )


    discount_rate = (
        project.finance.discount_rate
    )


    npv_usd = calculate_npv(
        cash_flow_values,
        discount_rate,
    )


    irr = calculate_irr(
        cash_flow_values
    )


    lcoe = calculate_lcoe_usd_per_mwh(
        cash_flows,
        discount_rate,
    )


    simple_payback = (
        calculate_simple_payback_years(
            cash_flows
        )
    )


    discounted_payback = (
        calculate_discounted_payback_years(
            cash_flows,
            discount_rate,
        )
    )


    lifetime_generation = math.fsum(
        row.generation_mwh
        for row in cash_flows
    )


    lifetime_revenue = math.fsum(
        row.revenue_usd
        for row in cash_flows
    )


    lifetime_opex = math.fsum(
        row.total_opex_usd
        for row in cash_flows
    )


    initial_capex = (
        cash_flows[0].capital_cost_usd
    )


    additional_capex = math.fsum(
        row.capital_cost_usd
        for row in cash_flows[1:]
    )


    metrics = FinancialMetrics(
        initial_capex_usd=initial_capex,
        npv_usd=npv_usd,
        irr=irr,
        lcoe_usd_per_mwh=lcoe,
        simple_payback_years=simple_payback,
        discounted_payback_years=discounted_payback,
        lifetime_generation_mwh=lifetime_generation,
        lifetime_revenue_usd=lifetime_revenue,
        lifetime_opex_usd=lifetime_opex,
        additional_capex_usd=additional_capex,
    )


    return FinancialAnalysis(
        cash_flows=cash_flows,
        metrics=metrics,
    )
