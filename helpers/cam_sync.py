#!/usr/bin/env python3
"""Auto-detect multi-cam clock offset via audio cross-correlation.

Two cameras shooting the same event will have slightly different internal
clocks. To use audio from one camera over video from another, you need to
know the offset to sub-frame precision.

This script extracts a short audio segment from each camera, downsamples
to mono 8kHz, computes FFT cross-correlation, and reports the offset.

For a 90-min interview, sample multiple points to detect cumulative drift
(cheap cameras can drift ~1ms per minute).

Usage:
  cam_sync.py MAIN.mp4 BTS.mp4                              # quick check (1 sample at middle)
  cam_sync.py MAIN.mp4 BTS.mp4 --samples 5                  # 5 samples across the file
  cam_sync.py MAIN.mp4 BTS.mp4 --window 30                  # 30-second analysis window
  cam_sync.py MAIN.mp4 BTS.mp4 --reference MAIN -o sync.json # write to JSON

Output: offset in seconds = (BTS_time - MAIN_time). Positive means BTS is
ahead of MAIN (BTS recorded earlier in real time at the same camera frame).

Requires: numpy, scipy (pip install numpy scipy).
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import numpy as np
    from scipy.signal import correlate, correlation_lags
    from scipy.io import wavfile
except ImportError:
    print("Missing deps. Install with: pip install numpy scipy", file=sys.stderr)
    sys.exit(1)


def ffprobe_duration(path: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True
    )
    return float(r.stdout.strip())


def extract_audio_segment(video: str, start: float, duration: float, sr: int = 8000) -> np.ndarray:
    """Pull a mono audio segment at the given sample rate."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        cmd = [
            "ffmpeg", "-y", "-ss", f"{start:.6f}", "-i", video,
            "-t", f"{duration:.6f}",
            "-vn", "-ac", "1", "-ar", str(sr), "-c:a", "pcm_s16le",
            tmp.name
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        _, data = wavfile.read(tmp.name)
    Path(tmp.name).unlink(missing_ok=True)
    return data.astype(np.float32) / 32768.0


def cross_correlate_offset(a: np.ndarray, b: np.ndarray, sr: int) -> tuple[float, float]:
    """Return (offset_seconds, peak_strength_0_to_1).

    Offset is how much b lags a. Positive offset = b is later than a.
    Peak strength near 1 = confident match. Below 0.3 = suspicious.
    """
    a = (a - a.mean()) / (a.std() + 1e-9)
    b = (b - b.mean()) / (b.std() + 1e-9)
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]

    corr = correlate(a, b, mode="full")
    lags = correlation_lags(len(a), len(b), mode="full")
    peak_idx = np.argmax(np.abs(corr))
    offset_samples = lags[peak_idx]
    offset_seconds = offset_samples / sr

    # Peak strength: ratio of peak to RMS of full correlation
    peak_strength = float(abs(corr[peak_idx]) / (np.sqrt((corr ** 2).mean()) + 1e-9) / 10)
    peak_strength = min(peak_strength, 1.0)

    return float(offset_seconds), peak_strength


def detect_offset(cam_a: str, cam_b: str, samples: int = 1, window: float = 20.0,
                  sr: int = 8000) -> dict:
    """Sample at N points across the file, report offset + drift."""
    dur_a = ffprobe_duration(cam_a)
    dur_b = ffprobe_duration(cam_b)
    min_dur = min(dur_a, dur_b)

    # Sample positions: evenly spaced, skip first/last 5%
    margin = min_dur * 0.05
    usable = min_dur - 2 * margin - window
    if samples == 1:
        positions = [margin + usable / 2]
    else:
        positions = [margin + i * usable / (samples - 1) for i in range(samples)]

    results = []
    for pos in positions:
        try:
            a = extract_audio_segment(cam_a, pos, window, sr)
            b = extract_audio_segment(cam_b, pos, window, sr)
            offset, strength = cross_correlate_offset(a, b, sr)
            results.append({
                "sample_at_s": round(pos, 2),
                "offset_s": round(offset, 4),
                "confidence": round(strength, 3),
            })
            print(f"  @ {pos:6.1f}s  offset={offset:+.4f}s  confidence={strength:.3f}")
        except Exception as e:
            print(f"  @ {pos:6.1f}s  FAILED: {e}")

    # Drift = max offset - min offset across samples
    offsets = [r["offset_s"] for r in results]
    drift_ms = (max(offsets) - min(offsets)) * 1000 if len(offsets) > 1 else 0.0
    mean_offset = sum(offsets) / len(offsets) if offsets else 0.0

    summary = {
        "cam_a": cam_a,
        "cam_b": cam_b,
        "cam_a_duration_s": round(dur_a, 3),
        "cam_b_duration_s": round(dur_b, 3),
        "mean_offset_s": round(mean_offset, 4),
        "drift_across_file_ms": round(drift_ms, 2),
        "samples": results,
        "interpretation": "offset > 0 means cam_b is later than cam_a (cam_b started recording earlier)",
    }
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cam_a", help="First camera (often MAIN)")
    ap.add_argument("cam_b", help="Second camera (often BTS)")
    ap.add_argument("--samples", type=int, default=3,
                    help="Number of sample points across the file (default: 3 — start/mid/end)")
    ap.add_argument("--window", type=float, default=20.0,
                    help="Analysis window in seconds (default: 20)")
    ap.add_argument("--sr", type=int, default=8000,
                    help="Downsample rate for correlation (default: 8000 Hz)")
    ap.add_argument("-o", "--output", help="Write summary JSON to this path")
    args = ap.parse_args()

    print(f"Cross-correlating audio:")
    print(f"  A: {args.cam_a}")
    print(f"  B: {args.cam_b}")
    print(f"  Sampling {args.samples} window(s) of {args.window:.0f}s @ {args.sr}Hz\n")

    summary = detect_offset(args.cam_a, args.cam_b, args.samples, args.window, args.sr)

    print(f"\nMean offset: {summary['mean_offset_s']:+.4f}s")
    print(f"Drift across file: {summary['drift_across_file_ms']:.2f}ms")
    if summary["drift_across_file_ms"] > 40:
        print("⚠️  Drift > 1 frame — cameras have clock skew, consider sampling more points")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"\nSummary written to {args.output}")


if __name__ == "__main__":
    main()
