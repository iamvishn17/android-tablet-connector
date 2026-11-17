import os, platform, shutil, subprocess, threading, tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

APP_ID = "com.usbpendisplay.diagnostic"

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
        root.title("USB Pen Display")
        root.geometry("720x510")
        root.minsize(650, 470)
        style = ttk.Style(); style.theme_use("clam")
        style.configure("TFrame", background="#101722")
        style.configure("TLabel", background="#101722", foreground="#e8eef7", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"), foreground="#ffffff")
        style.configure("Muted.TLabel", foreground="#9eafc4")
        style.configure("TButton", font=("Segoe UI", 10), padding=8)
        outer = ttk.Frame(root, padding=24); outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="USB PEN DISPLAY", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text=f"Windows companion • {platform.system()} {platform.release()} • Build 0.2.0", style="Muted.TLabel").pack(anchor="w", pady=(4,20))
        card = ttk.LabelFrame(outer, text=" TABLET CONNECTION ", padding=15); card.pack(fill="x")
        self.status = ttk.Label(card, text="Checking for Android Debug Bridge…", font=("Segoe UI",12,"bold")); self.status.pack(anchor="w")
        self.detail = ttk.Label(card, text="Connect your Tab P12 using a USB data cable.", style="Muted.TLabel"); self.detail.pack(anchor="w", pady=8)
        row = ttk.Frame(card); row.pack(anchor="w")
        self.refresh_btn = ttk.Button(row, text="Refresh connection", command=self.refresh); self.refresh_btn.pack(side="left", padx=(0,8))
        self.launch_btn = ttk.Button(row, text="Open tablet diagnostic", command=self.launch, state="disabled"); self.launch_btn.pack(side="left", padx=8)
        self.install_btn = ttk.Button(row, text="Install / update APK", command=self.install, state="disabled"); self.install_btn.pack(side="left", padx=8)
        setup = ttk.LabelFrame(outer, text=" FIRST-TIME USB SETUP ", padding=14); setup.pack(fill="x", pady=16)
        ttk.Label(setup, justify="left", text="1. Install Android SDK Platform-Tools (ADB) on Windows.\n2. On the tablet, enable Developer options, then USB debugging.\n3. Connect by USB, unlock the tablet and accept the debugging authorization prompt.\n4. Click Refresh connection.").pack(anchor="w")
        ttk.Label(outer, text="ACTIVITY LOG", style="Muted.TLabel").pack(anchor="w", pady=(0,5))
        self.log = tk.Text(outer, height=7, bg="#0b111a", fg="#c8d6e8", relief="flat", font=("Consolas",9), padx=9, pady=7, state="disabled")
        self.log.pack(fill="both", expand=True)
        self.write("PC companion started. USB/ADB connection manager ready.")
        root.after(300, self.refresh)

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
        if not self.adb: self.write("ADB not found. Install: developer.android.com/tools/releases/platform-tools")

    def launch(self):
        if not self.adb or not self.device: return
        def work():
            try:
                p=subprocess.run([self.adb,"-s",self.device,"shell","monkey","-p",APP_ID,"1"],capture_output=True,text=True,timeout=15)
                if p.returncode: raise RuntimeError((p.stderr or p.stdout).strip())
                msg="Launch command sent to tablet."
                self.root.after(0,lambda:self.write(msg))
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

def main():
    root=tk.Tk(); Host(root); root.mainloop()
if __name__=="__main__": main()
