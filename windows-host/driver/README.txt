VIRTUAL DISPLAY DRIVER - INCLUDED IN MILESTONE 4 PACKAGE

The official Virtual Display Driver release is bundled in:
Windows/Virtual-Display-Driver/

Official project: https://github.com/VirtualDrivers/Virtual-Display-Driver
Official releases: https://github.com/VirtualDrivers/Virtual-Display-Driver/releases
License: MIT (upstream project)

INSTALL
1. Open the Extracted-Driver-Files folder beside this README.
2. Follow the upstream installer/control-app instructions included in that release.
3. Approve the Windows administrator/UAC prompt when asked.
4. Open Windows Settings > System > Display.
5. Choose "Extend these displays" and arrange the virtual monitor.
6. Select a tablet-friendly resolution (for example 1920x1200 or 1600x1000).

CONNECT AND STREAM
1. Connect the tablet with a USB data cable and enable USB debugging.
2. Accept the USB debugging authorization prompt on the tablet.
3. Start USBPenDisplayHost.exe.
4. Click Refresh tablet, then Start USB receiver.
5. Install and open Android/app-debug.apk.
6. Click Refresh displays, select the virtual monitor, then Start screen video.

NOTES
- This is the upstream third-party driver, not a driver compiled by this project.
- Driver installation requires administrator approval and may require a Windows restart.
- Review the upstream release notes and license before installation.
- If display problems occur, use the upstream Virtual Driver Control/uninstaller to disable or remove the virtual display driver.
- The PC companion does not install or change drivers automatically when it starts.
- The PC companion captures only the display selected in its display dropdown.
- Stylus pressure/tilt/hover telemetry remains on the separate USB data channel. Native Windows Ink injection is not part of this milestone.
