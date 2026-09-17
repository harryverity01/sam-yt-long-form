"""Make a soft desktop wallpaper for the stage when you have no macOS wallpaper to hand.

    python make_wallpaper.py out.png [--w 3840 --h 2400]

Any image works as a wallpaper; this one is a quiet silver-to-blue gradient with two soft colour
blooms, so window cards and the presenter card read cleanly on top of it.
"""
import argparse

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--w", type=int, default=3840)
    ap.add_argument("--h", type=int, default=2400)
    a = ap.parse_args()
    W, H = a.w, a.h
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    u = x / W * 0.7 + y / H * 0.3
    c0, c1 = np.array([236, 232, 226]), np.array([196, 206, 222])
    img = (c0[None, None, :] * (1 - u[..., None]) + c1[None, None, :] * u[..., None]).astype(np.uint8)
    im = Image.fromarray(img)
    bloom = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(bloom)
    d.ellipse([int(W * 0.62), int(-H * 0.17), int(W * 1.15), int(H * 0.58)], fill=(120, 150, 200))
    d.ellipse([int(-W * 0.16), int(H * 0.54), int(W * 0.39), int(H * 1.25)], fill=(220, 170, 140))
    bloom = bloom.filter(ImageFilter.GaussianBlur(int(W * 0.11)))
    im = Image.blend(im, bloom, 0.35)
    im.save(a.out)
    print("wrote", a.out, im.size)


if __name__ == "__main__":
    main()
