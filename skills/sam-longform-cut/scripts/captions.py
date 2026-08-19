"""Big-word trailer captions in Sam's font (Archivo Black), burned as a PNG layer.

This ffmpeg build has no drawtext (no libfreetype), so every caption is drawn with
PIL and overlaid as an RGBA sequence.
"""
import json, os, shutil, sys
from PIL import Image, ImageDraw, ImageFont
import build_cut as B
import plan as P

W, H   = 1920, 1080
FONT   = 'assets/fonts/ArchivoBlack-Regular.ttf'
SIZE   = 88
STROKE = 9
BASE_Y = 838            # text block centre; clear of the mic and of his hands
MAXW   = int(W * 0.82)
MAX_WORDS = 3
MAX_DUR   = 1.45
OUT    = 'edit/caps'

# a caption never ends on one of these
GLUE = {"a","an","the","my","your","his","her","their","our","to","of","and","but",
        "so","is","was","are","be","i","he","she","we","you","it","that","this",
        "in","on","at","for","with","like","just","what","when","how","who","if",
        "can","do","does","did","me","them","us","out","up","as","or","then"}

def chunks(words):
    """Two or three words a screen. Hard break on punctuation and on real pauses.
    Otherwise break so a line ends on a content word and the glue starts the next."""
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        end_punct = w['t'].rstrip()[-1:] in '.?!'
        gap_next  = (nxt['a'] - w['b']) > 0.20 if nxt else True
        long_now  = (w['b'] - cur[0]['a']) >= MAX_DUR
        nxt_glue  = nxt is not None and B.norm(nxt['t']) in GLUE
        if end_punct or gap_next or long_now:
            out.append(cur); cur = []
        elif len(cur) >= MAX_WORDS or (len(cur) >= 2 and nxt_glue):
            out.append(cur); cur = []
    if cur:
        out.append(cur)
    # a stranded single word joins the line before it, but only if that line is short
    merged = []
    for c in out:
        if len(c) == 1 and merged and len(merged[-1]) <= 3 and \
           (c[0]['a'] - merged[-1][-1]['b']) < 0.20:
            merged[-1] = merged[-1] + c
        else:
            merged.append(c)
    return merged

def render(text, path, font):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d  = ImageDraw.Draw(im)
    f  = font
    # shrink to fit rather than wrap: a trailer caption is one line
    while d.textlength(text, font=f) > MAXW and f.size > 40:
        f = ImageFont.truetype(FONT, f.size - 4)
    tw = d.textlength(text, font=f)
    asc, desc = f.getmetrics()
    x = (W - tw) / 2
    y = BASE_Y - (asc + desc) / 2
    d.text((x, y), text, font=f, fill=(255, 255, 255, 255),
           stroke_width=STROKE, stroke_fill=(0, 0, 0, 235))
    im.save(path)

if __name__ == '__main__':
    cut = json.load(open('edit/trailer.json'))
    S   = cut['segments']
    WS  = [w for w in B.load_words() if w['spk'] == 'Sam']
    drops = P.TRAILER_DROPS
    font  = ImageFont.truetype(FONT, SIZE)
    os.makedirs(OUT, exist_ok=True)

    # source time -> output frame, per segment
    events = []
    of = 0
    for s in S:
        a, b = s['f0'] / P.FPS, s['f1'] / P.FPS
        sel = [w for w in WS if w['b'] > a and w['a'] < b
               and not any(w['a'] < d1 and w['b'] > d0 for d0, d1 in drops)
               and B.norm(w['t']) not in P.DROP_TOKENS]
        for ch in chunks(sel):
            f0 = of + int(round((max(ch[0]['a'], a) - a) * P.FPS))
            f1 = of + int(round((min(ch[-1]['b'], b) - a) * P.FPS))
            txt = " ".join(w['t'].strip() for w in ch).upper()
            txt = txt.replace('7 000', '7,000').replace('  ', ' ').strip(' ,')
            if f1 - f0 >= 3 and txt:
                events.append((f0, f1, txt))
        of += s['f1'] - s['f0']
    total = cut['total_frames']
    assert of == total

    # de-overlap and hold each caption until the next one starts
    events.sort()
    for i in range(len(events) - 1):
        f0, f1, t = events[i]
        nxt = events[i + 1][0]
        events[i] = (f0, min(nxt, max(f1 + 4, f1)), t)

    uniq = {}
    for _, _, t in events:
        if t not in uniq:
            p = f"{OUT}/txt_{len(uniq):03d}.png"
            render(t, p, font)
            uniq[t] = p
    blank = f"{OUT}/blank.png"
    Image.new('RGBA', (W, H), (0, 0, 0, 0)).save(blank)

    frame_of = {}
    for f0, f1, t in events:
        for f in range(max(0, f0), min(total, f1)):
            frame_of[f] = uniq[t]
    seq = f"{OUT}/seq"
    os.makedirs(seq, exist_ok=True)
    for f in range(total):
        shutil.copyfile(frame_of.get(f, blank), f"{seq}/c_{f:05d}.png")
    print(f"{len(events)} captions, {len(uniq)} unique, {total} frames written")
    print("first 12:", " | ".join(t for _, _, t in events[:12]))
