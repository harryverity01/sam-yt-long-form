#!/usr/bin/env python3
"""ElevenLabs Scribe transcription wrapper. Caches results per source.

Word-level verbatim with timestamps. Mandatory for the cutter pipeline —
the EDL is generated from word boundaries.

Usage:
  transcribe.py <video.mp4>                              # cache to ./edit/transcripts/<name>.json
  transcribe.py <video.mp4> --num-speakers 2             # diarize
  transcribe.py <video.mp4> --out-dir /custom/transcripts
  transcribe.py <video.mp4> --force                      # re-transcribe even if cached

Requires:
  ELEVENLABS_API_KEY in env or .env at repo root.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import requests
except ImportError:
    print("Missing requests. Install with: pip install requests python-dotenv", file=sys.stderr)
    sys.exit(1)


def load_env():
    """Load ELEVENLABS_API_KEY from env or .env at repo root."""
    if os.environ.get("ELEVENLABS_API_KEY"):
        return os.environ["ELEVENLABS_API_KEY"]
    # Look for .env in this script's parent directories
    here = Path(__file__).resolve().parent
    for p in [here, here.parent, here.parent.parent]:
        env = p / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith("ELEVENLABS_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def extract_audio_to_wav(video: str) -> str:
    """Extract mono 16kHz audio (Scribe-optimal) to a temp WAV."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    subprocess.run([
        "ffmpeg", "-y", "-i", video,
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
        tmp.name
    ], capture_output=True, check=True)
    return tmp.name


def transcribe(video: str, num_speakers: int | None = None) -> dict:
    api_key = load_env()
    if not api_key:
        print("❌ ELEVENLABS_API_KEY not found in env or .env", file=sys.stderr)
        sys.exit(1)

    print(f"  extracting audio...")
    wav = extract_audio_to_wav(video)
    sz_mb = os.path.getsize(wav) / 1024 / 1024
    print(f"  uploading {sz_mb:.1f} MB to Scribe...")

    url = "https://api.elevenlabs.io/v1/speech-to-text"
    headers = {"xi-api-key": api_key}
    data = {
        "model_id": "scribe_v1",
        "timestamps_granularity": "word",
        "tag_audio_events": "true",
    }
    if num_speakers:
        data["num_speakers"] = str(num_speakers)
        data["diarize"] = "true"

    with open(wav, "rb") as f:
        files = {"file": (Path(video).name, f, "audio/wav")}
        r = requests.post(url, headers=headers, data=data, files=files, timeout=600)

    Path(wav).unlink(missing_ok=True)
    r.raise_for_status()
    return r.json()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", help="Video or audio file to transcribe")
    ap.add_argument("--num-speakers", type=int, help="Number of speakers (enables diarization)")
    ap.add_argument("--out-dir", help="Output directory (default: <video_dir>/edit/transcripts/)")
    ap.add_argument("--force", action="store_true", help="Re-transcribe even if cached")
    args = ap.parse_args()

    video = Path(args.video).resolve()
    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        out_dir = video.parent / "edit" / "transcripts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{video.stem}.json"

    if out_path.exists() and not args.force:
        print(f"✓ Cached: {out_path}")
        return

    print(f"Transcribing {video.name}...")
    result = transcribe(str(video), args.num_speakers)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    n_words = sum(1 for w in result.get("words", []) if w.get("type") == "word")
    print(f"✓ Saved {n_words} words to {out_path}")


if __name__ == "__main__":
    main()
