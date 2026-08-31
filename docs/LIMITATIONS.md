# Limitations and appropriate use

## Appropriate use

The simulator is suitable for transparent screening, scenario comparison, teaching,
and early techno-economic exploration. It is not a substitute for a measured site
campaign, grid study, geotechnical assessment, environmental study, lender model,
independent engineer, or certified energy-yield assessment.

## Cross-cutting limitations

- Reanalysis grid cells are not site measurements and may smooth local extremes.
- Historical variability does not include all forward-looking climate uncertainty.
- The empirical P-values use the selected years only; short periods can be unstable.
- Results are only as defensible as the cost, tariff, loss, and technology inputs.
- No exchange-rate, inflation-regime, construction schedule, financing, tax, subsidy,
  insurance, land, transmission, grid-connection, decommissioning, or salvage model is
  included unless represented explicitly in user cash-flow assumptions.
- The model is unlevered. Project IRR is not equity IRR.
- LCOE and NPV can be numerically valid while the underlying scenario is commercially
  unrealistic; evidence labels and warnings must be read with the result.

## Solar limitations

- The rated-power model does not replace a full PV performance model.
- Cell-temperature effects are omitted when complete cell-temperature data are absent.
- Horizontal-irradiance fallback cannot physically represent tilt and azimuth.
- Soiling, clipping, mismatch, inverter efficiency, degradation modes, snow, shading,
  curtailment, availability, and AC/DC ratio are not independently resolved unless
  captured by aggregate losses or user assumptions.

## Wind limitations

- The built-in cubic power curve is a screening approximation.
- No wake, layout, terrain, turbulence, extreme-wind, electrical-loss, icing, or detailed
  availability model is included.
- Air-density correction is omitted when complete density data are unavailable.
- Fractional turbine counts are allowed to scale the reference machine to project size;
  this is analytically convenient but not a physical layout.

## Wave limitations

- Wave energy remains pre-commercial or early-commercial for many applications.
- Open-Meteo mean wave period is a proxy for energy period.
- The current model assumes deep water and cannot verify that assumption without depth.
- Direction is preserved but does not modify device output.
- Effective capture width and conversion efficiency are not a device power matrix.
- Array interaction, mooring, survivability, cable losses, maintenance access, and port
  logistics are not modeled.
- Wave CAPEX, OPEX, lifetime, degradation, and availability are research-scenario inputs,
  not market facts.

## Reporting rule

Do not publish a headline metric without its technology, site, resource source and
period, generation basis, financial assumptions, evidence labels, and warnings. An
undefined IRR, LCOE, or payback must remain undefined rather than being converted to
zero or omitted silently.
