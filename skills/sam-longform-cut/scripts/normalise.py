"""Loudness-normalise a spliced WAV without changing its sample count.

The mux contract is total_frames * 1600 samples. loudnorm can hand back a
different length, so the result is trimmed or zero-padded back to the contract
before it is written.
"""
import json, os, subprocess, sys, wave
import numpy as np

FF  = open('ffpath.txt').read().strip()
SPF = 1600

def read_wav(p):
    w = wave.open(p, 'rb'); n = w.getnframes(); w.close()
    off = os.path.getsize(p) - n * 4
    return np.array(np.memmap(p, dtype='<i2', mode='r', offset=off, shape=(n, 2)))

def write_wav(p, a):
    o = wave.open(p, 'wb'); o.setnchannels(2); o.setsampwidth(2); o.setframerate(48000)
    o.writeframes(a.astype('<i2').tobytes()); o.close()

if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'longform'
    cut_p = 'edit/trailer.json' if which == 'trailer' else 'edit/cut.json'
    src   = 'edit/trailer_raw.wav' if which == 'trailer' else 'edit/cut_raw.wav'
    dst   = 'edit/trailer.wav' if which == 'trailer' else 'edit/cut.wav'
    want  = json.load(open(cut_p))['total_frames'] * SPF
    tmp   = src.replace('_raw.wav', '_ln.wav')
    subprocess.run([FF, "-v", "error", "-y", "-i", src,
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", tmp], check=True)
    a = read_wav(tmp)
    if len(a) > want:
        a = a[:want]
    elif len(a) < want:
        a = np.vstack([a, np.zeros((want - len(a), 2), dtype=a.dtype)])
    write_wav(dst, a)
    peak = int(np.max(np.abs(a)))
    rms  = float(np.sqrt(np.mean(a.astype(np.float64) ** 2)))
    print(f"{dst}: {len(a)} samples ({len(a)/48000:.3f}s), "
          f"peak {20*np.log10(max(peak,1)/32768):.1f} dBFS, "
          f"rms {20*np.log10(max(rms,1)/32768):.1f} dBFS")
