"""The desktop stage: composite wallpaper + window cards + presenter card + cursor at 2x,
then film it with a 3D camera (zoom, pan, tilt) into a 1920x1080 stream.

    python stage.py project.json camera.json out_video.mp4

project.json fields used here:
  fps, out [w,h], canvas [w,h], base_w, wallpaper (png), duration,
  presenter {src (cut mp4 at 1920x1080), rect [x,y,w,h], radius, in},
  layers [{id, kind: frames|video|image, dir|src, actions, rect, radius, in, out,
           chrome: traffic|none, title, bar_h, cursor: true}],
  hud [{kind: pill|source, text, in, out}]
camera.json: [{t, target [x,y], zoom, rotY, rotX, dur, ease, drift}, ...]  (t = arrival time)
"""
import math
import os
import sys

import cv2
import numpy as np

from common import (blend_alpha, cursor_image, ease, ffmpeg_writer, lerp, load_json, paste_card,
                    paste_rgba, render_pill, render_source, render_titlebar, rounded_mask, shadow_alpha)

POP_DUR = 0.42


# ---------------------------------------------------------------- camera
class Camera:
    def __init__(self, keys, project):
        self.keys = sorted(keys, key=lambda k: k["t"])
        self.out = project["out"]
        self.base_w = project.get("base_w", project["canvas"][0] * 0.9)
        self.canvas = project["canvas"]
        self.F = project.get("focal_mult", 1.3) * self.canvas[0]

    def _hold_state(self, i, t):
        """State while holding on key i at time t (drift applied)."""
        k = self.keys[i]
        hold_end = self.keys[i + 1]["t"] - self.keys[i + 1].get("dur", 0.9) if i + 1 < len(self.keys) else k["t"] + 6.0
        hold_len = max(0.001, hold_end - k["t"])
        p = min(1.0, max(0.0, (t - k["t"]) / hold_len))
        z = k["zoom"] * (1 + k.get("drift", 0.0) * p)
        return dict(target=list(k["target"]), zoom=z, rotY=k.get("rotY", 0), rotX=k.get("rotX", 0))

    def state(self, t):
        ks = self.keys
        if t <= ks[0]["t"]:
            return self._hold_state(0, ks[0]["t"])
        for i in range(len(ks) - 1):
            k1 = ks[i + 1]
            start = k1["t"] - k1.get("dur", 0.9)
            if t < start:
                return self._hold_state(i, t)
            if t < k1["t"]:
                a = self._hold_state(i, start)
                p = ease((t - start) / max(0.001, k1["t"] - start), k1.get("ease", "inOut"))
                return dict(
                    target=[lerp(a["target"][0], k1["target"][0], p), lerp(a["target"][1], k1["target"][1], p)],
                    zoom=math.exp(lerp(math.log(a["zoom"]), math.log(k1["zoom"]), p)),
                    rotY=lerp(a["rotY"], k1.get("rotY", 0), p), rotX=lerp(a["rotX"], k1.get("rotX", 0), p),
                )
        return self._hold_state(len(ks) - 1, t)

    def homography(self, st, q=1.0):
        """Map canvas (scaled by q) -> output. Returns (H, effective_scale)."""
        Wc, Hc = self.canvas
        ow, oh = self.out
        s = ow / self.base_w * st["zoom"]
        tx, ty = st["target"]
        th, ph = math.radians(st["rotY"]), math.radians(st["rotX"])
        F = self.F
        src, dst = [], []
        for x, y in ((0, 0), (Wc, 0), (Wc, Hc), (0, Hc)):
            X, Y = x - tx, y - ty
            X1, Z1 = X * math.cos(th), X * math.sin(th)
            Y2, Z2 = Y * math.cos(ph) - Z1 * math.sin(ph), Y * math.sin(ph) + Z1 * math.cos(ph)
            u, v = F * X1 / (F - Z2), F * Y2 / (F - Z2)
            src.append((x * q, y * q))
            dst.append((s * u + ow / 2, s * v + oh / 2))
        H = cv2.getPerspectiveTransform(np.float32(src), np.float32(dst))
        return H, s


