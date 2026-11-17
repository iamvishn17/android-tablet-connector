VIRTUAL DISPLAY DRIVER SETUP

This project uses the existing Virtual Display Driver maintained by VirtualDrivers.
Official project: https://github.com/VirtualDrivers/Virtual-Display-Driver
Official releases: https://github.com/VirtualDrivers/Virtual-Display-Driver/releases
WinGet package: VirtualDrivers.Virtual-Display-Driver

INSTALL
1. Open PowerShell as Administrator.
2. Run setup-virtual-display-driver.ps1 from this folder.
3. If Virtual Driver Control opens or is installed, launch it and click Install.
4. Open Windows Settings > System > Display.
5. Choose "Extend these displays" and arrange the virtual monitor.
6. Select a tablet-friendly resolution (for example 1920x1200 or 1600x1000).

CONNECT AND STREAM
1. Connect the tablet with a USB data cable and enable USB debugging.
2. Accept the USB debugging authorization prompt on the tablet.
3. Start USBPenDisplayHost.exe.
4. Click Refresh tablet, then Start USB receiver.
5. Install and open the Android APK.
6. Click Refresh displays, select the virtual monitor, then Start screen video.

NOTES
- This is a third-party signed driver; it is not compiled by this project.
- The setup script uses the official WinGet package. If WinGet is unavailable, it opens the official releases page.
- Review upstream release notes and documentation before installation.
- Driver installation requires administrator approval.
- If display problems occur, use Virtual Driver Control to uninstall or disable the virtual display driver.
- The PC companion does not install or change drivers automatically when it starts.
- The PC companion captures only the display selected in its display dropdown.
- Stylus pressure/tilt/hover telemetry remains on the separate USB data channel. Native Windows Ink injection is not part of this milestone.
