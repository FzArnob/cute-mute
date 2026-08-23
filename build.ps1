<#
    Build CuteMute.exe

        .\build.ps1              # one-file, no console window
        .\build.ps1 -OneDir      # folder build: starts faster, easy to inspect

    Needs PyInstaller:  python -m pip install pyinstaller
    CuteMute itself has no third-party dependencies.
#>
[CmdletBinding()]
param(
    [switch]$OneDir,
    [switch]$Clean
)

# Windows PowerShell 5.1 turns any native stderr write into a terminating
# NativeCommandError when ErrorActionPreference is Stop -- and PyInstaller logs
# its INFO lines to stderr. So stay on Continue and check exit codes by hand.
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

function Invoke-Step($label, $block) {
    Write-Host "==> $label" -ForegroundColor Cyan
    & $block
    if ($LASTEXITCODE -ne 0) {
        Write-Host "$label failed (exit $LASTEXITCODE)" -ForegroundColor Red
        exit 1
    }
}

if ($Clean) {
    foreach ($d in @("build", "dist", "__pycache__")) {
        if (Test-Path $d) { Remove-Item $d -Recurse -Force }
    }
}

Invoke-Step "generating CuteMute.ico" { python tools\make_ico.py CuteMute.ico }

$mode = if ($OneDir) { "--onedir" } else { "--onefile" }

Invoke-Step "PyInstaller ($mode)" {
    python -m PyInstaller `
        $mode `
        --noconsole `
        --name CuteMute `
        --icon CuteMute.ico `
        --noconfirm `
        --clean `
        --exclude-module numpy `
        --exclude-module PIL `
        --exclude-module unittest `
        --exclude-module pydoc `
        --exclude-module email `
        --exclude-module http `
        --exclude-module xml `
        --exclude-module pdb `
        CuteMute.pyw
}

$exe = if ($OneDir) { "dist\CuteMute\CuteMute.exe" } else { "dist\CuteMute.exe" }
if (-not (Test-Path $exe)) {
    Write-Host "PyInstaller reported success but $exe is missing" -ForegroundColor Red
    exit 1
}
$size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host ""
Write-Host "Built $exe ($size MB)" -ForegroundColor Green
Write-Host "Run it, then look for the CuteMute icon in the tray." -ForegroundColor Green
