from core.models import SimulationResult, Technology


def test_simulation_result_allows_undefined_lcoe():
    result = SimulationResult(
        scenario_id="NO_GENERATION_CASE",
        technology=Technology.WAVE,
        annual_generation_mwh=0.0,
        capacity_factor=0.0,
        total_capex_usd=1_000_000.0,
        annual_opex_usd=0.0,
        annual_revenue_usd=0.0,
        npv_usd=-1_000_000.0,
        irr=None,
        lcoe_usd_per_mwh=None,
        payback_years=None,
    )

    assert result.lcoe_usd_per_mwh is None
