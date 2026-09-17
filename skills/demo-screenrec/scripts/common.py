"""Shared helpers for the demo-screenrec stage: easing, masks, cursor, labels, ffmpeg.

Everything works in BGR uint8 numpy arrays (OpenCV convention) plus float32 alpha masks.
"""
import json
import math
import os
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Fonts ship with the skill (assets/fonts). Override with DEMO_FONT_DISPLAY / DEMO_FONT_UI if you like.
_ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")
FONT_DISPLAY = os.environ.get("DEMO_FONT_DISPLAY", os.path.join(_ASSETS, "Montserrat-ExtraBold.ttf"))
FONT_UI = os.environ.get("DEMO_FONT_UI", os.path.join(_ASSETS, "DejaVuSans.ttf"))
FONT_UI_FALLBACK = "/System/Library/Fonts/SFNS.ttf"
FONT_LINUX = ("/System/Library/Fonts/HelveticaNeue.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf")


def font(path, size):
    for p in (path, FONT_UI, FONT_UI_FALLBACK) + FONT_LINUX:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------- easing
def ease(p, kind="inOut"):
    p = max(0.0, min(1.0, p))
    if kind == "linear":
        return p
    if kind == "in":
        return p * p
    if kind == "out":
        return 1 - (1 - p) * (1 - p)
    if kind == "out3":
        return 1 - (1 - p) ** 3
    if kind == "inOut3":
        return 4 * p * p * p if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2
    # power2 inOut (GSAP power2.inOut) — the reference's zoom curve
    return 2 * p * p if p < 0.5 else 1 - (-2 * p + 2) ** 2 / 2


def lerp(a, b, p):
    return a + (b - a) * p


# ---------------------------------------------------------------- masks and shadows
def rounded_mask(w, h, r):
    """float32 HxW alpha in 0..1 with anti-aliased rounded corners."""
    ss = 4
    im = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(im).rounded_rectangle([0, 0, w * ss - 1, h * ss - 1], radius=r * ss, fill=255)
    im = im.resize((w, h), Image.LANCZOS)
    return np.asarray(im, dtype=np.float32) / 255.0


def shadow_alpha(w, h, r, blur=70, alpha=0.42):
    """Soft drop shadow for a rounded card. Returns (alpha float32, pad).

    The array is (h+2*pad) x (w+2*pad); place it at (x-pad, y-pad+offset_y).
    """
    pad = blur * 2
    im = Image.new("L", (w + 2 * pad, h + 2 * pad), 0)
    ImageDraw.Draw(im).rounded_rectangle([pad, pad, pad + w - 1, pad + h - 1], radius=r, fill=int(255 * alpha))
    im = im.filter(ImageFilter.GaussianBlur(blur / 2))
    return np.asarray(im, dtype=np.float32) / 255.0, pad


def blend_alpha(canvas, alpha, x, y, colour=(0, 0, 0)):
    """Blend a flat colour with per-pixel alpha onto canvas at (x, y). Clips to the canvas."""
    H, W = canvas.shape[:2]
    h, w = alpha.shape
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    a = alpha[y0 - y : y1 - y, x0 - x : x1 - x][..., None]
    region = canvas[y0:y1, x0:x1].astype(np.float32)
    col = np.array(colour, dtype=np.float32)[None, None, :]
    canvas[y0:y1, x0:x1] = (region * (1 - a) + col * a).astype(np.uint8)


def paste_rgba(canvas, img, alpha, x, y):
    """Alpha-blend a BGR image with a float32 alpha mask onto canvas at (x, y), clipped."""
    H, W = canvas.shape[:2]
    h, w = img.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    src = img[y0 - y : y1 - y, x0 - x : x1 - x]
    a = alpha[y0 - y : y1 - y, x0 - x : x1 - x][..., None]
    region = canvas[y0:y1, x0:x1].astype(np.float32)
    canvas[y0:y1, x0:x1] = (region * (1 - a) + src.astype(np.float32) * a).astype(np.uint8)


