import json, os, platform, queue, shutil, socket, subprocess, threading, tkinter as tk
from video_stream import VideoStreamer
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

APP_ID = "com.usbpendisplay.diagnostic"
PORT = 27183

def find_adb():
    found = shutil.which("adb") or shutil.which("adb.exe")
    if found:
        return found
    roots = [os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT"),
             str(Path.home() / "AppData/Local/Android/Sdk"), "C:/platform-tools"]
    for root in roots:
        if root:
            candidate = Path(root) / "platform-tools" / "adb.exe"
            if candidate.is_file():
                return str(candidate)
            candidate = Path(root) / "adb.exe"
            if candidate.is_file():
                return str(candidate)
    return None

class Host:
    def __init__(self, root):
        self.root = root
        self.adb = None
        self.device = None
        self.busy = False
        self.server = None
        self.server_thread = None
        self.client_socket = None
        self.messages = queue.Queue()
        self.connected = False
        self.hello_received = False
        self.event_count = 0
        self.max_pressure = 0.0
        self.last_pressure = 0.0
        self.last_point = None
        self.last_pointer = None
        self.video_streamer = VideoStreamer(self.write)

        root.title("USB Pen Display — Pressure Canvas")
        root.geometry("1050x850")
        root.minsize(850, 700)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#101722")
        style.configure("TLabel", background="#101722", foreground="#e8eef7", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 21, "bold"), foreground="#ffffff")
        style.configure("Muted.TLabel", foreground="#9eafc4")
        style.configure("TButton", font=("Segoe UI", 9), padding=7)

        outer = ttk.Frame(root, padding=16)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="USB PEN PRESSURE TEST", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Draw on the tablet canvas — the same stroke and pressure should appear here.",
                  style="Muted.TLabel").pack(anchor="w", pady=(3, 10))

        connection = ttk.LabelFrame(outer, text=" USB CONNECTION ", padding=10)
        connection.pack(fill="x")
        self.status = ttk.Label(connection, text="Checking ADB…", font=("Segoe UI", 11, "bold"))
        self.status.pack(anchor="w")
        self.detail = ttk.Label(connection, text="Connect your tablet with USB debugging enabled.", style="Muted.TLabel")
        self.detail.pack(anchor="w", pady=3)
        buttons = ttk.Frame(connection)
        buttons.pack(anchor="w", pady=(5, 0))
        self.refresh_btn = ttk.Button(buttons, text="Refresh tablet", command=self.refresh)
        self.refresh_btn.pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Start USB receiver", command=self.start_link).pack(side="left", padx=6)
        ttk.Button(buttons, text="Start screen video", command=self.start_video).pack(side="left", padx=6)
        self.launch_btn = ttk.Button(buttons, text="Open tablet app", command=self.launch, state="disabled")
        self.launch_btn.pack(side="left", padx=6)
        self.install_btn = ttk.Button(buttons, text="Install / update APK", command=self.install, state="disabled")
        self.install_btn.pack(side="left", padx=6)

        telemetry = ttk.LabelFrame(outer, text=" RECEIVED FROM TABLET ", padding=10)
        telemetry.pack(fill="x", pady=10)
        self.link_label = ttk.Label(telemetry, text="TCP: not connected     App handshake: not received     Pen events: 0",
                                    font=("Segoe UI", 10, "bold"))
        self.link_label.pack(anchor="w")
        self.readout = ttk.Label(telemetry, text="Tool: —     Action: —     Pressure: —     Max pressure: 0.000",
                                 style="Muted.TLabel")
        self.readout.pack(anchor="w", pady=(5, 4))
        self.pressure_bar = tk.Canvas(telemetry, height=18, bg="#263345", highlightthickness=0)
        self.pressure_bar.pack(fill="x")
        
        drawing = ttk.LabelFrame(outer, text=" PC DRAWING CANVAS — TABLET INPUT ", padding=8)
        drawing.pack(fill="both", expand=True)
        canvas_row = ttk.Frame(drawing)
        canvas_row.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(canvas_row, bg="white", highlightthickness=1, highlightbackground="#6b7b90",
                                width=900, height=430, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        footer = ttk.Frame(drawing)
        footer.pack(fill="x", pady=(6, 0))
        ttk.Label(footer, text="A pressure-sensitive stroke should appear above.").pack(side="left")
        ttk.Button(footer, text="Clear PC canvas", command=self.clear_canvas).pack(side="right")

        log_frame = ttk.LabelFrame(outer, text=" DIAGNOSTIC LOG ", padding=6)
        log_frame.pack(fill="x", pady=(8, 0))
        self.log = tk.Text(log_frame, height=4, bg="#0b111a", fg="#c8d6e8", relief="flat",
                           font=("Consolas", 9), state="disabled")
        self.log.pack(fill="x")
        self.write("Ready. Start the receiver, then open the tablet app.")
        root.after(250, self.refresh)
        root.after(30, self.process_messages)
        root.protocol("WM_DELETE_WINDOW", self.close)

    def write(self, message):
        self.log.configure(state="normal")
        self.log.insert("end", message.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def refresh(self):
        if self.busy:
            return
        self.busy = True
        self.refresh_btn.configure(state="disabled")
        def work():
            try:
                adb = find_adb()
                if not adb:
                    result = {"adb": None}
                else:
                    p = subprocess.run([adb, "devices", "-l"], capture_output=True, text=True, timeout=12)
                    lines = [x.strip() for x in p.stdout.splitlines()[1:] if x.strip()]
                    good = next((x for x in lines if len(x.split()) > 1 and x.split()[1] == "device"), None)
                    unauthorized = any("unauthorized" in x for x in lines)
                    if good:
                        parts = good.split()
                        model = next((x.split(":", 1)[1] for x in parts[2:] if x.startswith("model:")), "")
                        result = {"adb": adb, "device": parts[0], "model": model.replace("_", " ")}
                    else:
                        result = {"adb": adb, "unauthorized": unauthorized}
            except Exception as exc:
                result = {"error": str(exc)}
            self.root.after(0, lambda: self.finish_refresh(result))
        threading.Thread(target=work, daemon=True).start()

    def finish_refresh(self, result):
        self.busy = False
        self.refresh_btn.configure(state="normal")
        self.adb = result.get("adb")
        self.device = result.get("device")
        if result.get("error"):
            self.status.configure(text="ADB check failed")
            self.detail.configure(text=result["error"])
        elif not self.adb:
            self.status.configure(text="ADB not found")
            self.detail.configure(text="Android Platform-Tools could not be located.")
        elif self.device:
            self.status.configure(text="TABLET CONNECTED • " + self.device)
            self.detail.configure(text=result.get("model") or "USB debugging authorized.")
            self.write("ADB device ready: " + self.device)
        elif result.get("unauthorized"):
            self.status.configure(text="Tablet detected — authorization required")
            self.detail.configure(text="Unlock tablet and accept USB debugging.")
        else:
            self.status.configure(text="ADB ready — tablet not detected")
            self.detail.configure(text="Reconnect the USB cable and refresh.")
        state = "normal" if self.device else "disabled"
        self.launch_btn.configure(state=state)
        self.install_btn.configure(state=state)

    def start_link(self):
        if not self.adb or not self.device:
            messagebox.showwarning("USB Pen Display", "Connect and authorize the tablet first.")
            return
        if self.server:
            self.write("Receiver is already running.")
            return
        self.link_label.configure(text="TCP: starting receiver…")
        def work():
            try:
                p = subprocess.run([self.adb, "-s", self.device, "reverse",
                                    f"tcp:{PORT}", f"tcp:{PORT}"], capture_output=True, text=True, timeout=12)
                if p.returncode:
                    raise RuntimeError((p.stderr or p.stdout).strip())
                server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.bind(("127.0.0.1", PORT))
                server.listen(2)
                server.settimeout(1.0)
                self.server = server
                self.root.after(0, lambda: self.write(f"ADB reverse configured; PC TCP listener active on {PORT}."))
                self.root.after(0, lambda: self.link_label.configure(text="TCP: listening — launch the Android app to connect"))
                self.server_thread = threading.Thread(target=self.accept_loop, daemon=True)
                self.server_thread.start()
            except Exception as exc:
                self.root.after(0, lambda e=str(exc): messagebox.showerror("USB Pen Display", e))
        threading.Thread(target=work, daemon=True).start()

    def start_video(self):
        if not self.adb or not self.device:
            messagebox.showwarning("USB Pen Display", "Connect and authorize the tablet first.")
            return
        self.video_streamer.start(self.adb, self.device)

    def accept_loop(self):
        while self.server:
            try:
                conn, _ = self.server.accept()
                self.client_socket = conn
                self.messages.put(("tcp", "Android socket connected. Waiting for protocol handshake…"))
                threading.Thread(target=self.read_client, args=(conn,), daemon=True).start()
            except socket.timeout:
                continue
            except OSError:
                break

    def read_client(self, conn):
        try:
            stream = conn.makefile("r", encoding="utf-8", errors="replace")
            for line in stream:
                try:
                    packet = json.loads(line)
                    self.messages.put(("packet", packet))
                except json.JSONDecodeError as exc:
                    self.messages.put(("log", "Bad JSON line from tablet: " + str(exc)))
        except OSError as exc:
            self.messages.put(("log", "Socket read ended: " + str(exc)))
        finally:
            try:
                conn.close()
            except OSError:
                pass
            self.messages.put(("disconnected", "Android socket closed."))

    def process_messages(self):
        try:
            while True:
                kind, payload = self.messages.get_nowait()
                if kind == "tcp":
                    self.connected = True
                    self.write(payload)
                elif kind == "log":
                    self.write(payload)
                elif kind == "disconnected":
                    self.connected = False
                    self.hello_received = False
                    self.write(payload)
                elif kind == "packet":
                    self.handle_packet(payload)
        except queue.Empty:
            pass
        self.update_status()
        self.root.after(30, self.process_messages)

    def handle_packet(self, packet):
        kind = packet.get("type")
        if kind == "hello":
            self.hello_received = True
            self.write("APP HANDSHAKE received — protocol " + str(packet.get("protocol", "?")))
            return
        if kind != "pen":
            self.write("Unknown packet type: " + str(kind))
            return
        self.event_count += 1
        pressure = float(packet.get("pressure", 0.0))
        self.last_pressure = pressure
        self.max_pressure = max(self.max_pressure, pressure)
        tool = str(packet.get("tool", "unknown"))
        action = str(packet.get("action", "unknown"))
        self.readout.configure(text=(f"Tool: {tool}     Action: {action}     Pressure: {pressure:.4f}     "
                                     f"Max pressure: {self.max_pressure:.4f}     Events: {self.event_count}"))
        self.pressure_bar.delete("all")
        bar_width = max(1, self.pressure_bar.winfo_width())
        self.pressure_bar.create_rectangle(0, 0, bar_width, 18, fill="#263345", outline="")
        fill = max(0, min(1, pressure)) * bar_width
        self.pressure_bar.create_rectangle(0, 0, fill, 18, fill="#19a7e0", outline="")
        self.draw_remote_event(packet)

    def draw_remote_event(self, packet):
        action = packet.get("action", "")
        tool = packet.get("tool", "")
        if tool not in ("STYLUS", "ERASER", "FINGER"):
            return
        if packet.get("hover"):
            return
        cw = max(1.0, float(packet.get("canvasWidth", 1)))
        ch = max(1.0, float(packet.get("canvasHeight", 1)))
        px = float(packet.get("canvasX", 0)) / cw
        py = float(packet.get("canvasY", 0)) / ch
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        x = max(0, min(width, px * width))
        y = max(0, min(height, py * height))
        pressure = max(0.0, min(1.0, float(packet.get("pressure", 0.0))))
        stroke_width = 1.5 + pressure * 14.0
        pointer = packet.get("pointerId", 0)
        if action in ("ACTION_DOWN", "ACTION_POINTER_DOWN"):
            self.last_point = (x, y)
            self.last_pointer = pointer
            color = "white" if tool == "ERASER" else "#145fd7"
            self.canvas.create_oval(x, y, x + 1, y + 1, fill=color, outline=color)
        elif action == "ACTION_MOVE":
            if self.last_point is not None:
                old_x, old_y = self.last_point
                color = "white" if tool == "ERASER" else "#145fd7"
                self.canvas.create_line(old_x, old_y, x, y, fill=color, width=stroke_width,
                                        capstyle=tk.ROUND, smooth=True, splinesteps=12)
            self.last_point = (x, y)
            self.last_pointer = pointer
        elif action in ("ACTION_UP", "ACTION_POINTER_UP", "ACTION_CANCEL"):
            self.last_point = None
            self.last_pointer = None

    def update_status(self):
        tcp = "connected" if self.connected else ("listening" if self.server else "not started")
        handshake = "received" if self.hello_received else "not received"
        self.link_label.configure(text=f"TCP: {tcp}     App handshake: {handshake}     Pen events received: {self.event_count}")

    def clear_canvas(self):
        self.canvas.delete("all")
        self.last_point = None
        self.last_pointer = None

    def launch(self):
        if not self.adb or not self.device:
            return
        def work():
            try:
                p = subprocess.run([self.adb, "-s", self.device, "shell", "monkey", "-p", APP_ID, "1"],
                                   capture_output=True, text=True, timeout=15)
                if p.returncode:
                    raise RuntimeError((p.stderr or p.stdout).strip())
                self.root.after(0, lambda: self.write("Launch command sent to tablet."))
            except Exception as exc:
                self.root.after(0, lambda e=str(exc): messagebox.showerror("USB Pen Display", e))
        threading.Thread(target=work, daemon=True).start()

    def install(self):
        if not self.adb or not self.device:
            return
        apk = filedialog.askopenfilename(title="Select Android APK", filetypes=[("Android APK", "*.apk")])
        if not apk:
            return
        def work():
            try:
                p = subprocess.run([self.adb, "-s", self.device, "install", "-r", apk],
                                   capture_output=True, text=True, timeout=90)
                if p.returncode:
                    raise RuntimeError((p.stdout + "\n" + p.stderr).strip())
                self.root.after(0, lambda: messagebox.showinfo("USB Pen Display", "APK installed successfully."))
            except Exception as exc:
                self.root.after(0, lambda e=str(exc): messagebox.showerror("USB Pen Display", e))
        threading.Thread(target=work, daemon=True).start()

    def close(self):
        try:
            if self.client_socket:
                self.client_socket.close()
            self.video_streamer.stop(self.adb, self.device)
            if self.server:
                self.server.close()
            if self.adb and self.device:
                subprocess.Popen([self.adb, "-s", self.device, "reverse", "--remove", f"tcp:{PORT}"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        self.root.destroy()

def main():
    root = tk.Tk()
    Host(root)
    root.mainloop()

if __name__ == "__main__":
    main()
