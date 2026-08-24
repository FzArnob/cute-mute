<#
    Pack CuteMute as an MSIX for the Microsoft Store.

        .\tools\make_msix.ps1                       # -> dist\CuteMute.msix
        .\tools\make_msix.ps1 -SelfSign             # ...and sign it for local testing
        .\tools\make_msix.ps1 -IdentityName 12345Name.CuteMute `
                              -IdentityPublisher "CN=ABCDEF12-..." `
                              -PublisherDisplayName "Md. Farhan Zaman"

    The three Identity values come from Partner Center once the app name is
    reserved (Product > Product identity). A package whose Identity does not
    match the reservation exactly is rejected at submission, so the defaults
    here are placeholders that build a *testable* package, not a submittable
    one. See STORE_SUBMISSION.md.

    Needs the Windows SDK for makeappx.exe (and signtool.exe with -SelfSign).
    GitHub's windows-latest runners have both; a local machine may not, which is
    why .github/workflows/msix.yml is the reference build.

    Store submission uploads the *unsigned* package: Microsoft re-signs it with
    its own certificate, which is exactly why a Store install shows your
    publisher name and raises no SmartScreen prompt. -SelfSign is only so you
    can install it yourself and see it work before submitting.
#>
[CmdletBinding()]
param(
    [string]$IdentityName = "CuteMute.FzLab",
    [string]$IdentityPublisher = "CN=CuteMute Development, O=CuteMute, C=US",
    [string]$PublisherDisplayName = "Md. Farhan Zaman",
    [string]$DisplayName = "CuteMute",
    [switch]$SelfSign,
    [switch]$SkipBuild
)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Fail($message) {
    Write-Host $message -ForegroundColor Red
    exit 1
}

function Find-SdkTool($name) {
    $bases = @("${env:ProgramFiles(x86)}\Windows Kits\10\bin",
               "$env:ProgramFiles\Windows Kits\10\bin")
    foreach ($base in $bases) {
        if (-not (Test-Path $base)) { continue }
        $hit = Get-ChildItem -Path $base -Recurse -Filter $name -ErrorAction SilentlyContinue |
               Where-Object { $_.FullName -match "\\x64\\" } |
               Sort-Object FullName -Descending | Select-Object -First 1
        if ($hit) { return $hit.FullName }
    }
    return $null
}

