# Assumptions and evidence policy

## Evidence levels

Every catalogued numeric assumption is classified as one of:

- `global_benchmark`: published international benchmark.
- `technical_reference`: engineering or reference-technology assumption.
- `pakistan_evidence`: value derived from an authoritative Pakistan source.
- `scenario_assumption`: plausible research scenario, not a universal measured value.
- `user_required`: project-specific input that must be supplied.
- `validation_only`: plausibility check that is not fed into the simulation.

`None` is meaningful in the assumption catalog. It indicates that the project does not
have a sufficiently defensible generic value and refuses to invent one.

## Current reference-case values

| Input | Solar | Onshore wind | Wave |
|---|---:|---:|---:|
| CAPEX | 667 USD/kW, global 2025 benchmark | 976 USD/kW, global 2025 benchmark | unresolved |
| Fixed OPEX | 22 USD/kW-year, US technical reference | 44 USD/kW-year, US technical reference | unresolved |
| Lifetime | 30 years, technical reference | 30 years, technical reference | unresolved |
| Degradation | 0.7%/year, technical reference | unresolved | unresolved |
| Validation CF | 17.4%, global validation only | 34%, global validation only | unresolved |

The validation capacity factors are context, not targets. Site physics determines the
Pakistan project capacity factor.

The CAPEX defaults use IRENA's latest published observations available on 30 August
2026: projects commissioned in 2025, expressed in 2025 USD. They are global benchmark
defaults, not live vendor quotations or Pakistan EPC bids. A current project quotation
should override them and retain its quote date and source.

## Inputs that remain project-specific

Electricity sale price and discount rate are always user inputs. They are not inferred
from a historic tariff. Pakistan tariff publications can support a documented scenario,
but plant-specific tariffs are not universal prices for a new project. Currency display
conversion uses a separately sourced USD/PKR rate with an exact as-of timestamp; it does
not alter the underlying real project economics.

Solar still needs a defensible array orientation and site O&M interpretation. Wind
needs the selected turbine curve, site losses, and degradation policy. Wave needs a
specific device or power matrix, cost basis, lifetime, availability, and deployment
concept.

## Scenario labels

Results should distinguish:

- provider-backed historical resource observations;
- global or technical benchmark assumptions;
- Pakistan-specific evidence;
- user-entered project assumptions; and
- pre-commercial research scenarios.

The UI and exports must preserve these labels and the engine's warnings. Wave economics
must never be described as a market forecast or commercial benchmark unless supported
by a new documented source.