def paste_card(canvas, img, mask, x, y, r):
    """Fast opaque card paste: copy the interior, alpha-blend only the four corner squares
    against what is already on the canvas. mask is the rounded mask of img, r its radius."""
    H, W = canvas.shape[:2]
    h, w = img.shape[:2]
    if x < 0 or y < 0 or x + w > W or y + h > H:
        paste_rgba(canvas, img, mask, x, y)
        return
    r = max(1, min(r, w // 2, h // 2))
    corners = {}
    for cy, cx in ((0, 0), (0, w - r), (h - r, 0), (h - r, w - r)):
        corners[(cy, cx)] = canvas[y + cy : y + cy + r, x + cx : x + cx + r].astype(np.float32)
    canvas[y : y + h, x : x + w] = img
    for (cy, cx), bg in corners.items():
        sub = img[cy : cy + r, cx : cx + r].astype(np.float32)
        a = mask[cy : cy + r, cx : cx + r][..., None]
        canvas[y + cy : y + cy + r, x + cx : x + cx + r] = (bg * (1 - a) + sub * a).astype(np.uint8)


# ---------------------------------------------------------------- cursor
def cursor_image(scale=2.0):
    """The macOS arrow pointer as (bgr, alpha). Hotspot is the top-left tip. scale 2 = Retina size."""
    pts = [(0, 0), (0, 16.5), (4, 12.8), (6.8, 19.6), (9.6, 18.4), (6.8, 11.8), (11.8, 11.8)]
    ss = 4
    s = scale * ss
    w, h = int(14 * scale) + 4, int(22 * scale) + 4
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    poly = [(x * s + 2 * ss, y * s + 2 * ss) for x, y in pts]
    d.polygon(poly, fill=(255, 255, 255, 255), outline=(255, 255, 255, 255), width=int(2.2 * s))
    d.polygon(poly, fill=(0, 0, 0, 255))
    im = im.resize((w, h), Image.LANCZOS)
    arr = np.asarray(im).astype(np.float32)
    bgr = arr[..., :3][..., ::-1].copy().astype(np.uint8)
    alpha = arr[..., 3] / 255.0
    return bgr, alpha, (2, 2)


# ---------------------------------------------------------------- HUD labels
def render_pill(text, size=46, pad_x=26, pad_y=13, radius=16):
    """Reference chapter pill: white Montserrat ExtraBold on a dark navy translucent pill."""
    f = font(FONT_DISPLAY, size)
    tw, th = _text_size(f, text)
    w, h = tw + 2 * pad_x, th + 2 * pad_y
    im = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([20, 20, 20 + w, 20 + h], radius=radius, fill=(20, 26, 52, 218))
    glow = im.filter(ImageFilter.GaussianBlur(10))
    im = Image.alpha_composite(glow, im)
    d = ImageDraw.Draw(im)
    d.text((20 + pad_x, 20 + pad_y - _text_top(f, text)), text, font=f, fill=(255, 255, 255, 255))
    return _rgba_to_bgr_alpha(im)


def render_source(text, size=22):
    f = font(FONT_DISPLAY, size)
    tw, th = _text_size(f, text)
    im = Image.new("RGBA", (tw + 8, th + 8), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((4, 4 - _text_top(f, text)), text, font=f, fill=(0, 0, 0, 255))
    return _rgba_to_bgr_alpha(im)


def render_titlebar(w, title, bar_h=76):
    """A macOS-style window title bar at 2x: traffic lights + centred title."""
    im = Image.new("RGBA", (w, bar_h), (243, 243, 245, 255))
    d = ImageDraw.Draw(im)
    r = 12
    for i, col in enumerate(((255, 95, 87), (254, 188, 46), (40, 200, 64))):
        cx = 30 + i * 40
        d.ellipse([cx - r, bar_h // 2 - r, cx + r, bar_h // 2 + r], fill=col + (255,))
    if title:
        f = font(FONT_UI, 26)
        tw, th = _text_size(f, title)
        d.text(((w - tw) // 2, (bar_h - th) // 2 - _text_top(f, title)), title, font=f, fill=(70, 70, 74, 255))
    d.line([(0, bar_h - 1), (w, bar_h - 1)], fill=(218, 218, 222, 255), width=1)
    arr = np.asarray(im)[..., :3][..., ::-1].copy()
    return arr


def _text_size(f, text):
    l, t, r, b = f.getbbox(text)
    return r - l, b - t


def _text_top(f, text):
    return f.getbbox(text)[1]


def _rgba_to_bgr_alpha(im):
    arr = np.asarray(im).astype(np.float32)
    return arr[..., :3][..., ::-1].copy().astype(np.uint8), arr[..., 3] / 255.0


# ---------------------------------------------------------------- ffmpeg
def x264_args(crf=16):
    return [
        "-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p",
        "-profile:v", "high", "-x264-params", "keyint=25:min-keyint=25:scenecut=0",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
        "-video_track_timescale", "25000",
    ]


def ffmpeg_writer(path, w, h, fps):
    cmd = [
        "ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}",
        "-r", str(fps), "-i", "-", "-an",
    ] + x264_args() + [path]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def probe_frames(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
         "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", path],
        capture_output=True, text=True,
    ).stdout.strip()
    return int(out or 0)


def load_json(p):
    with open(p) as f:
        return json.load(f)


def save_json(p, obj):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    with open(p, "w") as f:
        json.dump(obj, f, indent=1)
