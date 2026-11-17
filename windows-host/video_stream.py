"""Low-latency USB screen streaming for USB Pen Display.

Protocol is unchanged: 4-byte big-endian JPEG length followed by JPEG bytes.
The capture side always overwrites a single latest-frame slot; it never builds
an unbounded queue of stale frames.
"""

import socket
import struct
import subprocess
import threading
import time
from io import BytesIO

import mss
from PIL import Image

VIDEO_PORT = 27184
MAX_WIDTH = 1280
MAX_HEIGHT = 720
TARGET_FPS = 30
JPEG_QUALITY = 45
PERF_REPORT_SECONDS = 5.0
SEND_TIMEOUT_SECONDS = 1.5


class LatestFrame:
    """One-frame mailbox. New captures replace an unsent older capture."""

    def __init__(self):
        self._condition = threading.Condition()
        self._frame = None
        self._sequence = 0
        self._dropped = 0

    def put(self, frame):
        with self._condition:
            if self._frame is not None:
                self._dropped += 1
            self._frame = frame
            self._sequence += 1
            self._condition.notify()

    def take(self, stop_event):
        with self._condition:
            while self._frame is None and not stop_event.is_set():
                self._condition.wait(timeout=0.25)
            frame, self._frame = self._frame, None
            return frame

    def dropped_count(self):
        with self._condition:
            return self._dropped

    def wake(self):
        with self._condition:
            self._condition.notify_all()


class PerfStats:
    """Five-second rolling performance report for the sender thread."""

    def __init__(self, log, latest):
        self.log = log
        self.latest = latest
        self.reset()

    def reset(self):
        self.started = time.perf_counter()
        self.frames = 0
        self.encode_seconds = 0.0
        self.send_seconds = 0.0
        self.capture_seconds = 0.0
        self.total_bytes = 0
        self.last_dropped = self.latest.dropped_count()

    def record(self, capture_seconds, encode_seconds, send_seconds, frame_bytes):
        self.frames += 1
        self.capture_seconds += capture_seconds
        self.encode_seconds += encode_seconds
        self.send_seconds += send_seconds
        self.total_bytes += frame_bytes
        elapsed = time.perf_counter() - self.started
        if elapsed >= PERF_REPORT_SECONDS:
            n = max(1, self.frames)
            dropped = self.latest.dropped_count() - self.last_dropped
            self.log(
                f"[perf] fps={n / elapsed:.1f} dropped={dropped} "
                f"capture={self.capture_seconds / n * 1000:.1f}ms "
                f"encode={self.encode_seconds / n * 1000:.1f}ms "
                f"send={self.send_seconds / n * 1000:.1f}ms "
                f"avg_frame={self.total_bytes / n / 1024:.0f}KB"
            )
            self.reset()


def list_monitors():
    """Return real display outputs (excluding mss' virtual all-monitors entry)."""
    with mss.mss() as capture:
        return [
            (index, int(item["width"]), int(item["height"]),
             int(item["left"]), int(item["top"]))
            for index, item in enumerate(capture.monitors)
            if index > 0
        ]


