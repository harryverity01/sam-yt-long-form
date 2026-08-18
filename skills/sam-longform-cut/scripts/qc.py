"""Motion-signature probe: where did each segment's first frame actually land?

Audio-to-audio measurement does NOT detect a picture-placement error. For a
sample of segments this renders source frames f0-2 .. f0+2 through the same
filter chain the segment used and reports which offset the segment's own first
frame matches. The minimum must be 0 every time.
"""
import json, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image
import render_video as RV

FF = RV.FF

def png(cmd, path):
    subprocess.run(cmd + [path], check=True)
    return np.asarray(Image.open(path).convert('L').resize((480, 270)), dtype=np.float32)

def seg_first_frame(segdir, i, tmp):
    p = f"{tmp}/seg{i}.png"
    return png([FF, "-v", "error", "-y", "-i", f"{segdir}/seg_{i:04d}.mp4",
                "-frames:v", "1"], p)

def src_frame(s, f, tmp, tag):
    ss = (f - 0.5) / RV.FPS
    p = f"{tmp}/src{tag}.png"
    return png([FF, "-v", "error", "-y", "-ss", f"{ss:.6f}", "-i", RV.SRC,
                "-frames:v", "1", "-vf", RV.vf(s)], p)

if __name__ == '__main__':
    which  = sys.argv[1] if len(sys.argv) > 1 else 'longform'
    cut_p  = 'edit/trailer.json' if which == 'trailer' else 'edit/cut.json'
    segdir = 'edit/segs_trailer' if which == 'trailer' else 'edit/segs'
    cut = json.load(open(cut_p))
    S = cut['segments']
    n = len(S)
    picks = sorted({int(round(x)) for x in np.linspace(0, n - 1, min(7, n))})
    bad = 0
    with tempfile.TemporaryDirectory() as tmp:
        for i in picks:
            s = S[i]
            a = seg_first_frame(segdir, i, tmp)
            ds = []
            for d in (-2, -1, 0, 1, 2):
                b = src_frame(s, s['f0'] + d, tmp, d)
                ds.append(float(np.mean(np.abs(a - b))))
            best = int(np.argmin(ds)) - 2
            flag = "OK " if best == 0 else "DRIFT"
            if best != 0:
                bad += 1
            print(f"  seg {i:4d} f0={s['f0']:7d}  match at {best:+d} frames  {flag}  "
                  + " ".join(f"{d:+d}:{v:5.2f}" for d, v in zip((-2, -1, 0, 1, 2), ds)))
    print("PICTURE PLACEMENT:", "0 frames of drift on every checkpoint" if not bad
          else f"{bad} checkpoints OFF — do not ship")
