#!/usr/bin/env python3
"""Audio/video sync verifier.

Catches the "audio is N ms shorter than video" class of drift at the point
of origin. Run this on every source you import and every render you produce.

Original motivating failure (Sam Ey Am long-form): a preview build had
video=243.720s but audio=243.178s (542ms / 0.22% mismatch). The drift got
baked into every CapCut segment and was only noticed in the final export
after the user had spent days editing on top of it.

Usage:
  verify_sync.py <video.mp4>
  verify_sync.py <video.mp4> --max-drift-ms 80
  verify_sync.py <video.mp4> --strict
  verify_sync.py a.mp4 b.mp4 c.mp4              # batch

Exits non-zero on drift so it can gate CI / render pipelines.
"""
import argparse
import subprocess
import sys
from pathlib import Path


def ffprobe_stream_duration(path: str, stream: str) -> float | None:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", stream,
         "-show_entries", "stream=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True
    )
    out = r.stdout.strip()
    if not out or out == "N/A":
        return None
    try:
        return float(out)
    except ValueError:
        return None


def ffprobe_pts_end(path: str, stream: str) -> float | None:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", stream,
         "-show_entries", "packet=pts_time",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True
    )
    times = [float(x) for x in r.stdout.split() if x and x != "N/A"]
    return max(times) if times else None


def check_file(path: str, max_drift_ms: float = 40.0, strict: bool = False) -> tuple[bool, str]:
    p = Path(path)
    if not p.exists():
        return False, f"❌ {path}: file does not exist"

    v_dur = ffprobe_stream_duration(path, "v:0")
    a_dur = ffprobe_stream_duration(path, "a:0")

    if v_dur is None and a_dur is None:
        return False, f"❌ {path}: no video or audio streams"
    if v_dur is None:
        return True, f"⚠️  {path}: audio-only ({a_dur:.3f}s), no sync to check"
    if a_dur is None:
        return True, f"⚠️  {path}: video-only ({v_dur:.3f}s), no sync to check"

    drift_ms = abs(v_dur - a_dur) * 1000
    direction = "audio shorter" if a_dur < v_dur else "audio longer"

    if strict:
        v_end = ffprobe_pts_end(path, "v:0")
        a_end = ffprobe_pts_end(path, "a:0")
        if v_end and a_end:
            pts_drift_ms = abs(v_end - a_end) * 1000
            drift_ms = max(drift_ms, pts_drift_ms)

    msg = (f"{path}\n"
           f"  video: {v_dur:.3f}s | audio: {a_dur:.3f}s | drift: {drift_ms:.0f}ms ({direction})")

    if drift_ms > max_drift_ms:
        return False, f"❌ DRIFT — {msg}\n  exceeds {max_drift_ms:.0f}ms threshold\n  → fix the source build before propagating downstream"
    return True, f"✓ sync OK — {msg}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="video file(s) to check")
    ap.add_argument("--max-drift-ms", type=float, default=40.0,
                    help="fail if drift exceeds this many ms (default: 40 = 1 frame @ 25fps)")
    ap.add_argument("--strict", action="store_true",
                    help="also check PTS end (catches container-vs-stream mismatch). Slower.")
    args = ap.parse_args()

    all_ok = True
    for f in args.files:
        ok, msg = check_file(f, args.max_drift_ms, args.strict)
        print(msg)
        if not ok:
            all_ok = False

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
