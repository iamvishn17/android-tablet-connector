# USB Pen Display
USB-connected Android pen-display project targeting Windows 10 and Windows 11.

## Android diagnostic APK 0.1.0
The first APK reports Android input events and values exposed by the tablet: tool type, X/Y, pressure, tilt, orientation and button state. It does not create a Windows extended display yet.

## Windows companion 0.2.0
The Windows app detects Android devices through ADB over USB, reports authorization state, can launch the tablet diagnostic app, and can install/update an APK.

### Download the Windows app
Open the repository Actions tab, select **Build Windows Host**, open the latest successful run, and download the **USB-Pen-Display-Windows** artifact. Extract the ZIP and run `USBPenDisplayHost.exe`.

### One-time Windows setup
1. Install Android SDK Platform-Tools from https://developer.android.com/tools/releases/platform-tools
2. On the Lenovo Tab P12, enable Developer options (tap Build number seven times in Settings > About tablet).
3. In Developer options, enable USB debugging.
4. Connect the tablet to the PC using a USB data cable.
5. Unlock the tablet and accept the USB debugging authorization prompt.
6. Open the Windows companion and click **Refresh connection**.

The companion expects `adb.exe` on PATH or in a standard Android SDK Platform-Tools location.

## Build the Windows host locally
On Windows 10 or 11, install Python 3.11+ once. Double-click `windows-host/build.bat`. The executable is created at `windows-host/dist/USBPenDisplayHost.exe`.

## Build the APK without Android Studio
Open Actions, select **Build Android APK**, and download the `USB-Pen-Display-debug-APK` artifact from a successful run.

## Next milestones
1. Verify which pen values the Lenovo Tab P12 exposes to Android.
2. Add a USB data protocol between tablet and Windows host.
3. Implement Windows virtual display creation and video streaming.
4. Implement pressure-sensitive pen injection into Windows.

The current APK and Windows companion are diagnostic/connection foundations, not a finished second-monitor product.
