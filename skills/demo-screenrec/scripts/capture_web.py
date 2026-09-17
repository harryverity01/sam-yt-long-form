"""Deterministic web-app capture at Retina scale.

Drives a page with a step list and writes one PNG per output frame plus an action log.
Time is virtual: every frame is a screenshot after the scripted state for that frame, so
nothing drops, nothing drifts, and the capture is crisp at 2x for the stage's zooms.

    python capture_web.py steps.json out_dir

steps.json:
{
  "viewport": [1100, 700],          # CSS px; frames are viewport * dpr
  "dpr": 2, "fps": 25,
  "steps": [
    {"goto": "https://…", "wait": 1.0},
    {"hide": ["[id*='cookie' i]"]},   # nuke banners (optional; the default list runs anyway)
    {"hold": 0.8},
    {"move": "text=Routines", "dur": 0.7},   # selector or [x, y] in CSS px
    {"click": "text=Routines", "wait": 1.2},
    {"scroll": 600, "dur": 1.4},
    {"type": "hello", "cps": 11},
    {"hover": "css=.button"}
  ]
}

Output: out_dir/frames/f_%05d.png and out_dir/actions.json
  {"css":[w,h],"dpr":2,"fps":25,"frames":N,
   "cursor":[[x,y],...] per frame (CSS px, or null when hidden),
   "events":[{"t":sec,"kind":"click|type|scroll|hover","x":..,"y":..,"end":sec}]}
"""
import json
import math
import os
import sys

from playwright.sync_api import sync_playwright

NUKE = """(()=>{const k=['[id*="cookie" i]','[class*="cookie" i]','[id*="consent" i]','[class*="consent" i]',
'[id*="onetrust" i]','[class*="gdpr" i]','[id*="cmplz" i]','[class*="banner" i][class*="cookie" i]'];
for(const s of k){document.querySelectorAll(s).forEach(e=>{const r=e.getBoundingClientRect();
if(r.height<780) e.remove()})}})()"""

STILL = """*,*::before,*::after{transition:none!important;animation:none!important;scroll-behavior:auto!important;caret-color:transparent!important}"""


def load_netscape_cookies(path):
    """A cookies.txt (yt-dlp --cookies-from-browser chrome --cookies f) filtered to one site."""
    out = []
    for line in open(path):
        if line.startswith("#") or not line.strip():
            continue
        d, _flag, p, secure, _exp, name, val = line.rstrip("\n").split("\t")
        out.append(dict(name=name, value=val, domain=d, path=p, secure=(secure == "TRUE"), expires=-1))
    return out


def ease_in_out(p):
    p = max(0.0, min(1.0, p))
    return 2 * p * p if p < 0.5 else 1 - (-2 * p + 2) ** 2 / 2


