import shoot
import json, os, subprocess, sys

FF  = open('ffpath.txt').read().strip()
FPS = 30

def count_frames(p):
    r = subprocess.run([FF, "-v", "error", "-i", p, "-map", "0:v:0",
                        "-c", "copy", "-f", "framemd5", "-"],
                       capture_output=True, text=True)
    return sum(1 for l in r.stdout.splitlines() if l and not l.startswith('#'))

if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'longform'
    if which == 'trailer':
        cut_p, segdir, wav = 'edit/trailer.json', 'edit/segs_trailer', 'edit/trailer.wav'
        out = sys.argv[2] if len(sys.argv) > 2 else shoot.out('trailer', 1)
    else:
        cut_p, segdir, wav = 'edit/cut.json', 'edit/segs', 'edit/cut.wav'
        out = sys.argv[2] if len(sys.argv) > 2 else shoot.out('longform', 1)
    os.makedirs('out', exist_ok=True)
    cut = json.load(open(cut_p))
    n = len(cut['segments'])
    lst = f"{segdir}/concat.txt"
    with open(lst, 'w') as f:
        for i in range(n):
            f.write(f"file '{os.path.abspath(segdir)}/seg_{i:04d}.mp4'\n")
    silent = f"{segdir}/_video.mp4"
    subprocess.run([FF, "-v", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", lst, "-c", "copy", silent], check=True)
    got = count_frames(silent)
    want = cut['total_frames']
    if got != want:
        raise SystemExit(f"REFUSING TO MUX: concat has {got} frames, cut.json says {want}")
    print(f"concat OK: {got} frames = {got/FPS:.3f}s")
    subprocess.run([FF, "-v", "error", "-y", "-i", silent, "-i", wav,
                    "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                    "-movflags", "+faststart", "-shortest", out], check=True)
    print("WROTE", out, os.path.getsize(out) / 1e6, "MB")
