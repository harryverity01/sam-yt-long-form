#!/usr/bin/env python3
"""Build a master SRT for the cut output from per-source transcripts + EDL.

CRITICAL: timestamps are in OUTPUT timeline, computed as
  output_time = word.start - segment.source_start + segment.output_start

Otherwise captions misalign after segment concat.

Caption style: 2-word chunks, UPPERCASE, break on punctuation.
Override --chunk-words for longer captions.

Usage:
  build_master_srt.py <edl.json> --transcripts-dir <dir> -o master.srt
  build_master_srt.py <edl.json> --transcripts-dir <dir> -o master.srt --chunk-words 4 --case natural
"""
import argparse
import json
from pathlib import Path


def fmt_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("edl", help="EDL JSON path")
    ap.add_argument("--transcripts-dir", required=True)
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--chunk-words", type=int, default=2)
    ap.add_argument("--case", choices=["upper", "title", "natural"], default="upper")
    args = ap.parse_args()

    with open(args.edl) as f:
        edl = json.load(f)
    transcripts_dir = Path(args.transcripts_dir)

    # Cache transcripts by source key
    transcripts = {}
    for key, src_path in edl["sources"].items():
        stem = Path(src_path).stem
        tj = transcripts_dir / f"{stem}.json"
        if tj.exists():
            with open(tj) as f:
                transcripts[key] = json.load(f)
        else:
            print(f"⚠️  No transcript for {key} ({tj})")

    # Walk ranges, project words into output timeline
    output_offset = 0.0
    captions = []
    for r in edl["ranges"]:
        src = r["source"]
        s_start = r["start"]
        s_end = r["end"]
        dur = s_end - s_start
        t = transcripts.get(src)
        if not t:
            output_offset += dur
            continue
        for w in t.get("words", []):
            if w.get("type") != "word":
                continue
            ws = w.get("start", 0)
            we = w.get("end", ws)
            if ws < s_start or we > s_end:
                continue
            out_start = ws - s_start + output_offset
            out_end = we - s_start + output_offset
            captions.append({
                "start": out_start,
                "end": out_end,
                "text": w["text"].strip(),
            })
        output_offset += dur

    # Chunk
    chunks = []
    cur = {"start": None, "end": None, "words": []}
    for c in captions:
        if cur["start"] is None:
            cur["start"] = c["start"]
        cur["end"] = c["end"]
        cur["words"].append(c["text"])
        if len(cur["words"]) >= args.chunk_words or c["text"].endswith((".", "?", "!", ",")):
            chunks.append(cur)
            cur = {"start": None, "end": None, "words": []}
    if cur["words"]:
        chunks.append(cur)

    # Render
    lines = []
    for i, c in enumerate(chunks, start=1):
        text = " ".join(c["words"])
        if args.case == "upper":
            text = text.upper()
        elif args.case == "title":
            text = text.title()
        lines.append(str(i))
        lines.append(f"{fmt_ts(c['start'])} --> {fmt_ts(c['end'])}")
        lines.append(text)
        lines.append("")

    Path(args.output).write_text("\n".join(lines))
    print(f"✓ Wrote {len(chunks)} caption chunks → {args.output}")


if __name__ == "__main__":
    main()
