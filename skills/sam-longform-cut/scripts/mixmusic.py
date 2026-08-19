"""Lay the music bed under the voice at a fixed speech-to-bed separation."""
import json, os, subprocess, sys, wave
import numpy as np

FF  = open('ffpath.txt').read().strip()
SPF = 1600

# Speech-to-bed separation, in dB. A trailer and a long form want different numbers.
# 16 dB is the long-form VO spec: the bed must never compete with a 40 minute talk.
# On a 50 second trailer 16 dB is inaudible on a phone. Harry rejected it at v4.
# 9 dB is the trailer spec: you hear the music, the words still win.
SEP = {'trailer': 9.0, 'longform': 16.0}
HEAD_DUCK = 0.0        # bed level multiplier before the first word (1.0 = full)

def read_wav(p):
    w = wave.open(p, 'rb'); n = w.getnframes(); ch = w.getnchannels(); w.close()
    off = os.path.getsize(p) - n * ch * 2
    a = np.array(np.memmap(p, dtype='<i2', mode='r', offset=off, shape=(n, ch)))
    return a if ch == 2 else np.repeat(a, 2, axis=1)

if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'trailer'
    voice_p = f'edit/{which}.wav'
    bed_src = sys.argv[2] if len(sys.argv) > 2 else 'assets/music/trailer_bed.mp3'
    SEP_DB  = float(sys.argv[3]) if len(sys.argv) > 3 else SEP.get(which, SEP['longform'])
    out     = f'edit/{which}_mixed.wav'
    tmp     = 'edit/_bed48.wav'
    v = read_wav(voice_p).astype(np.float32)
    n = len(v)
    subprocess.run([FF, "-v", "error", "-y", "-i", bed_src, "-ar", "48000", "-ac", "2",
                    "-c:a", "pcm_s16le", tmp], check=True)
    b = read_wav(tmp).astype(np.float32)
    if len(b) < n:
        b = np.vstack([b] * (n // len(b) + 1))
    b = b[:n]

    # measure speech level only where he is actually speaking
    env = np.abs(v).max(axis=1)
    k = 2400                                   # 50 ms window
    sm = np.convolve(env, np.ones(k) / k, mode='same')
    speech = sm > (0.12 * sm.max())
    v_rms = float(np.sqrt(np.mean(v[speech] ** 2))) if speech.any() else 1.0
    b_rms = float(np.sqrt(np.mean(b ** 2))) or 1.0
    gain = (v_rms / b_rms) * (10 ** (-SEP_DB / 20))
    b *= gain

    # 1.2 s fade in, 2.5 s fade out
    fi, fo = int(1.2 * 48000), int(2.5 * 48000)
    b[:fi] *= np.linspace(0, 1, fi, dtype=np.float32)[:, None]
    b[-fo:] *= np.linspace(1, 0, fo, dtype=np.float32)[:, None]

    mix = v + b
    peak = float(np.max(np.abs(mix)))
    if peak > 0.891 * 32768:
        mix *= (0.891 * 32768) / peak
    o = wave.open(out, 'wb'); o.setnchannels(2); o.setsampwidth(2); o.setframerate(48000)
    o.writeframes(np.clip(mix, -32768, 32767).astype('<i2').tobytes()); o.close()
    print(f"speech {20*np.log10(v_rms/32768):.1f} dBFS, bed {20*np.log10(b_rms*gain/32768):.1f} dBFS, "
          f"separation {SEP_DB:.1f} dB, peak {20*np.log10(max(peak,1)/32768):.1f} dBFS, "
          f"{len(mix)} samples")