# ---------------------------------------------------------------- layers
class Layer:
    def __init__(self, spec, project):
        self.spec = spec
        self.id = spec["id"]
        self.kind = spec["kind"]
        self.fps = project["fps"]
        self.t_in = spec.get("in", 0.0)
        self.t_out = spec.get("out")
        self.rect = [int(v) for v in spec["rect"]]
        self.radius = int(spec.get("radius", 24))
        self.bar = None
        self.bar_h = 0
        if spec.get("chrome") == "traffic":
            self.bar_h = int(spec.get("bar_h", 76))
            self.bar = render_titlebar(self.rect[2], spec.get("title", ""), self.bar_h)
        self.mask = rounded_mask(self.rect[2], self.rect[3], self.radius)
        self.shadow, self.pad = shadow_alpha(self.rect[2], self.rect[3], self.radius,
                                             blur=int(spec.get("shadow_blur", 70)), alpha=spec.get("shadow_alpha", 0.42))
        self.shadow_dy = int(spec.get("shadow_dy", 28))
        self.actions = load_json(spec["actions"]) if spec.get("actions") else None
        self.show_cursor = spec.get("cursor", True) and self.actions is not None
        self.n_frames = None
        self.cap = None
        self.last = None
        self.last_idx = -1
        if self.kind == "frames":
            files = sorted(f for f in os.listdir(spec["dir"]) if f.endswith(".png"))
            self.files = [os.path.join(spec["dir"], f) for f in files]
            self.n_frames = len(self.files)
        elif self.kind == "video":
            self.cap = cv2.VideoCapture(spec["src"])
            self.n_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        elif self.kind == "image":
            self.last = cv2.imread(spec["src"], cv2.IMREAD_COLOR)

    def visible(self, t):
        return t >= self.t_in and (self.t_out is None or t < self.t_out + POP_DUR)

    def pop(self, t):
        """(scale, alpha) of the entry/exit pop."""
        if self.t_in <= 0 and t < POP_DUR:
            return 1.0, 1.0  # a layer present from frame 0 never pops: the film opens on it
        if t < self.t_in + POP_DUR:
            p = ease((t - self.t_in) / POP_DUR, "out3")
            return lerp(0.94, 1.0, p), p
        if self.t_out is not None and t >= self.t_out:
            p = ease((t - self.t_out) / POP_DUR, "in")
            return lerp(1.0, 0.96, p), 1 - p
        return 1.0, 1.0

    def frame(self, t):
        """Content BGR at the card size for time t (holds the last frame after the capture ends)."""
        idx = int(math.floor((t - self.t_in) * self.fps + 1e-6))
        if self.kind == "image":
            img = self.last
        elif self.kind == "frames":
            idx = min(max(idx, 0), self.n_frames - 1)
            if idx != self.last_idx:
                self.last = cv2.imread(self.files[idx], cv2.IMREAD_COLOR)
                self.last_idx = idx
            img = self.last
        else:  # video, sequential
            idx = min(max(idx, 0), self.n_frames - 1)
            while self.last_idx < idx:
                ok, fr = self.cap.read()
                if not ok:
                    break
                self.last = fr
                self.last_idx += 1
            img = self.last
        cw, ch = self.rect[2], self.rect[3] - self.bar_h
        if img.shape[1] != cw or img.shape[0] != ch:
            img = cv2.resize(img, (cw, ch), interpolation=cv2.INTER_AREA if img.shape[1] > cw else cv2.INTER_CUBIC)
        if self.bar is not None:
            img = np.vstack([self.bar, img])
        if self.spec.get("chrome") == "inset":
            # Electron apps with a hidden-inset title bar (Obsidian): draw the traffic lights
            # into the gap the app leaves at its top-left, where macOS would put them
            img = img.copy()
            for i, col in enumerate(((87, 95, 255), (46, 188, 254), (64, 200, 40))):  # BGR
                cv2.circle(img, (26 + i * 40, 28), 12, col, -1, cv2.LINE_AA)
        return img

    def cursor_at(self, t):
        """Cursor position in canvas px, or None."""
        if not self.show_cursor:
            return None
        a = self.actions
        idx = int(math.floor((t - self.t_in) * self.fps + 1e-6))
        idx = min(max(idx, 0), len(a["cursor"]) - 1)
        c = a["cursor"][idx]
        if c is None:
            return None
        sx = self.rect[2] / a["css"][0]
        return self.rect[0] + c[0] * sx, self.rect[1] + self.bar_h + c[1] * sx


