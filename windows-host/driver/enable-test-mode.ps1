$ErrorActionPreference = "Stop"
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Right-click PowerShell and choose Run as administrator, then run this script again."
}
Write-Warning "This enables Windows TESTSIGNING mode for development drivers. It is not intended as a normal security setting."
Write-Host "If Secure Boot is enabled, Windows may refuse this setting. Do not disable Secure Boot unless you understand the security implications."
$answer = Read-Host "Type ENABLE to enable test-signing mode"
if ($answer -cne "ENABLE") { Write-Host "Cancelled."; exit 0 }
& bcdedit.exe /set testsigning on
if ($LASTEXITCODE -ne 0) { throw "Could not enable test-signing mode. Secure Boot or policy may be blocking it." }
Write-Host "Test-signing mode enabled. Restart Windows before installing the test driver." -ForegroundColor Yellow
