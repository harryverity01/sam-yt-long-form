#!/usr/bin/env python3
"""Composite renderer — per-segment extract → concat → overlays → subtitles.

Reads an EDL JSON (see sam-yt-cutter and sam-yt-broll-producer for the
format), extracts each segment with frame-aligned cuts + 30ms audio fades,
concatenates losslessly, overlays b-roll with PTS-shifted timing, and
burns subtitles LAST (so they aren't hidden by overlays).

Usage:
  render.py <edl.json> -o <out.mp4>
  render.py <edl.json> -o preview.mp4 --preview        # 720p fast
  render.py <edl.json> -o out.mp4 --build-subtitles    # generate master.srt inline
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

FPS = 25
WIDTH = 1920
HEIGHT = 1080

SUB_FORCE_STYLE = (
    "FontName=Helvetica,FontSize=18,Bold=1,"
    "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H00000000,"
    "BorderStyle=1,Outline=2,Shadow=0,"
    "Alignment=2,MarginV=35"
)


def snap_frame(t: float, fps: int = FPS) -> float:
    return round(t * fps) / fps


def extract_segment(src: str, start: float, end: float, out: str, preview: bool = False,
                    grade_filter: str = "") -> None:
    """Extract a single segment, frame-aligned, with 30ms audio fades."""
    start = snap_frame(start)
    end = snap_frame(end)
    dur = end - start

    vf_parts = []
    if preview:
        vf_parts.append("scale=1280:720")
    else:
        vf_parts.append(f"scale={WIDTH}:{HEIGHT}")
    if grade_filter:
        vf_parts.append(grade_filter)
    vf = ",".join(vf_parts)

    af = f"afade=t=in:st=0:d=0.03,afade=t=out:st={dur-0.03:.3f}:d=0.03"

    crf = "23" if preview else "18"
    preset = "veryfast" if preview else "medium"

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start:.6f}", "-i", src,
        "-t", f"{dur:.6f}",
        "-vf", vf,
        "-af", af,
        "-c:v", "libx264", "-preset", preset, "-crf", crf,
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        out
    ]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        print(f"❌ Failed to extract {src}[{start}-{end}]:\n{r.stderr.decode()[-500:]}", file=sys.stderr)
        sys.exit(1)


def concat_lossless(clips: list[str], out: str) -> None:
    """Concat already-encoded segments with no re-encode."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for c in clips:
            f.write(f"file '{os.path.abspath(c)}'\n")
        list_file = f.name
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
           "-c", "copy", out]
    subprocess.run(cmd, capture_output=True, check=True)
    Path(list_file).unlink(missing_ok=True)


def apply_overlays(base: str, overlays: list[dict], out: str) -> None:
    """Overlay each clip onto base. Each overlay: {file, start_in_output, duration}.

    Uses setpts=PTS-STARTPTS+T/TB so each overlay's frame 0 starts at its window.
    """
    if not overlays:
        # Just copy
        subprocess.run(["ffmpeg", "-y", "-i", base, "-c", "copy", out],
                       capture_output=True, check=True)
        return

    inputs = ["-i", base]
    for o in overlays:
        inputs.extend(["-i", o["file"]])

    # Build filter graph
    filters = []
    last_v = "[0:v]"
    for i, o in enumerate(overlays, start=1):
        start = o["start_in_output"]
        end = start + o["duration"]
        # Shift overlay timing to start at `start`
        filters.append(
            f"[{i}:v]setpts=PTS-STARTPTS+{start}/TB[ov{i}]"
        )
        filters.append(
            f"{last_v}[ov{i}]overlay=enable='between(t,{start},{end})'[v{i}]"
        )
        last_v = f"[v{i}]"

    fc = ";".join(filters)
    cmd = [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", fc,
        "-map", last_v, "-map", "0:a",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        out
    ]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        print(f"❌ Overlay failed:\n{r.stderr.decode()[-1000:]}", file=sys.stderr)
        sys.exit(1)


def burn_subtitles(video: str, srt: str, out: str) -> None:
    """Burn subtitles LAST so they're never hidden by overlays."""
    vf = f"subtitles={srt}:force_style='{SUB_FORCE_STYLE}'"
    cmd = [
        "ffmpeg", "-y", "-i", video,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        out
    ]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        print(f"❌ Subtitle burn failed:\n{r.stderr.decode()[-500:]}", file=sys.stderr)
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("edl", help="EDL JSON path")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--preview", action="store_true", help="720p fast render")
    ap.add_argument("--tmp-dir", help="Working dir (default: <output_dir>/_render_tmp)")
    args = ap.parse_args()

    with open(args.edl) as f:
        edl = json.load(f)

    out_path = Path(args.output)
    tmp = Path(args.tmp_dir or out_path.parent / "_render_tmp")
    tmp.mkdir(parents=True, exist_ok=True)

    # 1. Extract each segment
    print(f"Extracting {len(edl['ranges'])} segments...")
    clips = []
    grade = edl.get("grade", "")
    for i, r in enumerate(edl["ranges"]):
        src = edl["sources"][r["source"]]
        clip = str(tmp / f"seg_{i:03d}.mp4")
        extract_segment(src, r["start"], r["end"], clip, args.preview, grade)
        clips.append(clip)
        print(f"  ✓ seg {i}: {r.get('beat', '?')}")

    # 2. Concat
    print("Concatenating...")
    concat = str(tmp / "concat.mp4")
    concat_lossless(clips, concat)

    # 3. Overlays
    overlays = edl.get("overlays", [])
    if overlays:
        print(f"Applying {len(overlays)} overlays...")
        with_overlays = str(tmp / "with_overlays.mp4")
        apply_overlays(concat, overlays, with_overlays)
    else:
        with_overlays = concat

    # 4. Subtitles LAST
    srt = edl.get("subtitles")
    if srt and Path(srt).exists():
        print(f"Burning subtitles...")
        burn_subtitles(with_overlays, srt, str(out_path))
    else:
        os.replace(with_overlays, out_path)

    # 5. Verify
    print(f"\n✓ Rendered: {out_path}")
    here = Path(__file__).parent
    subprocess.run(["python3", str(here / "verify_sync.py"), str(out_path)])


if __name__ == "__main__":
    main()