class Capture:
    def __init__(self, spec, out_dir):
        self.spec = spec
        self.css = spec.get("viewport", [1100, 700])
        self.dpr = spec.get("dpr", 2)
        self.fps = spec.get("fps", 25)
        self.out = out_dir
        self.frames_dir = os.path.join(out_dir, "frames")
        os.makedirs(self.frames_dir, exist_ok=True)
        self.n = 0
        self.cursor = []
        self.events = []
        self.cur = None  # current cursor position (CSS px) or None

    # -- frame clock -----------------------------------------------------------
    @property
    def t(self):
        return self.n / self.fps

    def snap(self):
        path = os.path.join(self.frames_dir, f"f_{self.n:05d}.png")
        self.page.screenshot(path=path, type="png", animations="disabled", caret="hide")
        self.cursor.append(list(self.cur) if self.cur else None)
        self.n += 1

    def frames_for(self, seconds):
        return max(1, int(round(seconds * self.fps)))

    # -- element helpers -------------------------------------------------------
    def point(self, target):
        if isinstance(target, (list, tuple)):
            return float(target[0]), float(target[1])
        loc = self.page.locator(target).locator("visible=true").first
        try:
            loc.scroll_into_view_if_needed(timeout=5000)
        except Exception:
            pass
        box = loc.bounding_box()
        if not box:
            raise SystemExit(f"capture: element not found or not visible: {target}")
        return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2

    # -- steps -----------------------------------------------------------------
    def run(self):
        with sync_playwright() as pw:
            cdp = self.spec.get("cdp")
            if cdp:
                # an Electron app (Obsidian, ButterDocs) launched with --remote-debugging-port=N,
                # or any Chrome with remote debugging. We drive its existing window.
                b = pw.chromium.connect_over_cdp(cdp)
                prefix = self.spec.get("page", "")
                pages = []
                for _ in range(20):  # the page list fills in shortly after connecting
                    pages = [p for c in b.contexts for p in c.pages if p.url.startswith(prefix)]
                    if pages:
                        break
                    import time as _t
                    _t.sleep(0.25)
                if not pages:
                    seen = [p.url for c in b.contexts for p in c.pages]
                    raise SystemExit(f"capture: no page starting with {prefix!r} at {cdp}; saw {seen}")
                ctx = pages[0].context
                self.page = pages[0]
                self.page.bring_to_front()
                # size the real window so the capture is exactly viewport * dpr
                try:
                    s = ctx.new_cdp_session(self.page)
                    win = s.send("Browser.getWindowForTarget")
                    s.send("Browser.setWindowBounds", {"windowId": win["windowId"],
                           "bounds": {"width": self.css[0], "height": self.css[1] + self.spec.get("titlebar_pt", 0)}})
                except Exception as e:
                    print("capture: could not set window bounds:", e)
                self.page.wait_for_timeout(600)
                self.css = self.page.evaluate("[innerWidth, innerHeight]")
                self.dpr = self.page.evaluate("window.devicePixelRatio")
                self.settle()
            else:
                exe = os.environ.get("DEMO_CHROME")  # e.g. /opt/pw-browsers/chromium-1194/chrome-linux/chrome
                b = pw.chromium.launch(headless=True, executable_path=exe,
                                       args=["--no-sandbox", "--hide-scrollbars"] if exe else None)
                ctx = b.new_context(
                    viewport={"width": self.css[0], "height": self.css[1]},
                    device_scale_factor=self.dpr,
                    reduced_motion="reduce",
                    user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                                "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"),
                )
                if self.spec.get("cookies"):
                    ctx.add_cookies(load_netscape_cookies(self.spec["cookies"]))
                self.page = ctx.new_page()
            for step in self.spec["steps"]:
                self.do(step)
            if cdp:
                b.close()  # detaches only; the app keeps running
            else:
                ctx.close()
                b.close()
        meta = {"css": self.css, "dpr": self.dpr, "fps": self.fps, "frames": self.n,
                "cursor": self.cursor, "events": self.events}
        with open(os.path.join(self.out, "actions.json"), "w") as f:
            json.dump(meta, f)
        print(f"capture: {self.n} frames -> {self.frames_dir}")

    def settle(self):
        try:
            self.page.evaluate(NUKE)
            self.page.add_style_tag(content=STILL)
        except Exception:
            pass

    def do(self, s):
        if "goto" in s:
            self.page.goto(s["goto"], wait_until="domcontentloaded", timeout=45000)
            try:
                self.page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            self.settle()
            self.page.wait_for_timeout(int(s.get("wait", 1.0) * 1000))
            self.settle()
            if s.get("start_hidden", True):
                self.cur = None
            return
        if "hide" in s:
            for sel in s["hide"]:
                self.page.evaluate("(sel)=>document.querySelectorAll(sel).forEach(e=>e.remove())", sel)
            return
        if "hold" in s:
            for _ in range(self.frames_for(s["hold"])):
                self.snap()
            return
        if "move" in s:
            self.move(self.point(s["move"]), s.get("dur", 0.7))
            return
        if "hover" in s:
            self.move(self.point(s["hover"]), s.get("dur", 0.6))
            x, y = self.cur
            self.events.append({"t": self.t, "kind": "hover", "x": x, "y": y, "end": self.t + s.get("wait", 1.0)})
            for _ in range(self.frames_for(s.get("wait", 1.0))):
                self.snap()
            return
        if "click" in s:
            pt = self.point(s["click"])
            if self.cur is None or math.dist(self.cur, pt) > 2:
                self.move(pt, s.get("dur", 0.7))
            x, y = self.cur
            self.page.mouse.down()
            self.snap()
            self.page.mouse.up()
            self.events.append({"t": self.t, "kind": "click", "x": x, "y": y, "end": self.t + s.get("wait", 1.0)})
            self.page.wait_for_timeout(120)
            self.settle()
            for _ in range(self.frames_for(s.get("wait", 1.0))):
                self.snap()
            return
        if "type" in s:
            text = s["type"]
            cps = s.get("cps", 11)
            x, y = self.cur if self.cur else (self.css[0] / 2, self.css[1] / 2)
            t0 = self.t
            per = self.fps / cps
            acc = 0.0
            for ch in text:
                self.page.keyboard.type(ch)
                acc += per
                while acc >= 1:
                    self.snap()
                    acc -= 1
            self.events.append({"t": t0, "kind": "type", "x": x, "y": y, "end": self.t})
            for _ in range(self.frames_for(s.get("wait", 0.6))):
                self.snap()
            return
        if "press" in s:
            self.page.keyboard.press(s["press"])
            for _ in range(self.frames_for(s.get("wait", 0.8))):
                self.snap()
            return
        if "scroll" in s:
            dy = float(s["scroll"])
            n = self.frames_for(s.get("dur", 1.2))
            t0 = self.t
            if s.get("wheel", self.cur is not None):
                # wheel at the cursor: scrolls whatever pane is under it (editors, panels)
                done = 0.0
                for i in range(1, n + 1):
                    target = dy * ease_in_out(i / n)
                    self.page.mouse.wheel(0, target - done)
                    done = target
                    self.snap()
            else:
                y0 = self.page.evaluate("window.scrollY")
                for i in range(1, n + 1):
                    y = y0 + dy * ease_in_out(i / n)
                    self.page.evaluate("(y)=>window.scrollTo(0,y)", y)
                    self.snap()
            cx, cy = self.cur if self.cur else (self.css[0] / 2, self.css[1] / 2)
            self.events.append({"t": t0, "kind": "scroll", "x": cx, "y": cy, "end": self.t})
            for _ in range(self.frames_for(s.get("wait", 0.5))):
                self.snap()
            return
        if "eval" in s:
            self.page.evaluate(s["eval"])
            self.settle()
            for _ in range(self.frames_for(s.get("wait", 0.3))):
                self.snap()
            return
        raise SystemExit(f"capture: unknown step {s}")

    def move(self, pt, dur):
        x1, y1 = pt
        if self.cur is None:
            # the cursor enters from just outside the bottom-right of the viewport
            self.cur = (min(self.css[0] - 40, x1 + 260), min(self.css[1] - 30, y1 + 180))
        x0, y0 = self.cur
        n = self.frames_for(dur)
        for i in range(1, n + 1):
            p = ease_in_out(i / n)
            self.cur = (x0 + (x1 - x0) * p, y0 + (y1 - y0) * p)
            self.page.mouse.move(*self.cur)
            self.snap()


if __name__ == "__main__":
    spec = json.load(open(sys.argv[1]))
    Capture(spec, sys.argv[2]).run()
