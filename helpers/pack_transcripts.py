#!/usr/bin/env python3
"""Pack Scribe transcripts into a phrase-level reading view.

The LLM reads `takes_packed.md` to pick cuts. Phrase-level is the sweet
spot: word-boundary precision from text alone, ~1/10 the tokens of raw JSON.

Phrases break on:
  - Silence ≥ 0.5s (configurable)
  - Speaker change (when diarized)
  - Audio event (laughs, etc.) — these become their own line

Usage:
  pack_transcripts.py --edit-dir <dir>           # reads <dir>/transcripts/*.json
  pack_transcripts.py --edit-dir <dir> --gap 0.4 # tighter phrase boundaries

Output: <edit-dir>/takes_packed.md
"""
import argparse
import json
from pathlib import Path


def pack_one(transcript: dict, source_name: str, gap_threshold: float = 0.5) -> str:
    """Convert one Scribe JSON to phrase-level markdown."""
    words = transcript.get("words", [])
    if not words:
        return f"## {source_name}\n  (no words)\n"

    phrases = []
    current = {"start": None, "end": None, "speaker": None, "text": []}

    def flush():
        if current["text"]:
            phrases.append({
                "start": current["start"],
                "end": current["end"],
                "speaker": current["speaker"],
                "text": " ".join(current["text"]).strip(),
            })

    prev_end = 0.0
    prev_speaker = None
    for w in words:
        w_type = w.get("type", "word")
        text = w.get("text", "")
        start = w.get("start", 0)
        end = w.get("end", start)
        speaker = w.get("speaker_id", "S0")

        # Audio events get their own phrase line
        if w_type == "audio_event":
            flush()
            current = {"start": None, "end": None, "speaker": None, "text": []}
            phrases.append({
                "start": start, "end": end, "speaker": speaker,
                "text": f"({text.strip('()')})",
            })
            prev_end = end
            prev_speaker = speaker
            continue

        gap = start - prev_end
        if (gap >= gap_threshold or speaker != prev_speaker) and current["text"]:
            flush()
            current = {"start": start, "end": end, "speaker": speaker, "text": [text]}
        else:
            if current["start"] is None:
                current["start"] = start
            current["speaker"] = speaker
            current["text"].append(text)
            current["end"] = end

        prev_end = end
        prev_speaker = speaker

    flush()

    # Get total duration
    total_dur = phrases[-1]["end"] if phrases else 0
    lines = [f"## {source_name}  (duration: {total_dur:.1f}s, {len(phrases)} phrases)"]
    for p in phrases:
        lines.append(
            f"  [{p['start']:06.2f}-{p['end']:06.2f}] {p['speaker']} {p['text']}"
        )
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--edit-dir", required=True, help="Path to edit/ directory")
    ap.add_argument("--gap", type=float, default=0.5, help="Silence threshold to break phrases (default: 0.5s)")
    args = ap.parse_args()

    edit_dir = Path(args.edit_dir)
    trans_dir = edit_dir / "transcripts"
    if not trans_dir.exists():
        print(f"❌ {trans_dir} does not exist")
        return

    json_files = sorted(trans_dir.glob("*.json"))
    if not json_files:
        print(f"❌ No JSON transcripts in {trans_dir}")
        return

    out = ["# Packed transcripts\n"]
    for jf in json_files:
        with open(jf) as f:
            transcript = json.load(f)
        out.append(pack_one(transcript, jf.stem, args.gap))
        out.append("")

    out_path = edit_dir / "takes_packed.md"
    out_path.write_text("\n".join(out))
    print(f"✓ Packed {len(json_files)} transcripts → {out_path}")


if __name__ == "__main__":
    main()
