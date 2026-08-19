"""One readable line per transcript segment, plus the gap budget. Read all of it."""
import json, sys
p = sys.argv[1]
d = json.load(open(p))
fmt = lambda t: f"{int(t//60):02d}:{t%60:05.2f}"
for s in d['segments']:
    ws = s.get('words') or []
    spk = {}
    for w in ws:
        spk[w.get('speaker', '?')] = spk.get(w.get('speaker', '?'), 0) + 1
    lab = max(spk, key=spk.get) if spk else '?'
    print(f"[{fmt(s['start'])}-{fmt(s['end'])}] {lab}: {s['text'].strip()}")
W = sorted([w for s in d['segments'] for w in (s.get('words') or [])], key=lambda w: w['start'])
gaps = [W[i+1]['start'] - W[i]['end'] for i in range(len(W) - 1)]
for th in (0.34, 1.0, 2.0):
    sel = [g for g in gaps if g > th]
    print(f"# gaps>{th}: n={len(sel)} total={sum(sel)/60:.1f} min", file=sys.stderr)
