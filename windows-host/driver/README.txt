MILESTONE 4 - VIRTUAL DISPLAY DRIVER (DEVELOPMENT PREVIEW)

This folder contains scripts for the Microsoft IddCx sample driver package built for this project.
The driver is a development/test build, not a production-signed release.

INSTALL ORDER
1. Read the project README and Microsoft IddCx sample documentation.
2. Run enable-test-mode.ps1 as Administrator only if you accept the security implications.
3. Restart Windows.
4. Run install-driver.ps1 as Administrator.
5. Run IddSampleApp.exe and leave it open. It creates the sample software device; closing it removes the virtual display.
6. Open Windows Settings > System > Display and choose Extend these displays.
7. Open USBPenDisplayHost.exe, click Refresh displays, select the virtual display, then click Start screen video.

IMPORTANT
- The Microsoft sample is only a starting point. It enumerates a virtual display and processes the OS swap chain, but it does not yet send frames to Android itself.
- Our PC companion captures the selected Windows display and sends it over the existing ADB USB tunnel.
- Test-signing mode may be blocked by Secure Boot or organization policy.
- This is not a production driver and must not be distributed as a signed commercial driver.
- Windows 10/11 compatibility depends on the installed Windows build and available IddCx/WDK support.
- Keep the original Microsoft copyright and license notices with the sample source.

CI note: only the x64 WDK package is restored, and the driver build is driven by Microsoft's Build-Samples.ps1 script.