# ---------------------------------------------------------------- HUD
class Hud:
    def __init__(self, items, out):
        self.items = []
        for it in items or []:
            if it["kind"] == "pill":
                img, a = render_pill(it["text"].upper())
                pos = (out[0] // 2 - img.shape[1] // 2, int(out[1] * 0.885) - img.shape[0] // 2)
            else:
                img, a = render_source(it["text"].upper())
                pos = (14, 10)
            self.items.append(dict(img=img, a=a, pos=pos, t_in=it["in"], t_out=it["out"], kind=it["kind"]))

    def draw(self, frame, t):
        for it in self.items:
            if t < it["t_in"] or t >= it["t_out"] + 0.25:
                continue
            fade = 0.25
            k = min(1.0, (t - it["t_in"]) / fade) if t < it["t_in"] + fade else 1.0
            if t >= it["t_out"]:
                k = max(0.0, 1 - (t - it["t_out"]) / fade)
            k = ease(k, "out")
            dy = int((1 - k) * 12) if it["kind"] == "pill" else 0
            paste_rgba(frame, it["img"], it["a"] * k, it["pos"][0], it["pos"][1] + dy)


# ---------------------------------------------------------------- render
def render(project, keys, out_path, t0=0.0, t1=None, progress=True):
    fps = project["fps"]
    W, H = project["canvas"]
    ow, oh = project["out"]
    duration = project["duration"] if t1 is None else t1
    n0, n1 = int(round(t0 * fps)), int(round(duration * fps))

    wall = cv2.imread(project["wallpaper"], cv2.IMREAD_COLOR)
    # cover-fit the wallpaper to the canvas
    s = max(W / wall.shape[1], H / wall.shape[0])
    wall = cv2.resize(wall, (int(math.ceil(wall.shape[1] * s)), int(math.ceil(wall.shape[0] * s))), interpolation=cv2.INTER_AREA)
    ox, oy = (wall.shape[1] - W) // 2, (wall.shape[0] - H) // 2
    wall = np.ascontiguousarray(wall[oy : oy + H, ox : ox + W])

    pres_spec = dict(project["presenter"])
    pres_spec.update(id="presenter", kind="video", radius=pres_spec.get("radius", 28))
    presenter = Layer(pres_spec, project)
    layers = [Layer(L, project) for L in project["layers"]]
    all_layers = layers + [presenter]  # presenter drawn last (on top)
    cam = Camera(keys, project)
    hud = Hud(project.get("hud"), project["out"])
    cur_img, cur_a, hot = cursor_image(project.get("cursor_scale", 2.0))

    # wallpaper variants with the shadows of every steady visible layer baked in
    variants = {}

    def base_for(vis_ids):
        key = tuple(sorted(vis_ids))
        if key not in variants:
            b = wall.copy()
            for L in all_layers:
                if L.id in vis_ids:
                    x, y, w, h = L.rect
                    blend_alpha(b, L.shadow, x - L.pad, y - L.pad + L.shadow_dy)
            variants[key] = b
        return variants[key]

    writer = ffmpeg_writer(out_path, ow, oh, fps)
    # presenter video must be positioned at frame n0
    if n0 > 0:
        presenter.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    for n in range(n0, n1):
        t = n / fps
        steady, popping = [], []
        for L in all_layers:
            if not L.visible(t):
                continue
            sc, al = L.pop(t)
            (steady if (sc == 1.0 and al == 1.0) else popping).append(L)
        canvas = base_for([L.id for L in steady]).copy()
        cursor = None
        for L in all_layers:
            if L not in steady and L not in popping:
                continue
            img = L.frame(t)
            x, y, w, h = L.rect
            if L in steady:
                paste_card(canvas, img, L.mask, x, y, L.radius)
            else:
                sc, al = L.pop(t)
                sw, sh = int(w * sc), int(h * sc)
                sx, sy = x + (w - sw) // 2, y + (h - sh) // 2
                blend_alpha(canvas, L.shadow * al, sx - L.pad, sy - L.pad + L.shadow_dy)
                small = cv2.resize(img, (sw, sh), interpolation=cv2.INTER_AREA)
                m = cv2.resize(L.mask, (sw, sh), interpolation=cv2.INTER_AREA) * al
                paste_rgba(canvas, small, m, sx, sy)
            c = L.cursor_at(t) if L is not presenter else None
            if c is not None:
                cursor = c
        if cursor is not None:
            paste_rgba(canvas, cur_img, cur_a, int(cursor[0]) - hot[0], int(cursor[1]) - hot[1])

        st = cam.state(t)
        H1, s_eff = cam.homography(st)
        # pre-shrink with INTER_AREA when the camera is wide, so text does not alias
        q = 1.0
        if s_eff < 0.8:
            q = max(0.35, s_eff * 1.15)
            src = cv2.resize(canvas, (int(W * q), int(H * q)), interpolation=cv2.INTER_AREA)
            H1, _ = cam.homography(st, q)
        else:
            src = canvas
        frame = cv2.warpPerspective(src, H1, (ow, oh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        hud.draw(frame, t)
        writer.stdin.write(frame.tobytes())
        if progress and n % 25 == 0:
            print(f"  frame {n}/{n1}  t={t:.1f}s zoom={st['zoom']:.2f}", flush=True)
    writer.stdin.close()
    writer.wait()
    return n1 - n0


if __name__ == "__main__":
    project = load_json(sys.argv[1])
    keys = load_json(sys.argv[2])
    t0 = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
    t1 = float(sys.argv[5]) if len(sys.argv) > 5 else None
    n = render(project, keys, sys.argv[3], t0=t0, t1=t1)
    print(f"stage: wrote {n} frames -> {sys.argv[3]}")
