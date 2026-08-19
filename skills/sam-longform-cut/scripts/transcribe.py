"""Transcribe src/source.mov with ElevenLabs Scribe. Word level, diarized.

    python3 transcribe.py

Scribe, never Whisper. Whisper's word timings drift by tens of milliseconds and
this whole skill cuts on word boundaries, so a loose timing becomes a clipped
consonant or a filler that bleeds back in. Scribe is tight enough to cut on.

Writes meta/<shoot>.json in the shape the rest of the skill reads:

    {"segments": [{"start", "end", "text",
                   "words": [{"word", "start", "end", "speaker"}]}]}

Needs ELEVENLABS_API_KEY.
"""
import json, os, subprocess, sys
import requests
import shoot

FF = open('ffpath.txt').read().strip()
SRC = 'src/source.mov'
MP3 = 'meta/_audio.mp3'
OUT = f'meta/{shoot.NAME}.json'

# a new segment starts on a speaker change, or a silence at least this long
SEG_GAP = 0.8

def extract():
    os.makedirs('meta', exist_ok=True)
    if os.path.exists(MP3) and os.path.getsize(MP3) > 0:
        print(f"[ff] reuse {MP3} ({os.path.getsize(MP3)/1e6:.1f} MB)", flush=True)
        return
    print("[ff] extracting mono 16k mp3", flush=True)
    p = subprocess.run([FF, "-y", "-v", "error", "-i", SRC, "-vn", "-ac", "1",
                        "-ar", "16000", "-b:a", "48k", MP3],
                       capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit("ffmpeg failed:\n" + p.stderr[-1500:])
    print(f"[ff] mp3 {os.path.getsize(MP3)/1e6:.1f} MB", flush=True)

def scribe():
    key = os.environ.get('ELEVENLABS_API_KEY')
    if not key:
        sys.exit("ELEVENLABS_API_KEY not set.")
    print("[scribe] one diarized call, so speaker labels stay consistent", flush=True)
    with open(MP3, 'rb') as fh:
        r = requests.post(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers={"xi-api-key": key},
            data={"model_id": "scribe_v1", "timestamps_granularity": "word",
                  "diarize": "true"},
            files={"file": (os.path.basename(MP3), fh, "audio/mpeg")},
            timeout=3000)
    if r.status_code != 200:
        sys.exit(f"[scribe] {r.status_code}: {r.text[:800]}")
    return r.json()

def to_segments(words):
    """Scribe's flat word list -> the segment shape build_cut.py and timeline.py read."""
    segs, cur = [], None
    for w in words:
        if w.get('type') != 'word':
            continue                      # spacing and audio_event carry no timing we cut on
        a, b = w.get('start'), w.get('end')
        if a is None or b is None:
            continue
        a, b = float(a), float(b)
        if b <= a:
            b = a + 0.06
        spk = w.get('speaker_id') or '?'
        txt = (w.get('text') or '').strip()
        if not txt:
            continue
        item = {'word': txt, 'start': a, 'end': b, 'speaker': spk}
        if cur and spk == cur['_spk'] and a - cur['end'] < SEG_GAP:
            cur['words'].append(item); cur['end'] = b
        else:
            if cur:
                segs.append(cur)
            cur = {'start': a, 'end': b, '_spk': spk, 'words': [item]}
    if cur:
        segs.append(cur)
    for s in segs:
        s['text'] = ' '.join(w['word'] for w in s['words'])
        del s['_spk']
    return segs

if __name__ == '__main__':
    extract()
    j = scribe()
    segs = to_segments(j.get('words', []))
    if not segs:
        sys.exit("[scribe] returned no words.")
    json.dump({'text': j.get('text', ''), 'segments': segs}, open(OUT, 'w'))

    nw = sum(len(s['words']) for s in segs)
    spk = {}
    for s in segs:
        for w in s['words']:
            spk[w['speaker']] = spk.get(w['speaker'], 0) + 1
    dur = segs[-1]['end']
    print(f"[scribe] {nw} words, {len(segs)} segments, {dur/60:.1f} min -> {OUT}")
    print("[scribe] speakers:", ", ".join(f"{k}={v}" for k, v in
                                          sorted(spk.items(), key=lambda x: -x[1])))
    print("\nNext: python3 timeline.py " + OUT + "   (read all of it)")
