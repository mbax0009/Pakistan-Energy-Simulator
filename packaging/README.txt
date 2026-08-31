PAKISTAN ENERGY SIMULATOR v1.0.1
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
- Economics, comparison, sensitivity, break-even, and seeded risk analysis.

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
  Verify the ZIP SHA-256 value in SHA256SUMS.txt before running it.
- The runtime cache and temporary files live beside the executable under
  runtime-data. They can be removed while the application is closed.

SCOPE
This is an engineering screening and academic decision-support tool, not a
bankability study or final project design. Read the visible warnings, methodology,
sources, and limitations before relying on results.

Project: Pakistan Renewable Energy Techno-Economic Simulator
Release: v1.0.1, Windows x64
