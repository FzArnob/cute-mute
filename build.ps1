<#
    Build CuteMute.exe

        .\build.ps1              # one-file, no console window
        .\build.ps1 -OneDir      # folder build: starts faster, easy to inspect
        .\build.ps1 -Certificate mycert.pfx        # ...and sign it
        .\build.ps1 -Certificate 1A2B3C...         # ...with a store thumbprint

    Needs PyInstaller:  python -m pip install pyinstaller
    CuteMute itself has no third-party dependencies.

    Signing is optional and off by default, because it needs a certificate you
    have to obtain yourself. Without one the exe still carries its full version
    resource -- name, publisher, version, copyright -- but SmartScreen will call
    the publisher unknown, and only a signature changes that.
#>
[CmdletBinding()]
param(
    [switch]$OneDir,
    [switch]$Clean,
    [string]$Certificate,
    [string]$TimestampServer = "http://timestamp.digicert.com"
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

$versionFile = "build\version_info.txt"
Invoke-Step "generating the version resource" {
    python tools\make_version.py $versionFile
}

$mode = if ($OneDir) { "--onedir" } else { "--onefile" }

Invoke-Step "PyInstaller ($mode)" {
    python -m PyInstaller `
        $mode `
        --noconsole `
        --name CuteMute `
        --icon CuteMute.ico `
        --version-file $versionFile `
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
if ($Certificate) {
    Write-Host "==> signing" -ForegroundColor Cyan
    $cert = $null
    if (Test-Path $Certificate) {
        $cert = Get-PfxCertificate -FilePath $Certificate
    } else {
        $cert = Get-ChildItem -Path "Cert:\CurrentUser\My\$Certificate" -ErrorAction SilentlyContinue
        if (-not $cert) {
            $cert = Get-ChildItem -Path "Cert:\LocalMachine\My\$Certificate" -ErrorAction SilentlyContinue
        }
    }
    if (-not $cert) {
        Write-Host "no certificate found for '$Certificate'" -ForegroundColor Red
        exit 1
    }
    $signed = Set-AuthenticodeSignature -FilePath $exe -Certificate $cert `
        -HashAlgorithm SHA256 -TimestampServer $TimestampServer
    Write-Host ("signature: " + $signed.Status) -ForegroundColor Green
}

$size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
$info = (Get-Item $exe).VersionInfo
Write-Host ""
Write-Host "Built $exe ($size MB)" -ForegroundColor Green
Write-Host ("  product   : " + $info.ProductName + " " + $info.ProductVersion)
Write-Host ("  publisher : " + $info.CompanyName)
Write-Host ("  copyright : " + $info.LegalCopyright)
Write-Host ("  signature : " + (Get-AuthenticodeSignature $exe).Status)
Write-Host "Run it once: it adds itself to the Start menu." -ForegroundColor Green
