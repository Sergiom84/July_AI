param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$JulyArgs
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    throw "No existe .venv. Ejecuta primero .\scripts\bootstrap.ps1"
}

& $venvPython -m july @JulyArgs
