"""Print the in and out words of every block. Fix every trailing fragment before rendering."""
import json, sys
import build_cut as B

which = sys.argv[1] if len(sys.argv) > 1 else 'longform'
cut = json.load(open('edit/trailer.json' if which == 'trailer' else 'edit/cut.json'))
W = [w for w in B.load_words() if w['spk'] == 'Sam']
segs = cut['segments']
for bm in cut['blocks']:
    bs = [s for s in segs if s['block'] == bm['i']]
    a0, b1 = bs[0]['f0'] / 30, bs[-1]['f1'] / 30
    first = [w['t'] for w in W if w['b'] > a0 and w['a'] < a0 + 2.2][:5]
    last  = [w['t'] for w in W if w['b'] > b1 - 2.2 and w['a'] < b1][-6:]
    print(f"[{bm['i']:02d}] IN: {' '.join(first):<40} || OUT: ...{' '.join(last)}")
