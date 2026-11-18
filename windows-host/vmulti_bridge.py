#!/usr/bin/env python3
"""Bridge Android PenTelemetry JSON to the VMulti Windows HID digitizer.

VMulti must be installed separately (administrator install + reboot may be required).
This process never installs or modifies a kernel driver.
"""
from __future__ import annotations

import json
import math
import socket
import threading
import time

PORT = 27183
VID = 0x00FF
PID = 0xBACC
VMULTI_ID = 0x40
REPORT_ID_EXTENDED = 0x06
REPORT_SIZE = 12

class VMultiBridge:
    def __init__(self, log):
        self.log = log
        self.stop_event = threading.Event()
        self.server = None
        self.thread = None
        self.device = None
        self.hid_module = None
        self.last_state = None
        self.last_report_time = 0.0

    def start(self):
        self.thread = threading.Thread(target=self._serve, name="VMultiBridge", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        try:
            if self.server:
                self.server.close()
        except Exception:
            pass
        self._close_device()

    def _close_device(self):
        if self.device:
            try:
                self.device.close()
            except Exception:
                pass
            self.device = None

    def _open_device(self):
        if self.device:
            return True
        try:
            import hid
            self.hid_module = hid
        except Exception as exc:
            self.log("VMulti bridge: Python hidapi is unavailable: " + str(exc))
            return False
        try:
            candidates = hid.enumerate(VID, PID)
            if not candidates:
                self.log("VMulti not detected. Install VMulti from https://github.com/X9VoiD/vmulti-bin/releases/latest")
                return False
            for item in candidates:
                path = item.get("path")
                if not path:
                    continue
                dev = hid.device()
                try:
                    dev.open_path(path)
                    self.device = dev
                    self.log("VMulti HID device opened (VID 00FF / PID BACC).")
                    return True
                except Exception:
                    try:
                        dev.close()
                    except Exception:
                        pass
            self.log("VMulti was detected but could not be opened. Check driver installation and permissions.")
        except Exception as exc:
            self.log("VMulti detection failed: " + str(exc))
        return False

    @staticmethod
    def _signed_byte(value):
        return int(value) & 0xFF

    def _make_report(self, packet):
        width = max(float(packet.get("canvasWidth", 0) or 0), 1.0)
        height = max(float(packet.get("canvasHeight", 0) or 0), 1.0)
        x = max(0, min(32767, round(float(packet.get("canvasX", 0) or 0) / width * 32767)))
        y = max(0, min(32767, round(float(packet.get("canvasY", 0) or 0) / height * 32767)))
        pressure = max(0.0, min(1.0, float(packet.get("pressure", 0) or 0)))
        tool = str(packet.get("tool", "")).upper()
        action = str(packet.get("action", "")).upper()
        contact = bool(packet.get("contact", False)) and not bool(packet.get("hover", False))
        in_range = bool(packet.get("hover", False)) or contact
        if action in ("ACTION_HOVER_EXIT", "ACTION_UP", "ACTION_CANCEL", "ACTION_OUTSIDE"):
            contact = False
            in_range = action not in ("ACTION_HOVER_EXIT", "ACTION_CANCEL", "ACTION_OUTSIDE")
            if action == "ACTION_UP":
                in_range = True

        buttons = 0
        if in_range:
            buttons |= 0x10
        if contact and pressure > 0:
            buttons |= 0x01
        if tool == "ERASER":
            buttons |= 0x04
        android_buttons = int(packet.get("buttons", 0) or 0)
        if android_buttons & (32 | 64):
            buttons |= 0x02

        tilt = max(0.0, min(math.pi / 2, float(packet.get("tilt", 0) or 0)))
        orientation = float(packet.get("orientation", 0) or 0)
        tilt_x = max(-90, min(90, round(math.degrees(math.sin(orientation) * tilt))))
        tilt_y = max(-90, min(90, round(math.degrees(math.cos(orientation) * tilt))))

        pressure_value = round(pressure * 16383) if contact else 0
        # VMulti DigitizerInputReport: header(4), X/Y/pressure(2 each), X/Y tilt(1 each).
        return bytes((
            VMULTI_ID, REPORT_SIZE - 1, REPORT_ID_EXTENDED, buttons,
            x & 0xFF, (x >> 8) & 0xFF,
            y & 0xFF, (y >> 8) & 0xFF,
            pressure_value & 0xFF, (pressure_value >> 8) & 0xFF,
            self._signed_byte(tilt_x), self._signed_byte(tilt_y),
        ))

    def _send(self, packet):
        if not self._open_device():
            return
        try:
            report = self._make_report(packet)
            written = self.device.write(list(report))
            if written <= 0:
                raise RuntimeError("HID write returned no bytes")
            self.last_report_time = time.monotonic()
        except Exception as exc:
            self.log("VMulti pen report failed: " + str(exc))
            self._close_device()

    def _serve(self):
        # Probe immediately so a missing driver is visible before the user starts drawing.
        self._open_device()
        try:
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server.bind(("127.0.0.1", PORT))
            self.server.listen(1)
            self.server.settimeout(0.5)
            self.log(f"VMulti bridge listening on 127.0.0.1:{PORT}; waiting for Android pen telemetry.")
        except Exception as exc:
            self.log("VMulti bridge could not listen: " + str(exc))
            return

        while not self.stop_event.is_set():
            try:
                conn, address = self.server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            self.log("Android pen telemetry connected.")
            with conn:
                conn.settimeout(1.0)
                buffer = b""
                while not self.stop_event.is_set():
                    try:
                        chunk = conn.recv(4096)
                        if not chunk:
                            break
                        buffer += chunk
                        while b"\n" in buffer:
                            line, buffer = buffer.split(b"\n", 1)
                            if not line.strip():
                                continue
                            try:
                                packet = json.loads(line.decode("utf-8"))
                            except Exception:
                                continue
                            if packet.get("type") == "hello":
                                self.log("Pen telemetry protocol " + str(packet.get("protocol", "?")) + " ready.")
                            elif packet.get("type") == "pen":
                                self._send(packet)
                    except socket.timeout:
                        continue
                    except Exception as exc:
                        self.log("Pen telemetry connection error: " + str(exc))
                        break
            self._send({"canvasWidth": 1, "canvasHeight": 1, "canvasX": 0, "canvasY": 0,
                        "pressure": 0, "contact": False, "hover": False, "action": "ACTION_UP"})
            self.log("Android pen telemetry disconnected.")
        self._close_device()
