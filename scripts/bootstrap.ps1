param(
    [string]$PythonVersion = "",
    [string]$VenvPath = ".venv"
)

$ErrorActionPreference = "Stop"

function Resolve-Python {
    param([string]$RequestedVersion)

    $versionsToTry = @()
    if ($RequestedVersion) {
        $versionsToTry += $RequestedVersion
    } else {
        $versionsToTry += @("3.13", "3.12", "3.11")
    }

    foreach ($version in $versionsToTry) {
        $command = "py -$version -c ""import sys; print(sys.executable)"""
        $pythonExe = Invoke-Expression $command 2>$null
        if ($pythonExe) {
            return $pythonExe.Trim()
        }
    }

    if ($RequestedVersion) {
        throw "No se encontro Python $RequestedVersion. Instala Python 3.11+ o ejecuta este script con -PythonVersion 3.11, 3.12 o 3.13 segun lo que tengas disponible."
    }

    throw "No se encontro ningun Python compatible. July necesita Python 3.11 o superior."
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvFullPath = Join-Path $repoRoot $VenvPath
$venvPython = Join-Path $venvFullPath "Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    $pythonExe = Resolve-Python -RequestedVersion $PythonVersion
    Write-Host "Creando entorno virtual en $venvFullPath con $pythonExe"
    & $pythonExe -m venv $venvFullPath
} else {
    Write-Host "Entorno virtual ya disponible en $venvFullPath"
}

Write-Host "Actualizando pip"
& $venvPython -m pip install --upgrade pip

Write-Host "Instalando July en modo editable"
& $venvPython -m pip install -e $repoRoot

Write-Host ""
Write-Host "Bootstrap completado."
Write-Host "Usa: .\scripts\july.ps1 stats"
