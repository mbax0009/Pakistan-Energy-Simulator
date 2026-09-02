$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$packageRoot = [System.IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\')
$manifestPath = Join-Path $packageRoot "FILE-MANIFEST.sha256"

if (-not (Test-Path -LiteralPath $manifestPath)) {
    throw "FILE-MANIFEST.sha256 was not found beside this script."
}

$checked = 0
foreach ($line in Get-Content -LiteralPath $manifestPath) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    $parts = $line -split '\s{2,}', 2
    if ($parts.Count -ne 2) { throw "Invalid manifest line: $line" }
    $expected = $parts[0].ToLowerInvariant()
    $relative = $parts[1].Replace('/', '\')
    $filePath = [System.IO.Path]::GetFullPath((Join-Path $packageRoot $relative))
    if (-not $filePath.StartsWith($packageRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Manifest path escapes the package folder: $relative"
    }
    if (-not (Test-Path -LiteralPath $filePath -PathType Leaf)) {
        throw "Package file is missing: $relative"
    }
    $actual = (Get-FileHash -LiteralPath $filePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected) {
        throw "Checksum mismatch: $relative"
    }
    $checked += 1
}

Write-Host "Package verified: $checked files match FILE-MANIFEST.sha256."
