#!/usr/bin/env python3
"""Disable AnyDisplay's synthetic pen path when the VMulti bridge is the selected backend."""
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
path = root / "windows/src/win/input.rs"
source = path.read_text(encoding="utf-8")
old = """            InputEvent::Pen(p) => {
                let vdesk = monitors::virtual_screen();
                for s in &p.samples {
                    let points = self.pen_state.sample(s, &target);
                    for pt in points {
                        self.inject_pen(&pt, vdesk);
                    }
                }
            }"""
new = """            // Pen samples are forwarded by the Android telemetry channel to the
            // dedicated VMulti HID digitizer backend. Avoid injecting a second,
            // competing synthetic pointer stream here.
            InputEvent::Pen(_p) => {}"""
if new not in source:
    if old not in source:
        raise SystemExit("Could not locate AnyDisplay native pen match arm; pinned upstream source changed.")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")
print("Disabled AnyDisplay synthetic pen injection; VMulti is the active pen backend.")
