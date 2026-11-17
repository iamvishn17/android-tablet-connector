# USB Pen Display
USB-connected Android tablet + Windows pen-display project targeting Windows 10 and Windows 11.

## Current test build: USB pen data over USB (0.3.0 / Android 0.2.0)

The Android app reads stylus MotionEvents and sends them as newline-delimited JSON over a local TCP socket. The Windows companion creates an ADB reverse tunnel (tcp:27183) over the USB cable, receives those events, and displays the latest X/Y, pressure, tilt, orientation, button, hover and contact values.

This is a transport proof-of-concept. It is not yet a virtual monitor, video streamer, or Windows Ink pen injector.

### Build and download

- **Android APK:** open Actions → **Build Android APK** → latest successful run → download **USB-Pen-Display-debug-APK**.
- **Windows EXE:** open Actions → **Build Windows Host** → latest successful run → download **USB-Pen-Display-Windows**. Extract and run USBPenDisplayHost.exe.

No Android Studio is required; the APK is built by GitHub Actions.

### Test the USB pen link

1. Install Android SDK Platform-Tools (ADB) on Windows: https://developer.android.com/tools/releases/platform-tools
2. Enable Developer options and USB debugging on the Lenovo Tab P12.
3. Connect the tablet using a USB data cable, unlock it, and accept the USB debugging authorization prompt.
4. Open the Windows companion and click **Refresh connection**. Confirm the tablet is authorized.
5. Click **Start USB pen link** in the **Live USB Pen Data** section.
6. Open the updated Android diagnostic APK on the tablet (or click **Open tablet diagnostic**).
7. Move the Lenovo pen, hover if supported, and press with different pressure. The Windows window should show incoming values in **Last received pen event**.

If the PC link says it is waiting, make sure the Windows app is the new 0.3.0 build, click Start USB pen link first, and then reopen the Android diagnostic app. Keep the diagnostic app open during this test.

### Protocol details

- Transport: ADB reverse TCP over the physical USB connection; no Wi-Fi or internet transport is used.
- Host listener: 127.0.0.1:27183.
- Protocol: UTF-8 JSON Lines; first message is a protocol hello, followed by pen event objects.
- The Android app retries the local socket connection while it is open and keeps a bounded event queue to avoid unbounded memory growth.

## Build Windows host locally

On Windows 10 or 11, install Python 3.11+ and run windows-host/build.bat. The executable is created at windows-host/dist/USBPenDisplayHost.exe.

## Roadmap

1. Validate live stylus data delivery and measure latency.
2. Improve event fidelity and connection lifecycle.
3. Implement Windows virtual display creation and PC-to-tablet video streaming.
4. Implement pressure-sensitive pen injection into Windows.
5. Package and optimize the complete wired extended-display product.

The current build only proves the USB pen-data transport; it does not yet create an extended desktop.
