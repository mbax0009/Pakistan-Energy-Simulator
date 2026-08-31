# Development guide

## Storage policy

This working copy, virtual environment, caches, temporary files, frontend dependencies,
and release artifacts belong beneath:

```text
D:\Projects\Pakistan-Energy-Simulator
```

Do not place project build or dependency storage on C:. The launcher redirects runtime
TEMP, TMP, and resource cache folders to `.runtime/` in development or `runtime-data/`
beside a frozen executable.

## Quality checks

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
git diff --check
```

Network-backed validation is separate from the fast deterministic test suite. Run it
only when refreshing resource evidence or proving cache behavior.

## Architecture rules

- `physics/` converts resource observations into interval power and energy.
- `analysis/` owns annual distributions, lifecycle cases, sensitivity, risk, and
  comparisons.
- `finance/` owns project cash flows and financial metrics.
- `data/` owns providers, provider normalization, cache, and source-labelled assumptions.
- `simulator_api/` translates typed external requests to authoritative domain objects.
- The frontend must call the API; it must not duplicate scientific formulas in JavaScript.

Warnings are part of the result contract. New approximations require a test, an explicit
warning, and an entry in methodology or limitations documentation.

## Cache and secrets

Copy `.env.example` to `.env` for local overrides. `.env`, local cache data, generated
reports, builds, and credentials are ignored. Never add real credentials to Git, tests,
screenshots, packaged defaults, or generated OpenAPI examples.

## API evolution

All production endpoints are versioned under `/api/v1`. Add or change schemas in
`simulator_api/schemas.py`, keep conversions in `simulator_api/service.py`, update API
tests, and preserve reproducibility fields. Breaking changes require a new API or
methodology version.

## Git discipline

Keep generated resource payloads and reports outside commits. Vendor only small,
licensed reference material needed for deterministic validation and include its exact
notice. Commit scientific, API, visual, and packaging milestones separately so they can
be audited.