$makeappx = Find-SdkTool "makeappx.exe"
if (-not $makeappx) {
    Fail @"
makeappx.exe not found. Install the Windows SDK (the "Windows SDK Signing Tools
for Desktop Apps" component is enough), or let CI do it:

    gh workflow run msix.yml

Download: https://developer.microsoft.com/windows/downloads/windows-sdk/
"@
}
Write-Host "==> makeappx: $makeappx" -ForegroundColor Cyan

# --- the payload ---------------------------------------------------------- #
# onedir, not onefile: a onefile exe unpacks itself to a temp directory on every
# launch, which inside a package is pure waste -- MSIX already compresses, and
# the files can simply sit there.
if (-not $SkipBuild) {
    Write-Host "==> building (onedir)" -ForegroundColor Cyan
    & "$root\build.ps1" -OneDir
    if ($LASTEXITCODE -ne 0) { Fail "build failed" }
}
$payload = "$root\dist\CuteMute"
if (-not (Test-Path "$payload\CuteMute.exe")) {
    Fail "no onedir build at $payload -- run without -SkipBuild"
}

$version = (python -c "import cutemute; print(cutemute.__version__)").Trim()
if (-not $version) { Fail "could not read cutemute.__version__" }
# MSIX versions are four parts, and the Store requires the revision to be 0.
$parts = @($version.Split(".")) + @("0", "0", "0")
$msixVersion = "{0}.{1}.{2}.0" -f $parts[0], $parts[1], $parts[2]
$description = (python -c "import cutemute; print(cutemute.DESCRIPTION)").Trim()

# --- stage ---------------------------------------------------------------- #
$stage = "$root\build\msix"
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Force $stage | Out-Null

Write-Host "==> staging the payload" -ForegroundColor Cyan
Copy-Item "$payload\*" $stage -Recurse -Force

# The startup task cannot pass arguments, so it launches this copy instead and
# app.py reads its own filename to decide to start hidden. Verified: the onedir
# bootloader locates _internal from the exe's directory, not its name.
Copy-Item "$stage\CuteMute.exe" "$stage\CuteMuteTray.exe" -Force

Copy-Item "$root\packaging\msix\Assets" $stage -Recurse -Force
if (-not (Test-Path "$stage\Assets\StoreLogo.png")) {
    Fail "package assets missing -- run: python tools\make_msix_assets.py"
}

Write-Host "==> writing the manifest" -ForegroundColor Cyan
$manifest = Get-Content "$root\packaging\msix\AppxManifest.xml" -Raw
$manifest = $manifest.Replace("{{IDENTITY_NAME}}", $IdentityName)
$manifest = $manifest.Replace("{{IDENTITY_PUBLISHER}}", $IdentityPublisher)
$manifest = $manifest.Replace("{{VERSION}}", $msixVersion)
$manifest = $manifest.Replace("{{DISPLAY_NAME}}", $DisplayName)
$manifest = $manifest.Replace("{{PUBLISHER_DISPLAY_NAME}}", $PublisherDisplayName)
$manifest = $manifest.Replace("{{DESCRIPTION}}", $description)
if ($manifest -match "{{\w+}}") {
    Fail "unsubstituted placeholder in the manifest: $($Matches[0])"
}
[IO.File]::WriteAllText("$stage\AppxManifest.xml", $manifest,
                        (New-Object Text.UTF8Encoding $false))

# Reject a manifest that is not well-formed before makeappx has to say so.
try { [xml](Get-Content "$stage\AppxManifest.xml" -Raw) | Out-Null }
catch { Fail "AppxManifest.xml is not valid XML: $_" }

# --- pack ----------------------------------------------------------------- #
New-Item -ItemType Directory -Force "$root\dist" | Out-Null
$msix = "$root\dist\CuteMute.msix"
if (Test-Path $msix) { Remove-Item $msix -Force }

Write-Host "==> packing" -ForegroundColor Cyan
& $makeappx pack /d $stage /p $msix /o
if ($LASTEXITCODE -ne 0) { Fail "makeappx failed (exit $LASTEXITCODE)" }

# --- optionally sign, for local testing only ------------------------------ #
if ($SelfSign) {
    $signtool = Find-SdkTool "signtool.exe"
    if (-not $signtool) { Fail "signtool.exe not found (Windows SDK)" }

    # The certificate subject must match Identity Publisher exactly or Windows
    # refuses to install the package.
    Write-Host "==> self-signing for local install" -ForegroundColor Cyan
    $cert = Get-ChildItem Cert:\CurrentUser\My |
            Where-Object { $_.Subject -eq $IdentityPublisher } |
            Select-Object -First 1
    if (-not $cert) {
        $cert = New-SelfSignedCertificate -Type Custom -Subject $IdentityPublisher `
            -KeyUsage DigitalSignature -FriendlyName "CuteMute MSIX test" `
            -CertStoreLocation "Cert:\CurrentUser\My" `
            -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3",
                             "2.5.29.19={text}")
        Write-Host "created a test certificate: $($cert.Thumbprint)"
    }
    & $signtool sign /fd SHA256 /sha1 $cert.Thumbprint $msix
    if ($LASTEXITCODE -ne 0) { Fail "signtool failed" }

    Write-Host ""
    Write-Host "To install it locally you must first trust that test" -ForegroundColor Yellow
    Write-Host "certificate, in an elevated prompt:" -ForegroundColor Yellow
    Write-Host "  Export-Certificate -Cert Cert:\CurrentUser\My\$($cert.Thumbprint) -FilePath test.cer"
    Write-Host "  Import-Certificate -FilePath test.cer -CertStoreLocation Cert:\LocalMachine\TrustedPeople"
    Write-Host "  Add-AppxPackage .\dist\CuteMute.msix"
    Write-Host "Remove it again with: Get-AppxPackage *CuteMute* | Remove-AppxPackage" -ForegroundColor Yellow
}

$size = [math]::Round((Get-Item $msix).Length / 1MB, 1)
Write-Host ""
Write-Host "Built $msix ($size MB)" -ForegroundColor Green
Write-Host "  identity  : $IdentityName"
Write-Host "  publisher : $IdentityPublisher"
Write-Host "  shown as  : $PublisherDisplayName"
Write-Host "  version   : $msixVersion"
if (-not $SelfSign) {
    Write-Host "  unsigned, which is what Partner Center wants: Microsoft signs it." -ForegroundColor Green
}
