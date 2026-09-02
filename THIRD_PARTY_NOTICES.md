# Third-party notices

Pakistan Energy Simulator is distributed under the BSD 3-Clause License. It uses or
bundles the following principal third-party components; their own copyright notices
and license terms remain in force.

| Component | Use | License |
| --- | --- | --- |
| Python | Bundled runtime | Python Software Foundation License |
| FastAPI | Local API | MIT |
| Uvicorn | Local ASGI server | BSD-3-Clause |
| Pydantic | API validation | MIT |
| NumPy | Numerical calculations | BSD-3-Clause |
| pandas | Tabular resource processing | BSD-3-Clause |
| Requests | HTTP client | Apache-2.0 |
| React and React DOM | User interface | MIT |
| Apache ECharts | Charts | Apache-2.0 |
| echarts-for-react | React chart binding | MIT |
| Phosphor Icons | Interface icons | MIT |
| Inter | Interface typeface | OFL-1.1 |
| Vite and React plugin | Frontend build | MIT |
| PyInstaller | Windows packaging | GPL-2.0-or-later with the PyInstaller bootloader exception |

The complete frontend dependency graph and exact resolved versions are recorded in
`frontend/package-lock.json`; Python dependency constraints are recorded in
`pyproject.toml`. Those machine-readable inventories are authoritative for a source
build.

## Turbine reference data

`data/reference/turbines/IEA_Reference_3.4MW_130.csv` is sourced from the National
Laboratory of the Rockies Wind Turbine Power Curve Archive and is distributed under
BSD-3-Clause. Its source link and attribution are retained in the adjacent `NOTICE.md`.

## Data services

Open-Meteo and optional Copernicus Marine data remain subject to their providers'
terms. The application records the provider, dataset, coordinates and retrieval
context for each run; see `docs/DATA_SOURCES.md`.

This notice is not a substitute for the full license text shipped by each dependency.
