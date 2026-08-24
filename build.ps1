<#
    Build CuteMute.exe

        .\build.ps1              # one-file, no console window
        .\build.ps1 -OneDir      # folder build: starts faster, easy to inspect
        .\build.ps1 -Sigstore    # ...and sign it, keylessly, for free
        .\build.ps1 -Certificate mycert.pfx        # ...or with Authenticode
        .\build.ps1 -Certificate 1A2B3C...         # ...from a store thumbprint

    Needs PyInstaller:  python -m pip install pyinstaller
    CuteMute itself has no third-party dependencies.

    Two kinds of signature, doing two different jobs:

    -Sigstore     Free, and there is no key to keep anywhere. Writes
                  CuteMute.exe.sigstore.json, a detached bundle anyone can check
                  with `sigstore verify`, with the signature recorded in a
                  public transparency log. Windows does not read it, so it does
                  NOT stop the SmartScreen prompt -- it proves who published a
                  file to whoever bothers to ask.
                  Needs: python -m pip install sigstore

    -Certificate  Authenticode: the one Windows itself understands, so the one
                  that fills in the publisher name and, given enough downloads,
                  quiets SmartScreen. Needs a certificate you have to obtain
                  yourself, and they are not free.

    Neither is required. Without either, the exe still carries its full version
    resource -- name, publisher, version, copyright -- and Windows will still
    call the publisher unknown.

    Release builds are signed by .github/workflows/release.yml rather than here,
    so their signature attests to a workflow anyone can read instead of to
    whatever happened on one laptop.
#>
[CmdletBinding()]
param(
    [switch]$OneDir,
    [switch]$Clean,
    [switch]$Sigstore,
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
        --noupx `
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

# Sigstore last: it signs a hash of the file, so it has to see the final bytes,
# and Set-AuthenticodeSignature above rewrites them.
$bundle = $null
if ($Sigstore) {
    Write-Host "==> signing with Sigstore" -ForegroundColor Cyan
    python -m sigstore --version *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "sigstore is not installed: python -m pip install sigstore" -ForegroundColor Red
        exit 1
    }
    $bundle = "$exe.sigstore.json"
    # No key, so no key prompt: this opens a browser and asks an identity
    # provider who you are. In CI there is no browser and no question -- the
    # runner already holds a workflow OIDC token, which sigstore finds by
    # itself.
    python -m sigstore sign --bundle $bundle --overwrite $exe
    if ($LASTEXITCODE -ne 0) {
        Write-Host "sigstore signing failed" -ForegroundColor Red
        exit 1
    }
    Write-Host ""
    python tools\sigstore_identity.py $bundle
}

$size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
$info = (Get-Item $exe).VersionInfo
Write-Host ""
Write-Host "Built $exe ($size MB)" -ForegroundColor Green
Write-Host ("  product      : " + $info.ProductName + " " + $info.ProductVersion)
Write-Host ("  publisher    : " + $info.CompanyName)
Write-Host ("  copyright    : " + $info.LegalCopyright)
Write-Host ("  sha256       : " + (Get-FileHash $exe -Algorithm SHA256).Hash.ToLower())
Write-Host ("  authenticode : " + (Get-AuthenticodeSignature $exe).Status)
if ($bundle) {
    Write-Host ("  sigstore     : " + $bundle)
} else {
    Write-Host "  sigstore     : not signed (pass -Sigstore)"
}
Write-Host "Run it once: it adds itself to the Start menu." -ForegroundColor Green
