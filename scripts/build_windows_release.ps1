param(
    [string]$Version = "1.1.0",
    [string]$WorkDirectoryName = ".release-work",
    [switch]$SkipOneFile,
    [switch]$SkipFrontend,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
if (-not $projectRoot.StartsWith("D:\", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Release builds must run from D: so caches and build output do not consume C: storage."
}

function Assert-WithinProject([string]$PathToCheck) {
    $resolved = [System.IO.Path]::GetFullPath($PathToCheck)
    $prefix = $projectRoot.TrimEnd('\') + '\'
    if (-not $resolved.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to modify a path outside the project: $resolved"
    }
    return $resolved
}

function Reset-ProjectDirectory([string]$PathToReset) {
    $resolved = Assert-WithinProject $PathToReset
    if (Test-Path -LiteralPath $resolved) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
    New-Item -ItemType Directory -Path $resolved -Force | Out-Null
    return $resolved
}

$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$frontendRoot = Join-Path $projectRoot "frontend"
$releaseRoot = Assert-WithinProject (Join-Path $projectRoot "release")
$workRoot = Reset-ProjectDirectory (Join-Path $projectRoot $WorkDirectoryName)
$pyiWork = New-Item -ItemType Directory -Path (Join-Path $workRoot "pyinstaller") -Force
$pyiOneFileWork = New-Item -ItemType Directory -Path (Join-Path $workRoot "pyinstaller-onefile") -Force
$pyiDist = New-Item -ItemType Directory -Path (Join-Path $workRoot "dist") -Force
$tempRoot = New-Item -ItemType Directory -Path (Join-Path $workRoot "tmp") -Force
$npmCache = New-Item -ItemType Directory -Path (Join-Path $workRoot "npm-cache") -Force
$pipCache = New-Item -ItemType Directory -Path (Join-Path $workRoot "pip-cache") -Force

if (-not (Test-Path -LiteralPath $python)) {
    throw "The repository-local D: virtual environment is missing: $python"
}

$env:TEMP = $tempRoot.FullName
$env:TMP = $tempRoot.FullName
$env:PIP_CACHE_DIR = $pipCache.FullName
$env:npm_config_cache = $npmCache.FullName
$env:PYINSTALLER_CONFIG_DIR = (Join-Path $workRoot "pyinstaller-config")
$env:PAK_ENERGY_CACHE_DIR = (Join-Path $projectRoot ".runtime\cache\resources")

Push-Location $projectRoot
try {
    if (-not $SkipTests) {
        & $python -m pytest
        if ($LASTEXITCODE -ne 0) { throw "Python tests failed." }
        & $python -m ruff check .
        if ($LASTEXITCODE -ne 0) { throw "Ruff failed." }
    }

    if (-not $SkipFrontend) {
        Push-Location $frontendRoot
        try {
            & npm run build
            if ($LASTEXITCODE -ne 0) { throw "Frontend production build failed." }
            & npm run test:sites
            if ($LASTEXITCODE -ne 0) { throw "Frontend integration tests failed." }
        }
        finally {
            Pop-Location
        }
    }

    $spec = Join-Path $projectRoot "packaging\PakistanEnergySimulator.spec"
    & $python -m PyInstaller --noconfirm --clean --workpath $pyiWork.FullName --distpath $pyiDist.FullName $spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

    if (Test-Path -LiteralPath $releaseRoot) {
        $releaseRoot = Assert-WithinProject $releaseRoot
    }
    else {
        New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null
    }

    $stageRoot = Reset-ProjectDirectory (Join-Path $releaseRoot "Pakistan Energy Simulator")
    $builtRoot = Join-Path $pyiDist.FullName "PakistanEnergySimulator"
    if (-not (Test-Path -LiteralPath (Join-Path $builtRoot "PakistanEnergySimulator.exe"))) {
        throw "Expected packaged executable was not produced."
    }
    Copy-Item -Path (Join-Path $builtRoot "*") -Destination $stageRoot -Recurse -Force

    $runtimeData = New-Item -ItemType Directory -Path (Join-Path $stageRoot "runtime-data") -Force
    New-Item -ItemType Directory -Path (Join-Path $runtimeData.FullName "cache\resources") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $runtimeData.FullName "tmp") -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $projectRoot "packaging\README.txt") -Destination (Join-Path $stageRoot "README.txt") -Force
    Copy-Item -LiteralPath (Join-Path $projectRoot "packaging\Verify-Package.ps1") -Destination (Join-Path $stageRoot "Verify-Package.ps1") -Force
    Copy-Item -LiteralPath (Join-Path $projectRoot "THIRD_PARTY_NOTICES.md") -Destination (Join-Path $stageRoot "THIRD_PARTY_NOTICES.md") -Force
    Copy-Item -LiteralPath (Join-Path $projectRoot "LICENSE") -Destination (Join-Path $stageRoot "LICENSE") -Force

    $commit = (& git rev-parse --short=12 HEAD 2>$null)
    if (-not $commit) { $commit = "uncommitted-source" }
    $manifest = @(
        "Pakistan Energy Simulator",
        "Version: $Version",
        "Platform: Windows x64",
        "Built UTC: $([DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ'))",
        "Source commit: $commit",
        "Methodology version: 1.1.0",
        "Local bind: 127.0.0.1:8765",
        "Telemetry: none",
        "Resource providers: Open-Meteo; optional Copernicus Marine"
    )
    Set-Content -LiteralPath (Join-Path $stageRoot "RELEASE-MANIFEST.txt") -Value $manifest -Encoding UTF8

    $manifestPath = Join-Path $stageRoot "FILE-MANIFEST.sha256"
    $files = Get-ChildItem -LiteralPath $stageRoot -File -Recurse |
        Where-Object { $_.FullName -ne $manifestPath } |
        Sort-Object FullName
    $hashLines = foreach ($file in $files) {
        $relative = [System.IO.Path]::GetRelativePath($stageRoot, $file.FullName).Replace('\', '/')
        $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        "$hash  $relative"
    }
    Set-Content -LiteralPath $manifestPath -Value $hashLines -Encoding ASCII

    & (Join-Path $stageRoot "Verify-Package.ps1")
    if ($LASTEXITCODE -ne 0) { throw "Internal file-manifest verification failed." }

    $zipName = "Pakistan-Energy-Simulator-v$Version-win-x64.zip"
    $zipPath = Assert-WithinProject (Join-Path $releaseRoot $zipName)
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    Compress-Archive -LiteralPath $stageRoot -DestinationPath $zipPath -CompressionLevel Optimal
    $zipHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()

    $checksumLines = @("$zipHash  $zipName")
    if (-not $SkipOneFile) {
        $oneFileSpec = Join-Path $projectRoot "packaging\PakistanEnergySimulatorOneFile.spec"
        & $python -m PyInstaller --noconfirm --clean --workpath $pyiOneFileWork.FullName --distpath $pyiDist.FullName $oneFileSpec
        if ($LASTEXITCODE -ne 0) { throw "PyInstaller one-file build failed." }

        $builtOneFile = Join-Path $pyiDist.FullName "PakistanEnergySimulator-OneFile.exe"
        if (-not (Test-Path -LiteralPath $builtOneFile)) {
            throw "Expected one-file executable was not produced."
        }
        $oneFileName = "Pakistan-Energy-Simulator-v$Version-win-x64.exe"
        $oneFilePath = Assert-WithinProject (Join-Path $releaseRoot $oneFileName)
        Copy-Item -LiteralPath $builtOneFile -Destination $oneFilePath -Force
        $oneFileHash = (Get-FileHash -LiteralPath $oneFilePath -Algorithm SHA256).Hash.ToLowerInvariant()
        $checksumLines += "$oneFileHash  $oneFileName"
        Write-Host "One-click executable: $oneFilePath"
        Write-Host "EXE SHA-256: $oneFileHash"
    }

    Set-Content -LiteralPath (Join-Path $releaseRoot "SHA256SUMS.txt") -Value $checksumLines -Encoding ASCII

    Write-Host "Release package: $zipPath"
    Write-Host "SHA-256: $zipHash"
}
finally {
    Pop-Location
}
