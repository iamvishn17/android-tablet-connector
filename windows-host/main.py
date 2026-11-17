import json, os, platform, shutil, socket, subprocess, threading, tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

APP_ID = "com.usbpendisplay.diagnostic"
PORT = 27183

def find_adb():
    found = shutil.which("adb") or shutil.which("adb.exe")
    if found: return found
    roots = [os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT"),
             str(Path.home() / "AppData/Local/Android/Sdk"), "C:/platform-tools"]
    for root in roots:
        if root:
            candidate = Path(root) / "platform-tools" / "adb.exe"
            if candidate.is_file(): return str(candidate)
            candidate = Path(root) / "adb.exe"
            if candidate.is_file(): return str(candidate)
    return None

class Host:
    def __init__(self, root):
        self.root, self.adb, self.device, self.busy = root, None, None, False
        self.server = None
        self.server_thread = None
        self.client_socket = None
        root.title("USB Pen Display")
        root.geometry("780x650")
        root.minsize(700, 590)
        style = ttk.Style(); style.theme_use("clam")
        style.configure("TFrame", background="#101722")
        style.configure("TLabel", background="#101722", foreground="#e8eef7", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"), foreground="#ffffff")
        style.configure("Muted.TLabel", foreground="#9eafc4")
        style.configure("TButton", font=("Segoe UI", 10), padding=8)
        outer = ttk.Frame(root, padding=24); outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="USB PEN DISPLAY", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text=f"Windows companion • {platform.system()} {platform.release()} • Build 0.3.0", style="Muted.TLabel").pack(anchor="w", pady=(4,16))
        card = ttk.LabelFrame(outer, text=" TABLET CONNECTION ", padding=13); card.pack(fill="x")
        self.status = ttk.Label(card, text="Checking for Android Debug Bridge…", font=("Segoe UI",12,"bold")); self.status.pack(anchor="w")
        self.detail = ttk.Label(card, text="Connect your Tab P12 using a USB data cable.", style="Muted.TLabel"); self.detail.pack(anchor="w", pady=6)
        row = ttk.Frame(card); row.pack(anchor="w")
        self.refresh_btn = ttk.Button(row, text="Refresh connection", command=self.refresh); self.refresh_btn.pack(side="left", padx=(0,8))
        self.launch_btn = ttk.Button(row, text="Open tablet diagnostic", command=self.launch, state="disabled"); self.launch_btn.pack(side="left", padx=8)
        self.install_btn = ttk.Button(row, text="Install / update APK", command=self.install, state="disabled"); self.install_btn.pack(side="left", padx=8)
        link = ttk.LabelFrame(outer, text=" LIVE USB PEN DATA ", padding=13); link.pack(fill="x", pady=13)
        self.link_status = ttk.Label(link, text="Not started — connect tablet first", font=("Segoe UI",12,"bold")); self.link_status.pack(anchor="w")
        self.link_detail = ttk.Label(link, text="Starts a local TCP receiver and creates an ADB reverse tunnel over USB.", style="Muted.TLabel"); self.link_detail.pack(anchor="w", pady=5)
        ttk.Button(link, text="Start USB pen link", command=self.start_link).pack(anchor="w", pady=(3,0))
        self.live = ttk.LabelFrame(outer, text=" LAST RECEIVED PEN EVENT ", padding=13); self.live.pack(fill="x")
        self.live_values = ttk.Label(self.live, text="Waiting for Android pen data…", style="Muted.TLabel", justify="left")
        self.live_values.pack(anchor="w")
        ttk.Label(outer, text="ACTIVITY LOG", style="Muted.TLabel").pack(anchor="w", pady=(12,5))
        self.log = tk.Text(outer, height=6, bg="#0b111a", fg="#c8d6e8", relief="flat", font=("Consolas",9), padx=9, pady=7, state="disabled")
        self.log.pack(fill="both", expand=True)
        self.write("PC companion started. ADB connection manager ready.")
        root.after(300, self.refresh)
        root.protocol("WM_DELETE_WINDOW", self.close)

    def write(self, msg):
        self.log.configure(state="normal"); self.log.insert("end", msg.rstrip()+"\n"); self.log.see("end"); self.log.configure(state="disabled")

    def refresh(self):
        if self.busy: return
        self.busy=True; self.refresh_btn.configure(state="disabled")
        def work():
            try:
                adb=find_adb()
                if not adb: result={"adb":None}
                else:
                    p=subprocess.run([adb,"devices","-l"],capture_output=True,text=True,timeout=12)
                    lines=[x.strip() for x in p.stdout.splitlines()[1:] if x.strip()]
                    good=next((x for x in lines if len(x.split())>1 and x.split()[1]=="device"),None)
                    unauthorized=any("unauthorized" in x for x in lines)
                    if good:
                        parts=good.split(); model=next((x.split(":",1)[1] for x in parts[2:] if x.startswith("model:")),"")
                        result={"adb":adb,"device":parts[0],"model":model.replace("_"," ")}
                    else: result={"adb":adb,"unauthorized":unauthorized}
            except Exception as e: result={"error":str(e)}
            self.root.after(0,lambda:self.finish(result))
        threading.Thread(target=work,daemon=True).start()

    def finish(self,r):
        self.busy=False; self.refresh_btn.configure(state="normal")
        self.adb=r.get("adb"); self.device=r.get("device")
        if r.get("error"):
            self.status.configure(text="Connection check failed"); self.detail.configure(text=r["error"])
        elif not self.adb:
            self.status.configure(text="ADB tools not found"); self.detail.configure(text="Install Android SDK Platform-Tools, then restart this app.")
        elif self.device:
            self.status.configure(text="TABLET CONNECTED • "+self.device); self.detail.configure(text=r.get("model") or "Android device authorized over USB.")
            self.write("Connected: "+self.device+" "+r.get("model",""))
        elif r.get("unauthorized"):
            self.status.configure(text="Tablet detected — authorization needed"); self.detail.configure(text="Unlock tablet and accept the USB debugging prompt.")
        else:
            self.status.configure(text="ADB ready — no tablet detected"); self.detail.configure(text="Connect tablet, enable USB debugging and accept the prompt.")
        state="normal" if self.device else "disabled"
        self.launch_btn.configure(state=state); self.install_btn.configure(state=state)
        if not self.adb: self.write("ADB not found. Install Android SDK Platform-Tools.")

    def start_link(self):
        if not self.adb or not self.device:
            messagebox.showwarning("USB Pen Display","Connect and authorize the tablet first, then refresh.")
            return
        self.link_status.configure(text="Starting USB pen receiver…")
        def work():
            try:
                p=subprocess.run([self.adb,"-s",self.device,"reverse",f"tcp:{PORT}",f"tcp:{PORT}"],capture_output=True,text=True,timeout=12)
                if p.returncode: raise RuntimeError((p.stderr or p.stdout).strip())
                server=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
                server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
                server.bind(("127.0.0.1",PORT)); server.listen(1); server.settimeout(1.0)
                self.server=server
                self.root.after(0,lambda:self.link_status.configure(text="USB tunnel ready — open the tablet diagnostic"))
                self.root.after(0,lambda:self.write(f"ADB reverse tunnel active on TCP {PORT}."))
                self.server_thread=threading.Thread(target=self.accept_loop,daemon=True); self.server_thread.start()
            except Exception as e:
                self.root.after(0,lambda:self.link_status.configure(text="Could not start USB pen link"))
                self.root.after(0,lambda:messagebox.showerror("USB Pen Display",str(e)))
        threading.Thread(target=work,daemon=True).start()

    def accept_loop(self):
        while self.server:
            try:
                conn,_=self.server.accept()
                self.client_socket=conn
                self.root.after(0,lambda:self.link_status.configure(text="ANDROID APP CONNECTED — receiving pen events"))
                self.root.after(0,lambda:self.write("Android diagnostic connected through USB tunnel."))
                threading.Thread(target=self.read_client,args=(conn,),daemon=True).start()
            except socket.timeout: continue
            except OSError: break

    def read_client(self,conn):
        try:
            stream=conn.makefile("r",encoding="utf-8",errors="replace")
            for line in stream:
                try:
                    data=json.loads(line)
                    if data.get("type")=="hello":
                        self.root.after(0,lambda:self.write("Android protocol handshake received."))
                    elif data.get("type")=="pen":
                        summary=(f"Tool: {data.get('tool')}    Event: {data.get('action')}\n"
                                 f"X: {data.get('x',0):.1f}    Y: {data.get('y',0):.1f}    "
                                 f"Pressure: {data.get('pressure',0):.4f}\n"
                                 f"Tilt: {data.get('tilt',0):.4f} rad    Orientation: {data.get('orientation',0):.4f} rad\n"
                                 f"Buttons: {data.get('buttons')}    Hover: {data.get('hover')}    Contact: {data.get('contact')}")
                        self.root.after(0,lambda s=summary:self.live_values.configure(text=s))
                except Exception as e:
                    self.root.after(0,lambda:self.write("Invalid event received: "+str(e)))
        except OSError: pass
        finally:
            try: conn.close()
            except OSError: pass
            if self.client_socket is conn:
                self.client_socket=None
                self.root.after(0,lambda:self.link_status.configure(text="USB receiver ready — waiting for Android app"))

    def launch(self):
        if not self.adb or not self.device: return
        def work():
            try:
                p=subprocess.run([self.adb,"-s",self.device,"shell","monkey","-p",APP_ID,"1"],capture_output=True,text=True,timeout=15)
                if p.returncode: raise RuntimeError((p.stderr or p.stdout).strip())
                self.root.after(0,lambda:self.write("Launch command sent to tablet."))
            except Exception as e: self.root.after(0,lambda:messagebox.showerror("USB Pen Display",str(e)))
        threading.Thread(target=work,daemon=True).start()

    def install(self):
        if not self.adb or not self.device: return
        apk=filedialog.askopenfilename(title="Select diagnostic APK",filetypes=[("Android APK","*.apk")])
        if not apk: return
        def work():
            try:
                p=subprocess.run([self.adb,"-s",self.device,"install","-r",apk],capture_output=True,text=True,timeout=90)
                if p.returncode: raise RuntimeError((p.stdout+"\n"+p.stderr).strip())
                self.root.after(0,lambda:self.write("APK install/update successful."))
                self.root.after(0,lambda:messagebox.showinfo("USB Pen Display","APK installed successfully."))
            except Exception as e: self.root.after(0,lambda:messagebox.showerror("USB Pen Display",str(e)))
        threading.Thread(target=work,daemon=True).start()

    def close(self):
        try:
            if self.client_socket: self.client_socket.close()
            if self.server: self.server.close()
            if self.adb and self.device:
                subprocess.Popen([self.adb,"-s",self.device,"reverse","--remove",f"tcp:{PORT}"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        except Exception: pass
        self.root.destroy()

def main():
    root=tk.Tk(); Host(root); root.mainloop()
if __name__=="__main__": main()
