# Pakistan Renewable Energy Techno-Economic Simulator

[![CI](https://github.com/GreenInvest-Pakistan/Pakistan-Energy-Simulator/actions/workflows/ci.yml/badge.svg)](https://github.com/GreenInvest-Pakistan/Pakistan-Energy-Simulator/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/GreenInvest-Pakistan/Pakistan-Energy-Simulator)](https://github.com/GreenInvest-Pakistan/Pakistan-Energy-Simulator/releases/latest)

A local-first engineering screening environment for utility-scale solar PV, onshore
wind, and research-grade wave energy in Pakistan. Enter coordinates directly, run a
traceable physical model, and carry P90/P50/P10 resource evidence into lifecycle
economics, comparison, sensitivity, break-even, and seeded Monte Carlo risk analysis.

![Pakistan Energy Simulator comparison](docs/images/comparison.png)

The simulator is decision support, not a bankability study. It deliberately keeps
source metadata, assumptions, uncertainty, and warnings visible and never collapses
unlike technologies into a fabricated overall score.

## Product experience

![Pakistan Energy Simulator home page](docs/images/home.png)

- Editorial home page and a guided New Analysis workflow.
- Direct latitude/longitude input for any site inside the Pakistan analysis bounds
  (23.5–37.1° N, 60.8–77.9° E); city selection is not required.
- Separate Resource, Economics, Compare, Sensitivity, Risk, Methodology, and Sources
  workspaces with functional tabs and real model outputs.
- Solar, Wind, and Wave project names remain distinct from editable site names.
- Historical annual-generation evidence with empirical P90/P50/P10 statistics.
- CAPEX × conversion-efficiency wave competitiveness surface and root-found
  break-even detail.
- Evidence-pack export, dated current-cost context, and transparent USD/PKR display
  conversion.
- Premium tobacco, walnut, ochre, and warm off-white interface designed as an
  engineering laboratory rather than a generic green dashboard.

## Scientific and economic scope

- Hourly solar and wind retrieval from Open-Meteo historical/ERA5-derived data.
- Copernicus Marine wave support when credentials are supplied, with a documented
  Open-Meteo marine fallback.
- Explicit solar temperature/loss/degradation, wind hub-height/power-curve, and
  deep-water wave-flux/capture-width model chains.
- NPV, unlevered project IRR, LCOE, simple payback, and discounted payback.
- One-way and two-way sensitivity, break-even root finding, and reproducible Monte
  Carlo analysis.
- Typed FastAPI requests and responses, local JSON caching, and automatic OpenAPI
  documentation.

Default solar and wind CAPEX inputs use IRENA's 2025 global benchmarks in 2025 USD and
remain editable project assumptions. Electricity sale price is also editable; the UI
does not present one universal Pakistan tariff. USD/PKR is a dated display conversion
from an identified live feed with a dated bundled fallback and an SBP reference link.

## Windows x64 standalone

The release artifacts are available from the
[v1.0.0 release](https://github.com/GreenInvest-Pakistan/Pakistan-Energy-Simulator/releases/tag/v1.0.0):

- [Portable Windows ZIP](https://github.com/GreenInvest-Pakistan/Pakistan-Energy-Simulator/releases/download/v1.0.0/Pakistan-Energy-Simulator-v1.0.0-win-x64.zip)
- [One-click Windows EXE](https://github.com/GreenInvest-Pakistan/Pakistan-Energy-Simulator/releases/download/v1.0.0/Pakistan-Energy-Simulator-v1.0.0-win-x64.exe)
- [SHA-256 checksums](https://github.com/GreenInvest-Pakistan/Pakistan-Energy-Simulator/releases/download/v1.0.0/SHA256SUMS.txt)

Both bundle the application, Python runtime, local API, scientific models, reference
data, and compiled frontend. The portable ZIP starts fastest after extraction; the
single EXE is the easiest one-click option and unpacks its runtime on launch. Neither
requires Python, Node, npm, pip, or a compiler. A first analysis for a new coordinate
requires internet access to retrieve its historical resource record; repeat requests
use the local cache beside the executable.

Build it from the repository-local D: environment:

```powershell
Set-Location D:\Projects\Pakistan-Energy-Simulator
.\scripts\build_windows_release.ps1
```

The script runs tests and linting, builds the frontend, creates the portable ZIP and
one-click EXE, creates a per-file manifest, writes `release\SHA256SUMS.txt`, and stores
every build cache and temporary file under D:. See [the release guide](docs/WINDOWS_RELEASE.md).

## Development setup on Windows

```powershell
git clone https://github.com/GreenInvest-Pakistan/Pakistan-Energy-Simulator.git D:\Projects\Pakistan-Energy-Simulator
Set-Location D:\Projects\Pakistan-Energy-Simulator
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev,wave,package]"
Set-Location frontend
npm ci
npm run build
Set-Location ..
.\.venv\Scripts\python.exe -m simulator_api.launcher
```

The launcher binds to `127.0.0.1:8765`, stores cache and temporary files in the local
project/runtime folder, and opens the application in the default browser.

Run verification:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
Set-Location frontend
npm run build
npm run test:sites
```

## Repository map

```text
analysis/       Sensitivity, comparison, risk, and project evaluation
core/           Validated domain models, lifecycle logic, and units
data/           Providers, cache, assumptions, market context, reference data
finance/        Cash-flow and financial metrics
physics/        Solar, wind, and wave production models
simulator_api/  FastAPI contract, service layer, and desktop launcher
frontend/       React product interface and charts
packaging/      PyInstaller specification and release payload
scripts/        Validation cases and Windows release automation
tests/          Unit and integration tests
docs/           Methods, sources, assumptions, limits, validation, release notes
```

## Documentation

- [Methodology](docs/METHODOLOGY.md)
- [Data sources](docs/DATA_SOURCES.md)
- [Assumptions](docs/ASSUMPTIONS.md)
- [Validation](docs/VALIDATION.md)
- [Limitations](docs/LIMITATIONS.md)
- [Development](docs/DEVELOPMENT.md)
- [Windows release](docs/WINDOWS_RELEASE.md)

## Licensing status

The project license decision remains with the owner. Until a license is selected, the
original source is treated as all rights reserved. Third-party material retains its
own terms; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and the vendored wind
reference [notice](data/reference/turbines/NOTICE.md).
