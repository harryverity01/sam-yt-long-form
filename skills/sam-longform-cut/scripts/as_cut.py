"""Write the as-cut transcript: what the finished file actually says, in output time."""
import shoot
import json, sys
import build_cut as B
import plan as P

def tc(t):
    return f"{int(t//3600):02d}:{int(t%3600//60):02d}:{t%60:06.3f}"

if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'longform'
    cut_p = 'edit/trailer.json' if which == 'trailer' else 'edit/cut.json'
    out   = 'edit/TRAILER - AS CUT.md' if which == 'trailer' else 'edit/MASTERCLASS - AS CUT.md'
    cut = json.load(open(cut_p))
    W = [w for w in B.load_words() if w['spk'] == 'Sam']
    blocks = {b['i']: b for b in cut['blocks']}
    lines = []
    p = 0.0
    cur = None
    buf = []
    for s in cut['segments']:
        a, b = s['f0'] / P.FPS, s['f1'] / P.FPS
        if s['block'] != cur:
            if buf:
                lines.append(" ".join(buf)); buf = []
            cur = s['block']
            bm = blocks[cur]
            lines.append(f"\n## [{tc(p)}] {bm['label']}\n")
        txt = " ".join(w['t'] for w in W if w['b'] > a and w['a'] < b)
        buf.append(txt)
        p += (b - a)
    if buf:
        lines.append(" ".join(buf))
    hdr = (f"# {which} — as cut\n\n"
           f"Runtime {tc(cut['total_frames']/P.FPS)} "
           f"({cut['total_frames']} frames at {P.FPS} fps, {len(cut['segments'])} cuts).\n"
           f"Sam's audio only. Source: {shoot.NAME}\n")
    open(out, 'w').write(hdr + "\n".join(lines) + "\n")
    print("wrote", out)
