# Methodology

## Scope and conventions

The simulator evaluates project-level, unlevered cash flows for utility-scale solar PV,
onshore wind, and explicit wave-energy research scenarios. Internal energy units are
MW, MWh, kW, kWh, metres, seconds, and decimal fractions. Monetary values are nominal
USD unless the user defines a different interpretation for their scenario.

Solar azimuth is measured clockwise from north:

- 0 degrees: north
- 90 degrees: east
- 180 degrees: south
- 270 degrees: west

Provider adapters are responsible for translating any external convention.

## Resource assessment and exceedance cases

Hourly provider records are grouped by calendar year. A year is accepted only when its
completeness ratio meets the requested threshold, which defaults to 0.99. Each accepted
year is simulated independently and then summarized empirically.

The labels use exceedance-probability terminology:

- P90 generation is the 10th percentile of annual generation.
- P50 generation is the median annual generation.
- P10 generation is the 90th percentile of annual generation.

This makes P90 the conservative case and P10 the high-generation case. No parametric
distribution is imposed on the historical annual series.

## Solar model

For each interval, the simplified rated-power model is:

```text
P_ideal = P_rated * G / G_ref
P_net   = min(P_rated, P_ideal * f_temperature * (1 - system_losses))
E       = sum(P_net * delta_t)
```

Plane-of-array irradiance is preferred. If only horizontal irradiance is present, the
engine can fall back with an explicit warning because tilt and azimuth are then not
physically represented. Cell-temperature correction is applied only when cell
temperature is actually present; ambient temperature is never silently substituted.

## Wind model

Wind speed may be adjusted from measurement height to hub height with the power law:

```text
v_hub = v_ref * (h_hub / h_ref) ^ alpha
```

The default turbine model uses the bundled NLR/IEA Reference 3.4 MW, 130 m-rotor
tabulated curve. Electrical output is linearly interpolated between adjacent wind-speed
points, scaled to the configured turbine rating, set to zero below cut-in and at or above
cut-out, and capped at rated output. Availability is then applied. The former cubic
approximation remains available only when `power_curve_id` is explicitly set to `null`.

Optional air-density correction is used only when complete density observations exist.
A selected turbine's certified power curve, wake model, terrain-flow model, electrical
losses, and curtailment model are still needed for engineering or investment-grade work.

## Wave model

Deep-water wave power flux is calculated from significant wave height and energy period:

```text
J = rho * g^2 * Hs^2 * Te / (64 * pi)
```

The resulting flux is multiplied by effective capture width, conversion efficiency,
and availability, capped at device rated power, and scaled to project capacity. When
Open-Meteo is used, its mean wave-period field is explicitly treated as a proxy for
energy period. A device power matrix is not inferred.

## Lifecycle generation

The selected first-year P-case is degraded over the project lifetime:

```text
E_y = E_1 * (1 - degradation_rate) ^ (y - 1)
```

The same lifecycle schedule feeds every financial metric, preventing P-case or
degradation inconsistencies between energy and economics.

## Financial model

Year 0 contains initial CAPEX:

```text
initial_capex = capacity_kW * capex_USD_per_kW
```

For operating year `y`, the model applies price and OPEX escalation, then calculates:

```text
revenue_y = generation_y * electricity_price_y
net_cash_flow_y = revenue_y - fixed_opex_y - variable_opex_y - additional_capex_y
```

NPV discounts the complete project cash-flow series. Project IRR is returned only when
there is one unambiguous sign change and a root can be bracketed. LCOE is discounted
lifetime cost divided by discounted lifetime generation. Simple and discounted payback
are linearly interpolated within the crossing year; they remain undefined if recovery
never occurs.

## Sensitivity, risk, and comparison

Sensitivity paths reuse the baseline resource data and recalculate only the affected
layers. Two-way analysis is limited to 1,000 cells through the API. Break-even analysis
uses a bounded numerical search and reports non-convergence rather than inventing a
solution.

Monte Carlo runs use an explicit seed and declared distributions. Supported inputs are
uniform, triangular, truncated normal, and empirical distributions. Results preserve
each sample, summarize valid and undefined metric counts, and never replace undefined
IRR or LCOE values with zeros.

Joint uncertainty draws shared economic inputs once per iteration and applies that draw
to Solar, Wind, and Wave. Technology-specific costs, performance inputs and empirical
resource-year sequences are sampled separately. Pairwise probabilities such as
`P(NPV_solar > NPV_wind)` and `P(LCOE_wave < LCOE_solar)` are counted only from results
inside the same iteration. Ties are reported separately; undefined metric pairs are
excluded from that metric's denominator and the valid-pair count is returned.

Comparison reports metric-specific rankings. It deliberately has no opaque composite
or overall score.
