# Validation record

## Test baseline

The scientific baseline has 106 automated tests covering domain validation, solar, wind,
wave, lifecycle generation, finance, caching, sensitivity, uncertainty, comparisons,
and the typed API. The suite is deterministic except for tests that explicitly exercise
seeded random sampling.

## Jhimpir solar case

Configuration: 100 MW fixed-tilt PV at 25.025 N, 67.95 E; 25-degree tilt; south-facing
internal azimuth 180 degrees; 14.1% system losses; hourly 2015-2024 Open-Meteo ERA5.

| Measure | Result |
|---|---:|
| P90 generation | 189,366 MWh |
| P50 generation | 194,705 MWh |
| P10 generation | 196,660 MWh |
| P50 capacity factor | 22.23% |
| P50 LCOE | 51.77 USD/MWh |
| P50 NPV | 14.27 million USD |
| P50 project IRR | 12.55% |

PVGIS-ERA5 reported 1,730.27 kWh/kWp versus 1,947.05 kWh/kWp in the simulator, a
12.53% positive difference and inside the declared 15% screening tolerance. This is an
implementation cross-check, not a calibration. The simulator records that full
cell-temperature data were unavailable, so no temperature correction was applied.

## Jhimpir wind case

Configuration: 100 MW onshore wind at the same location; 100 m hub height; 3.37 MW
reference rating; 95% availability; hourly 2015-2024 Open-Meteo ERA5 wind.

| Measure | Result |
|---|---:|
| Mean 100 m wind speed | 6.77 m/s |
| P90 generation | 333,125 MWh |
| P50 generation | 353,441 MWh |
| P10 generation | 390,960 MWh |
| P50 capacity factor | 40.35% |
| P50 LCOE | 41.74 USD/MWh |
| P50 NPV | 60.83 million USD |
| P50 project IRR | 17.07% |

The production model and validation script independently load and linearly interpolate
the same vendored NLR/IEA curve. Their P50 outputs agree within 0.00002%, which checks
implementation parity rather than independently validating the turbine or resource.
Density correction, wake, electrical, icing, curtailment, and terrain-flow losses are
not separately modeled.

## Joint uncertainty

Tests verify fixed-seed reproducibility, one Solar/Wind/Wave result per shared iteration,
unique shared and technology-specific variables, pairwise valid denominators, and that
win/tie probabilities sum to one. This validates pairing and arithmetic; it does not
validate the chosen uncertainty ranges as forecasts.

## Offshore Karachi wave research case

Configuration: 100 MW at 24.5 N, 66.5 E; 30% conversion efficiency; 20 m effective
capture width; 1 MW devices; 90% availability; hourly 2015-2024 Open-Meteo ERA5-Ocean.

| Measure | Result |
|---|---:|
| Mean significant wave height | 1.257 m |
| Mean wave-period proxy | 7.35 s |
| Mean deep-water flux | 8.48 kW/m |
| P50 generation | 39,236 MWh |
| P50 capacity factor | 4.48% |
| Scenario LCOE | 1,921.43 USD/MWh |
| Scenario NPV | -616.29 million USD |
| Scenario IRR | undefined |

The exact equation differs from the `0.49 * Hs^2 * Te` approximation by at most 0.055%
for the validation observations. This does not validate the wave resource dataset or a
device model. Copernicus cross-validation remains pending user credentials. The period
is a proxy, bathymetry is unavailable, finite-depth effects are untested, and economics
are explicit research assumptions.

## Re-running

Run the three scripts in `scripts/`. They write timestamped JSON content beneath
`reports/generated/`, which is ignored by Git. Preserve provider metadata, warnings,
and the exact source period with any published result.
