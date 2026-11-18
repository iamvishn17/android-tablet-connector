import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
from vmulti_bridge import VMultiBridge

PACKAGE = "dev.anydisplay.client"
POLL_SECONDS = 2.0

def app_dir():
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent

def hidden_flags():
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)

class Receiver:
    def __init__(self, root):
        self.root = root
        self.base = app_dir()
        self.adb = self.base / "platform-tools" / "adb.exe"
        self.host = self.base / "anydisplay-win.exe"
        self.apk = self.base.parent / "Android" / "AnyDisplay-Final.apk"
        self.events = queue.Queue()
        self.device = None
        self.session_device = None
        self.host_process = None
        self.worker_busy = False
        self.stopping = False
        self.last_log = ""
        self.root.title("USB Pen Display")
        self.root.geometry("900x650")
        self.root.minsize(760, 560)
        self.root.configure(bg="#0b1220")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#0b1220")
        style.configure("Panel.TFrame", background="#121d2e")
        style.configure("TLabel", background="#0b1220", foreground="#e6edf7", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 25, "bold"), foreground="#ffffff")
        style.configure("Sub.TLabel", foreground="#91a3ba", font=("Segoe UI", 10))
        style.configure("PanelTitle.TLabel", background="#121d2e", foreground="#ffffff",
                        font=("Segoe UI", 11, "bold"))
        style.configure("Value.TLabel", background="#121d2e", foreground="#e6edf7",
                        font=("Segoe UI", 12, "bold"))
        style.configure("Action.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 10))
        style.configure("TButton", padding=7)

        outer = ttk.Frame(root, padding=22)
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer)
        header.pack(fill="x")
        ttk.Label(header, text="USB PEN DISPLAY", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Wired display streaming with integrated pressure-sensitive pen input",
                  style="Sub.TLabel").pack(anchor="w", pady=(3, 18))

        status_panel = ttk.Frame(outer, style="Panel.TFrame", padding=18)
        status_panel.pack(fill="x")
        self.main_status = ttk.Label(status_panel, text="Looking for your tablet…",
                                     style="PanelTitle.TLabel", font=("Segoe UI", 17, "bold"))
        self.main_status.pack(anchor="w")
        self.detail = ttk.Label(status_panel, text="Connect the tablet by USB and unlock it. USB debugging must be enabled.",
                                background="#121d2e", foreground="#91a3ba", wraplength=800)
        self.detail.pack(anchor="w", pady=(7, 0))

        grid = ttk.Frame(outer)
        grid.pack(fill="x", pady=14)
        self.connection_value = self.make_card(grid, "USB CONNECTION", "Searching…", 0)
        self.stream_value = self.make_card(grid, "DISPLAY STREAM", "Waiting for tablet", 1)
        self.pen_value = self.make_card(grid, "PEN INPUT", "Ready when connected", 2)

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(0, 12))
        self.retry_button = ttk.Button(actions, text="Reconnect / Retry", style="Action.TButton",
                                       command=self.retry)
        self.retry_button.pack(side="left")
        self.stop_button = ttk.Button(actions, text="Stop sharing", command=self.stop_sharing,
                                      state="disabled")
        self.stop_button.pack(side="left", padx=8)
        ttk.Label(actions, text="Automatic USB detection is enabled",
                  style="Sub.TLabel").pack(side="right", pady=8)

        log_panel = ttk.Frame(outer, style="Panel.TFrame", padding=12)
        log_panel.pack(fill="both", expand=True)
        ttk.Label(log_panel, text="CONNECTION LOG", style="PanelTitle.TLabel").pack(anchor="w")
        self.log = tk.Text(log_panel, height=12, bg="#080e18", fg="#b9c9dc", insertbackground="white",
                           relief="flat", borderwidth=0, font=("Consolas", 9), state="disabled",
                           wrap="word")
        self.log.pack(fill="both", expand=True, pady=(8, 0))
        self.write("Receiver ready. Waiting for a USB-authorized Android tablet.")
        self.write("When detected, the receiver installs/opens the tablet client and starts the display session.")
        self.vm_bridge = VMultiBridge(self.write)
        self.vm_bridge.start()
        self.write("Pen output backend: VMulti virtual HID digitizer (Windows Ink).")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(500, self.tick)

    def make_card(self, parent, heading, value, column):
        card = ttk.Frame(parent, style="Panel.TFrame", padding=14)
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 7, 0))
        parent.columnconfigure(column, weight=1)
        ttk.Label(card, text=heading, style="PanelTitle.TLabel").pack(anchor="w")
        label = ttk.Label(card, text=value, style="Value.TLabel")
        label.pack(anchor="w", pady=(9, 0))
        return label

    def write(self, line):
        stamp = time.strftime("%H:%M:%S")
        self.log.configure(state="normal")
        self.log.insert("end", f"[{stamp}] {line}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def adb_run(self, args, timeout=25):
        if not self.adb.is_file():
            raise RuntimeError("ADB is missing. Keep the platform-tools folder beside this receiver.")
        return subprocess.run([str(self.adb), *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout,
                              creationflags=hidden_flags())

    def scan(self):
        try:
            result = self.adb_run(["devices", "-l"], timeout=10)
            rows = [x.strip() for x in result.stdout.splitlines()[1:] if x.strip()]
            for row in rows:
                parts = row.split()
                if len(parts) > 1 and parts[1] == "device":
                    serial = parts[0]
                    model = next((p.split(":", 1)[1].replace("_", " ") for p in parts[2:]
                                  if p.startswith("model:")), "Android tablet")
                    return serial, model, None
            if any("unauthorized" in row for row in rows):
                return None, None, "Tablet detected. Unlock it and accept the USB debugging authorization prompt."
            return None, None, None
        except Exception as exc:
            return None, None, str(exc)

    def tick(self):
        if self.stopping:
            return
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "log":
                    self.write(payload)
                elif kind == "worker_done":
                    self.worker_busy = False
                elif kind == "host_started":
                    self.stream_value.configure(text="Host running — connecting")
                    self.pen_value.configure(text="Native pen input enabled")
                    self.stop_button.configure(state="normal")
                elif kind == "setup_failed":
                    self.worker_busy = False
                    self.session_device = None
                    self.stream_value.configure(text="Connection failed")
                    self.pen_value.configure(text="Not active")
                    self.main_status.configure(text="Could not start display sharing")
                    self.detail.configure(text=payload)
                elif kind == "host_exit":
                    code = payload
                    self.host_process = None
                    self.stream_value.configure(text="Stream stopped")
                    self.pen_value.configure(text="Not active")
                    if self.device:
                        self.main_status.configure(text="Tablet connected — stream stopped")
                        self.detail.configure(text="Use Reconnect / Retry to start the display session again.")
                    self.write(f"Display host exited (code {code}).")
        except queue.Empty:
            pass

        if not self.worker_busy:
            serial, model, error = self.scan()
            if error:
                self.connection_value.configure(text="Check USB authorization")
                self.main_status.configure(text="Tablet needs attention")
                self.detail.configure(text=error)
            elif serial:
                self.connection_value.configure(text=model)
                self.device = serial
                if self.session_device != serial and self.host_process is None:
                    self.start_session(serial, model)
                elif self.host_process and self.host_process.poll() is None:
                    self.main_status.configure(text="Connected — display sharing active")
                    self.detail.configure(text=f"{model} is connected over USB. Pen pressure is integrated into the Windows pen input stream.")
            else:
                self.connection_value.configure(text="Not connected")
                if self.device or self.host_process:
                    self.write("Tablet disconnected.")
                    self.stop_host_process()
                self.device = None
                self.session_device = None
                self.stream_value.configure(text="Waiting for tablet")
                self.pen_value.configure(text="Ready when connected")
                self.main_status.configure(text="Looking for your tablet…")
                self.detail.configure(text="Connect the tablet by USB and unlock it. USB debugging must be enabled.")
        self.root.after(int(POLL_SECONDS * 1000), self.tick)

    def start_session(self, serial, model):
        self.worker_busy = True
        self.session_device = serial
        self.main_status.configure(text="Preparing tablet connection…")
        self.detail.configure(text="Checking the tablet client and starting the USB display session.")
        self.stream_value.configure(text="Starting…")
        self.pen_value.configure(text="Initializing…")
        self.write(f"Authorized tablet found: {model} ({serial}).")
        threading.Thread(target=self.session_worker, args=(serial,), daemon=True).start()

    def session_worker(self, serial):
        try:
            if not self.host.is_file():
                raise RuntimeError("anydisplay-win.exe is missing from the Windows folder.")
            if not self.apk.is_file():
                raise RuntimeError("The bundled Android APK is missing. Re-extract the complete ZIP.")
            self.events.put(("log", "Installing/updating the Android display client…"))
            install = self.adb_run(["-s", serial, "install", "-r", str(self.apk)], timeout=120)
            if install.returncode != 0:
                raise RuntimeError((install.stderr or install.stdout).strip() or "APK installation failed.")
            self.events.put(("log", "Opening the USB reverse tunnel for pen telemetry…"))
            reverse = self.adb_run(["-s", serial, "reverse", "tcp:27183", "tcp:27183"], timeout=15)
            if reverse.returncode != 0:
                raise RuntimeError((reverse.stderr or reverse.stdout).strip() or "Could not establish the pen telemetry USB tunnel.")
            self.events.put(("log", "VMulti pen telemetry tunnel is ready."))
            self.events.put(("log", "Launching the tablet display client…"))
            launch = self.adb_run(["-s", serial, "shell", "monkey", "-p", PACKAGE, "1"], timeout=20)
            if launch.returncode != 0:
                raise RuntimeError((launch.stderr or launch.stdout).strip() or "Could not launch the tablet client.")
            time.sleep(1.5)
            self.events.put(("log", "Starting AnyDisplay USB host with native pen injection…"))
            process = subprocess.Popen(
                [str(self.host), "usb", serial, "--codec", "h264", "--no-audio",
                 "--no-clipboard", "--yes"],
                cwd=str(self.base), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                creationflags=hidden_flags()
            )
            self.host_process = process
            self.events.put(("host_started", process.pid))
            threading.Thread(target=self.read_host_log, args=(process,), daemon=True).start()
            self.events.put(("log", "Display host launched. Waiting for the tablet session handshake…"))
        except Exception as exc:
            self.events.put(("log", "Connection setup failed: " + str(exc)))
            self.events.put(("setup_failed", str(exc)))
        finally:
            self.events.put(("worker_done", None))

    def read_host_log(self, process):
        try:
            for line in process.stdout:
                clean = line.strip()
                if clean:
                    self.events.put(("log", clean))
        except Exception as exc:
            self.events.put(("log", "Host log reader: " + str(exc)))
        code = process.wait()
        self.events.put(("host_exit", code))

    def retry(self):
        self.stop_host_process()
        self.session_device = None
        self.write("Manual reconnect requested.")
        self.tick()

    def stop_host_process(self):
        process = self.host_process
        self.host_process = None
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        self.stream_value.configure(text="Stopped")
        self.pen_value.configure(text="Not active")

    def stop_sharing(self):
        self.stop_host_process()
        self.session_device = self.device
        self.main_status.configure(text="Sharing stopped")
        self.detail.configure(text="The tablet remains connected. Press Reconnect / Retry to resume sharing.")

    def close(self):
        self.stopping = True
        self.stop_host_process()
        if self.device:
            try:
                self.adb_run(["-s", self.device, "reverse", "--remove", "tcp:27183"], timeout=5)
            except Exception:
                pass
        self.vm_bridge.stop()
        self.root.destroy()

def main():
    root = tk.Tk()
    Receiver(root)
    root.mainloop()

if __name__ == "__main__":
    main()
