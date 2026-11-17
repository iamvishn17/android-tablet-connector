$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$inf = Join-Path $root "IddSampleDriver.inf"
$cert = Join-Path $root "IddSampleDriver.cer"

Write-Host "LAB/USB Pen Display - Milestone 4 virtual display driver installer" -ForegroundColor Cyan
if (-not (Test-Path $inf)) { throw "IddSampleDriver.inf is missing from this folder." }

$boot = (bcdedit /enum "{current}" 2>$null | Out-String)
if ($boot -notmatch "testsigning\s+Yes") {
    Write-Host "Windows test-signing mode is not enabled." -ForegroundColor Yellow
    Write-Host "This is a development/test driver, not a production-signed driver."
    Write-Host "Run enable-test-mode.ps1 as Administrator, reboot, then run this installer again."
    exit 2
}

if (Test-Path $cert) {
    Import-Certificate -FilePath $cert -CertStoreLocation "Cert:\LocalMachine\Root" | Out-Null
    Import-Certificate -FilePath $cert -CertStoreLocation "Cert:\LocalMachine\TrustedPublisher" | Out-Null
} else {
    Write-Warning "No test certificate file found. Windows may reject the driver package."
}

& pnputil.exe /add-driver $inf /install
if ($LASTEXITCODE -ne 0) { throw "pnputil failed with exit code $LASTEXITCODE" }
Write-Host "Driver package added. Next, run IddSampleApp.exe to create the virtual display device." -ForegroundColor Green
