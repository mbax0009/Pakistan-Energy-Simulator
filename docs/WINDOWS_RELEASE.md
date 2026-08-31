# Windows x64 standalone release

## Artifact

`release/Pakistan-Energy-Simulator-v1.0.1-win-x64.zip`

`release/Pakistan-Energy-Simulator-v1.0.1-win-x64.exe`

The ZIP contains one `Pakistan Energy Simulator` folder with the windowed executable,
bundled Python/runtime libraries, compiled frontend, empty local runtime-data folders,
release manifest, file hashes, quick-start guide, and notices. End users do not need a
separate Python or Node installation.

The single EXE contains the same runtime and application for one-click use. It has a
slower cold start because Windows must unpack its embedded runtime before launch; the
extracted ZIP is the preferred option for repeated use and fastest startup.

## Build

Run from a repository-local D: virtual environment with the package extra installed:

```powershell
Set-Location D:\Projects\Pakistan-Energy-Simulator
.\.venv\Scripts\python.exe -m pip install -e ".[dev,package]"
.\scripts\build_windows_release.ps1
```

The script refuses to run outside D:. It redirects TEMP, TMP, pip, npm, and PyInstaller
state into `.release-work` under the repository. Before packaging it runs Python tests,
Ruff, the Vite production build, and the frontend integration test. Use `-SkipTests` or
`-SkipFrontend` only for a diagnosed incremental build; never use either for a public
release.

## Runtime behavior

1. The executable creates `runtime-data/tmp` and `runtime-data/cache/resources` beside
   itself.
2. It binds only to `127.0.0.1:8765` by default.
3. It serves the compiled React interface and typed `/api/v1` API from the same origin.
4. It opens the local application in the user's default browser.
5. The process continues until the executable is stopped.

Set `PAK_ENERGY_OPEN_BROWSER=0` for automated smoke tests, and set
`PAK_ENERGY_PORT` to an unused local port when testing alongside a development server.

## Required package QA

After building, launch the staged executable with browser opening disabled and a clean
port. Confirm:

- `GET /api/v1/health` returns version `1.0.1`;
- `/` and the hashed JS/CSS assets return successfully;
- the home page and every primary workspace render;
- cached solar, wind, and wave comparisons complete;
- arbitrary Pakistan coordinate entry changes the resolved resource result;
- warnings, source metadata, cost basis, and evidence export remain visible;
- the process writes only inside the extracted `runtime-data` folder; and
- the SHA-256 values in `release/SHA256SUMS.txt` match the final ZIP and EXE.

## Distribution notes

The binary is not code-signed, so Windows SmartScreen may show a warning. Users should
verify the published SHA-256 before running it. A first analysis for a new coordinate
requires internet access. Copernicus Marine credentials are optional and must be
supplied at runtime; they are never embedded in the package.
