"""Native macOS capture: record the real desktop (real Dock, menu bar, windows) while
driving the pointer and keyboard with Quartz events. Same step DSL as capture_web.py.

    python capture_mac.py steps.json out_dir

Needs Screen Recording permission for the app that runs this (System Settings ->
Privacy & Security -> Screen & System Audio Recording). Without it `screencapture -v`
exits 1 with "could not create image from display". Check with:
    screencapture -x /tmp/t.png && echo ok

Steps (coordinates in screen POINTS, origin top-left of the main display):
  {"open": "Claude"}                        open an app by name and wait
  {"hold": 1.0}
  {"move": [x, y], "dur": 0.7}
  {"click": [x, y], "wait": 1.0}
  {"type": "hello", "cps": 11}
  {"key": "cmd+n"}                          key chord
  {"scroll": -6, "wait": 0.5}               scroll wheel ticks at the current pointer

Output: out_dir/screen.mp4 (CFR at fps, Retina pixels), out_dir/actions.json in the
same shape as capture_web.py (css = points, dpr = backing scale), so stage.py treats
the recording as a full-canvas video layer with a rendered cursor.
The recording captures the system pointer too, so pass "cursor": false on the layer
if you prefer the real one, or hide it during the recording with the `hide_cursor`
step (uses `cliclick` if installed).
"""
import json
import math
import os
import subprocess
import sys
import time

import Quartz

FPS_OUT = 25


def ease_in_out(p):
    p = max(0.0, min(1.0, p))
    return 2 * p * p if p < 0.5 else 1 - (-2 * p + 2) ** 2 / 2


def display_info():
    did = Quartz.CGMainDisplayID()
    w_px, h_px = Quartz.CGDisplayPixelsWide(did), Quartz.CGDisplayPixelsHigh(did)
    b = Quartz.CGDisplayBounds(did)
    w_pt, h_pt = int(b.size.width), int(b.size.height)
    return (w_pt, h_pt), (w_px, h_px), w_px / w_pt


def post_mouse(kind, x, y, button=Quartz.kCGMouseButtonLeft):
    ev = Quartz.CGEventCreateMouseEvent(None, kind, (x, y), button)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)


def post_key(text):
    for ch in text:
        ev = Quartz.CGEventCreateKeyboardEvent(None, 0, True)
        Quartz.CGEventKeyboardSetUnicodeString(ev, len(ch), ch)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        ev = Quartz.CGEventCreateKeyboardEvent(None, 0, False)
        Quartz.CGEventKeyboardSetUnicodeString(ev, len(ch), ch)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)


KEYCODES = {"a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9, "b": 11, "q": 12,
            "w": 13, "e": 14, "r": 15, "y": 16, "t": 17, "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23,
            "9": 25, "7": 26, "8": 28, "0": 29, "o": 31, "u": 32, "i": 34, "p": 35, "l": 37, "j": 38, "k": 40,
            "n": 45, "m": 46, "return": 36, "tab": 48, "space": 49, "escape": 53, "left": 123, "right": 124,
            "down": 125, "up": 126}
MODS = {"cmd": Quartz.kCGEventFlagMaskCommand, "shift": Quartz.kCGEventFlagMaskShift,
        "alt": Quartz.kCGEventFlagMaskAlternate, "ctrl": Quartz.kCGEventFlagMaskControl}


def post_chord(chord):
    parts = chord.lower().split("+")
    flags = 0
    for p in parts[:-1]:
        flags |= MODS[p]
    code = KEYCODES[parts[-1]]
    for down in (True, False):
        ev = Quartz.CGEventCreateKeyboardEvent(None, code, down)
        Quartz.CGEventSetFlags(ev, flags)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)


class Recorder:
    def __init__(self, path):
        self.path = path
        self.proc = None

    def start(self):
        self.proc = subprocess.Popen(["screencapture", "-v", "-x", self.path])
        self.t0 = time.monotonic()
        time.sleep(0.6)
        if self.proc.poll() is not None:
            raise SystemExit("screencapture -v exited at once: Screen Recording permission is missing")

    def stop(self):
        import signal
        self.proc.send_signal(signal.SIGINT)
        self.proc.wait(timeout=30)


def main():
    spec = json.load(open(sys.argv[1]))
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    fps = spec.get("fps", FPS_OUT)
    pts, px, scale = display_info()
    cursor, events = [], []
    cur = [pts[0] // 2, pts[1] // 2]
    raw = os.path.join(out, "screen_raw.mov")
    rec = Recorder(raw)

    def now():
        return time.monotonic() - rec.t0

    def log_cursor_until(t_end):
        # sample the (known) pointer position at the output frame rate
        while len(cursor) / fps < t_end:
            cursor.append(list(cur))

    def move(x1, y1, dur):
        x0, y0 = cur
        n = max(1, int(dur * 60))
        t_start = now()
        for i in range(1, n + 1):
            p = ease_in_out(i / n)
            cur[0], cur[1] = x0 + (x1 - x0) * p, y0 + (y1 - y0) * p
            post_mouse(Quartz.kCGEventMouseMoved, cur[0], cur[1])
            log_cursor_until(t_start + dur * i / n)
            time.sleep(max(0, t_start + dur * i / n - now()))

    def hold(sec):
        t_end = now() + sec
        log_cursor_until(t_end)
        time.sleep(max(0, t_end - now()))

    rec.start()
    for s in spec["steps"]:
        if "open" in s:
            subprocess.run(["open", "-a", s["open"]], check=False)
            hold(s.get("wait", 1.5))
        elif "hold" in s:
            hold(s["hold"])
        elif "move" in s:
            move(s["move"][0], s["move"][1], s.get("dur", 0.7))
        elif "click" in s:
            move(s["click"][0], s["click"][1], s.get("dur", 0.7))
            t = now()
            post_mouse(Quartz.kCGEventLeftMouseDown, *cur)
            time.sleep(0.06)
            post_mouse(Quartz.kCGEventLeftMouseUp, *cur)
            events.append({"t": t, "kind": "click", "x": cur[0], "y": cur[1], "end": t + s.get("wait", 1.0)})
            hold(s.get("wait", 1.0))
        elif "type" in s:
            t = now()
            for ch in s["type"]:
                post_key(ch)
                hold(1.0 / s.get("cps", 11))
            events.append({"t": t, "kind": "type", "x": cur[0], "y": cur[1], "end": now()})
            hold(s.get("wait", 0.6))
        elif "key" in s:
            post_chord(s["key"])
            hold(s.get("wait", 0.8))
        elif "scroll" in s:
            t = now()
            ticks = int(s["scroll"])
            for _ in range(abs(ticks)):
                ev = Quartz.CGEventCreateScrollWheelEvent(None, Quartz.kCGScrollEventUnitLine, 1, -1 if ticks > 0 else 1)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
                hold(0.04)
            events.append({"t": t, "kind": "scroll", "x": cur[0], "y": cur[1], "end": now()})
            hold(s.get("wait", 0.5))
        else:
            raise SystemExit(f"unknown step {s}")
    total = now()
    log_cursor_until(total)
    rec.stop()

    # constant frame rate, frame count pinned to the cursor log
    n = len(cursor)
    mp4 = os.path.join(out, "screen.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-vf", f"fps={fps}", "-frames:v", str(n),
                    "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p", "-an", mp4], check=True)
    json.dump({"css": list(pts), "dpr": scale, "fps": fps, "frames": n, "cursor": cursor, "events": events,
               "pixels": list(px)}, open(os.path.join(out, "actions.json"), "w"))
    print(f"capture: {n} frames -> {mp4}")


if __name__ == "__main__":
    main()