class VideoStreamer:
    def __init__(self, log):
        self.log = log
        self.running = False
        self.server = None
        self.client = None
        self.thread = None
        self._state_lock = threading.Lock()

    def start(self, adb, device, monitor_index=1):
        if self.running:
            self.log("Video streamer is already running.")
            return

        def setup():
            try:
                result = subprocess.run(
                    [adb, "-s", device, "reverse", f"tcp:{VIDEO_PORT}", f"tcp:{VIDEO_PORT}"],
                    capture_output=True, text=True, timeout=12
                )
                if result.returncode:
                    raise RuntimeError((result.stderr or result.stdout).strip())
                server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.bind(("127.0.0.1", VIDEO_PORT))
                server.listen(1)
                server.settimeout(1.0)
                with self._state_lock:
                    self.server = server
                    self.running = True
                self.log(f"Video channel ready on USB port {VIDEO_PORT}; waiting for tablet.")
                self.thread = threading.Thread(
                    target=self._accept, args=(monitor_index,), daemon=True,
                    name="UsbVideoAccept"
                )
                self.thread.start()
            except Exception as exc:
                self.log("Could not start video channel: " + str(exc))

        threading.Thread(target=setup, daemon=True, name="UsbVideoSetup").start()

    def _accept(self, monitor_index):
        while self.running and self.server:
            try:
                conn, _ = self.server.accept()
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                # Bound kernel buffering so a slow tablet cannot accumulate a
                # long backlog of obsolete JPEG frames.
                conn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 512 * 1024)
                conn.settimeout(SEND_TIMEOUT_SECONDS)
                self.client = conn
                self.log(f"Tablet connected to video channel. Streaming Windows display #{monitor_index} at up to {TARGET_FPS} FPS.")
                threading.Thread(
                    target=self._send_frames, args=(conn, monitor_index), daemon=True,
                    name="UsbVideoSender"
                ).start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _capture_frames(self, capture, monitor, latest, stop_event):
        interval = 1.0 / TARGET_FPS
        next_frame_at = time.perf_counter()
        while self.running and not stop_event.is_set():
            started = time.perf_counter()
            try:
                shot = capture.grab(monitor)
                # Copy the raw buffer because the mss screenshot object is
                # released/reused after the next grab.
                frame = (shot.size, bytes(shot.bgra), time.perf_counter() - started)
                latest.put(frame)
            except Exception as exc:
                self.log("Screen capture failed: " + str(exc))
                stop_event.set()
                latest.wake()
                break
            next_frame_at += interval
            delay = next_frame_at - time.perf_counter()
            if delay > 0:
                stop_event.wait(delay)
            else:
                # If capture is behind schedule, reset the clock rather than
                # trying to burst-capture frames to catch up.
                next_frame_at = time.perf_counter()

    def _send_frames(self, conn, monitor_index):
        stop_event = threading.Event()
        capture_thread = None
        latest = LatestFrame()
        try:
            with mss.mss() as capture:
                if monitor_index <= 0 or monitor_index >= len(capture.monitors):
                    monitor_index = 1
                monitor = capture.monitors[monitor_index]
                capture_thread = threading.Thread(
                    target=self._capture_frames,
                    args=(capture, monitor, latest, stop_event),
                    daemon=True, name="UsbVideoCapture"
                )
                capture_thread.start()
                stats = PerfStats(self.log, latest)
                while self.running and conn is self.client and not stop_event.is_set():
                    item = latest.take(stop_event)
                    if item is None:
                        continue
                    size, bgra, capture_seconds = item
                    encode_started = time.perf_counter()
                    frame = Image.frombytes("RGB", size, bgra, "raw", "BGRX")
                    if frame.width > MAX_WIDTH or frame.height > MAX_HEIGHT:
                        frame.thumbnail((MAX_WIDTH, MAX_HEIGHT), Image.Resampling.BILINEAR)
                    buffer = BytesIO()
                    frame.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=False)
                    payload = buffer.getvalue()
                    encode_seconds = time.perf_counter() - encode_started
                    send_started = time.perf_counter()
                    conn.sendall(struct.pack(">I", len(payload)) + payload)
                    send_seconds = time.perf_counter() - send_started
                    stats.record(capture_seconds, encode_seconds, send_seconds, len(payload))
        except socket.timeout:
            if self.running:
                self.log("Video send stalled for too long; reconnecting to avoid showing delayed frames.")
        except (ConnectionError, OSError) as exc:
            if self.running:
                self.log("Video connection ended: " + str(exc))
        except Exception as exc:
            if self.running:
                self.log("Video streamer error: " + str(exc))
        finally:
            stop_event.set()
            latest.wake()
            if capture_thread and capture_thread.is_alive():
                capture_thread.join(timeout=2.0)
            try:
                conn.close()
            except OSError:
                pass
            if self.client is conn:
                self.client = None

    def stop(self, adb=None, device=None):
        self.running = False
        for item in (self.client, self.server):
            try:
                if item:
                    item.close()
            except OSError:
                pass
        self.client = None
        self.server = None
        if adb and device:
            try:
                subprocess.Popen(
                    [adb, "-s", device, "reverse", "--remove", f"tcp:{VIDEO_PORT}"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            except OSError:
                pass
