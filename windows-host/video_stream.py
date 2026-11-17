import socket
import struct
import subprocess
import threading
import time
from io import BytesIO

import mss
from PIL import Image

VIDEO_PORT = 27184
MAX_WIDTH = 1600
MAX_HEIGHT = 1000
TARGET_FPS = 24
JPEG_QUALITY = 65


class VideoStreamer:
    def __init__(self, log):
        self.log = log
        self.running = False
        self.server = None
        self.client = None
        self.thread = None

    def start(self, adb, device):
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
                server.settimeout(1)
                self.server = server
                self.running = True
                self.log(f"Video channel ready on USB port {VIDEO_PORT}; waiting for tablet.")
                self.thread = threading.Thread(target=self._accept, daemon=True)
                self.thread.start()
            except Exception as exc:
                self.log("Could not start video channel: " + str(exc))

        threading.Thread(target=setup, daemon=True).start()

    def _accept(self):
        while self.running and self.server:
            try:
                conn, _ = self.server.accept()
                self.client = conn
                self.log("Tablet connected to video channel. Sending primary screen.")
                threading.Thread(target=self._send_frames, args=(conn,), daemon=True).start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _send_frames(self, conn):
        try:
            with mss.mss() as capture:
                monitor = capture.monitors[1]
                while self.running and conn is self.client:
                    started = time.perf_counter()
                    shot = capture.grab(monitor)
                    frame = Image.frombytes("RGB", shot.size, shot.rgb)
                    frame.thumbnail((MAX_WIDTH, MAX_HEIGHT), Image.Resampling.LANCZOS)
                    buffer = BytesIO()
                    frame.save(buffer, format="JPEG", quality=JPEG_QUALITY)
                    payload = buffer.getvalue()
                    conn.sendall(struct.pack(">I", len(payload)) + payload)
                    time.sleep(max(0, 1 / TARGET_FPS - (time.perf_counter() - started)))
        except Exception as exc:
            if self.running:
                self.log("Video connection ended: " + str(exc))
        finally:
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
