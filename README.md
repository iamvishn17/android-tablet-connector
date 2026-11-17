# USB Pen Display
USB-connected Android pen-display project targeting Windows 10 and Windows 11.

## Build 0.1.0: stylus diagnostic
The first APK reports Android input events and values exposed by the tablet: tool type, X/Y, pressure, tilt, orientation and button state. It does not create a Windows extended display yet.

## Build the APK without Android Studio
1. Open the repository's Actions tab.
2. Select Build Android APK.
3. Click Run workflow, or wait for the automatic build after a push.
4. Open the completed workflow run.
5. Download the USB-Pen-Display-debug-APK artifact and extract the APK.

## Install on the Lenovo Tab P12
Transfer the APK to the tablet, open it, and allow installation from that source if Android asks. Launch USB Pen Display - Pen Test and test the Lenovo pen.

## Build the Windows host
On Windows 10 or 11, install Python 3.11+ once. Double-click windows-host/build.bat. The executable is created at windows-host/dist/USBPenDisplayHost.exe.

## Next milestones
1. Verify which pen values the Lenovo Tab P12 actually exposes to Android.
2. Implement reliable USB transport.
3. Implement Windows virtual display creation and video streaming.
4. Implement pressure-sensitive pen injection into Windows.

The APK and host app in this first build are diagnostic scaffolding, not a finished second-monitor product.
