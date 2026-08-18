import json, os, subprocess, sys, hashlib
from concurrent.futures import ThreadPoolExecutor

FF   = open('ffpath.txt').read().strip()
SRC  = 'src/source.mov'
FPS  = 30
SW, SH = 3840, 2160          # source
OW, OH = 1920, 1080          # output
CX, CY = 0.435, 0.440        # Sam sits left of centre and high in the frame

X264 = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-profile:v", "high", "-x264-params", "keyint=60:min-keyint=60:scenecut=0",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
        "-video_track_timescale", "30000", "-an"]

def vf(s):
    z = s['zoom']
    if z[0] == 'none':
        return f"scale={OW}:{OH}:flags=bicubic"
    if z[0] == 'static':
        k = float(z[1])
        w = int(SW / k) // 2 * 2
        h = int(SH / k) // 2 * 2
        x = int(round((SW - w) * CX)) // 2 * 2
        y = int(round((SH - h) * CY)) // 2 * 2
        x = max(0, min(SW - w, x)); y = max(0, min(SH - h, y))
        return f"crop={w}:{h}:{x}:{y},scale={OW}:{OH}:flags=bicubic"
    # animated push: scale first, then sub-pixel perspective (zoompan judders)
    z0, z1 = float(z[1]), float(z[2])
    off = s['zoff']; tot = max(2, s['ztot'])
    Z  = f"{z0}+({z1 - z0})*(on+{off})/{tot - 1}"
    dx = f"(W-W/({Z}))*{CX}"; rx = f"(W-W/({Z}))*{1 - CX}"
    dy = f"(H-H/({Z}))*{CY}"; ry = f"(H-H/({Z}))*{1 - CY}"
    per = (f"perspective=x0='{dx}':y0='{dy}':x1='W-{rx}':y1='{dy}':"
           f"x2='{dx}':y2='H-{ry}':x3='W-{rx}':y3='H-{ry}':"
           f"interpolation=cubic:sense=source:eval=frame")
    return f"scale={OW}:{OH}:flags=bicubic,{per}"

def job(args):
    i, s, outdir = args
    n   = s['f1'] - s['f0']
    out = f"{outdir}/seg_{i:04d}.mp4"
    tag = hashlib.md5((vf(s) + str(s['f0']) + str(s['f1'])).encode()).hexdigest()[:8]
    stamp = out + ".stamp"
    if os.path.exists(out) and os.path.exists(stamp) and open(stamp).read() == tag:
        return (i, n, "cached")
    ss = (s['f0'] - 0.5) / FPS          # land squarely on frame f0
    cmd = [FF, "-v", "error", "-y", "-ss", f"{ss:.6f}", "-i", SRC,
           "-frames:v", str(n), "-vf", vf(s), "-threads", "2"] + X264 + [out]
    subprocess.run(cmd, check=True)
    got = count_frames(out)
    if got != n:
        raise SystemExit(f"seg {i}: got {got} frames, want {n}")
    open(stamp, "w").write(tag)
    return (i, n, "ok")

def count_frames(p):
    # no ffprobe in this build; count packets without decoding
    r = subprocess.run([FF, "-v", "error", "-i", p, "-map", "0:v:0",
                        "-c", "copy", "-f", "framemd5", "-"],
                       capture_output=True, text=True)
    return sum(1 for l in r.stdout.splitlines() if l and not l.startswith('#'))

if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'longform'
    src   = 'edit/trailer.json' if which == 'trailer' else 'edit/cut.json'
    outdir = 'edit/segs_trailer' if which == 'trailer' else 'edit/segs'
    os.makedirs(outdir, exist_ok=True)
    cut = json.load(open(src))
    S = cut['segments']
    done = 0
    with ThreadPoolExecutor(max_workers=2) as ex:
        for i, n, st in ex.map(job, [(i, s, outdir) for i, s in enumerate(S)]):
            done += 1
            if done % 10 == 0 or st != 'ok' or done == len(S):
                print(f"[{done:3d}/{len(S)}] seg {i:04d} {n:5d}f {st}", flush=True)
    print("ALL SEGMENTS RENDERED", flush=True)
