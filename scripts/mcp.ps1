param()

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$julyScript = Join-Path $PSScriptRoot "july.ps1"

if (-not (Test-Path $julyScript)) {
    throw "No existe scripts\july.ps1"
}

& $julyScript mcp
