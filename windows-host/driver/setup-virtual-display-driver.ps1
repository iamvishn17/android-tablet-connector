# Installs the official VirtualDrivers virtual display driver package via WinGet.
# Run this script from an elevated PowerShell window.
$ErrorActionPreference = "Stop"
$packageId = "VirtualDrivers.Virtual-Display-Driver"
$releasePage = "https://github.com/VirtualDrivers/Virtual-Display-Driver/releases/latest"

Write-Host "Installing the official Virtual Display Driver package..."
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Warning "WinGet is not available on this Windows installation."
    Write-Host "Open the official releases page and install Virtual Driver Control manually:"
    Start-Process $releasePage
    exit 2
}

winget install --id $packageId --exact --accept-source-agreements --accept-package-agreements
if ($LASTEXITCODE -ne 0) {
    Write-Warning "WinGet installation did not complete. Opening the official releases page."
    Start-Process $releasePage
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Package installed. Open Virtual Driver Control and click Install to install/enable the virtual display driver."
Write-Host "Then open Windows Settings > System > Display and choose Extend these displays."
