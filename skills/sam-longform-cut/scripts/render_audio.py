import json, sys, wave, os
import numpy as np

SPF   = 1600          # 48000 / 30, exact
FADE  = 192           # 4 ms de-click at every splice
WAV   = 'src/master48.wav'

def master():
    w = wave.open(WAV, 'rb')
    n, ch, sw, sr = w.getnframes(), w.getnchannels(), w.getsampwidth(), w.getframerate()
    w.close()
    assert (sr, ch, sw) == (48000, 2, 2), (sr, ch, sw)
    off = os.path.getsize(WAV) - n * ch * sw          # data chunk is last
    a = np.memmap(WAV, dtype='<i2', mode='r', offset=off, shape=(n, ch))
    return a, n

if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'longform'
    src   = 'edit/trailer.json' if which == 'trailer' else 'edit/cut.json'
    out   = 'edit/trailer_raw.wav' if which == 'trailer' else 'edit/cut_raw.wav'
    cut = json.load(open(src))
    S   = cut['segments']
    a, N = master()
    total = cut['total_frames'] * SPF
    mix = np.zeros((total, 2), dtype=np.float32)
    p = 0
    for s in S:
        n = (s['f1'] - s['f0']) * SPF
        i0 = s['f0'] * SPF
        i1 = min(i0 + n, N)
        chunk = np.zeros((n, 2), dtype=np.float32)
        chunk[:i1 - i0] = a[i0:i1].astype(np.float32)
        f = min(FADE, n // 2)
        r = np.linspace(0.0, 1.0, f, dtype=np.float32)[:, None]
        chunk[:f] *= r
        chunk[-f:] *= r[::-1]
        mix[p:p + n] = chunk
        p += n
    assert p == total, (p, total)

    # levels are set by normalise.py (loudnorm); this stage stays bit-faithful
    o = wave.open(out, 'wb')
    o.setnchannels(2); o.setsampwidth(2); o.setframerate(48000)
    o.writeframes(np.clip(mix, -32768, 32767).astype('<i2').tobytes())
    o.close()
    print(f"{out}: {total} samples = {total/48000:.3f}s "
          f"({cut['total_frames']} frames)")
