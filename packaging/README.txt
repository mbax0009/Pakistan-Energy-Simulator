PAKISTAN ENERGY SIMULATOR v1.1.0
=================================

QUICK START
1. Extract the entire ZIP. Do not run the application from inside the ZIP.
2. Double-click PakistanEnergySimulator.exe.
3. The simulator opens in your default browser at http://127.0.0.1:8765.
4. Keep the extracted folder together while using the application.

WHAT IS INCLUDED
- A self-contained Windows x64 Python runtime and local API.
- The compiled premium desktop web interface.
- Solar PV, onshore wind, and research-grade wave models.
- Coordinate entry for any site within the Pakistan analysis bounds.
- Economics, comparison, sensitivity, break-even, standalone risk, and paired
  joint-uncertainty analysis across Solar, Wind, and Wave.
- Default tabulated NLR/IEA 3.4 MW wind-turbine curve with linear interpolation.

DATA AND INTERNET ACCESS
- The application runs locally and binds to 127.0.0.1 only by default.
- A first analysis at a new coordinate needs internet access to retrieve the
  historical resource series. Repeated identical requests use runtime-data\cache.
- Solar and wind use Open-Meteo historical data. Wave prefers Copernicus Marine
  when credentials are configured and otherwise uses the documented marine fallback.
- Current indicative USD/PKR display conversion is dated and identified in the UI.
- No telemetry is included.

STOPPING THE APPLICATION
Close PakistanEnergySimulator.exe from Task Manager if required. Closing only the
browser tab does not stop the local process.

TROUBLESHOOTING
- If port 8765 is already occupied, close the other local simulator process.
- Windows may show a SmartScreen warning because this release is not code-signed.
  Before extracting, download SHA256SUMS.txt from the same GitHub release and
  compare it with Get-FileHash on the downloaded ZIP or EXE.
- After extraction, FILE-MANIFEST.sha256 verifies every file inside the portable
  package. Right-click Verify-Package.ps1 and choose Run with PowerShell, or run it
  from a PowerShell prompt. It is intentionally different from the release-level
  SHA256SUMS.txt.
- The runtime cache and temporary files live beside the executable under
  runtime-data. They can be removed while the application is closed.

SCOPE
This is an engineering screening and academic decision-support tool, not a
bankability study or final project design. Read the visible warnings, methodology,
sources, and limitations before relying on results.

Project: Pakistan Renewable Energy Techno-Economic Simulator
License: BSD-3-Clause
Release: v1.1.0, Windows x64
