import platform
import tkinter as tk
from tkinter import ttk

def main():
    root = tk.Tk()
    root.title("USB Pen Display Host 0.1.0")
    root.geometry("620x360")
    root.minsize(520, 300)
    frame = ttk.Frame(root, padding=24)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="USB PEN DISPLAY", font=("Segoe UI", 20, "bold")).pack(anchor="w")
    ttk.Label(frame, text=f"Windows host prototype • {platform.system()} {platform.release()}").pack(anchor="w", pady=(4, 20))
    ttk.Label(frame, text="Build 1: host application shell").pack(anchor="w")
    ttk.Label(frame, text="The Android diagnostic APK is built by GitHub Actions.\nUSB transport and extended-display streaming are not connected yet.\n\nNext milestone: establish a reliable USB link and read pen telemetry.", justify="left").pack(anchor="w", pady=12)
    ttk.Label(frame, text="Status: waiting for Android USB connection").pack(anchor="w", pady=(16, 0))
    ttk.Button(frame, text="Close", command=root.destroy).pack(anchor="e", side="bottom")
    root.mainloop()

if __name__ == "__main__":
    main()
