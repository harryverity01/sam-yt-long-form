"""Masterclass v2: trailer (with its music bed) at the front, then the body.

The v1 masterclass opened on its own two-beat cold open. That is the same material
the trailer uses, so the cold open is dropped and the trailer becomes the opening,
exactly like the last Sam long form (SAM_YT_FULL_v8.1: trailer at the front, music
on the trailer only, ending clean on the trailer's final frame).
"""
import json, os, subprocess, wave
import numpy as np

FF  = open('ffpath.txt').read().strip()
SPF = 1600
FPS = 30

def read_wav(p):
    w = wave.open(p, 'rb'); n = w.getnframes(); ch = w.getnchannels(); w.close()
    off = os.path.getsize(p) - n * ch * 2
    return np.array(np.memmap(p, dtype='<i2', mode='r', offset=off, shape=(n, ch)))

def count_frames(p):
    r = subprocess.run([FF, "-v", "error", "-i", p, "-map", "0:v:0",
                        "-c", "copy", "-f", "framemd5", "-"],
                       capture_output=True, text=True)
    return sum(1 for l in r.stdout.splitlines() if l and not l.startswith('#'))

cut = json.load(open('edit/cut.json'))
tr  = json.load(open('edit/trailer.json'))
S   = cut['segments']
body = [i for i, s in enumerate(S) if s['block'] not in (0, 1)]
cold_frames = sum(S[i]['f1'] - S[i]['f0'] for i in range(body[0]))
body_frames = sum(S[i]['f1'] - S[i]['f0'] for i in body)
total = tr['total_frames'] + body_frames
print(f"trailer {tr['total_frames']}f + body {body_frames}f = {total}f "
      f"({total/FPS/60:.2f} min)")

# ---- video: stream-copy concat, trailer segments then body segments -------
lst = 'edit/_v2_concat.txt'
with open(lst, 'w') as f:
    for i in range(len(tr['segments'])):
        f.write(f"file '{os.path.abspath('edit/segs_trailer')}/seg_{i:04d}.mp4'\n")
    for i in body:
        f.write(f"file '{os.path.abspath('edit/segs')}/seg_{i:04d}.mp4'\n")
silent = 'edit/_v2_video.mp4'
subprocess.run([FF, "-v", "error", "-y", "-f", "concat", "-safe", "0",
                "-i", lst, "-c", "copy", silent], check=True)
got = count_frames(silent)
if got != total:
    raise SystemExit(f"REFUSING: concat has {got} frames, want {total}")
print("concat OK:", got, "frames")

# ---- audio: trailer mix (music already in it) then the body ---------------
tra = read_wav('edit/trailer_mixed.wav').astype(np.int32)
assert len(tra) == tr['total_frames'] * SPF, (len(tra), tr['total_frames'] * SPF)
full = read_wav('edit/cut.wav').astype(np.int32)
bod = full[cold_frames * SPF: (cold_frames + body_frames) * SPF]
assert len(bod) == body_frames * SPF, (len(bod), body_frames * SPF)

# 20 ms crossfade at the join so the music tail does not click into the body
x = 960
mix = np.concatenate([tra, bod])
a = mix[len(tra) - x:len(tra)].astype(np.float32)
b = mix[len(tra):len(tra) + x].astype(np.float32)
r = np.linspace(0, 1, x, dtype=np.float32)[:, None]
mix[len(tra) - x:len(tra)] = (a * (1 - r)).astype(np.int32)
mix[len(tra):len(tra) + x] = (b * r).astype(np.int32)
assert len(mix) == total * SPF

o = wave.open('edit/v2_audio.wav', 'wb')
o.setnchannels(2); o.setsampwidth(2); o.setframerate(48000)
o.writeframes(np.clip(mix, -32768, 32767).astype('<i2').tobytes()); o.close()
print("audio", len(mix), "samples =", len(mix) / 48000, "s")

out = 'out/sam_tobi_YT_MASTERCLASS_v2.mp4'
subprocess.run([FF, "-v", "error", "-y", "-i", silent, "-i", 'edit/v2_audio.wav',
                "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                "-movflags", "+faststart", "-shortest", out], check=True)
print("WROTE", out, os.path.getsize(out) / 1e6, "MB")
print("final frames", count_frames(out), "want", total)
