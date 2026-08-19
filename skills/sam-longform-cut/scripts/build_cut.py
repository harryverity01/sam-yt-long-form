import json, sys, os
import plan as P

import shoot
TRANSCRIPT = shoot.transcript()

def load_words():
    d = json.load(open(TRANSCRIPT))
    W = []
    for s in d['segments']:
        for w in (s.get('words') or []):
            a, b = float(w['start']), float(w['end'])
            if b <= a:
                b = a + 0.06
            if b - a > P.MAX_WORD_LEN:          # runaway token, see plan.MAX_WORD_LEN
                b = a + P.MAX_WORD_LEN
            W.append({'t': w['word'].strip(), 'a': a, 'b': b,
                      'spk': w.get('speaker', '?')})
    W.sort(key=lambda w: (w['a'], w['b']))
    return W

def norm(t):
    return t.lower().strip(" .,?!:;-—\"'")

def clean(words):
    """Drop fillers and stutters from an already Sam-only word list."""
    out = []
    for w in words:
        n = norm(w['t'])
        if not n:
            continue
        if n in P.DROP_TOKENS:
            continue
        if out and norm(out[-1]['t']) == n and len(n) <= 4:
            out[-1] = w                          # stutter: keep the later one
            continue
        out.append(w)
    return out

def runs(words, gap=None):
    """Split kept words into runs at gaps wider than the threshold."""
    gap = P.GAP_SPLIT_ABOVE if gap is None else gap
    R = []
    cur = [words[0]]
    for w in words[1:]:
        if w['a'] - cur[-1]['b'] > gap:
            R.append(cur); cur = [w]
        else:
            cur.append(w)
    R.append(cur)
    return R

def build(groups, W, tight=None):
    """groups: list of (blocks, drops). Blocks keep their order across groups."""
    import bisect
    T = dict(GAP_SPLIT_ABOVE=P.GAP_SPLIT_ABOVE, HEAD_PAD=P.HEAD_PAD,
             TAIL_PAD=P.TAIL_PAD, BLOCK_TAIL=P.BLOCK_TAIL)
    if tight:
        T.update(tight)
    starts = [w['a'] for w in W]

    def prev_end(t):
        i = bisect.bisect_left(starts, t) - 1
        while i >= 0 and W[i]['b'] > t:      # skip words overlapping t
            i -= 1
        return W[i]['b'] if i >= 0 else None

    def next_start(t):
        i = bisect.bisect_left(starts, t)     # first word starting at or after t
        return W[i]['a'] if i < len(W) else None

    segs = []
    blockmeta = []
    flat = []
    for blocks, drops in groups:
        for b in blocks:
            flat.append((b, drops))
    for bi, ((t0, t1, zoom, label), drops) in enumerate(flat):
        sel = [w for w in W
               if w['spk'] == 'Sam' and w['b'] > t0 and w['a'] < t1
               and not any(w['a'] < d1 and w['b'] > d0 for d0, d1 in drops)]
        if not sel:
            print(f"  !! block {bi} '{label}' selected 0 words")
            continue
        sel = clean(sel)
        if not sel:
            continue
        keep = []
        for r in runs(sel, T['GAP_SPLIT_ABOVE']):
            if len(r) < P.MIN_RUN_WORDS and norm(r[0]['t']) in P.ORPHAN_TOKENS:
                continue
            keep.append(r)
        if not keep:
            continue
        # never end a section on a dangling connective
        while keep and len(keep[-1]) > 1 and norm(keep[-1][-1]['t']) in P.TRAIL_STRIP:
            keep[-1] = keep[-1][:-1]
        block_segs = []
        for ri, r in enumerate(keep):
            a = max(t0 - 0.30, r[0]['a'] - T['HEAD_PAD'])
            tail = T['TAIL_PAD'] + (T['BLOCK_TAIL'] if ri == len(keep) - 1 else 0.0)
            b = min(t1 + 0.60, r[-1]['b'] + tail)
            # never bleed the neighbouring word in — that is how a dropped filler
            # or the next speaker's first syllable gets back into the cut
            pe = prev_end(r[0]['a'])
            ns = next_start(r[-1]['b'])
            if pe is not None:
                a = max(a, pe + 0.03)
            if ns is not None:
                b = min(b, ns - 0.05)
            if b - a < 0.15:
                b = a + 0.15
            f0 = int(a * P.FPS)
            f1 = int(b * P.FPS + 0.999)
            if f1 - f0 < 3:
                continue
            block_segs.append({'f0': f0, 'f1': f1, 'block': bi})
        # merge segments that touch or overlap after padding
        merged = []
        for s in block_segs:
            if merged and s['f0'] <= merged[-1]['f1']:
                merged[-1]['f1'] = max(merged[-1]['f1'], s['f1'])
            else:
                merged.append(s)
        nfr = sum(s['f1'] - s['f0'] for s in merged)
        blockmeta.append({'i': bi, 'label': label, 'zoom': list(zoom),
                          'frames': nfr, 'segs': len(merged),
                          'src': [round(t0, 2), round(t1, 2)]})
        segs.extend(merged)

    # attach zoom position within each block
    zoff = {}
    for s in segs:
        b = s['block']
        s['zoff'] = zoff.get(b, 0)
        zoff[b] = s['zoff'] + (s['f1'] - s['f0'])
    for s in segs:
        bm = next(m for m in blockmeta if m['i'] == s['block'])
        s['zoom'] = bm['zoom']
        s['ztot'] = bm['frames']
    total = sum(s['f1'] - s['f0'] for s in segs)
    return {'fps': P.FPS, 'spf': P.SPF, 'segments': segs,
            'blocks': blockmeta, 'total_frames': total}

if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'longform'
    W = load_words()
    if which == 'trailer':
        cut = build([(P.TRAILER, P.TRAILER_DROPS)], W, P.TRAILER_TIGHT)
        out = 'edit/trailer.json'
    else:
        cut = build([(P.COLD_OPEN, []), (P.BODY, P.BODY_DROPS)], W)
        out = 'edit/cut.json'
    os.makedirs('edit', exist_ok=True)
    json.dump(cut, open(out, 'w'), indent=1)
    t = cut['total_frames'] / P.FPS
    print(f"{which}: {len(cut['segments'])} segments, "
          f"{cut['total_frames']} frames = {int(t//60)}m{t%60:04.1f}s")
    for b in cut['blocks']:
        d = b['frames'] / P.FPS
        print(f"  [{b['i']:02d}] {int(d//60)}m{d%60:04.1f}s  "
              f"{b['segs']:3d} cuts  src {b['src'][0]:7.1f}  {b['label']}")
