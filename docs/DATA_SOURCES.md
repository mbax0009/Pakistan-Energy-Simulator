# Data sources and provenance

## Operational resource providers

| Technology | Production/default source | Variables used | Authentication | Cache namespace |
|---|---|---|---|---|
| Solar | Open-Meteo Historical Weather API, ERA5 | Global tilted irradiance, temperature where usable | None | `open-meteo-solar` |
| Wind | Open-Meteo Historical Weather API, ERA5 | Hourly wind speed at requested/available height | None | `open-meteo-wind` |
| Wave | Open-Meteo Marine API, ERA5-Ocean fallback | Significant wave height, wave period proxy, direction | None | `open-meteo-marine-wave` |
| Wave | Copernicus Marine WAVERYS preferred path | Significant wave height and VTM10 energy-period variable | User credentials | Provider-managed |

Primary documentation:

- [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)
- [Open-Meteo Marine Weather API](https://open-meteo.com/en/docs/marine-weather-api)
- [Copernicus Marine GLOBAL_MULTIYEAR_WAV_001_032](https://data.marine.copernicus.eu/product/GLOBAL_MULTIYEAR_WAV_001_032/description)
- [Copernicus Marine Toolbox documentation](https://help.marine.copernicus.eu/en/collections/4060068-copernicus-marine-toolbox)

The API response records provider, dataset, requested and resolved coordinates, time
range, sample count, and time step. Raw provider payloads are stored only in the local
JSON cache and are excluded from Git.

## Independent validation sources

- Solar uses the European Commission Joint Research Centre
  [PVGIS API](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/getting-started-pvgis/api-non-interactive-service_en)
  as an independent implementation cross-check.
- Wind uses the
  [National Laboratory of the Rockies turbine-model archive](https://github.com/NatLabRockies/turbine-models)
  IEA Reference 3.4 MW power curve. The exact CSV and its notice are vendored for
  reproducibility.
- Wave checks the implemented deep-water equation against the common
  `0.49 * Hs^2 * Te` kW/m approximation. This is a formula check, not an independent
  resource-dataset validation.

## Assumption evidence

The code catalog in `data/assumptions/assumptions.py` identifies every reference value
with a stable source ID, organization, publication title, year, geography, evidence
level, and notes. Current source families include IRENA Renewable Power Generation
Costs in 2024, NREL 2024 Annual Technology Baseline references, DOE/NREL wave reference
material, and NEPRA Pakistan tariff evidence.

Source geography is intentionally explicit. A global or United States benchmark is not
presented as a measured Pakistan project value.

## Credentials and offline behavior

Real credentials are never committed or embedded in an executable. Copernicus can use
`PAK_ENERGY_COPERNICUS_CREDENTIALS_FILE`, pointing to a user-controlled file on D:, or
the standard Copernicus Marine environment variables. Without credentials, automatic
wave analysis uses Open-Meteo and surfaces the mean-period and bathymetry limitations.

Previously cached Open-Meteo data permits repeat analysis without another download.
Clearing the cache is an explicit API action.
